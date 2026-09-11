"""Tests for the saturation scan endpoint and the profile field."""
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
_tmp = Path(__file__).parent / "_testdata_scan"
_tmp.mkdir(exist_ok=True)
os.environ["PGS_DATA_DIR"] = str(_tmp)
os.environ["PGS_DB_PATH"] = str(_tmp / "jobs.sqlite3")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.config import get_settings  # noqa: E402

get_settings.cache_clear()
from backend.app.main import app  # noqa: E402

client = TestClient(app)
UBIQ = ("MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG")


def wait_job(job_id: str, timeout: float = 60) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/v1/jobs/{job_id}").json()
        if s["status"] in ("done", "error"):
            return s
        time.sleep(0.05)
    pytest.fail(f"job {job_id} timed out")


class TestScan:
    def test_scan_lifecycle(self):
        r = client.post("/api/v1/scan", json={"sequence": UBIQ, "position": 44})
        assert r.status_code == 200
        job_id = r.json()["job_id"]

        s = wait_job(job_id)
        assert s["status"] == "done", s.get("error")

        res = client.get(f"/api/v1/jobs/{job_id}/result").json()
        assert res["position"] == 44 and res["wt_aa"] == "I"
        rows = res["rows"]
        assert len(rows) == 19
        assert {r["mut_aa"] for r in rows} == set("ACDEFGHIKLMNPQRSTVWY") - {"I"}
        # sorted strongest-first
        loc = [r["local_rmsd"] for r in rows]
        assert loc == sorted(loc, reverse=True)
        assert res["best"] == rows[0]["mut_aa"]
        assert "Скан позиции 44" in res["summary"]
        # artifacts
        assert client.get(f"/api/v1/files/{job_id}/wt.pdb").status_code == 200
        aa = res["best"]
        assert client.get(f"/api/v1/files/{job_id}/scan_{aa}.pdb").status_code == 200

    def test_scan_position_validation(self):
        r = client.post("/api/v1/scan", json={"sequence": UBIQ, "position": 500})
        assert r.status_code == 422

    def test_profile_field_validation(self):
        r = client.post("/api/v1/mutate", json={
            "sequence": UBIQ, "position": 44, "mutant_aa": "A", "profile": "tpu"})
        assert r.status_code == 422

    def test_profile_dummy_switch(self):
        """Explicit dummy profile must run and be reported in the result."""
        r = client.post("/api/v1/mutate", json={
            "sequence": UBIQ, "position": 44, "mutant_aa": "A", "profile": "dummy"})
        assert r.status_code == 200
        s = wait_job(r.json()["job_id"])
        assert s["status"] == "done", s.get("error")
        res = client.get(f"/api/v1/jobs/{r.json()['job_id']}/result").json()
        assert "dummy" in res["model"]
        # per-residue pLDDT arrays present for the chart
        assert len(res["plddt_wt_list"]) == len(UBIQ)
        assert len(res["plddt_mut_list"]) == len(UBIQ)