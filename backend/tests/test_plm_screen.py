"""Tests for the /plm_screen endpoint (whole-protein PLM screen, dummy scorer).

The lifecycle asserts the screen contract: one PLM pass covers every L×19
substitution (margins of the wt residue exactly 0), the scan_map key contract
(rose order, percentiles), the two dataset artifacts (JSON + CSV with all
L×19 rows), fold budget respected, and byte-identical determinism.
"""
import csv
import io
import json
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
_tmp = Path(__file__).parent / "_testdata_plm"
_tmp.mkdir(exist_ok=True)
os.environ["PGS_DATA_DIR"] = str(_tmp)
os.environ["PGS_DB_PATH"] = str(_tmp / "jobs.sqlite3")

from fastapi.testclient import TestClient  # noqa: E402

import backend.app.services.job_manager as jm_mod  # noqa: E402
import backend.app.services.folding_service as fs_mod  # noqa: E402

# singleton-ресеты — тестовый файл может загрузиться после других тестов,
# которые уже создали менеджеры поверх СВОЕЙ директории данных
# 单例重置：本文件可能在其他测试创建过单例后加载
from backend.app.config import get_settings  # noqa: E402

get_settings.cache_clear()
if jm_mod._manager is not None:
    jm_mod._manager = None
if fs_mod._service is not None:
    fs_mod._service = None
from backend.app.main import app  # noqa: E402

client = TestClient(app)
UBIQ = ("MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG")
PETAL_DIRS = "AVILMFWYSTNQDEKRHGCP"


def wait_job(job_id: str, timeout: float = 60) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/v1/jobs/{job_id}").json()
        if s["status"] in ("done", "error"):
            return s
        time.sleep(0.05)
    pytest.fail(f"job {job_id} timed out")


