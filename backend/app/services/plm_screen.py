"""Whole-protein PLM screen: pure assembly of the screen result.

The router folds nothing itself: it runs one PLM pass (ml.folding.plm_scoring),
then this module turns the [L, 20] margin matrix into scan_map-shaped
position rows (PETAL_DIRS order, WT slot = missing), within-protein
percentiles, the fold plan (top-K most damaging per position) and the flat
CSV projection. Same key contract as services/sensitivity.py so the
frontend's heatmap / 3D-paint / percentile machinery works unmodified.

Скаляр V(i) здесь построен на plm_damage (=-margin), не на структурных
метриках: скрин даёт полный рейтинг без единого фолда; структурные
колонки у строк появятся только после top-K фолдинга (заполняются
роутером через fill_structural).
"""
from __future__ import annotations

import numpy as np

from .mutagenesis import grantham
from .sensitivity import PETAL_DIRS, SECTOR_OF, petal_dirs, percentile_rank

# CSV — набор датасета (ProteinGym-подобные строки; структурные колонки
# пустые, пока строка не была сфолднута).
# CSV — 数据集行（ProteinGym 形状；未折叠行结构列为空）。
PLM_CSV_HEADER = (
    "position,wt_aa,mut_aa,sector,grantham,plm_margin,plm_logprob_alt,"
    "plm_logprob_wt,plm_damage,local_rmsd,global_rmsd,tm_score,plddt_mut,"
    "dplddt,dplddt_local,abs_dplddt_local,engine"
)


def plm_row_fields(seq: str, pos: int, mut_aa: str, score) -> dict:
    """One (position, substitution) field dict straight from the margin matrix."""
    pos0 = pos - 1
    return {
        "mut_aa": mut_aa,
        "grantham": grantham(seq[pos0], mut_aa),
        "sector": SECTOR_OF[mut_aa],
        "plm_margin": round(score.margin(pos0, mut_aa), 6),
        "plm_logprob_alt": round(score.logprob(pos0, mut_aa), 6),
        "plm_logprob_wt": round(score.logprob(pos0, seq[pos0]), 6),
        "plm_damage": round(-score.margin(pos0, mut_aa), 6),
    }


def build_positions(seq: str, score) -> list[dict]:
    """scan_map-shaped positions from one PlmScoreResult.

    rows: the 19 alts of the position in compass order (WT slot stays
    empty, like scan_map); stats: plm scalars of the row's damage vector.
    """
    positions = []
    for pos in range(1, len(seq) + 1):
        wt_aa = seq[pos - 1]
        rows = [plm_row_fields(seq, pos, mut_aa, score)
                for mut_aa in petal_dirs(wt_aa)]
        damages = [r["plm_damage"] for r in rows]
        positions.append({
            "pos": pos,
            "wt_aa": wt_aa,
            "rows": rows,
            "stats": {
                "plm_v_med": float(np.median(damages)),
                "plm_v_max": max(damages),
                "plm_v_mean": float(np.mean(damages)),
                "logprob_wt": score.logprob(pos - 1, wt_aa),
            },
        })
    return positions


def normalize_plm_screen(positions: list[dict]) -> None:
    """Within-protein percentiles — the SAME key contract as
    sensitivity.normalize_protein: stats["pctl_v_max"], stats["pctl_v_med"],
    per-row "pctl", and the same ties-at-bottom percentile_rank. The pool for
    rows is plm_damage (the heat channel of this map).
    """
    if not positions:
        return
    v_maxes = [p["stats"]["plm_v_max"] for p in positions]
    v_meds = [p["stats"]["plm_v_med"] for p in positions]
    pool = [r["plm_damage"] for p in positions for r in p["rows"]]
    for p in positions:
        p["stats"]["pctl_v_max"] = percentile_rank(p["stats"]["plm_v_max"], v_maxes)
        p["stats"]["pctl_v_med"] = percentile_rank(p["stats"]["plm_v_med"], v_meds)
        for r in p["rows"]:
            r["pctl"] = percentile_rank(r["plm_damage"], pool)


def fold_order(positions: list[dict]) -> list[dict]:
    """Positions sorted by predicted fragility (plm_v_max, hottest first)."""
    return sorted(positions, key=lambda p: p["stats"]["plm_v_max"], reverse=True)


def topk_damaging(rows: list[dict], k: int) -> list[dict]:
    """The k rows with the LOWEST margin = the most damaging alts of a position."""
    assert k <= len(rows)
    return sorted(rows, key=lambda r: r["plm_damage"], reverse=True)[:k]


def fill_structural(row: dict, al, mut, wt) -> None:
    """Write the structural response of one folded mutant into its rows entry.

    `al` is an align_service.AlignOutput (global/local RMSD, TM, engine);
    the local ΔpLDDT window mean mirrors _run_scan_map exactly.
    """
    a, b = al.local_window  # 1-based, inclusive
    dplddt_local = float(sum(
        mut.plddt[j] - wt.plddt[j] for j in range(a - 1, b)) / (b - a + 1))
    row.update({
        "local_rmsd": al.local_rmsd, "global_rmsd": al.global_rmsd,
        "tm_score": al.tm_score, "plddt_mut": mut.plddt_mean,
        "dplddt": float(mut.plddt_mean - wt.plddt_mean),
        "dplddt_local": dplddt_local,
        "abs_dplddt_local": abs(dplddt_local),
        "engine": al.engine,
    })


def build_plm_csv(positions: list[dict]) -> str:
    """All L*19 rows; structural columns empty until the row was folded."""
    out = [PLM_CSV_HEADER]
    def _num(v, fmt):
        return "" if v is None else fmt % v
    for p in positions:
        for r in p["rows"]:
            out.append(",".join([
                str(p["pos"]), p["wt_aa"], r["mut_aa"], r["sector"],
                str(r["grantham"]),
                f"{r['plm_margin']:.6f}",
                f"{r['plm_logprob_alt']:.6f}",
                f"{r['plm_logprob_wt']:.6f}",
                f"{r['plm_damage']:.6f}",
                _num(r.get("local_rmsd"), "%.6f"),
                _num(r.get("global_rmsd"), "%.6f"),
                _num(r.get("tm_score"), "%.6f"),
                _num(r.get("plddt_mut"), "%.4f"),
                _num(r.get("dplddt"), "%+.4f"),
                _num(r.get("dplddt_local"), "%+.4f"),
                _num(r.get("abs_dplddt_local"), "%.4f"),
                r.get("engine", ""),
            ]))
    return "\n".join(out) + "\n"