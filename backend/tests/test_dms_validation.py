"""Tests for /validate/* (DMS validation against a curated ProteinGym assay).

The synthetic assay is the fixed-point of the protocol: fitness is the dummy
PLM margin plus seeded noise, so the headline zero-shot correlation is
EXPECTED to be high — this verifies the plumbing (mapping, hygiene counters,
dedup, z-score, fold plan, correlations, artifacts), not model quality.
Real-model numbers come from the GPU run, never from here (dummy rule).
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
_tmp = Path(__file__).parent / "_testdata_dms"
_tmp.mkdir(exist_ok=True)
# env ставится В ФИКСТУРЕ (ниже), не при импорте: pytest импортирует ВСЕ
# тестовые модули до запуска, а поздний импорт test_plm_screen перезаписал бы
# PGS_DATA_DIR своим tempdir — тогда curated.json «не найден» (409).
# 配置在 fixture 中设置：pytest 先收集全部模块，后导入者的 env 会覆盖。
from fastapi.testclient import TestClient  # noqa: E402

import backend.app.services.job_manager as jm_mod  # noqa: E402
import backend.app.services.folding_service as fs_mod  # noqa: E402

from backend.app.config import get_settings  # noqa: E402

from backend.app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _own_env():
    """Fresh data dir + singletons per module run-time (не при сборе)."""
    os.environ["PGS_DATA_DIR"] = str(_tmp)
    os.environ["PGS_DB_PATH"] = str(_tmp / "jobs.sqlite3")
    get_settings.cache_clear()
    if jm_mod._manager is not None:
        jm_mod._manager = None
    if fs_mod._service is not None:
        fs_mod._service = None
    yield
    get_settings.cache_clear()

from ml.folding.plm_scoring import DummyPlmScorer  # noqa: E402

# синтетический assay: 40 aa таргет = хвост UBIQ, 6 позиций по 5 альтов
TARGET = "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPD"
SEQ = TARGET          # посылаем таргет как есть — map = exact-substring
ASSAY_ID = "TESTASSAY_Example_2023_1ABC"
POS0S = [1, 6, 12, 19, 27, 34]
N_ALTS = 5
NOISE_SD = 0.02


def _build_assay_dir() -> None:
    """Write curated.json + the synthetic CSV into the fresh data dir.

    Fitness = margin(dummy scorer, the SAME scorer the job will recompute)
    + seeded noise → the headline plm_all ρ is a fixture of the plumbing.
    """
    import numpy as np
    margin = DummyPlmScorer().score(SEQ).margins
    rng = np.random.default_rng(42)

    dms_dir = _tmp / "dms"
    (dms_dir / "assays").mkdir(parents=True, exist_ok=True)
    rows = []

    def mut_seq_for(pos: int, alt: str) -> str:
        return SEQ[:pos - 1] + alt + SEQ[pos:]

    singles = []
    for pos0 in POS0S:
        pos = pos0 + 1
        wt = SEQ[pos0]
        alts = [a for a in "ACDEFGHIKLMNPQRSTVWY" if a not in (wt,)]  # первые 5
        for alt in alts[:N_ALTS]:
            singles.append((pos, wt, alt,
                            float(margin[pos0, "ACDEFGHIKLMNPQRSTVWY".index(alt)])
                            + float(rng.normal(0.0, NOISE_SD))))

    # дубликат первой строки с чуть другим фитнесом → (pos,alt) merge
    dup = singles[0]
    singles.append((dup[0], dup[1], dup[2],
                    dup[3] + float(rng.normal(0.0, NOISE_SD))))

    for pos, wt, alt, fit in singles:
        rows.append({
            "mutant": f"{wt}{pos}{alt}",
            "mutated_sequence": mut_seq_for(pos, alt),
            "DMS_score": f"{fit:.6f}",
            "DMS_score_bin": "0.0",
        })
    # многострочные (2), непарсабельная (1), вне диапазона (1),
    # несоответствие буквы WT по mutated_sequence (1), пустой фитнес (1)
    rows += [
        {"mutant": "E3N:T3P", "mutated_sequence": SEQ, "DMS_score": "1.0",
         "DMS_score_bin": "1.0"},
        {"mutant": "E3N:P4V", "mutated_sequence": SEQ, "DMS_score": "0.5",
         "DMS_score_bin": "1.0"},
        {"mutant": "Q", "mutated_sequence": SEQ, "DMS_score": "0.3",
         "DMS_score_bin": "0.0"},
        {"mutant": "A45P", "mutated_sequence": SEQ, "DMS_score": "0.2",
         "DMS_score_bin": "0.0"},
        {"mutant": "T3P", "mutated_sequence": "A" * len(SEQ), "DMS_score": "0.1",
         "DMS_score_bin": "0.0"},
        {"mutant": "M1P", "mutated_sequence": mut_seq_for(1, "P"),
         "DMS_score": "", "DMS_score_bin": "0.0"},
    ]
    fpath = dms_dir / "assays" / f"{ASSAY_ID}.csv"
    with fpath.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["mutant", "mutated_sequence",
                                           "DMS_score", "DMS_score_bin"])
        w.writeheader()
        w.writerows(rows)

    manifest = {
        "rule": "test fixture (synthetic assay)",
        "giant_excluded": [],
        "swept": 1,
        "assays": [{
            "dms_id": ASSAY_ID,
            "file": f"data/dms/assays/{ASSAY_ID}.csv",
            "consensus_seq": TARGET,
            "rows": len(rows),
            "singles": len(singles),
            "multi": 2, "bad_rows": 1,
            "out_of_range": 1, "wt_letter_mismatches": 1,
            "positions_swept": len(POS0S),
            "positions_with_full_19": 0,
            "duplicate_pair_keys": 1,
        }],
    }
    (dms_dir / "curated.json").write_text(json.dumps(manifest))


_build_assay_dir()

# 37 строк, синглов с учётом дубликата 31, после merge — 30 уникальных
N_ROWS_CSV = 37
N_UNIQUE = 30


def wait_job(job_id: str, timeout: float = 120) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/v1/jobs/{job_id}").json()
        if s["status"] in ("done", "error"):
            return s
        time.sleep(0.05)
    pytest.fail(f"job {job_id} timed out")


class TestDmsAssayList:
    def test_assays_list(self):
        r = client.get("/api/v1/validate/assays")
        assert r.status_code == 200
        assays = r.json()["assays"]
        mine = [a for a in assays if a["dms_id"] == ASSAY_ID]
        assert mine and mine[0]["ok"] is True
        assert mine[0]["seq_len"] == len(TARGET)
        assert mine[0]["singles"] == 31  # 30 + дубликат

    def test_unknown_assay_404(self):
        r = client.post("/api/v1/validate/dms",
                        json={"sequence": SEQ, "assay_id": "NO_SUCH_ASSAY"})
        assert r.status_code == 404


class TestDmsValidationRun:
    def _submit(self, **params):
        body = {"sequence": SEQ, "assay_id": ASSAY_ID}
        body.update(params)
        r = client.post("/api/v1/validate/dms", json=body)
        assert r.status_code == 200, r.text
        return r.json()

    def test_full_protocol_correlations(self):
        body = self._submit(sample_n=10, fold_positions_max=5)
        assert body["length"] == len(SEQ)
        assert body["assay_id"] == ASSAY_ID
        s = wait_job(body["job_id"])
        assert s["status"] == "done", s.get("error")

        res = client.get(f"/api/v1/jobs/{body['job_id']}/result").json()
        assert res["kind"] == "dms_validation"
        assert res["plm_scorer"] == "dummy-plm"
        assert res["mapping"] == "exact-substring"
        assert res["n_rows"] == N_UNIQUE

        # счётчики гигиены сходятся до строки | счётчики сходятся до строки
        c = res["counts"]
        assert c["rows_total"] == N_ROWS_CSV
        assert c["rows_multi"] == 2
        assert c["rows_unparseable"] == 1
        assert c["rows_out_of_range"] == 1
        assert c["rows_wt_mismatch"] == 1
        assert c["rows_badseq"] == 0
        assert c["rows_no_score"] == 1
        assert c["rows_in_range"] == 31
        assert c["rows_unmapped"] == 0
        assert c["rows_wt_mismatch_local"] == 0
        assert c["rows_dup_merged"] == 1

        # фикстура: fitness = dummy margin + шум → headline ρ почти 1
        corr = {cr["name"]: cr for cr in res["correlations"]}
        assert list(corr) == ["plm_all", "plddt_fold", "rmsd_fold",
                              "pos_plm", "pos_struct_plm", "margin_rmsd"]
        assert corr["plm_all"]["spearman"] >= 0.95
        assert corr["plm_all"]["expected_sign"] == "+"
        assert corr["plm_all"]["n"] == N_UNIQUE
        assert corr["plm_all"]["ci"] is not None
        lo, hi = corr["plm_all"]["ci"]
        # CI — это перцентили БУТСРЭП-выборки; при ρ≈1 точечная оценка может
        # сидеть на их краю, поэтому строгость не гарантируем
        assert -1.0 <= lo <= hi <= 1.0
        # per-position: v_med (damage) против среднего fitness — анти-спелл
        assert corr["pos_plm"]["spearman"] is not None
        assert corr["pos_plm"]["spearman"] < -0.8
        assert corr["pos_plm"]["expected_sign"] == "-"
        # структурные и согласие: вычислимы, знак по физике в ответе
        assert corr["plddt_fold"]["n"] >= 5
        for name, sign in (("rmsd_fold", "-"), ("pos_struct_plm", "+"),
                           ("margin_rmsd", "-")):
            assert corr[name]["expected_sign"] == sign
            rho = corr[name]["spearman"]
            assert rho is None or -1.0 <= rho <= 1.0

        # per-position полоса: pos, pctl, эксперимент
        pp = res["per_position"]
        assert [p["pos"] for p in pp] == [p0 + 1 for p0 in POS0S]
        for p in pp:
            assert 0.0 <= p["v_med_pctl"] <= 1.0
            assert p["n_obs"] == N_ALTS
            assert -4.0 <= p["mean_fitness_z"] <= 4.0
        assert max(p["v_med_pctl"] for p in pp) == 1.0

        # scatter'ы и артефакты
        assert len(res["scatter_plm"]) == min(800, N_UNIQUE) == N_UNIQUE
        assert res["pdb_files"] == ["wt.pdb"]
        assert res["caveats"]
        assert {"dummyProfile", "zscoreCenter"} <= \
            {cv["key"] for cv in res["caveats"]}

        fj = client.get(f"/api/v1/files/{body['job_id']}/dms_validation.json")
        assert fj.status_code == 200
        art = json.loads(fj.text)
        assert len(art["rows"]) == N_UNIQUE
        assert art["counts"]["rows_total"] == N_ROWS_CSV
        fc = client.get(f"/api/v1/files/{body['job_id']}/dms_validation.csv")
        assert fc.status_code == 200
        rows = list(csv.reader(io.StringIO(fc.text)))
        assert len(rows) == 1 + N_UNIQUE
        assert rows[0][:4] == ["pos_dms", "pos", "wt_aa", "mut_aa"]
        assert rows[0][-1] == "folded"
        n_folded = sum(1 for r in rows[1:] if r[-1] == "1")
        assert corr["plddt_fold"]["n"] == n_folded
        # нефолднутые строки — пустые структурные колонки | нет данных — пустые
        empty = [r for r in rows[1:] if r[-1] == "0"]
        if empty:
            assert all(r[8] == "" for r in empty)
        wp = client.get(f"/api/v1/files/{body['job_id']}/wt.pdb")
        assert wp.status_code == 200

    def test_fold_plan_no_fitness_leak(self):
        """Top-1 per position chosen by LOWEST margin — not by fitness.

        The PLM-fragile cap must pick the worst-margin variant of each
        position, even when its measured fitness says something else.
        """
        body = self._submit(sample_n=0, fold_positions_max=3)
        s = wait_job(body["job_id"])
        assert s["status"] == "done", s.get("error")
        res = client.get(f"/api/v1/jobs/{body['job_id']}/result").json()
        folded = [r for r in client.get(
            f"/api/v1/files/{body['job_id']}/dms_validation.json"
        ).json()["rows"] if r["folded"]]
        # 3 позиции × топ-1 (без strat — sample_n=0) ровно
        assert len(folded) == 3
        # для каждой сфолднутой позиции это должен быть минимум margin среди
        # её уникальных вариантов в артефакте
        by_pos = {}
        for r in json.loads(client.get(
                f"/api/v1/files/{body['job_id']}/dms_validation.json"
        ).text)["rows"]:
            by_pos.setdefault(r["pos"], []).append(r["plm_margin"])
        for r in folded:
            assert r["plm_margin"] == min(by_pos[r["pos"]])

    def test_fast_mode_plm_only(self):
        """fold_positions_max=0 AND sample_n=0 → без фолдов, WT не пишем."""
        body = self._submit(sample_n=0, fold_positions_max=0)
        s = wait_job(body["job_id"])
        assert s["status"] == "done", s.get("error")
        res = client.get(f"/api/v1/jobs/{body['job_id']}/result").json()
        corr = {cr["name"]: cr for cr in res["correlations"]}
        assert corr["plm_all"]["spearman"] >= 0.95          # заголовок живёт
        assert corr["plddt_fold"]["spearman"] is None       # не фолдили
        assert corr["plddt_fold"]["n"] == 0
        assert res["pdb_files"] == []
        assert res["scatter_struct"] == []
        keys = {cv["key"] for cv in res["caveats"]}
        assert "foldSubset" in keys and "dummyProfile" in keys

    def test_history_label_and_retranslate(self):
        body = self._submit(sample_n=0)
        job_id = body["job_id"]
        wait_job(job_id)
        jobs = client.get("/api/v1/jobs").json()
        label = next(j["label"] for j in jobs if j["job_id"] == job_id)
        assert label == f"DMS {ASSAY_ID[:24]}"  # метка capped 24 символами
        ru = client.get(f"/api/v1/jobs/{job_id}/result").json()["summary"]
        en = client.get(f"/api/v1/jobs/{job_id}/result?lang=en").json()["summary"]
        assert ru.startswith("DMS-валидация")
        assert en.startswith("DMS validation")
        assert ru != en

    def test_short_sequence_422(self):
        r = client.post("/api/v1/validate/dms",
                        json={"sequence": SEQ[:15], "assay_id": ASSAY_ID})
        assert r.status_code == 422

    def test_homologous_sequence_maps_pairwise(self):
        """A ~97%-identical homolog still validates — mapping = pairwise; the
        position whose WT letter disagrees with our seq drops with a counter."""
        hom = SEQ[:1] + "P" + SEQ[2:]  # pos0=1 ('Q') — С живыми строками
        r = client.post("/api/v1/validate/dms",
                        json={"sequence": hom, "assay_id": ASSAY_ID,
                              "sample_n": 0})
        body = r.json()
        assert r.status_code == 200
        s = wait_job(body["job_id"])
        assert s["status"] == "done", s.get("error")
        res = client.get(f"/api/v1/jobs/{body['job_id']}/result").json()
        assert res["mapping"] == "pairwise"
        # позиция (dms pos 2) отныне не совпадает буквой WT: её 5 строк + 1
        # дубликат падают в счётчик, остальные 25 живут
        assert res["n_rows"] == 25
        assert res["counts"]["rows_wt_mismatch_local"] == 6