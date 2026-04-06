"""
FastAPI backend for spectra-to-structure inference.

Uploads are decoded, peak-parsed, and scored against the reference library
(spectral cosine similarity on binned MS/NMR, optional IR parsed for future use).
When MIST is installed and MIST_CKPT points to a checkpoint, MS spectra use MIST
encoding + library ranking instead.
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
from pydantic import BaseModel, Field

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
MIST_CKPT = os.getenv("MIST_CKPT", "")

logger.info("FIXTURES_DIR=%s  MIST_AVAILABLE=%s  MIST_CKPT=%s", FIXTURES_DIR, MIST_AVAILABLE, MIST_CKPT or "(none)")


class PredictRequest(BaseModel):
    nmr_csv: Optional[str] = None   # base64-encoded CSV: ppm,intensity
    ms_csv: Optional[str] = None    # base64-encoded CSV: mz,intensity
    ir_csv: Optional[str] = None    # base64-encoded CSV: wavenumber,intensity
    top_k: int = Field(default=10, ge=1, le=50)


class Candidate(BaseModel):
    smiles: str
    name: str = ""
    score: float
    rank: int
    valid: bool
    conformer_sdf: Optional[str] = None


class PredictResponse(BaseModel):
    candidates: List[Candidate]
    modalities_used: List[str]
    inference_engine: str  # "mist" | "spectral_similarity"
    warning: Optional[str] = None


def _decode_base64_csv(data: str) -> str:
    """Validate and decode a base64-encoded CSV string."""
    try:
        return base64.b64decode(data).decode("utf-8")
    except Exception as e:
        raise HTTPException(400, f"Invalid base64 CSV data: {e}")


@app.get("/health")
def health():
    fixtures_ok = FIXTURES_DIR.is_dir() and any(FIXTURES_DIR.glob("*.json"))
    mist_ckpt_ok = bool(MIST_CKPT and Path(MIST_CKPT).exists())
    return {
        "status": "ok",
        "fixtures_available": fixtures_ok,
        "mist_available": MIST_AVAILABLE,
        "mist_checkpoint_loaded": mist_ckpt_ok,
    }


DEMO_MOLECULES = [
    "aspirin", "ibuprofen", "acetaminophen", "dopamine",
    "cholesterol", "vanillin", "nicotine", "morphine",
    "serotonin", "glucose", "melatonin", "epinephrine",
    "codeine", "naproxen", "lidocaine", "quinine",
    "penicillin_g", "warfarin", "curcumin", "capsaicin",
]

@app.get("/fixtures")
def list_fixtures():
    """List reference molecules with metadata (for browsing / sample downloads)."""
    molecules = []
    for name in DEMO_MOLECULES:
        f = FIXTURES_DIR / f"{name}.json"
        if not f.exists():
            continue
        try:
            with open(f) as fh:
                data = json.load(fh)
            molecules.append({
                "name": name,
                "display_name": data.get("display_name", name.replace("_", " ").title()),
                "formula": data.get("formula", ""),
                "smiles": data.get("smiles", ""),
                "mw": data.get("mw", 0),
                "has_nmr": data.get("has_nmr", False),
                "has_ms": data.get("has_ms", False),
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
    modalities_used: List[str] = []
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

    if not modalities_used:
        raise HTTPException(400, "Upload at least one spectrum CSV (NMR, MS, and/or IR).")

    if set(modalities_used) <= {"ir"}:
        raise HTTPException(
            400,
            "Provide NMR and/or MS data; the current model does not rank structures from IR alone.",
        )

    # Require parseable peaks so predictions always reflect the uploaded file contents.
    if req.nmr_csv and not parse_csv_peaks(nmr_text or ""):
        raise HTTPException(400, "NMR CSV has no valid numeric peaks (expected two columns after a header row).")
    if req.ms_csv and not parse_csv_peaks(ms_text or ""):
        raise HTTPException(400, "MS CSV has no valid numeric peaks (expected two columns after a header row).")
    if req.ir_csv and not parse_csv_peaks(ir_text or ""):
        raise HTTPException(400, "IR CSV has no valid numeric peaks (expected two columns after a header row).")

    return _predict_live(ms_text, nmr_text, ir_text, modalities_used, req.top_k)


def _predict_live(
    ms_text: Optional[str],
    nmr_text: Optional[str],
    ir_text: Optional[str],
    modalities_used: List[str],
    top_k: int,
) -> PredictResponse:
    """Run inference: MIST (MS) when checkpoint set, else binned spectral similarity."""
    ms_peaks = parse_csv_peaks(ms_text) if ms_text else None
    nmr_peaks = parse_csv_peaks(nmr_text) if nmr_text else None
    ir_peaks = parse_csv_peaks(ir_text) if ir_text else None

    logger.info("Predict: modalities=%s top_k=%s mist_ckpt=%s", modalities_used, top_k, MIST_CKPT or "(none)")

    try:
        raw_candidates, engine = predict_live(
            ms_peaks=ms_peaks,
            nmr_peaks=nmr_peaks,
            ir_peaks=ir_peaks,
            top_k=top_k,
            model_ckpt=MIST_CKPT or None,
        )
    except Exception as e:
        logger.error("Inference error: %s", e)
        raise HTTPException(500, f"Inference failed: {e}")

    if not raw_candidates:
        raise HTTPException(404, "No matching molecules found for the provided spectra.")

    candidates_list = [Candidate(**c) for c in raw_candidates]

    warning_parts = []
    scoring_modalities = [m for m in modalities_used if m in ("nmr", "ms")]
    if len(scoring_modalities) == 1:
        warning_parts.append("Only one of NMR or MS provided; both usually improve ranking.")
    if "ir" in modalities_used:
        warning_parts.append("IR peaks are accepted but not yet used in similarity scoring against the library.")
    warning = " ".join(warning_parts) if warning_parts else None

    return PredictResponse(
        candidates=candidates_list,
        modalities_used=modalities_used,
        inference_engine=engine,
        warning=warning,
    )
