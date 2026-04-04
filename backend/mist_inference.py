"""
MIST inference wrapper.

Tries real MIST model inference when available (pip install -e ".[mist]").
Falls back to spectral cosine-similarity matching against the fixture library,
which provides a working live-prediction path without any ML model.
"""
import csv
import io
import json
import logging
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"
SPECTRA_DIR = FIXTURES_DIR / "spectra"

# ---------------------------------------------------------------------------
# Try importing MIST
# ---------------------------------------------------------------------------
try:
    import torch
    from mist.models import base as mist_base
    from mist.data import datasets as mist_datasets, featurizers as mist_featurizers

    MIST_AVAILABLE = True
    logger.info("MIST library detected")
except ImportError:
    MIST_AVAILABLE = False

# ---------------------------------------------------------------------------
# Try importing RDKit (used by both paths)
# ---------------------------------------------------------------------------
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False

# ---------------------------------------------------------------------------
# Preloaded reference library (built lazily on first call)
# ---------------------------------------------------------------------------
_REFERENCE_LIBRARY: Optional[dict] = None


def _load_reference_library() -> dict:
    """Build a reference library from fixture molecules and their spectra."""
    global _REFERENCE_LIBRARY
    if _REFERENCE_LIBRARY is not None:
        return _REFERENCE_LIBRARY

    library = {"molecules": [], "ms_spectra": [], "nmr_spectra": [], "fingerprints": []}

    for fixture_path in sorted(FIXTURES_DIR.glob("*.json")):
        try:
            with open(fixture_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        smiles = data.get("smiles", "")
        if not smiles:
            continue

        ms_peaks = _load_spectrum_csv(SPECTRA_DIR / f"{fixture_path.stem}_ms.csv")
        nmr_peaks = _load_spectrum_csv(SPECTRA_DIR / f"{fixture_path.stem}_nmr.csv")

        fp = np.zeros(2048, dtype=np.float32)
        if RDKIT_AVAILABLE:
            mol = Chem.MolFromSmiles(smiles)
            if mol:
                bv = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
                fp = np.array(bv, dtype=np.float32)

        library["molecules"].append(data)
        library["ms_spectra"].append(ms_peaks)
        library["nmr_spectra"].append(nmr_peaks)
        library["fingerprints"].append(fp)

    logger.info("Reference library loaded: %d molecules", len(library["molecules"]))
    _REFERENCE_LIBRARY = library
    return library


def _load_spectrum_csv(path: Path) -> List[Tuple[float, float]]:
    """Load (x, y) peaks from a two-column CSV with header."""
    if not path.exists():
        return []
    peaks = []
    with open(path) as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) >= 2:
                try:
                    peaks.append((float(row[0]), float(row[1])))
                except ValueError:
                    pass
    return peaks


def parse_csv_peaks(csv_text: str) -> List[Tuple[float, float]]:
    """Parse decoded CSV text into (x, y) peak list."""
    peaks = []
    reader = csv.reader(io.StringIO(csv_text))
    next(reader, None)
    for row in reader:
        if len(row) >= 2:
            try:
                peaks.append((float(row[0]), float(row[1])))
            except ValueError:
                pass
    return peaks


# ---------------------------------------------------------------------------
# Spectral similarity (fallback engine)
# ---------------------------------------------------------------------------

