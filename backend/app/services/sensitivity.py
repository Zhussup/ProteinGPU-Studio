"""Position sensitivity math for the scan map / "wind rose" (dum.md §5).

Pure stdlib: the fixed petal compass, per-position scalars, the
hedgehog/needle/disk/clover quadrant classification, within-protein percentile
normalization and the flat CSV projection. No folding here — the router feeds
measured 19-vectors in; this module turns them into rose-ready data (and into
the dataset rows the future surrogate + DMS bridge consume), unit-testable in
milliseconds like mutagenesis.py.
"""
from __future__ import annotations

import math

# Тот же алфавит, что mutagenesis.AA / ml.folding.base.AA_RE.
# 与 mutagenesis.AA / ml.folding.base.AA_RE 相同的字母表。
AA = "ACDEFGHIKLMNPQRSTVWY"

# Фиксированный компас розы (dum.md §5): физико-химические секторы в
# фиксированном порядке, внутри сектора — по алфавиту. Порядок не зависит
# от позиции, поэтому розы разных позиций сравнимы напрямую; WT-остаток
# позиции оставляет пустой слот (выемку), а не пересортировку компаса.
# 固定的玫瑰罗盘（dum.md §5）：理化扇区按固定顺序排列，扇区内按字母序。
# 该顺序与位点无关，不同位点的玫瑰可直接比较；位点的 WT 残基留空槽（缺口），
# 而不是打乱罗盘。
SECTORS: dict[str, str] = {
    "hydrophobic": "AVILM",
    "aromatic": "FWY",
    "polar": "STNQ",
    "acidic": "DE",
    "basic": "KRH",
    "special": "GCP",
}
SECTOR_ORDER = ("hydrophobic", "aromatic", "polar", "acidic", "basic", "special")
PETAL_DIRS = "".join(SECTORS[s] for s in SECTOR_ORDER)          # "AVILMFWYSTNQDEKRHGCP"
SECTOR_OF: dict[str, str] = {aa: s for s in SECTOR_ORDER for aa in SECTORS[s]}


def petal_dirs(wt_aa: str) -> list[str]:
    """The 19 substitution directions for a WT residue, in compass order."""
    return [aa for aa in PETAL_DIRS if aa != wt_aa]


# -- скаляры по позициям и квадрант ---------------------------------------------
# -- 位点标量与象限 ---------------------------------------------------------------

# Пороги квадрантов привязаны к существующим полосам честности: 1.0/2.0 Å —
# границы stable/critical в interpret_rmsd; игла должна реально выступать
# за полосу stable, чтобы считаться иглой.
# 象限阈值绑定于现有诚实区间：1.0/2.0 Å 即 interpret_rmsd 的 stable/critical 边界；
# 尖针必须真正超出 stable 区间才算尖针。
STRONG_MED = 1.0      # медиана локального RMSD (Å): quiet ↔ отклик | 局部 RMSD 中位数（Å）：quiet 与有响应的分界
SHARP_RATIO = 2.0     # отношение max/median, отмечающее одно доминирующее направление | 标记单一主导方向的 max/median 比值
NEEDLE_MIN_MAX = 1.0  # игла требует max >= этого (Å), иначе это шум | 尖针需 max ≥ 该值（Å），否则只是噪声

QUADRANTS = ("hedgehog", "needle", "disk", "clover")

QUADRANT_WORDS: dict[str, dict[str, str]] = {
    "ru": {
        "hedgehog": "ёж (ломается любая замена)",
        "needle": "игла (больно в одном химическом направлении)",
        "disk": "диск (толерантная позиция)",
        "clover": "клевер (сильно, но рвано — несколько ярких лепестков)",
    },
    "en": {
        "hedgehog": "hedgehog (every substitution hurts)",
        "needle": "needle (one chemical direction hurts)",
        "disk": "disk (tolerant position)",
        "clover": "clover (strong but ragged — several bright petals)",
    },
    "zh": {
        "hedgehog": "海胆（任何替换都致伤）",
        "needle": "尖针（仅一个化学方向致伤）",
        "disk": "圆盘（耐受位点）",
        "clover": "三叶草（强烈但破碎——几片亮花瓣）",
    },
}


