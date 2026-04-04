"""
FastAPI backend for DiamondHacks spectra-to-structure demo.
Serves fixture data in demo_mode (default), or runs live inference
via MIST (when installed) or spectral cosine-similarity fallback.
"""
import json
import base64
import logging
import os
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from backend.mist_inference import predict_live, parse_csv_peaks, MIST_AVAILABLE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="DiamondHacks Spectra API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"
SPECTRA_DIR = FIXTURES_DIR / "spectra"
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
MIST_CKPT = os.getenv("MIST_CKPT", "")

logger.info("DEMO_MODE=%s  FIXTURES_DIR=%s  MIST_AVAILABLE=%s", DEMO_MODE, FIXTURES_DIR, MIST_AVAILABLE)


class PredictRequest(BaseModel):
    nmr_csv: Optional[str] = None   # base64-encoded CSV: ppm,intensity
    ms_csv: Optional[str] = None    # base64-encoded CSV: mz,intensity
    ir_csv: Optional[str] = None    # base64-encoded CSV: wavenumber,intensity
    top_k: int = 5
    demo_molecule: Optional[str] = None

    @field_validator("top_k")
    @classmethod
    def clamp_top_k(cls, v: int) -> int:
        return max(1, min(v, 20))

    @field_validator("demo_molecule")
    @classmethod
    def sanitize_molecule_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        clean = v.strip().lower().replace(" ", "_")
        if not clean.replace("_", "").isalnum():
            raise ValueError("demo_molecule must be alphanumeric (underscores allowed)")
        return clean


class Candidate(BaseModel):
    smiles: str
    score: float
    rank: int
    valid: bool
    conformer_sdf: Optional[str] = None


class PredictResponse(BaseModel):
    candidates: List[Candidate]
    modalities_used: List[str]
    warning: Optional[str] = None
    demo_mode: bool = False


def _decode_base64_csv(data: str) -> str:
    """Validate and decode a base64-encoded CSV string."""
    try:
        return base64.b64decode(data).decode("utf-8")
    except Exception as e:
        raise HTTPException(400, f"Invalid base64 CSV data: {e}")


def _find_conformer_for_smiles(smiles: str, candidates: list) -> Optional[str]:
    """Find the conformer_sdf for a given SMILES from a candidate list."""
    for c in candidates:
        if c.get("smiles") == smiles and c.get("conformer_sdf"):
            return c["conformer_sdf"]
    return None


@app.get("/health")
def health():
    fixtures_ok = FIXTURES_DIR.is_dir() and any(FIXTURES_DIR.glob("*.json"))
    return {"status": "ok", "demo_mode": DEMO_MODE, "fixtures_available": fixtures_ok}


@app.get("/fixtures")
def list_fixtures():
    """List available demo molecules with metadata."""
    molecules = []
    for f in sorted(FIXTURES_DIR.glob("*.json")):
        try:
            with open(f) as fh:
                data = json.load(fh)
            name = f.stem
            molecules.append({
                "name": name,
                "display_name": data.get("display_name", name.replace("_", " ").title()),
                "formula": data.get("formula", ""),
                "smiles": data.get("smiles", ""),
                "mw": data.get("mw", 0),
                "has_nmr": data.get("has_nmr", False),
                "has_ms": data.get("has_ms", False),
                "nmr_csv": f"{name}_nmr.csv" if data.get("has_nmr") else None,
                "ms_csv": f"{name}_ms.csv" if data.get("has_ms") else None,
            })
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping corrupt fixture %s: %s", f.name, e)
    return {"molecules": molecules}


@app.get("/fixtures/{molecule_name}")
def get_fixture(molecule_name: str):
    """Return full fixture JSON for a specific molecule."""
    clean = molecule_name.strip().lower().replace(" ", "_")
    fixture_path = FIXTURES_DIR / f"{clean}.json"
    if not fixture_path.exists():
        raise HTTPException(404, f"Fixture '{clean}' not found")
    with open(fixture_path) as f:
        return json.load(f)


@app.get("/spectra/{filename}")
def get_spectrum_csv(filename: str):
    """Serve a raw spectrum CSV file (e.g. caffeine_ms.csv)."""
    if not filename.endswith(".csv") or "/" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = SPECTRA_DIR / filename
    if not path.exists():
        raise HTTPException(404, f"Spectrum file '{filename}' not found")
    return FileResponse(path, media_type="text/csv", filename=filename)


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    modalities_used = []
    ms_text = nmr_text = ir_text = None
    if req.nmr_csv:
        nmr_text = _decode_base64_csv(req.nmr_csv)
        modalities_used.append("nmr")
    if req.ms_csv:
        ms_text = _decode_base64_csv(req.ms_csv)
        modalities_used.append("ms")
    if req.ir_csv:
        ir_text = _decode_base64_csv(req.ir_csv)
        modalities_used.append("ir")

    if DEMO_MODE or req.demo_molecule:
        return _predict_demo(req, modalities_used)

    if not modalities_used:
        raise HTTPException(400, "At least one spectrum must be provided.")

    return _predict_live(ms_text, nmr_text, ir_text, modalities_used, req.top_k)