def _bin_peaks(peaks: List[Tuple[float, float]], lo: float, hi: float,
               n_bins: int) -> np.ndarray:
    """Bin a peak list into a fixed-length vector."""
    vec = np.zeros(n_bins, dtype=np.float64)
    for x, y in peaks:
        if lo <= x < hi:
            idx = min(int((x - lo) / (hi - lo) * n_bins), n_bins - 1)
            vec[idx] = max(vec[idx], y)
    norm = vec.max()
    if norm > 0:
        vec /= norm
    return vec.astype(np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot = float(np.dot(a, b))
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def predict_live(
    ms_peaks: Optional[List[Tuple[float, float]]] = None,
    nmr_peaks: Optional[List[Tuple[float, float]]] = None,
    ir_peaks: Optional[List[Tuple[float, float]]] = None,
    top_k: int = 5,
    model_ckpt: Optional[str] = None,
) -> List[dict]:
    """
    Run live inference.

    Returns a list of candidate dicts:
      [{"smiles": ..., "score": ..., "rank": ..., "valid": ..., "conformer_sdf": ...}, ...]
    """
    if MIST_AVAILABLE and model_ckpt and Path(model_ckpt).exists():
        try:
            return _predict_mist(ms_peaks, top_k, model_ckpt)
        except Exception as e:
            logger.warning("MIST inference failed, falling back to similarity: %s", e)

    return _predict_similarity(ms_peaks, nmr_peaks, ir_peaks, top_k)


# ---------------------------------------------------------------------------
# Path A: Real MIST inference
# ---------------------------------------------------------------------------
_MIST_MODEL = None


def _load_mist_model(ckpt_path: str):
    """Load MIST model from checkpoint (cached)."""
    global _MIST_MODEL
    if _MIST_MODEL is not None:
        return _MIST_MODEL

    device = torch.device("cpu")
    ckpt = torch.load(ckpt_path, map_location=device)
    hparams = ckpt["hyper_parameters"]
    model = mist_base.build_model(**hparams)
    model.load_state_dict(ckpt["state_dict"])
    model = model.to(device).eval()
    _MIST_MODEL = (model, hparams)
    logger.info("MIST model loaded from %s (epoch %s)", ckpt_path, ckpt.get("epoch"))
    return _MIST_MODEL


def _write_ms_file(peaks: List[Tuple[float, float]], parentmass: float,
                   formula: str, dest: Path):
    """Write peaks in the .ms format MIST expects."""
    with open(dest, "w") as f:
        f.write(f">compound query\n")
        f.write(f">formula {formula}\n")
        f.write(f">parentmass {parentmass:.4f}\n")
        f.write(f">ms2peaks\n")
        for mz, intensity in sorted(peaks):
            f.write(f"{mz:.4f} {intensity:.2f}\n")


def _predict_mist(
    ms_peaks: Optional[List[Tuple[float, float]]],
    top_k: int,
    ckpt_path: str,
) -> List[dict]:
    """Run MIST fingerprint prediction and match against library."""
    if not ms_peaks:
        return []

    model, hparams = _load_mist_model(ckpt_path)
    library = _load_reference_library()

    parentmass = max(mz for mz, _ in ms_peaks) if ms_peaks else 0.0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        spec_dir = tmpdir / "spectra"
        spec_dir.mkdir()
        _write_ms_file(ms_peaks, parentmass, "UNKNOWN", spec_dir / "query.ms")

        labels_path = tmpdir / "labels.tsv"
        with open(labels_path, "w") as f:
            f.write("spec\tformula\n")
            f.write("query\tUNKNOWN\n")

        infer_kwargs = dict(hparams)
        infer_kwargs.update({
            "labels_file": str(labels_path),
            "spec_folder": str(spec_dir),
            "max_count": None,
            "allow_none_smiles": True,
        })

        spec_features = model.spec_features(mode="test")
        infer_kwargs["spec_features"] = spec_features
        infer_kwargs["mol_features"] = "none"
        paired_featurizer = mist_featurizers.get_paired_featurizer(**infer_kwargs)

        spectra_mol_pairs = mist_datasets.get_paired_spectra(prog_bars=False, **infer_kwargs)
        spectra_mol_pairs = list(zip(*spectra_mol_pairs))

        test_dataset = mist_datasets.SpectraMolDataset(
            spectra_mol_list=spectra_mol_pairs,
            featurizer=paired_featurizer,
            **infer_kwargs,
        )

        with torch.no_grad():
            pred_fp = model.encode_all_spectras(
                test_dataset, no_grad=True, **infer_kwargs
            ).cpu().numpy().squeeze()

    return _rank_by_fingerprint(pred_fp, library, top_k)


def _rank_by_fingerprint(pred_fp: np.ndarray, library: dict, top_k: int) -> List[dict]:
    """Rank library molecules by Tanimoto similarity to predicted fingerprint."""
    scores = []
    for i, lib_fp in enumerate(library["fingerprints"]):
        inter = float(np.dot(pred_fp > 0.5, lib_fp > 0.5))
        union = float(np.sum(pred_fp > 0.5) + np.sum(lib_fp > 0.5) - inter)
        sim = inter / union if union > 0 else 0.0
        scores.append((sim, i))

    scores.sort(reverse=True)
    return _build_candidates(scores[:top_k], library)


# ---------------------------------------------------------------------------
# Path B: Spectral cosine-similarity fallback
# ---------------------------------------------------------------------------

def _predict_similarity(
    ms_peaks: Optional[List[Tuple[float, float]]],
    nmr_peaks: Optional[List[Tuple[float, float]]],
    ir_peaks: Optional[List[Tuple[float, float]]],
    top_k: int,
) -> List[dict]:
    """Rank library molecules by cosine similarity of binned spectra."""
    library = _load_reference_library()
    if not library["molecules"]:
        return []

    scores = np.zeros(len(library["molecules"]), dtype=np.float64)
    n_scored = 0

    if ms_peaks:
        query_ms = _bin_peaks(ms_peaks, 0.0, 2000.0, 2048)
        for i, ref_peaks in enumerate(library["ms_spectra"]):
            if ref_peaks:
                ref_vec = _bin_peaks(ref_peaks, 0.0, 2000.0, 2048)
                scores[i] += _cosine_similarity(query_ms, ref_vec)
        n_scored += 1

    if nmr_peaks:
        query_nmr = _bin_peaks(nmr_peaks, -2.0, 14.0, 1024)
        for i, ref_peaks in enumerate(library["nmr_spectra"]):
            if ref_peaks:
                ref_vec = _bin_peaks(ref_peaks, -2.0, 14.0, 1024)
                scores[i] += _cosine_similarity(query_nmr, ref_vec)
        n_scored += 1

    # IR: no reference spectra in the library yet, so don't count it in averaging

    if n_scored > 0:
        scores /= n_scored

    ranked = sorted(enumerate(scores), key=lambda x: -x[1])
    return _build_candidates([(s, i) for i, s in ranked[:top_k]], library)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_candidates(scored_indices: List[Tuple[float, int]], library: dict) -> List[dict]:
    """Convert (score, index) pairs into candidate dicts."""
    candidates = []
    for rank, (score, idx) in enumerate(scored_indices, 1):
        mol_data = library["molecules"][idx]
        smiles = mol_data.get("smiles", "")

        conformer_sdf = None
        top_candidates = mol_data.get("candidates", [])
        for c in top_candidates:
            if c.get("smiles") == smiles and c.get("conformer_sdf"):
                conformer_sdf = c["conformer_sdf"]
                break

        valid = True
        if RDKIT_AVAILABLE:
            valid = Chem.MolFromSmiles(smiles) is not None

        candidates.append({
            "smiles": smiles,
            "score": round(float(score), 4),
            "rank": rank,
            "valid": valid,
            "conformer_sdf": conformer_sdf,
        })
    return candidates
