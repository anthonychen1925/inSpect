"""
Backend API tests.

Run:  python -m pytest tests/test_api.py -v
"""
import base64
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"
SPECTRA_DIR = FIXTURES_DIR / "spectra"


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _load_spectrum_b64(name: str) -> str:
    path = SPECTRA_DIR / name
    return base64.b64encode(path.read_bytes()).decode()


# ---------------------------------------------------------------------------
# Health & fixtures
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "fixtures_available" in data
        assert data["mist_available"] in (True, False)
        assert "mist_checkpoint_loaded" in data

    def test_health_fixtures_present(self, client):
        r = client.get("/health")
        assert r.json()["fixtures_available"] is True


class TestFixtures:
    def test_list_fixtures(self, client):
        r = client.get("/fixtures")
        assert r.status_code == 200
        molecules = r.json()["molecules"]
        assert len(molecules) == 20
        names = [m["name"] for m in molecules]
        assert "aspirin" in names
        assert "vanillin" in names

    def test_fixture_metadata_fields(self, client):
        r = client.get("/fixtures")
        mol = r.json()["molecules"][0]
        for key in ["name", "display_name", "formula", "smiles", "mw", "has_nmr", "has_ms"]:
            assert key in mol, f"Missing field: {key}"

    def test_get_fixture_detail(self, client):
        r = client.get("/fixtures/caffeine")
        assert r.status_code == 200
        data = r.json()
        assert data["smiles"] == "Cn1cnc2c1c(=O)n(c(=O)n2C)C"
        assert "candidates" in data
        assert "variants" in data

    def test_get_fixture_404(self, client):
        r = client.get("/fixtures/nonexistent_molecule_xyz")
        assert r.status_code == 404

    def test_get_fixture_case_insensitive(self, client):
        r = client.get("/fixtures/Caffeine")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Spectra endpoint
# ---------------------------------------------------------------------------

class TestSpectra:
    def test_serve_csv(self, client):
        r = client.get("/spectra/caffeine_ms.csv")
        assert r.status_code == 200
        assert "mz" in r.text

    def test_serve_csv_404(self, client):
        r = client.get("/spectra/missing_file.csv")
        assert r.status_code == 404

    def test_path_traversal_blocked(self, client):
        r = client.get("/spectra/../../../etc/passwd")
        assert r.status_code in (400, 404, 422)

    def test_non_csv_blocked(self, client):
        r = client.get("/spectra/caffeine_ms.json")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Predict — always runs inference on uploaded peaks
# ---------------------------------------------------------------------------

class TestPredictInference:
    def test_predict_ms_only(self, client):
        ms_b64 = _load_spectrum_b64("caffeine_ms.csv")
        r = client.post("/predict", json={"ms_csv": ms_b64, "top_k": 10})
        assert r.status_code == 200
        data = r.json()
        assert data["inference_engine"] in ("mist", "spectral_similarity")
        assert len(data["candidates"]) == 10
        assert data["candidates"][0]["rank"] == 1
        assert data["modalities_used"] == ["ms"]

    def test_predict_nmr_only(self, client):
        nmr_b64 = _load_spectrum_b64("aspirin_nmr.csv")
        r = client.post("/predict", json={"nmr_csv": nmr_b64, "top_k": 5})
        assert r.status_code == 200
        data = r.json()
        assert data["inference_engine"] == "spectral_similarity"
        assert len(data["candidates"]) == 5
        assert data["modalities_used"] == ["nmr"]

    def test_predict_nmr_ms(self, client):
        ms_b64 = _load_spectrum_b64("caffeine_ms.csv")
        nmr_b64 = _load_spectrum_b64("caffeine_nmr.csv")
        r = client.post(
            "/predict",
            json={"ms_csv": ms_b64, "nmr_csv": nmr_b64, "top_k": 10},
        )
        assert r.status_code == 200
        data = r.json()
        assert set(data["modalities_used"]) == {"nmr", "ms"}
        assert len(data["candidates"]) == 10

    def test_predict_top_k(self, client):
        ms_b64 = _load_spectrum_b64("caffeine_ms.csv")
        r = client.post("/predict", json={"ms_csv": ms_b64, "top_k": 3})
        assert r.status_code == 200
        assert len(r.json()["candidates"]) == 3

    def test_predict_conformer_sdf_present(self, client):
        ms_b64 = _load_spectrum_b64("caffeine_ms.csv")
        r = client.post("/predict", json={"ms_csv": ms_b64, "top_k": 1})
        cand = r.json()["candidates"][0]
        assert cand.get("conformer_sdf") is not None
        assert "RDKit" in cand["conformer_sdf"]

    def test_predict_warning_single_modality(self, client):
        csv_b64 = _b64("ppm,intensity\n3.35,100\n7.69,100\n")
        r = client.post("/predict", json={"nmr_csv": csv_b64, "top_k": 5})
        assert r.status_code == 200
        assert r.json()["warning"] is not None


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestPredictErrors:
    def test_bad_base64(self, client):
        r = client.post("/predict", json={"ms_csv": "not-valid-base64!!!"})
        assert r.status_code == 400

    def test_no_spectra(self, client):
        r = client.post("/predict", json={})
        assert r.status_code == 400

    def test_ir_only_rejected(self, client):
        ir_b64 = _b64("wavenumber,intensity\n1700,1\n3000,0.5\n")
        r = client.post("/predict", json={"ir_csv": ir_b64})
        assert r.status_code == 400

    def test_empty_peaks(self, client):
        r = client.post("/predict", json={"nmr_csv": _b64("ppm,intensity\n")})
        assert r.status_code == 400

    def test_candidate_schema(self, client):
        ms_b64 = _load_spectrum_b64("caffeine_ms.csv")
        r = client.post("/predict", json={"ms_csv": ms_b64, "top_k": 1})
        cand = r.json()["candidates"][0]
        assert isinstance(cand["smiles"], str)
        assert isinstance(cand["score"], (int, float))
        assert isinstance(cand["rank"], int)
        assert isinstance(cand["valid"], bool)
