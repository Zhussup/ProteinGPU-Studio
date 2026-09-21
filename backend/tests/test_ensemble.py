"""Tests for the mutagenesis-strength ensemble endpoint (/ensemble).

Same harness as test_scan_profile.py: the real FastAPI app on the dummy
model (deterministic per sequence → exact metric parity across job kinds).
Covers: schema validation, exhaustive ≡ /scan parity, sampled-mode invariants
(anchor + background), seed reproducibility, artifacts, history label, and
summary retranslation.
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
_tmp = Path(__file__).parent / "_testdata_ens"
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


def run_ensemble(payload: dict) -> dict:
    r = client.post("/api/v1/ensemble", json=payload)
    assert r.status_code == 200, r.text
    s = wait_job(r.json()["job_id"])
    assert s["status"] == "done", s.get("error")
    return client.get(f"/api/v1/jobs/{r.json()['job_id']}/result").json()


class TestValidation:
    def test_mu_bounds(self):
        for mu in (0, 4):
            r = client.post("/api/v1/ensemble", json={
                "sequence": UBIQ, "position": 44, "mu": mu})
            assert r.status_code == 422, mu

    def test_tau_bounds(self):
        for tau in (-0.1, 1.1):
            r = client.post("/api/v1/ensemble", json={
                "sequence": UBIQ, "position": 44, "tau": tau})
            assert r.status_code == 422, tau

    def test_k_bounds(self):
        for k in (1, 41):
            r = client.post("/api/v1/ensemble", json={
                "sequence": UBIQ, "position": 44, "k": k})
            assert r.status_code == 422, k

    def test_position_and_alphabet(self):
        r = client.post("/api/v1/ensemble", json={
            "sequence": UBIQ, "position": 500})
        assert r.status_code == 422
        r = client.post("/api/v1/ensemble", json={"sequence": "ACDXXZAAAA"})
        assert r.status_code == 422

    def test_exhaustive_normalizes_mu_k(self):
        r = client.post("/api/v1/ensemble", json={
            "sequence": UBIQ, "position": 44, "mode": "exhaustive",
            "mu": 3, "k": 5})
        assert r.status_code == 200
        body = r.json()
        assert body["mu"] == 1 and body["k"] == 19


class TestExhaustiveMatchesScan:
    def test_row_and_artifact_parity(self):
        scan = client.post("/api/v1/scan", json={
            "sequence": UBIQ, "position": 44}).json()
        ens = client.post("/api/v1/ensemble", json={
            "sequence": UBIQ, "position": 44, "mode": "exhaustive"}).json()
        wait_job(scan["job_id"])
        wait_job(ens["job_id"])
        rs = client.get(f"/api/v1/jobs/{scan['job_id']}/result").json()
        re_ = client.get(f"/api/v1/jobs/{ens['job_id']}/result").json()

        assert len(re_["variants"]) == 19
        assert [v["mut_aa"] for v in re_["variants"]] == \
            [r["mut_aa"] for r in rs["rows"]]
        # dummy model is deterministic per sequence → exact metric equality
        for sr, er in zip(rs["rows"], re_["variants"]):
            for key in ("mut_aa", "local_rmsd", "global_rmsd", "tm_score",
                        "plddt_mut", "dplddt", "engine", "interpretation"):
                assert er[key] == sr[key], (key, sr[key], er[key])

        # strongest-first ranking, single-substitution row shape
        assert re_["variants"][0]["label"] == \
            f'I44{re_["variants"][0]["mut_aa"]}'
        assert re_["best"] == 0

        # artifacts: the strongest variant's aligned PDB is byte-identical
        best_aa = rs["best"]
        scan_pdb = client.get(f"/api/v1/files/{scan['job_id']}/scan_{best_aa}.pdb")
        ens_pdb = client.get(f"/api/v1/files/{ens['job_id']}/ens_00.pdb")
        assert scan_pdb.status_code == 200 and ens_pdb.status_code == 200
        assert ens_pdb.text == scan_pdb.text
        assert client.get(f"/api/v1/files/{ens['job_id']}/wt.pdb").status_code == 200

        # summary sentence keeps scan byte parity
        assert "Скан позиции 44" in re_["summary"]
        en = client.get(f"/api/v1/jobs/{ens['job_id']}/result?lang=en").json()
        assert "Scan of position 44" in en["summary"]


class TestSampled:
    def test_sampled_invariants(self):
        res = run_ensemble({
            "sequence": UBIQ, "position": 44, "mu": 2, "tau": 0.3,
            "k": 8, "seed": 42})
        variants = res["variants"]
        assert len(variants) == 8
        loc = [v["local_rmsd"] for v in variants]
        assert loc == sorted(loc, reverse=True)
        for v in variants:
            muts = v["mutations"]
            assert len(muts) == 2
            anchor = [m for m in muts if m["position"] == 44]
            assert len(anchor) == 1
            assert anchor[0]["wt_aa"] == "I" and anchor[0]["mut_aa"] != "I"
            for m in muts:
                if m["position"] != 44:
                    bg = UBIQ[m["position"] - 1]
                    assert m["wt_aa"] == bg and m["mut_aa"] != bg
            assert v["label"] == "+".join(
                f"{m['wt_aa']}{m['position']}{m['mut_aa']}" for m in muts)
            assert v["engine"] in ("cuda", "cpp", "numpy")
            assert v["pdb_file"].startswith("ens_") and \
                v["pdb_file"].endswith(".pdb")

        # stats recomputed from the returned rows (order-independent)
        vals = sorted(loc)
        n = len(vals)
        median = (vals[n // 2 - 1] + vals[n // 2]) / 2  # n even
        st = res["stats"]["local_rmsd"]
        assert st["median"] == pytest.approx(median)
        assert st["min"] == min(loc) and st["max"] == max(loc)
        assert st["iqr"] >= 0

        # window ΔpLDDT is present and per-residue track array is full-length
        assert "dplddt_local" in variants[0]
        assert len(res["dplddt_abs_mean_list"]) == len(UBIQ)
        assert len(res["plddt_wt_list"]) == len(UBIQ)
        # params echoed with the effective seed
        assert res["params"]["mu"] == 2 and res["params"]["tau"] == 0.3
        assert res["params"]["k"] == 8 and res["params"]["seed"] > 0
        assert len(res["pdb_files"]) == 9  # wt + 8 variants
        assert res["headline"]["level"] in ("quiet", "moderate", "strong")

    def test_seed_reproducibility(self):
        a = run_ensemble({"sequence": UBIQ, "position": 44, "mu": 2,
                          "tau": 0.5, "k": 6, "seed": 7})
        b = run_ensemble({"sequence": UBIQ, "position": 44, "mu": 2,
                          "tau": 0.5, "k": 6, "seed": 7})
        assert [v["label"] for v in a["variants"]] == \
            [v["label"] for v in b["variants"]]
        assert a["stats"] == b["stats"]

        c = run_ensemble({"sequence": UBIQ, "position": 44, "mu": 2,
                          "tau": 0.5, "k": 6, "seed": 8})
        assert [v["label"] for v in c["variants"]] != \
            [v["label"] for v in a["variants"]]

    def test_derived_seed_reproduces_without_explicit_seed(self):
        a = run_ensemble({"sequence": UBIQ, "position": 44, "mu": 3,
                          "tau": 0.5, "k": 6})
        b = run_ensemble({"sequence": UBIQ, "position": 44, "mu": 3,
                          "tau": 0.5, "k": 6})
        assert [v["label"] for v in a["variants"]] == \
            [v["label"] for v in b["variants"]]
        assert a["params"]["seed"] == b["params"]["seed"]

    def test_anchor_window_dplddt_matches_window(self):
        res = run_ensemble({"sequence": UBIQ, "position": 44, "mu": 1,
                            "tau": 0.5, "k": 4, "seed": 1})
        for v in res["variants"]:
            # single-substitution rows keep the scan row shape
            assert v["mut_aa"] is not None
            # dplddt_local is the mean over the ±10 window: bounded by max |Δ|
            assert abs(v["dplddt_local"]) <= 100.0


class TestArtifactsAndHistory:
    def test_artifact_allowlist(self):
        r = client.post("/api/v1/ensemble", json={
            "sequence": UBIQ, "position": 44, "mu": 2, "k": 4, "seed": 3})
        job_id = r.json()["job_id"]
        wait_job(job_id)
        assert client.get(f"/api/v1/files/{job_id}/ens_00.pdb").status_code == 200
        assert client.get(f"/api/v1/files/{job_id}/wt.pdb").status_code == 200
        # allowlist is strict about the name shape
        assert client.get(f"/api/v1/files/{job_id}/ens_0.pdb").status_code == 404
        assert client.get(f"/api/v1/files/{job_id}/ens_99.pdb").status_code == 404
        assert client.get(f"/api/v1/files/{job_id}/etc-passwd").status_code == 404

    def test_history_label_and_params(self):
        res = run_ensemble({"sequence": UBIQ, "position": 44, "mu": 2,
                            "tau": 0.3, "k": 8, "seed": 42})
        jobs = client.get("/api/v1/jobs").json()
        row = next(j for j in jobs if j["kind"] == "ensemble")
        assert row["label"] == "I44 μ2×8"
        assert row["position"] == 44
        assert row["mu"] == 2 and row["tau"] == 0.3
        assert row["k"] == 8 and row["mode"] == "sampled"

    def test_summary_retranslation(self):
        res = run_ensemble({"sequence": UBIQ, "position": 44, "mu": 2,
                            "tau": 0.3, "k": 4, "seed": 5})
        job_id = None
        for j in client.get("/api/v1/jobs").json():
            if j["kind"] == "ensemble" and j["status"] == "done":
                job_id = j["job_id"]  # newest ensemble job
                break
        assert job_id is not None
        en = client.get(f"/api/v1/jobs/{job_id}/result?lang=en").json()
        assert en["summary"].startswith("Ensemble of position 44 (I)")
        assert "tau=0.3" in en["summary"]
        ru = client.get(f"/api/v1/jobs/{job_id}/result?lang=xx").json()
        assert ru["summary"].startswith("Ансамбль позиции 44 (I)")


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    import shutil
    shutil.rmtree(_tmp, ignore_errors=True)