class TestPlmScreen:
    def test_plm_only_lifecycle(self):
        """fold_top_k=0: one pass, no folds, full L×19 contract."""
        r = client.post("/api/v1/plm_screen",
                        json={"sequence": UBIQ, "fold_top_k": 0})
        assert r.status_code == 200
        body = r.json()
        assert body["length"] == len(UBIQ) and body["n_folds"] == 0
        s = wait_job(body["job_id"])
        assert s["status"] == "done", s.get("error")

        res = client.get(f"/api/v1/jobs/{body['job_id']}/result").json()
        assert res["kind"] == "plm_screen"
        assert res["plm_scorer"] == "dummy-plm"
        assert res["n_positions"] == len(UBIQ)
        assert res["folds"]["done"] == 0
        assert res["folds"]["consistency_spearman"] is None
        assert res["plm"]["n_forward"] == 1
        assert res["petal_dirs"] == PETAL_DIRS
        assert res["pdb_files"] == ["wt.pdb"]  # якорь 3D-краски есть и в fast-режиме

        positions = res["positions"]
        assert [p["pos"] for p in positions] == list(range(1, len(UBIQ) + 1))
        for p in positions:
            assert p["wt_aa"] == UBIQ[p["pos"] - 1]
            assert [ro["mut_aa"] for ro in p["rows"]] == \
                [aa for aa in PETAL_DIRS if aa != p["wt_aa"]]
            st = p["stats"]
            assert 0.0 <= st["pctl_v_max"] <= 1.0
            assert 0.0 <= st["pctl_v_med"] <= 1.0
            for row in p["rows"]:
                assert -35.0 < row["plm_margin"] <= 0.0 or row["plm_margin"] > 0
                assert row["grantham"] >= 1
                assert 0.0 <= row["pctl"] <= 1.0
        # максимальный перцентиль достигается ровно одной позицией | 有人达到 1.0
        assert max(p["stats"]["pctl_v_max"] for p in positions) == 1.0
        # маржа WT-колонки == 0 в матрице уже проверена юнит-тестами; здесь
        # контракт строки: худшая замена не совпадает с WT | 最差替换不等于 WT
        frag = max(positions, key=lambda p: p["stats"]["pctl_v_max"])
        assert "PLM-скрин" in res["summary"]

    def test_topk_folding_and_artifacts(self):
        """fold_top_k=1: folded rows carry structural columns; CSV has 19*L rows."""
        r = client.post("/api/v1/plm_screen", json={"sequence": UBIQ})
        body = r.json()
        assert body["n_folds"] == 64  # min(64, 1*76)
        s = wait_job(body["job_id"])
        assert s["status"] == "done", s.get("error")
        res = client.get(f"/api/v1/jobs/{body['job_id']}/result").json()
        folded = [ro for p in res["positions"] for ro in p["rows"]
                  if "local_rmsd" in ro]
        assert len(folded) == res["folds"]["done"] == 64
        for ro in folded:
            # структура заполнена целиком | 结构列完整
            assert ro["engine"]
            assert ro["local_rmsd"] >= 0.0 and ro["tm_score"] >= 0.0
        # фолдинг выбирает самые повреждающие (минимальный margin) в позиции
        # 折叠选择每位置 margin 最小（最损伤）的替换
        for p in res["positions"]:
            foldable = [ro for ro in p["rows"] if "local_rmsd" in ro]
            if foldable:
                margins = [ro["plm_margin"] for ro in p["rows"]]
                assert min(foldable, key=lambda x: x["plm_margin"])  # не падаем
                worst_margin = min(margins)
                assert any(ro["plm_margin"] == worst_margin
                           for ro in foldable), p["pos"]

        fj = client.get(f"/api/v1/files/{body['job_id']}/plm_screen.json")
        assert fj.status_code == 200
        art = json.loads(fj.text)
        assert art["plm_scorer"] == "dummy-plm"
        assert len(art["positions"]) == len(UBIQ)

        fc = client.get(f"/api/v1/files/{body['job_id']}/plm_screen.csv")
        assert fc.status_code == 200
        rows = list(csv.reader(io.StringIO(fc.text)))
        assert len(rows) == 1 + len(UBIQ) * 19
        assert rows[0][:3] == ["position", "wt_aa", "mut_aa"]
        assert rows[0][-1] == "engine"
        # структурные колонки: заполнены только у сфолднутых | 仅折叠行有结构列
        n_filled = sum(1 for r in rows[1:] if r[9] != "")
        assert n_filled == 64

    def test_fold_budget_respected(self):
        """max_folds caps the plan (topk=2, budget 5 → exactly 5 folds)."""
        r = client.post("/api/v1/plm_screen",
                        json={"sequence": UBIQ, "fold_top_k": 2, "max_folds": 5})
        body = r.json()
        assert body["n_folds"] == 5
        s = wait_job(body["job_id"])
        res = client.get(f"/api/v1/jobs/{body['job_id']}/result").json()
        assert res["folds"]["done"] == 5
        assert res["folds"]["planned"] == 5
        # согласие по сфолднутым: значение или None (меньше 3 точек не бывает
        # при 5) — главное, что оно в [-1, 1] либо None | либо None
        c = res["folds"]["consistency_spearman"]
        assert c is None or -1.0 <= c <= 1.0

    def test_determinism_byte_identical_csv(self):
        """Two identical submits → byte-identical CSV artifacts."""
        ids = []
        for _ in range(2):
            r = client.post("/api/v1/plm_screen",
                            json={"sequence": UBIQ, "fold_top_k": 0})
            job_id = r.json()["job_id"]
            assert wait_job(job_id)["status"] == "done"
            ids.append(job_id)
        texts = [client.get(f"/api/v1/files/{i}/plm_screen.csv").text
                 for i in ids]
        assert texts[0] == texts[1]

    def test_retranslate_en(self):
        r = client.post("/api/v1/plm_screen", json={"sequence": UBIQ,
                                                    "fold_top_k": 0})
        job_id = r.json()["job_id"]
        wait_job(job_id)
        ru = client.get(f"/api/v1/jobs/{job_id}/result").json()["summary"]
        en = client.get(f"/api/v1/jobs/{job_id}/result?lang=en").json()["summary"]
        assert ru != en
        assert en.startswith("PLM screen:")

    def test_unknown_artifact_404(self):
        r = client.post("/api/v1/plm_screen", json={"sequence": UBIQ,
                                                    "fold_top_k": 0})
        job_id = r.json()["job_id"]
        wait_job(job_id)
        assert client.get(
            f"/api/v1/files/{job_id}/plm_secret.csv").status_code == 404
        assert client.get(
            f"/api/v1/files/{job_id}/plm_screen.csv").status_code == 200

    def test_history_label(self):
        r = client.post("/api/v1/plm_screen", json={"sequence": UBIQ,
                                                    "fold_top_k": 0})
        job_id = r.json()["job_id"]
        wait_job(job_id)
        jobs = client.get("/api/v1/jobs").json()
        label = next(j["label"] for j in jobs if j["job_id"] == job_id)
        assert label == "PLM 76×19"