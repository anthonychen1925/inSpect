# DiamondHacks — Multimodal Spectra → Structure

> Paste in NMR, MS, and/or IR spectra. Get ranked candidate molecules with 3D conformers.

## Stack
| Layer | Tech |
|---|---|
| Frontend | Next.js + Tailwind CSS |
| Backend | FastAPI + Uvicorn |
| MS inference | MIST (pretrained, MIT) |
| Chemistry | RDKit, SELFIES |

## Quickstart

```bash
# 1. Install Python deps
pip install -e ".[dev]"

# 2. Fetch real spectra for 20 demo molecules
python scripts/fetch_demo_data.py

# 3. Build fixture JSONs + conformers
python scripts/build_fixtures.py

# 4. Start API (inference uses uploaded CSVs; optional MIST via MIST_CKPT)
uvicorn backend.main:app --reload --port 8000

# 5. Start frontend
cd frontend && npm install && npm run dev
```

## Project structure
```
diamondhacks/
  configs/          — model, data, train YAML configs
  data/
    fixtures/       — precomputed JSON + spectra CSVs for 20 molecules
    raw/            — downloaded database files
  scripts/
    fetch_demo_data.py  — downloads spectra from MassBank + NMRShiftDB2
    build_fixtures.py   — generates fixture JSONs + RDKit conformers
  src/
    data/           — binning, datasets, schema
    models/         — encoder, fusion, decoder, heads
    chemistry/      — rdkit_utils, selfies_utils
    training/       — losses, metrics, loops
  backend/
    main.py         — FastAPI app
  frontend/         — Next.js app (npm create next-app)
  tests/            — pytest tests
```

## Demo molecules (20)
caffeine, aspirin, ibuprofen, acetaminophen, dopamine, serotonin,
nicotine, glucose, cholesterol, vanillin, menthol, capsaicin,
citric_acid, lidocaine, quinine, penicillin_g, ethanol, benzene,
acetone, toluene

## API
`POST /predict` — accepts base64-encoded CSV spectra, returns top-10 candidates
`GET  /fixtures` — lists available demo molecules
`GET  /health`   — health check (reports MIST availability / checkpoint)

## Demo flow (rehearse twice!)
1. Open site → clean landing page
2. Upload `data/fixtures/spectra/caffeine_nmr.csv` (and optionally `caffeine_ms.csv`)
3. Show top-k ranked candidates from spectral similarity (or MIST when `MIST_CKPT` is set)
4. Click top-1 → show 3D conformer in viewer
5. Compare NMR-only vs NMR+MS inputs
