"""Tests for the /scan_map sensitivity-map endpoint (dum.md §5, dummy model).

The lifecycle asserts the rose contract: 19 rows per position in fixed compass
order (WT slot skipped), per-position stats + within-protein percentiles, the
partial checkpoint, and the two dataset artifacts (JSON + CSV).
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
_tmp = Path(__file__).parent / "_testdata_map"
_tmp.mkdir(exist_ok=True)
os.environ["PGS_DATA_DIR"] = str(_tmp)
os.environ["PGS_DB_PATH"] = str(_tmp / "jobs.sqlite3")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.config import get_settings  # noqa: E402

get_settings.cache_clear()
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


class TestScanMap:
    def test_lifecycle_subset(self):
        """Two positions x 19 — the rose contract end to end."""
        r = client.post("/api/v1/scan_map",
                        json={"sequence": UBIQ, "positions": [20, 44]})
        assert r.status_code == 200
        body = r.json()
        assert body["n_positions"] == 2 and body["n_folds"] == 38
        s = wait_job(body["job_id"])
        assert s["status"] == "done", s.get("error")

        res = client.get(f"/api/v1/jobs/{body['job_id']}/result").json()
        assert res["n_folds"] == 39  # 38 мутантов + 1 WT | 38 个突变体 + 1 个 WT
        assert res["petal_dirs"] == PETAL_DIRS
        positions = res["positions"]
        assert [p["pos"] for p in positions] == [20, 44]

        by_pos = {p["pos"]: p for p in positions}
        for pos, wt_aa in ((20, "S"), (44, "I")):
            p = by_pos[pos]
            assert p["wt_aa"] == wt_aa
            rows = p["rows"]
            # порядок компаса, слот WT пропущен
            # 罗盘顺序，跳过 WT 槽位
            assert [r["mut_aa"] for r in rows] == \
                [aa for aa in PETAL_DIRS if aa != wt_aa]
            # каждая строка несёт полный набор метрик
            # 每行都带完整指标集
            for row in rows:
                assert row["engine"]
                assert row["grantham"] >= 1
                assert 0.0 <= row["pctl"] <= 1.0
            st = p["stats"]
            assert st["quadrant"] in ("hedgehog", "needle", "disk", "clover")
            assert 0.0 <= st["pctl_v_max"] <= 1.0
            assert 0.0 <= st["pctl_v_med"] <= 1.0
        # перцентили распределены по белку: у кого-то ровно 1.0
        # 百分位数覆盖整个蛋白：有人达到 1.0
        assert max(p["stats"]["pctl_v_max"] for p in positions) == 1.0
        # сводка называет перепись, модель остаётся с тегом
        # 摘要写出统计结果，模型保持带标签
        assert "Квадранты" in res["summary"]
        assert res["model"]

    def test_artifacts(self):
        r = client.post("/api/v1/scan_map",
                        json={"sequence": UBIQ, "positions": [2, 3, 4]})
        job_id = r.json()["job_id"]
        assert wait_job(job_id)["status"] == "done"
        # JSON-артефакт: хранилище, готовое для розы
        # JSON 工件：罗盘图就绪的数据存储
        fj = client.get(f"/api/v1/files/{job_id}/scan_map.json")
        assert fj.status_code == 200
        art = json.loads(fj.json() if isinstance(fj.json(), str) else fj.text)
        assert art["petal_dirs"] == PETAL_DIRS
        assert len(art["positions"]) == 3
        # CSV-артефакт: заголовок + 19*3 строк, валидный CSV
        # CSV 工件：表头 + 19*3 行，合法 CSV
        fc = client.get(f"/api/v1/files/{job_id}/scan_map.csv")
        assert fc.status_code == 200
        rows = list(csv.reader(io.StringIO(fc.text)))
        assert len(rows) == 1 + 57
        assert rows[0][:3] == ["position", "wt_aa", "mut_aa"]
        # чекпоинт существует и является валидным префиксом тех же данных
        # 检查点存在，且是同一数据的有效前缀
        fp = client.get(f"/api/v1/files/{job_id}/scan_map_partial.json")
        assert fp.status_code == 200
        partial = json.loads(fp.text)
        assert partial["done"] == 3

    def test_validation(self):
        # вне диапазона
        # 超出范围
        assert client.post("/api/v1/scan_map",
                           json={"sequence": UBIQ, "positions": [500]}).status_code == 422
        # дубликаты
        # 重复
        assert client.post("/api/v1/scan_map",
                           json={"sequence": UBIQ, "positions": [2, 2]}).status_code == 422
        # нет ключа positions → все позиции последовательности
        # 缺少 positions 键 → 序列的所有位置
        r = client.post("/api/v1/scan_map", json={"sequence": UBIQ})
        assert r.status_code == 200
        body = r.json()
        assert body["n_positions"] == len(UBIQ)
        assert wait_job(body["job_id"])["status"] == "done"

    def test_history_label(self):
        r = client.post("/api/v1/scan_map",
                        json={"sequence": UBIQ, "positions": [7]})
        job_id = r.json()["job_id"]
        wait_job(job_id)
        jobs = client.get("/api/v1/jobs").json()
        label = next(j["label"] for j in jobs if j["job_id"] == job_id)
        assert label == "map 1×19"