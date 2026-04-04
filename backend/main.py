"""
FastAPI backend for DiamondHacks spectra-to-structure demo.
Serves fixture data in demo_mode (default), or runs live MIST inference.
"""
import json
import base64
import os
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np

app = FastAPI(title="DiamondHacks Spectra API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FIXTURES_DIR = Path(__file__).parent.parent / "data" / "fixtures"
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

class PredictRequest(BaseModel):
    nmr_csv: Optional[str] = None   # base64-encoded CSV: ppm,intensity
    ms_csv: Optional[str] = None    # base64-encoded CSV: mz,intensity
    ir_csv: Optional[str] = None    # base64-encoded CSV: wavenumber,intensity
    top_k: int = 5
    demo_molecule: Optional[str] = None  # e.g. "caffeine" — forces fixture lookup

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

@app.get("/health")
def health():
    return {"status": "ok", "demo_mode": DEMO_MODE}

@app.get("/fixtures")
def list_fixtures():
    """List available demo molecules."""
    fixtures = [f.stem for f in FIXTURES_DIR.glob("*.json")]
    return {"molecules": sorted(fixtures)}

@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    modalities_used = []
    if req.nmr_csv: modalities_used.append("nmr")
    if req.ms_csv:  modalities_used.append("ms")
    if req.ir_csv:  modalities_used.append("ir")

    # Demo mode: return fixture data
    if DEMO_MODE or req.demo_molecule:
        mol_name = req.demo_molecule or _guess_molecule(req)
        fixture_path = FIXTURES_DIR / f"{mol_name}.json"
        if fixture_path.exists():
            with open(fixture_path) as f:
                fixture = json.load(f)
            
            # If no modalities specified, infer from fixture variants or use default
            if not modalities_used:
                variants = fixture.get("variants", {})
                if variants:
                    # Use first available variant
                    modalities_used = list(variants.keys())[0].split("_")
                else:
                    modalities_used = ["nmr"]  # default
            
            # Return the variant matching available modalities, but merge conformers from top-level candidates
            variant_key = "_".join(sorted(modalities_used))
            candidates_data = fixture.get("variants", {}).get(variant_key,
                              fixture.get("candidates", []))
            
            # Merge in top-level conformers if present (variants may have empty SDFs)
            top_level_candidates = fixture.get("candidates", [])
            candidates_list = []
            for i, c in enumerate(candidates_data[:req.top_k]):
                candidate_dict = dict(c)  # Copy to avoid modifying fixture
                # If this candidate's conformer is empty, try to get it from top-level
                if (not candidate_dict.get("conformer_sdf") and 
                    i < len(top_level_candidates) and 
                    top_level_candidates[i].get("conformer_sdf")):
                    candidate_dict["conformer_sdf"] = top_level_candidates[i]["conformer_sdf"]
                candidates_list.append(Candidate(**candidate_dict))
            
            warning = None
            if len(modalities_used) < 3:
                missing = [m for m in ["nmr", "ms", "ir"] if m not in modalities_used]
                warning = f"{', '.join(missing).upper()} not provided; results may be less accurate."
            
            return PredictResponse(
                candidates=candidates_list,
                modalities_used=modalities_used,
                warning=warning,
                demo_mode=True,
            )
        # Fallback: return first available fixture
        all_fixtures = list(FIXTURES_DIR.glob("*.json"))
        if all_fixtures:
            with open(all_fixtures[0]) as f:
                fixture = json.load(f)
            if not modalities_used:
                modalities_used = ["nmr"]
            candidates = [Candidate(**c) for c in fixture.get("candidates", [])[:req.top_k]]
            warning = "Fixture not found; returning fallback data."
            return PredictResponse(candidates=candidates, modalities_used=modalities_used,
                                   warning=warning, demo_mode=True)

    # Live mode: require at least one spectrum
    if not modalities_used:
        raise HTTPException(400, "At least one spectrum must be provided.")

    # Live mode: MIST inference (placeholder — wire in after hackathon setup)
    raise HTTPException(501, "Live inference not yet configured. Set DEMO_MODE=true.")

def _guess_molecule(req: PredictRequest) -> str:
    """Try to guess molecule from filename hints in CSV data (best effort)."""
    return "caffeine"  # default fallback
