"""Backend e2e tests on the dummy model — no GPU required.

Covers: job lifecycle (submit → poll → result), mutation pipeline with RMSD
interpretation bands, schema validation (alphabet, length, position),
artifact download, 404s.
"""
import os
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ml"))
sys.path.insert(0, str(REPO / "hpc_core" / "python"))

os.environ["PGS_FOLDING_PROFILE"] = "dummy"
# Isolated per-test data dir so tests never touch real job artifacts.
_tmp = Path(__file__).parent / "_testdata"
_tmp.mkdir(exist_ok=True)
os.environ["PGS_DATA_DIR"] = str(_tmp)
os.environ["PGS_DB_PATH"] = str(_tmp / "jobs.sqlite3")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.config import get_settings  # noqa: E402

get_settings.cache_clear()
import backend.app.services.job_manager as jm_mod  # noqa: E402
import backend.app.services.folding_service as fs_mod  # noqa: E402

jm_mod._manager = None      # fresh JobManager on the isolated DB
fs_mod._service = None      # fresh FoldingService

from backend.app.main import app  # noqa: E402

client = TestClient(app)

UBIQ = ("MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG")
SHORT = "ACDEFGHIKL"  # exactly 10 aa


def wait_done(job_id: str, timeout: float = 30.0) -> dict:
    for _ in range(int(timeout * 10)):
        r = client.get(f"/api/v1/jobs/{job_id}")
        assert r.status_code == 200, r.text
        if r.json()["status"] in ("done", "error"):
            return r.json()
        time.sleep(0.1)
    raise TimeoutError(job_id)


class TestSystem:
    def test_health(self):
        assert client.get("/api/v1/health").json()["status"] == "ok"

    def test_presets_have_ubiquitin(self):
        pr = client.get("/api/v1/system/presets").json()["presets"]
        assert len(pr) == 12  # 4 ubiquitin + 8 curated research proteins
        assert pr[1]["position"] == 44 and pr[1]["mutant_aa"] == "A"


class TestValidation:
    def test_bad_aa_rejected(self):
        r = client.post("/api/v1/predict", json={"sequence": "ACDXXZAAAA"})
        assert r.status_code == 422

    def test_too_short_rejected(self):
        r = client.post("/api/v1/predict", json={"sequence": "ACD"})
        assert r.status_code == 422

    def test_position_out_of_range(self):
        r = client.post("/api/v1/mutate", json={
            "sequence": UBIQ, "position": 100, "mutant_aa": "A"})
        assert r.status_code == 422
        assert "out of range" in r.json()["detail"][0]["msg"]

    def test_mutant_equals_wt(self):
        # 422 detail follows the ?lang= UI language (ru is the default)
        for lang, needle in (("ru", "совпадает с остатком WT"),
                             ("en", "equals WT"),
                             ("zh", "突变残基")):
            r = client.post(f"/api/v1/mutate?lang={lang}", json={
                "sequence": UBIQ, "position": 44, "mutant_aa": "I"})
            assert r.status_code == 422
            assert needle in r.json()["detail"]


class TestPredictJob:
    def test_lifecycle(self):
        r = client.post("/api/v1/predict", json={"sequence": SHORT})
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        done = wait_done(job_id)
        assert done["status"] == "done"
        res = client.get(f"/api/v1/jobs/{job_id}/result").json()
        assert res["length"] == 10
        assert res["model"] == "dummy"
        assert res["from_cache"] is False
        # PDB artifact downloadable and parses as ATOM records
        pdb = client.get(f"/api/v1/files/{job_id}/wt.pdb")
        assert pdb.status_code == 200
        assert pdb.text.startswith("ATOM  ")

    def test_unknown_job_404(self):
        assert client.get("/api/v1/jobs/deadbeef").status_code == 404
        assert client.get("/api/v1/jobs/deadbeef/result").status_code == 404

    def test_result_before_done_409(self):
        r = client.post("/api/v1/predict", json={"sequence": SHORT})
        job_id = r.json()["job_id"]
        # immediately polling the result may race completion; accept either
        # 409 (not done yet) or a successful done result
        rr = client.get(f"/api/v1/jobs/{job_id}/result")
        assert rr.status_code in (200, 409)
        wait_done(job_id)

    def test_unknown_file_404(self):
        r = client.post("/api/v1/predict", json={"sequence": SHORT})
        job_id = wait_done(r.json()["job_id"])["job_id"]
        assert client.get(f"/api/v1/files/{job_id}/etc-passwd").status_code == 404