def _predict_demo(req: PredictRequest, modalities_used: List[str]) -> PredictResponse:
    mol_name = req.demo_molecule or _guess_molecule(req)
    logger.info("Demo predict: molecule=%s modalities=%s", mol_name, modalities_used)

    fixture_path = FIXTURES_DIR / f"{mol_name}.json"
    if not fixture_path.exists():
        fixture_path = _fallback_fixture()
        if fixture_path is None:
            raise HTTPException(500, "No fixture data available.")
        logger.warning("Fixture '%s' not found, falling back to %s", mol_name, fixture_path.stem)

    with open(fixture_path) as f:
        fixture = json.load(f)

    if not modalities_used:
        variants = fixture.get("variants", {})
        if variants:
            modalities_used = list(variants.keys())[0].split("_")
        else:
            modalities_used = ["nmr"]

    variant_key = "_".join(sorted(modalities_used))
    candidates_data = fixture.get("variants", {}).get(variant_key,
                      fixture.get("candidates", []))

    top_level_candidates = fixture.get("candidates", [])
    candidates_list = []
    for i, c in enumerate(candidates_data[:req.top_k]):
        candidate_dict = dict(c)
        if not candidate_dict.get("conformer_sdf"):
            sdf = _find_conformer_for_smiles(candidate_dict["smiles"], top_level_candidates)
            if sdf:
                candidate_dict["conformer_sdf"] = sdf
        candidates_list.append(Candidate(**candidate_dict))

    warning = None
    if len(modalities_used) < 3:
        missing = [m for m in ["nmr", "ms", "ir"] if m not in modalities_used]
        warning = f"{', '.join(missing).upper()} not provided; results may be less accurate."

    is_fallback = fixture_path.stem != mol_name
    if is_fallback:
        warning = f"Fixture '{mol_name}' not found; returning fallback data."

    return PredictResponse(
        candidates=candidates_list,
        modalities_used=modalities_used,
        warning=warning,
        demo_mode=True,
    )


def _predict_live(
    ms_text: Optional[str],
    nmr_text: Optional[str],
    ir_text: Optional[str],
    modalities_used: List[str],
    top_k: int,
) -> PredictResponse:
    """Run live inference via MIST or spectral similarity fallback."""
    ms_peaks = parse_csv_peaks(ms_text) if ms_text else None
    nmr_peaks = parse_csv_peaks(nmr_text) if nmr_text else None
    ir_peaks = parse_csv_peaks(ir_text) if ir_text else None

    logger.info("Live predict: modalities=%s mist_ckpt=%s", modalities_used, MIST_CKPT or "(none)")

    try:
        raw_candidates = predict_live(
            ms_peaks=ms_peaks,
            nmr_peaks=nmr_peaks,
            ir_peaks=ir_peaks,
            top_k=top_k,
            model_ckpt=MIST_CKPT or None,
        )
    except Exception as e:
        logger.error("Live inference error: %s", e)
        raise HTTPException(500, f"Inference failed: {e}")

    if not raw_candidates:
        raise HTTPException(404, "No matching molecules found for the provided spectra.")

    candidates_list = [Candidate(**c) for c in raw_candidates]

    warning = None
    engine = "MIST" if (MIST_AVAILABLE and MIST_CKPT) else "spectral-similarity"
    if len(modalities_used) < 3:
        missing = [m for m in ["nmr", "ms", "ir"] if m not in modalities_used]
        warning = f"Engine: {engine}. {', '.join(missing).upper()} not provided."
    else:
        warning = f"Engine: {engine}."

    return PredictResponse(
        candidates=candidates_list,
        modalities_used=modalities_used,
        warning=warning,
        demo_mode=False,
    )


def _fallback_fixture() -> Optional[Path]:
    all_fixtures = sorted(FIXTURES_DIR.glob("*.json"))
    return all_fixtures[0] if all_fixtures else None


def _guess_molecule(req: PredictRequest) -> str:
    """Best-effort molecule name guess from CSV content."""
    for csv_field in [req.nmr_csv, req.ms_csv, req.ir_csv]:
        if not csv_field:
            continue
        try:
            text = base64.b64decode(csv_field).decode("utf-8", errors="ignore").lower()
            known = [f.stem for f in FIXTURES_DIR.glob("*.json")]
            for name in known:
                if name in text:
                    return name
        except Exception:
            pass
    return "caffeine"
