#!/usr/bin/env python
"""35_batch_validation.py — дипломные прогоны DMS-валидации по кюрируемому набору.

Для каждого assay из data/dms/curated.json (ok=true) прогоняет полный протокол
dms_validation (роутер backend/app/routers/validation.py):
  dms_load → dms_map → dms_plm → dms_folds → dms_stats,
и складывает result-словари в data/report/validation/{DMS_id}.json — вход
для scripts/36_thesis_figures.py и таблиц записки.

Два режима:
  по умолчанию — через FastAPI бэкенда (--api-url, порт 8077 как в дежурной
      документации): полный путь с очередью задач; несколько экземпляров
      скрипта шардируются между GPU вручную (--only/--skip).
  --offline — прямые вызовы того же кода (_run_dms_validation) в одном
      процессе без HTTP: реальный рантайм, реальная модель, артефакты и
      wt.pdb пишутся в data/jobs/<job_id>/.

Честность цифр диплома:
  dummy-модель (PGS_FOLDING_PROFILE=dummy) и профиль dummy скрипт отказывается
  использовать без --allow-dummy — det-фейк не попадает в записку.

Usage:
    .venv/bin/python scripts/35_batch_validation.py                 # по умолчанию, все ok-assays
    .venv/bin/python scripts/35_batch_validation.py --offline
    .venv/bin/python scripts/35_batch_validation.py --only VG08_BPP22_Tsuboyama_2023_2GP8
    .venv/bin/python scripts/35_batch_validation.py --skip 1        # каждый 2-й — шард на второй GPU
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DEST = REPO / "data" / "report" / "validation"
CURATED = REPO / "data" / "dms" / "curated.json"


def _consensus_of(assays: list[dict], dms_id: str) -> str | None:
    for a in assays:
        if a["dms_id"] == dms_id:
            return a["consensus_seq"]
    return None


def _load_curated(assay_id: str | None) -> tuple[list[str], dict[str, str]]:
    """(assay ids in curated.json, dms_id -> consensus_seq)."""
    data = json.loads(CURATED.read_text(encoding="utf-8"))
    pairs = [(a["dms_id"], a["consensus_seq"]) for a in data["assays"]]
    if assay_id:
        pairs = [(i, s) for i, s in pairs if i == assay_id]
        if not pairs:
            raise SystemExit(f"assay {assay_id!r} not in {CURATED}")
    return [i for i, _ in pairs], dict(pairs)


def run_via_api(url: str, args) -> int:
    import httpx

    ids, consensus = _load_curated(args.assay)
    keep = ids[args.skip::args.every]
    if args.assay:
        keep = ids
    base = url.rstrip("/")

    client = httpx.Client(timeout=120)
    try:
        inv = client.get(f"{base}/api/v1/validate/assays").json()["assays"]
    except Exception as e:
        raise SystemExit(f"бэкенд недоступен на {base}: {e} (запустите uvicorn)")
    ok_ids = {a["dms_id"] for a in inv if a["ok"]}
    missing = [i for i in keep if i not in ok_ids]
    if missing:
        raise SystemExit("CSV на диске не найден: " + ", ".join(missing))

    if args.profile == "dummy" and not args.allow_dummy:
        raise SystemExit("профиль dummy без --allow-dummy запрещён (цифры диплома)")

    rc = 0
    for dms_id in keep:
        dest = DEST / f"{dms_id}.json"
        if dest.exists() and not args.force:
            print(f"[skip] {dest.name} уже есть (--force перезапишет)")
            continue
        seq = consensus[dms_id]
        payload = {"sequence": seq, "assay_id": dms_id, "sample_n": args.sample_n,
                   "fold_positions_max": args.fold_positions_max, "seed": args.seed,
                   "profile": args.profile}
        t0 = time.perf_counter()
        r = client.post(f"{base}/api/v1/validate/dms?lang=ru", json=payload)
        if r.status_code != 200:
            print(f"[fail] {dms_id}: POST {r.status_code}: {r.text[:300]}")
            rc = 1
            continue
        job_id = r.json()["job_id"]
        for _ in range(24 * 3600):
            s = client.get(f"{base}/api/v1/jobs/{job_id}").json()
            if s["status"] in ("done", "error"):
                break
            print(f"\r  {dms_id}: {s['progress'] * 100:5.1f}% {s.get('message') or ''}",
                  end="", flush=True)
            time.sleep(2)
        print()
        if s["status"] == "error":
            print(f"[fail] {dms_id}: {s.get('error')}")
            rc = 1
            continue
        result = client.get(f"{base}/api/v1/jobs/{job_id}/result").json()
        if result.get("plm_scorer") == "dummy-plm" and not args.allow_dummy:
            print(f"[fail] {dms_id}: бэкенд отдал dummy-plm скорер — цифры не для записки")
            rc = 1
            continue
        result["_meta"] = {"via": "api", "wall_s": round(time.perf_counter() - t0, 1),
                           "profile": args.profile, "job_id": job_id}
        DEST.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        plm = next((c for c in result["correlations"] if c["name"] == "plm_all"), {})
        print(f"[ok] {dms_id}: n={result['n_rows']} ρ(plm_all)="
              f"{plm.get('spearman')}  → {dest}")
    return rc


def run_offline(args) -> int:
    os.environ.setdefault("PGS_DATA_DIR", str(REPO / "data"))
    sys.path.insert(0, str(REPO))

    from backend.app.routers.validation import _run_dms_validation
    from backend.app.services.folding_service import get_folding_service
    from backend.app.services.job_manager import Job, get_job_manager

    svc = get_folding_service()
    name = svc.model_name.lower()
    if "dummy" in name and not args.allow_dummy:
        raise SystemExit(f"модель {svc.model_name} — dummy дет-фейк без --allow-dummy запрещён")
    if "omegafold" not in name and not args.allow_dummy:
        print(f"[warn] модель {svc.model_name} — не omegafold; проверьте честность")

    jm = get_job_manager()
    ids, consensus = _load_curated(args.assay)
    keep = ids[args.skip::args.every]
    if args.assay:
        keep = ids
    rc = 0
    for dms_id in keep:
        dest = DEST / f"{dms_id}.json"
        if dest.exists() and not args.force:
            print(f"[skip] {dest.name} уже есть (--force перезапишет)")
            continue
        job = Job(job_id=f"offline_dms_{dms_id[:16].lower()}_{int(time.time()) % 100000}",
                  kind="dms_validation",
                  params={"sequence": consensus[dms_id], "assay_id": dms_id,
                          "sample_n": args.sample_n,
                          "fold_positions_max": args.fold_positions_max,
                          "seed": args.seed, "profile": args.profile,
                          "lang": "ru"})
        job.status = "running"
        t0 = time.perf_counter()
        try:
            # один CUDA-стрим — та же дисциплина, что у бэкенд-воркера
            with jm.gpu_sem:
                result = _run_dms_validation(job)
        except Exception as e:
            print(f"[fail] {dms_id}: {type(e).__name__}: {e}")
            rc = 1
            continue
        result["_meta"] = {"via": "offline", "wall_s": round(time.perf_counter() - t0, 1),
                           "profile": args.profile, "job_id": job.job_id}
        DEST.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        plm = next((c for c in result["correlations"] if c["name"] == "plm_all"), {})
        print(f"[ok] {dms_id}: n={result['n_rows']} ρ(plm_all)={plm.get('spearman')} "
              f"({result['_meta']['wall_s']} с) → {dest}")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api-url", default="http://127.0.0.1:8077",
                    help="базовый URL бэкенда (режим по умолчанию)")
    ap.add_argument("--offline", action="store_true",
                    help="без HTTP: прямой вызов _run_dms_validation в этом процессе")
    ap.add_argument("--assay", help="единственный DMS_id (иначе весь кюрируемый набор)")
    ap.add_argument("--only", help="синоним --assay; вместе с --skip/--every — шардирование")
    ap.add_argument("--skip", type=int, default=0, help="offset для шардирования")
    ap.add_argument("--every", type=int, default=1, help="шаг для шардирования (2 = каждый второй)")
    ap.add_argument("--sample-n", type=int, default=48)
    ap.add_argument("--fold-positions-max", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--profile", default="fp16-gpu",
                    help="профиль дипломных прогонов (fp16-gpu по умолчанию)")
    ap.add_argument("--force", action="store_true", help="перезаписать существующие JSON")
    ap.add_argument("--allow-dummy", action="store_true",
                    help="разрешить dummy-модель/профиль (только отладка, НЕ для записки)")
    args = ap.parse_args()
    if args.only:
        args.assay = args.only

    if not CURATED.exists():
        raise SystemExit(f"{CURATED} нет — запустите scripts/30_download_proteingym.py "
                         f"и scripts/34_curate_proteingym.py")
    if args.offline:
        # db_path в temp: офлайн-джобы не засоряют историю пользователя
        os.environ.setdefault("PGS_DB_PATH",
                              os.path.join(tempfile.mkdtemp(prefix="pgs_offline_"), "jobs.db"))
        return run_offline(args)
    return run_via_api(args.api_url, args)


if __name__ == "__main__":
    sys.exit(main())