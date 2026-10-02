"""DMS-validation data plumbing: curated ProteinGym assays, position mapping,
row hygiene and the fold-plan sampling. Pure files + pure functions — no GPU,
no folding; the router folds inside the job via plm_scoring/folding_service.

The manifest data/dms/curated.json is the COMMITTED contract between the
repository and this service: scripts/34_curate_proteingym.py sweeps the
gitignored substitution CSVs and records the numbering-clean small whites.
Everything downstream reads the assay CSVs through the manifest's `file`
paths (repo-relative), never through a second directory.

Знак величин: DMS_score — «чем выше, тем приспособленнее»; plm_margin —
«чем выше, тем предсказанно безвреднее». plm_damage = −margin.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..config import get_settings

MUT_SINGLE = re.compile(r"^([A-Z])(\d+)([A-Z])$")
DMS_DIR = "data/dms"
ASSAY_FITS = ("DMS_score", "fitness", "score")   # alias-колонки приспособленности

REPO_ROOT = Path(__file__).resolve().parents[3]


class DmsDataError(RuntimeError):
    """data/dms недоступен (нет curated.json) — гейтится локализованной 4xx."""
    pass


@dataclass
class DmsVariant:
    """One mapped single substitution with its assay fitness and PLM margin."""
    pos_dms: int                # нумерация DMS-таргета (1-based)
    pos0_local: int             # 0-based позиция в НАШЕЙ последовательности
    wt_aa: str
    alt_aa: str
    mut_seq: str                # наша последовательность с этой заменой
    fitness_raw: float
    fitness_z: float = 0.0
    plm_margin: float = 0.0
    count: int = 1              # дубликаты (pos, alt) слиты усреднением
    # структурный отклик — только у сфолднутых | структурный отклик — только у сфолднутых
    local_rmsd: float | None = None
    dplddt: float | None = None
    dplddt_local: float | None = None
    plddt_mut: float | None = None
    engine: str | None = None


def curated_path() -> Path:
    return Path(get_settings().data_dir) / "dms" / "curated.json"


def list_assays() -> list[dict]:
    """Curated assays + файловый статус ('ok' | 'missing'). JSON-родимо поле."""
    out = []
    for a in load_manifest().get("assays", []):
        out.append({
            "dms_id": a["dms_id"],
            "seq_len": len(a["consensus_seq"]),
            "singles": a["singles"],
            "positions": a["positions_swept"],
            "rows": a["rows"],
            "ok": assay_file(a).exists(),
        })
    return out


def load_manifest() -> dict:
    p = curated_path()
    if not p.exists():
        raise DmsDataError("data/dms/curated.json not found")
    return json.loads(p.read_text(encoding="utf-8"))


def assay_by_id(dms_id: str) -> dict:
    for a in load_manifest().get("assays", []):
        if a["dms_id"] == dms_id:
            return a
    raise DmsDataError(f"assay {dms_id!r} not in curated.json")


def assay_file(a: dict) -> Path:
    """Repo-relative path of the assay CSV, resolved from the settings data dir.

    data_dir по умолчанию <repo>/data, поэтому 'data/proteingym/…' resolves
    честно и в тестах (fresh PGS_DATA_DIR), и в бою.
    """
    f = a["file"]
    if f.startswith("data/"):
        return Path(get_settings().data_dir) / f.removeprefix("data/")
    return Path(f)


def load_assay(dms_id: str) -> tuple[list[tuple[int, str, str, float]], dict, str]:
    """Parse one assay CSV: singles only, hygiene checks; counters included.

    Returns (singles, counts, consensus_seq); singles = [(pos_dms, wt_aa,
    mut_aa, fitness_raw)] NOT aggregated yet. Column names are
    alias-tolerant: fitness column = DMS_score/fitness/score.
    """
    a = assay_by_id(dms_id)
    consensus: str = a["consensus_seq"]
    counts = {"rows_total": 0, "rows_multi": 0, "rows_unparseable": 0,
              "rows_out_of_range": 0, "rows_wt_mismatch": 0, "rows_badseq": 0,
              "rows_no_score": 0, "rows_in_range": 0,
              # дропается позже, в маппинге (validation.py): позиция не вошла
              # в колонки выравнивания / буква WT расходится с нашей
              "rows_unmapped": 0, "rows_wt_mismatch_local": 0, "rows_dup_merged": 0}
    singles: list[tuple[int, str, str, float]] = []
    with assay_file(a).open("r", encoding="utf-8", newline="") as fh:
        rdr = csv.DictReader(fh)
        cols = rdr.fieldnames or []
        fit_col = next((c for c in ASSAY_FITS if c in cols), None)
        if fit_col is None:
            raise DmsDataError(f"{dms_id}: no fitness column (have {cols[:6]}…)")
        for r in rdr:
            mut = (r.get("mutant") or "").strip()
            mut_seq = (r.get("mutated_sequence") or "").strip()
            counts["rows_total"] += 1
            if ":" in mut:
                counts["rows_multi"] += 1      # multi-мутанты мимо задачи
                continue
            m = MUT_SINGLE.match(mut)
            if not m:
                counts["rows_unparseable"] += 1
                continue
            wt_aa, pos_s, alt_aa = m.groups()
            pos = int(pos_s)
            if not (1 <= pos <= len(consensus)):
                counts["rows_out_of_range"] += 1
                continue
            # per-row гигиена через mutated_sequence: это последовательность
            # МУТАНТА — на позиции должен стоять alt, остальное — консенсус
            if mut_seq:
                if pos > len(mut_seq) or mut_seq[pos - 1] != alt_aa:
                    counts["rows_wt_mismatch"] += 1   # метка не совпала с seq
                    continue
                if len(mut_seq) != len(consensus) or any(
                        a != b for i, (a, b) in
                        enumerate(zip(mut_seq, consensus)) if i != pos - 1):
                    counts["rows_badseq"] += 1       # лишние расхождения
                    continue
            raw = (r.get(fit_col) or "").strip()
            if not raw:
                counts["rows_no_score"] += 1
                continue
            counts["rows_in_range"] += 1
            singles.append((pos, wt_aa, alt_aa, float(raw)))
    return singles, counts, consensus


def map_positions(target_seq: str, our_seq: str) -> tuple[str, dict[int, int]]:
    """DMS position (1-based) → our 0-based position.

    Exact substring first (the common case: our fasta contains the target).
    Otherwise a global pairwise alignment with BioPython, column by column:
    residue↔residue columns where the LETTERS match are counted into
    identity (mismatches — no); identity ≥ 0.9, otherwise ValueError —
    the caller turns it into a 422. Gaps: a DMS position that fell into an
    our-sequence gap does not get an entry — the router counts it in
    rows_unmapped.
    """
    if target_seq in our_seq:
        at = our_seq.index(target_seq)
        return "exact-substring", {i + 1: at + i for i in range(len(target_seq))}

    from Bio.Align import PairwiseAligner
    aln = PairwiseAligner(mode="global",
                          match_score=2, mismatch_score=-1,
                          open_gap_score=-5, extend_gap_score=-0.5)
    aligned = aln.align(our_seq, target_seq)[0]
    ours, theirs = aligned.indices  # две строки [n_cols]; -1 = гэп в колонке
    mapping: dict[int, int] = {}
    matched = 0
    for c in range(ours.shape[-1]):
        a, b = int(ours[c]), int(theirs[c])
        if a >= 0 and b >= 0:
            mapping[b + 1] = a
            if our_seq[a] == target_seq[b]:
                matched += 1
    identity = matched / len(target_seq)
    if identity < 0.9:
        raise ValueError(f"identity {identity:.2f} < 0.9 — wrong protein?")
    return "pairwise", mapping


def aggregate(singles: list[tuple[int, str, str, float]]) -> list[tuple[int, str, str, float, int]]:
    """Dedupe (pos, wt, alt): duplicates merge to MEAN fitness, count kept."""
    agg: dict[tuple[int, str, str], list[float]] = {}
    order: list[tuple[int, str, str]] = []
    for pos, wt_aa, alt_aa, raw in singles:
        key = (pos, wt_aa, alt_aa)
        if key not in agg:
            agg[key] = []
            order.append(key)
        agg[key].append(raw)
    return [(pos, wt, aa, sum(v) / len(v), len(v))
            for (pos, wt, aa) in order for v in (agg[(pos, wt, aa)],)]


def zscore(fitness: list[float]) -> tuple[list[float], float, float]:
    """Assay-internal z-score; sd≈0 → честные нули + флаг."""
    n = len(fitness)
    mu = sum(fitness) / n if n else 0.0
    sd = (sum((f - mu) ** 2 for f in fitness) / n) ** 0.5 if n else 0.0
    if sd < 1e-9:
        return [0.0] * n, mu, 0.0
    return [(f - mu) / sd for f in fitness], mu, sd


def stratified_sample(rows: list[DmsVariant], n: int, seed: int) -> list[DmsVariant]:
    """Quantile-balanced sample of fold targets by fitness (seeded).

    n=0 → [] (fast PLM-only mode); n >= len(rows) → всё; иначе квантильные
    бины по fitness_z + jitter с seed, чтобы не отдать только хвост.
    """
    if n <= 0:
        return []
    if len(rows) <= n:
        return list(rows)
    import numpy as np
    rng = np.random.default_rng(seed)
    zs = np.array([r.fitness_z for r in rows])
    qs = np.quantile(zs, np.linspace(0, 1, n + 1))
    bins = np.clip(np.searchsorted(qs, zs, side="right") - 1, 0, n - 1)
    picked: list[DmsVariant] = []
    for b in range(n):
        idxs = [i for i in range(len(rows)) if bins[i] == b]
        if idxs:
            picked.append(rows[idxs[int(rng.integers(len(idxs)))]])
    return picked


def pick_top1_per_position(variants: list[DmsVariant],
                           pctl_by_local: dict[int, float],
                           cap: int) -> list[tuple[str, DmsVariant]]:
    """ONE variant per position — chosen by LOWEST PLM margin (no fitness leak).

    The label must not decide which mutants get folded (that would leak the
    sampling into the validation numbers), so the fold plan is driven by the
    PLM prediction alone; positions come in PLM-fragility order, capped.
    """
    best: dict[int, DmsVariant] = {}
    for v in variants:
        cur = best.get(v.pos0_local)
        if cur is None or v.plm_margin < cur.plm_margin:
            best[v.pos0_local] = v
    ranked = sorted(best.values(), key=lambda v: pctl_by_local.get(v.pos0_local, 0.0),
                    reverse=True)
    if cap <= 0:
        return []  # fold_positions_max=0 → без per-position фолдов (fast-режим)
    return [(f"{v.wt_aa}{v.pos0_local + 1}{v.alt_aa}", v) for v in ranked[:cap]]