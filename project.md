# SpectraStruct — Project Reference

## Overview

SpectraStruct (DiamondHacks) is a multimodal spectroscopy-to-structure prediction tool.
Users upload NMR, MS, and/or IR spectra and receive ranked candidate molecules with
3D conformers. The system operates in two modes:

- **Demo mode** (default): serves precomputed fixture data for 20 well-known molecules
- **Live mode**: runs spectral similarity matching (or real MIST inference when installed)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                       │
│   Upload CSV  →  POST /predict  →  Render candidates + 3D view │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/JSON
┌──────────────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend (:8000)                        │
│                                                                 │
│  ┌──────────┐    ┌───────────────┐    ┌──────────────────────┐  │
│  │  /health │    │   /fixtures   │    │      /predict        │  │
│  │  /spectra│    │ /fixtures/:id │    │                      │  │
│  └──────────┘    └───────────────┘    │  DEMO_MODE=true?     │  │
│                                       │   ├─ yes → fixtures  │  │
│                                       │   └─ no  → live      │  │
│                                       └──────────┬───────────┘  │
│                                                  │              │
│                          ┌───────────────────────▼───────────┐  │
│                          │     mist_inference.py             │  │
│                          │                                   │  │
│                          │  MIST installed + checkpoint?     │  │
│                          │   ├─ yes → MIST fingerprint pred  │  │
│                          │   └─ no  → cosine similarity      │  │
│                          │           against fixture library  │  │
│                          └───────────────────────────────────┘  │
│                                       │                         │
│                          ┌────────────▼──────────────┐          │
│                          │  Reference Library (20)   │          │
│                          │  Morgan FP + spectra CSVs │          │
│                          └───────────────────────────┘          │
│                                       │                         │
│                          ┌────────────▼──────────────┐          │
│                          │  RDKit Chemistry Layer    │          │
│                          │  SMILES → mol → conformer │          │
│                          │  → SDF string for 3D view │          │
│                          └───────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

| Component | Path | Purpose |
|---|---|---|
| FastAPI app | `backend/main.py` | Routes, request validation, demo/live dispatch |
| MIST wrapper | `backend/mist_inference.py` | Live inference: MIST or spectral similarity fallback |
| RDKit utils | `src/chemistry/rdkit_utils.py` | SMILES parsing, fingerprints, conformer generation, SDF export |
| SELFIES utils | `src/chemistry/selfies_utils.py` | Robust molecular string encoding/decoding |
| Spectrum binning | `src/data/binning.py` | Bin raw spectra into fixed-length float32 vectors |
| Data schema | `src/data/schema.py` | `MolecularExample` dataclass for training pipeline |
| Dataset loader | `src/data/datasets.py` | PyTorch Dataset for `.npz` spectral data |
| Fixture builder | `scripts/build_fixtures.py` | Generate fixture JSONs + conformers for 20 demo molecules |
| Data fetcher | `scripts/fetch_demo_data.py` | Download real spectra from MassBank + NMRShiftDB2 |
| Configs | `configs/*.yaml` | Data binning, model architecture, training hyperparameters |

## Demo Flow (from scratch)

```bash
# 1. Clone and install
git clone <repo-url> && cd SpectraStruct
pip install -e ".[dev]"

# 2. Fetch real spectra (MassBank + NMRShiftDB2, falls back to synthetic)
python scripts/fetch_demo_data.py

# 3. Build fixture JSONs with RDKit conformers
python scripts/build_fixtures.py

# 4. Start backend (demo mode)
DEMO_MODE=true uvicorn backend.main:app --reload --port 8000

# 5. Start frontend
cd frontend && npm install && npm run dev

# 6. Open http://localhost:3000
```

### Demo script (rehearse twice)

1. Open site → clean landing page
2. Upload `data/fixtures/spectra/caffeine_nmr.csv`
3. Show top-5 candidates (correct molecule in top-3 with NMR alone)
4. Add `caffeine_ms.csv` → correct molecule jumps to #1
5. Click top-1 → show 3D conformer viewer
6. Compare: NMR alone vs NMR+MS vs all three modalities

## Dev Setup

**Prerequisites:** Python ≥ 3.10, Node.js ≥ 18, RDKit (installed via `rdkit-pypi`)