def position_stats(local_rmsd: list[float],
                   abs_dplddt_local: list[float]) -> dict[str, float | str]:
    """Scalars + quadrant for one position's 19 responses.

    local_rmsd: per-substitution local RMSD values (any order);
    abs_dplddt_local: |ΔpLDDT| of the local window per substitution.
    The 3D paint scalar V(i) is max/mean local RMSD; the rose's length channel
    stays |ΔpLDDT_local| (dum.md §6 honesty hierarchy) — both shipped.
    """
    if len(local_rmsd) != 19 or len(abs_dplddt_local) != 19:
        raise ValueError("a sensitivity vector has exactly 19 responses")
    xs = sorted(local_rmsd)
    med = xs[9]  # медиана из 19 = 10-е по счёту, без float-неоднозначности | 19 个值的中位数 = 第 10 小，无浮点歧义
    mx = xs[-1]
    mean = sum(xs) / len(xs)
    med_dp = sorted(abs_dplddt_local)[9]

    # Защита от отсутствия сигнала: ничего не двигается → disk независимо от отношения.
    # 无信号保护：处处不动 → disk，与比值无关。
    if mx < 1e-9:
        quadrant = "disk"
    elif med < STRONG_MED:
        sharp = mx >= max(med * SHARP_RATIO, NEEDLE_MIN_MAX)
        quadrant = "needle" if sharp else "disk"
    else:
        quadrant = "hedgehog" if mx < med * SHARP_RATIO else "clover"

    return {
        "median_local_rmsd": med, "max_local_rmsd": mx,
        "mean_local_rmsd": mean, "median_abs_dplddt_local": med_dp,
        "sharpness": mx / max(med, 1e-9),
        "quadrant": quadrant,
    }


# -- нормировка внутри белка ----------------------------------------------------
# -- 蛋白内归一化 -----------------------------------------------------------------

def percentile_rank(x: float, arr: list[float]) -> float:
    """Rank of x in arr, 0..1 — fraction of values strictly below, over n-1.

    Byte-parity with the frontend's SensitivityCompare.rank(): ties sit at the
    bottom (a constant array maps everything to 0.0, not 0.5); a single
    element maps to 0.5. Both sides normalize identically by construction.
    """
    below = sum(1 for v in arr if v < x)
    return below / (len(arr) - 1) if len(arr) > 1 else 0.5


def normalize_protein(positions: list[dict]) -> None:
    """Add within-protein percentiles in place (dum.md §5: petal length and
    paint scalar are percentiles inside the protein, raw values stay visible).

    Adds to each position dict: stats["pctl_v_max"], stats["pctl_v_med"] and a
    per-row "pctl" (rank of |dplddt_local| among ALL responses of the protein).
    """
    n_pos = len(positions)
    if n_pos == 0:
        return
    v_maxes = [p["stats"]["max_local_rmsd"] for p in positions]
    v_meds = [p["stats"]["median_local_rmsd"] for p in positions]
    pool: list[float] = []
    for p in positions:
        pool.extend(r["abs_dplddt_local"] for r in p["rows"])
    for p in positions:
        p["stats"]["pctl_v_max"] = percentile_rank(p["stats"]["max_local_rmsd"], v_maxes)
        p["stats"]["pctl_v_med"] = percentile_rank(p["stats"]["median_local_rmsd"], v_meds)
        for r in p["rows"]:
            r["pctl"] = percentile_rank(r["abs_dplddt_local"], pool)


# -- проекция в датасет ----------------------------------------------------------
# -- 数据集投影 -------------------------------------------------------------------

CSV_HEADER = ("position,wt_aa,mut_aa,sector,grantham,local_rmsd,global_rmsd,"
              "tm_score,plddt_mut,dplddt,dplddt_local,abs_dplddt_local,pctl,"
              "engine")


def build_csv(positions: list[dict]) -> str:
    """Flat DMS-ready projection: one row per (position, substitution).

    The scan map JSON is the viewer's artifact; this CSV is the dataset row
    format (dum.md §3) — the same values the rose displays, unfolded into
    ProteinGym-`DMS_substitutions`-shaped lines.
    """
    out = [CSV_HEADER]
    for p in positions:
        for r in p["rows"]:
            out.append(",".join([
                str(p["pos"]), p["wt_aa"], r["mut_aa"],
                SECTOR_OF[r["mut_aa"]],
                str(r["grantham"]),
                f"{r['local_rmsd']:.6f}", f"{r['global_rmsd']:.6f}",
                f"{r['tm_score']:.6f}", f"{r['plddt_mut']:.4f}",
                f"{r['dplddt']:+.4f}", f"{r['dplddt_local']:+.4f}",
                f"{r['abs_dplddt_local']:.4f}", f"{r['pctl']:.4f}",
                r["engine"],
            ]))
    return "\n".join(out) + "\n"


def quadrant_counts(positions: list[dict]) -> dict[str, int]:
    counts = {q: 0 for q in QUADRANTS}
    for p in positions:
        counts[p["stats"]["quadrant"]] += 1
    return counts


def most_fragile(positions: list[dict]) -> dict | None:
    """The position with the highest within-protein v_max percentile."""
    return max(positions, key=lambda p: p["stats"]["pctl_v_max"], default=None)