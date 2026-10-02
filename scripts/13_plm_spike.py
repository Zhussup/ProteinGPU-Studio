#!/usr/bin/env python
"""Stage 13 PLM spike: gate the direct OmegaPLM call BEFORE any API work.

Folds nothing — one weight-tied PLM pass (wild-type margin protocol,
Meier et al. 2021 / ESM-1v style) on real weights. Gates:
  * the vendored forward signature (tokens [*, L], mask [*, L], fwd_cfg);
  * fp32 numerics (finite log-probs) under every profile;
  * VRAM budget (< 4000 MB peak at L=250 and L=600 on a 6 GB card) — the
    PLM is one MSA row instead of 16 and no geoformer, must be cheap.
Writes data/report/plm_spike.json (a committed, REAL-measurement artifact:
dummy numbers here are forbidden, same rule as all benchmark scripts).

Спайк-гейт перед построением API: один weight-tying проход OmegaPLM.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# как 01/10: профили с реальными весами; dummy в spike запрещён | 与 01/10 相同：
# 仅真实权重；spike 禁止 dummy
sys.path.insert(0, str(REPO / "backend"))

REPORT = REPO / "data" / "report"

LYSOZYME = "".join(
    "KVFGRCELAAAMKRHGLDNYRGYSLGNWVCAAKFESNFNTQATNRNTDGSTDYGILQINSRWWCNDGTP"
    "GAVNACHLSCSALLQDNIADAVACAKRVVRDPQGIRAWVAWRNRCQNRDVRQYVQGCGV")


def _synthetic(length: int, seed: int = 13) -> str:
    """Deterministic pseudo-random mix (a realistic-ish length probe)."""
    import hashlib
    rng = np.random.default_rng(int(hashlib.sha256(f"spike:{seed}".encode()).hexdigest()[:12], 16))
    aa = np.array(list("ACDEFGHIKLMNPQRSTVWY"))
    return "".join(rng.choice(aa, size=length))


def run_length(svc, seq: str, budget_mb: float) -> dict:
    import torch
    from ml.folding.plm_scoring import get_plm_scorer

    scorer = get_plm_scorer(svc.model)
    if scorer.name == "dummy-plm":
        raise RuntimeError("spike requires the real OmegaPLM (weights + CUDA/cpu), "
                           "got the dummy scorer — check profile and OMEGAFOLD_WEIGHTS")

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        peak0 = torch.cuda.max_memory_allocated() / 1024**2
    else:
        peak0 = 0.0
    t0 = time.perf_counter()
    result = scorer.score(seq)
    wall = time.perf_counter() - t0
    if torch.cuda.is_available():
        peak = torch.cuda.max_memory_allocated() / 1024**2 - peak0
    else:
        peak = 0.0

    finite = bool(np.isfinite(result.logprobs).all()
                  and np.isfinite(result.margins).all())
    # хрупкость: damage = -margin; худшая замена позиции = argmin margin
    damage = -result.margins.max(axis=1)
    top3 = np.argsort(damage)[-3:][::-1]
    wt_aa = list(result.seq)
    top_fragile = []
    for p in top3:
        row = result.margins[int(p)]
        worst = int(np.argmin(row))
        top_fragile.append({
            "pos": int(p) + 1, "wt": wt_aa[int(p)],
            "alt": "ACDEFGHIKLMNPQRSTVWY"[worst],
            "margin": round(float(row[worst]), 4),
            "max_damage": round(float(damage[int(p)]), 4),
        })

    ok = finite and peak < budget_mb
    return {
        "length": len(seq), "scorer": result.scorer, "device": result.device,
        "wall_s": round(wall, 3), "elapsed_s": round(result.elapsed_s, 3),
        "vram_peak_mb": round(peak, 1),
        "logprobs_shape": list(result.logprobs.shape),
        "finite": finite,
        "probs_sum_max_err": float(np.abs(np.exp(result.logprobs).sum(axis=1) - 1).max()),
        "plddt_margin_wt_zero_err": float(np.abs(
            result.margins[np.arange(len(seq)),
                           ["ACDEFGHIKLMNPQRSTVWY".index(a) for a in seq]]).max()),
        "top_fragile": top_fragile,
        "ok": ok,
    }


def main() -> int:
    import argparse
    from backend.app.services.folding_service import get_folding_service
    from ml.folding.omegafold_model import weights_path

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", default="fp32-gpu",
                    choices=["fp32-gpu", "fp16-gpu", "cpu"])
    ap.add_argument("--budget-mb", type=float, default=4000.0)
    ap.add_argument("--lengths", default="130,250,600")
    args = ap.parse_args()

    wp = weights_path()
    if not wp.exists():
        print(f"ERROR: OmegaFold weights not found at {wp}\n"
              f"       set OMEGAFOLD_WEIGHTS=<path to release1.pt> "
              f"(repo copy: data/models/omegafold/release1.pt)", file=sys.stderr)
        return 2
    print(f"weights: {wp} ({wp.stat().st_size / 1e9:.2f} GB)")

    from backend.app.config import get_settings
    get_settings.cache_clear()
    import os
    os.environ["PGS_FOLDING_PROFILE"] = args.profile
    get_settings().folding_profile = args.profile
    svc = get_folding_service()
    svc.set_profile(args.profile)  # форсируем профиль на этом процессе

    lens = [int(x) for x in args.lengths.split(",") if x.strip()]
    seqs = []
    for n in lens:
        if n == len(LYSOZYME):
            seqs.append(LYSOZYME)
        else:
            seqs.append(_synthetic(n)[:n])

    rows = []
    ok_all = True
    for seq in seqs:
        print(f"--- PLM pass, L={len(seq)} (profile {svc.profile}) ---")
        row = run_length(svc, seq, args.budget_mb)
        rows.append(row)
        ok_all = ok_all and row["ok"]
        print(f"wall={row['wall_s']}s  peak VRAM={row['vram_peak_mb']} MB  "
              f"finite={row['finite']}")
        print(f"probs sum err (max) = {row['probs_sum_max_err']:.2e}; "
              f"margin(wt)==0 err = {row['plddt_margin_wt_zero_err']:.1e}")
        for f in row["top_fragile"]:
            print(f"  top damage: {f['wt']}{f['pos']}{f['alt']}  "
                  f"margin {f['margin']:+.2f}")
        if not row["ok"]:
            print("GATE FAIL: spike exceeded budget or produced non-finite scores")
    svc.close()

    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "plm_spike.json").write_text(json.dumps({
        "description": "OmegaPLM weight-tied logits spike (13_plm_spike.py)",
        "profile": args.profile, "budget_mb": args.budget_mb, "rows": rows,
    }, ensure_ascii=False, indent=2))
    print("written: data/report/plm_spike.json")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())