```bash
# Install with dev tools
pip install -e ".[dev]"

# Optional: install MIST for real MS inference
pip install -e ".[mist]"

# Run tests
python -m pytest tests/ -v

# Start backend (live mode with spectral similarity)
DEMO_MODE=false uvicorn backend.main:app --reload --port 8000

# Start backend with MIST model checkpoint
DEMO_MODE=false MIST_CKPT=path/to/model.ckpt uvicorn backend.main:app --reload --port 8000
```

## API Reference

### `GET /health`

Returns server status.

```json
{"status": "ok", "demo_mode": true, "fixtures_available": true}
```

### `GET /fixtures`

Lists all 20 demo molecules with metadata.

```json
{
  "molecules": [
    {
      "name": "caffeine",
      "display_name": "Caffeine",
      "formula": "C8H10N4O2",
      "smiles": "Cn1cnc2c1c(=O)n(c(=O)n2C)C",
      "has_nmr": true,
      "has_ms": true
    }
  ]
}
```

### `GET /fixtures/{molecule_name}`

Returns full fixture JSON including candidates and variant rankings.

### `GET /spectra/{filename}`

Serves raw spectrum CSV files (e.g., `caffeine_ms.csv`).

### `POST /predict`

**Request body:**

```json
{
  "nmr_csv": "<base64-encoded CSV: ppm,intensity>",
  "ms_csv": "<base64-encoded CSV: mz,intensity>",
  "ir_csv": "<base64-encoded CSV: wavenumber,intensity>",
  "top_k": 5,
  "demo_molecule": "caffeine"
}
```

All fields optional. At least one spectrum or `demo_molecule` required.

**Response:**

```json
{
  "candidates": [
    {
      "smiles": "Cn1cnc2c1c(=O)n(c(=O)n2C)C",
      "score": 0.94,
      "rank": 1,
      "valid": true,
      "conformer_sdf": "<SDF V2000 string or null>"
    }
  ],
  "modalities_used": ["nmr", "ms"],
  "warning": "IR not provided; results may be less accurate.",
  "demo_mode": true
}
```

**Behavior:**
- `DEMO_MODE=true` or `demo_molecule` set → returns fixture data with variant matching
- `DEMO_MODE=false` → runs live inference (MIST if available, else spectral similarity)

## File Structure

```
SpectraStruct/
├── backend/
│   ├── __init__.py
│   ├── main.py              ← FastAPI app, routes, validation
│   └── mist_inference.py    ← MIST wrapper + similarity fallback
├── configs/
│   ├── data.yaml            ← binning ranges, fingerprint config
│   ├── model.yaml           ← encoder/fusion architecture
│   └── train.yaml           ← training hyperparameters
├── data/
│   ├── fixtures/            ← 20 precomputed fixture JSONs
│   │   └── spectra/         ← 40 CSV files (20 × {ms,nmr})
│   └── raw/
│       └── manifest.json    ← fetch script output manifest
├── scripts/
│   ├── fetch_demo_data.py   ← download spectra from MassBank/NMRShiftDB2
│   └── build_fixtures.py    ← generate fixture JSONs + conformers
├── src/
│   ├── __init__.py
│   ├── chemistry/
│   │   ├── __init__.py
│   │   ├── rdkit_utils.py   ← SMILES, fingerprints, conformers, SDF
│   │   └── selfies_utils.py ← SELFIES encoding/decoding
│   └── data/
│       ├── __init__.py
│       ├── binning.py       ← spectrum → fixed-length vector
│       ├── datasets.py      ← PyTorch Dataset for .npz files
│       └── schema.py        ← MolecularExample dataclass
├── tests/
│   ├── __init__.py
│   ├── conftest.py          ← pytest fixtures (TestClient)
│   ├── test_api.py          ← 25 API endpoint tests
│   ├── test_binning.py      ← spectrum binning tests
│   └── test_rdkit_utils.py  ← RDKit utility tests
├── frontend/                ← Next.js app (separate setup)
├── CLAUDE.md                ← AI assistant instructions
├── README.md                ← quickstart guide
├── project.md               ← this file
├── pyproject.toml           ← dependencies + build config
└── run_demo.sh              ← start backend + frontend
```

## 20 Demo Molecules

caffeine, aspirin, ibuprofen, acetaminophen, dopamine, serotonin,
nicotine, glucose, cholesterol, vanillin, menthol, capsaicin,
citric_acid, lidocaine, quinine, penicillin_g, ethanol, benzene,
acetone, toluene

Each has precomputed MS + NMR spectra (real or synthetic), 3D conformers,
and ranked candidate lists for the demo ablation (NMR → MS → NMR+MS → all).