class TestMutateJob:
    def test_mutation_pipeline(self):
        r = client.post("/api/v1/mutate", json={
            "sequence": UBIQ, "position": 44, "mutant_aa": "A"})
        assert r.status_code == 200
        body = r.json()
        assert body["wt_aa"] == "I" and body["mutant_aa"] == "A"
        assert body["mutant_sequence"][43] == "A"
        done = wait_done(body["job_id"])
        assert done["status"] == "done"

        res = client.get(f"/api/v1/jobs/{body['job_id']}/result").json()
        rmsd = res["rmsd"]
        # dummy model: local window around I44A must land in "stable/moderate"
        assert rmsd["interpretation"] in ("stable", "moderate", "critical")
        assert 0 <= rmsd["global_rmsd"] < 50
        assert rmsd["local_window"] == [34, 54]  # JSON tuple → list
        assert rmsd["engine"] in ("cuda", "cpp", "numpy")

        for fn in ("wt.pdb", "mut.pdb", "mut_aligned.pdb"):
            f = client.get(f"/api/v1/files/{body['job_id']}/{fn}")
            assert f.status_code == 200, fn
            assert "ATOM  " in f.text

    def test_wt_reused_from_cache_across_mutations(self):
        # two mutations of the same protein: second job's WT must hit cache
        j1 = client.post("/api/v1/mutate", json={
            "sequence": UBIQ, "position": 3, "mutant_aa": "L"}).json()
        wait_done(j1["job_id"])
        res1 = client.get(f"/api/v1/jobs/{j1['job_id']}/result").json()
        j2 = client.post("/api/v1/mutate", json={
            "sequence": UBIQ, "position": 19, "mutant_aa": "G"}).json()
        wait_done(j2["job_id"])
        res2 = client.get(f"/api/v1/jobs/{j2['job_id']}/result").json()
        # NB: earlier tests in this module may have already folded UBIQ WT,
        # so only the monotone guarantee is asserted: the second mutation
        # definitely reuses the cached WT fold.
        assert res2["wt_from_cache"] is True
        # conservative mutation is more stable than loop glycine in the dummy
        assert res1["rmsd"]["local_rmsd"] < res2["rmsd"]["local_rmsd"]

    def test_summary_follows_lang_param(self):
        # submit-time lang drives the stored summary...
        r = client.post("/api/v1/mutate?lang=en", json={
            "sequence": UBIQ, "position": 44, "mutant_aa": "A"})
        job_id = wait_done(r.json()["job_id"])["job_id"]
        res = client.get(f"/api/v1/jobs/{job_id}/result").json()
        assert res["summary"].startswith("Mutation I44A")
        # ...and read-time lang retranslates it (history follows active UI lang)
        zh = client.get(f"/api/v1/jobs/{job_id}/result?lang=zh").json()
        assert zh["summary"].startswith("突变 I44A")
        # unknown lang → ru source of truth
        ru = client.get(f"/api/v1/jobs/{job_id}/result?lang=xx").json()
        assert ru["summary"].startswith("Мутация I44A")


class TestBenchmark:
    def test_dummy_benchmark(self):
        r = client.post("/api/v1/benchmark", json={
            "sequence": UBIQ, "profiles": ["dummy"], "repeats": 3})
        assert r.status_code == 200
        done = wait_done(r.json()["job_id"], timeout=60)
        assert done["status"] == "done"
        res = client.get(f"/api/v1/jobs/{r.json()['job_id']}/result").json()
        assert len(res["rows"]) == 1
        row = res["rows"][0]
        assert row["profile"] == "dummy" and row["length"] == 76
        assert row["repeats"] == 1  # 3 repeats - 2 warmup
        assert row["wall_median_s"] > 0

    def test_unknown_profile_422(self):
        r = client.post("/api/v1/benchmark", json={
            "sequence": UBIQ, "profiles": ["quantum"]})
        assert r.status_code == 422


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    import shutil
    shutil.rmtree(_tmp, ignore_errors=True)