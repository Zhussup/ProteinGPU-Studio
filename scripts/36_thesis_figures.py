#!/usr/bin/env python
"""36_thesis_figures.py — фигуры записки из батч-JSON валидации (scripts/35).

Вход: data/report/validation/{DMS_id}.json (полный result-словарь протокола).
Выход: data/report/figs/fig_validation_*.png (convention scripts/12: Agg, dpi=150,
подписи по-русски, серые шкалы + один красный).

  fig_validation_corr_bars.png  — ρ(PLM-маргин, fitness) по assay ± бутстрэп-CI
  fig_validation_scatter.png    — сетка scatter margin↔fitness по assay
  fig_validation_posstrip.png   — по-позиционное сравнение (exemplar-assay)
  fig_validation_agreement.png  — согласие PLM↔структура (ρ margin_rmsd, pos_struct_plm)

Честность: JSON со скорером dummy-plm отбрасываются без --allow-dummy.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
VAL_DIR = REPO / "data" / "report" / "validation"
FIGS = REPO / "data" / "report" / "figs"

C_DARK, C_GRAY, C_RED = "#111111", "#9ca3af", "#b91c1c"


def load_results(allow_dummy: bool) -> list[dict]:
    if not VAL_DIR.exists():
        raise SystemExit(f"{VAL_DIR} пуст — сначала scripts/35_batch_validation.py")
    out = []
    for p in sorted(VAL_DIR.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("plm_scorer") == "dummy-plm" and not allow_dummy:
            print(f"[skip] {p.name}: dummy-plm скорер")
            continue
        out.append(r)
    if not out:
        raise SystemExit("валидных результатов нет (все dummy или каталог пуст)")
    # короткие белки первыми: полный фолд-план покрывает их целиком
    out.sort(key=lambda r: r["dms_meta"]["seq_len"])
    return out


def corr(r: dict, name: str) -> dict | None:
    return next((c for c in r["correlations"] if c["name"] == name), None)


def short_id(dms_id: str) -> str:
    return dms_id.split("_Tsuboyama_")[0][:24] if "_Tsuboyama_" in dms_id else dms_id[:24]


def fig_corr_bars(results: list[dict]) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.0))
    for ax, name, title in (
        (ax1, "plm_all", "ρ(PLM-маргин, fitness) — zero-shot, все mapped-строки"),
        (ax2, "pos_plm", "ρ(хрупкость позиции, средний fitness) — по позиции"),
    ):
        labels = [short_id(r["assay_id"]) for r in results]
        rhos = [corr(r, name)["spearman"] for r in results]
        los, his = [], []
        for r in results:
            ci = corr(r, name)["ci"]
            rho = corr(r, name)["spearman"]
            los.append(max(0.0, min(1.0, rho - ci[0])) if ci and rho is not None else 0)
            his.append(max(0.0, min(1.0, ci[1] - rho)) if ci and rho is not None else 0)
        xs = np.arange(len(results))
        colors = []
        for r, rho in zip(results, rhos):
            c_item = corr(r, name)
            if rho is None:
                colors.append(C_GRAY)
            else:
                ok_sign = rho >= 0 if c_item["expected_sign"] == "+" else rho <= 0
                colors.append(C_DARK if ok_sign else C_RED)
        ax.bar(xs, [rho if rho is not None else 0 for rho in rhos],
               yerr=[los, his], capsize=3, color=colors)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
        ax.set_ylim(-1.05, 1.05)
        ax.set_ylabel("Spearman ρ ±95% CI (бутстрэп)")
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_validation_corr_bars.png", dpi=150)
    plt.close(fig)


def fig_scatter(results: list[dict], max_panels: int) -> None:
    sel = results[:max_panels]
    cols = min(3, len(sel))
    rows = math.ceil(len(sel) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 4.2, rows * 3.6), squeeze=False)
    for ax in axes.ravel():
        ax.set_visible(False)
    for ax, r in zip(axes.ravel(), sel):
        pts = r["scatter_plm"]
        x = [p["x"] for p in pts]
        y = [p["y"] for p in pts]
        ax.scatter(x, y, s=8, c=C_DARK, alpha=0.6, linewidths=0)
        rho = corr(r, "plm_all")
        title = f"{short_id(r['assay_id'])} (n={len(pts)})"
        if rho and rho["spearman"] is not None:
            title += f"\nρ=+{rho['spearman']:.2f}" if rho["spearman"] >= 0 \
                else f"\nρ={rho['spearman']:.2f}"
        ax.set_title(title, fontsize=9)
        ax.axhline(0, color="black", lw=0.5)
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=8)
    for ax in axes.ravel()[:len(sel)]:
        ax.set_xlabel("PLM-маргин", fontsize=9)
        ax.set_ylabel("fitness (z-score assay)", fontsize=9)
    fig.suptitle("zero-shot PLM-мargins против экспериментального fitness (ProteinGym)",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGS / "fig_validation_scatter.png", dpi=150)
    plt.close(fig)


def fig_posstrip(r: dict) -> None:
    """Exemplar: по позиции PLM-перцентиль хрупкости против среднего fitness."""
    pp = r["per_position"]
    pos = [p["pos"] for p in pp]
    pctl = [p["v_med_pctl"] for p in pp]
    fit = [p["mean_fitness_z"] for p in pp]

    fig, ax1 = plt.subplots(figsize=(11, 4.0))
    ax2 = ax1.twinx()
    ax2.axhline(0.5, color=C_GRAY, lw=0.5, ls=":")
    ax1.bar(np.array(pos) - 0.2, fit, width=0.4, color=C_GRAY,
            label="средний fitness (z, левая ось)")
    ax2.bar(np.array(pos) + 0.2, pctl, width=0.4, color=C_RED,
            label="PLM-хрупкость (pctl 0–1, правая ось)")
    ax1.set_ylabel("средний fitness, z-score"); ax1.grid(alpha=0.3, axis="y")
    ax2.set_ylabel("перцентиль PLM-хрупкости")
    ax1.set_xlabel("позиция (нумерация нашей последовательности)")
    rho = corr(r, "pos_plm")
    step = max(1, len(pos) // 40)
    ax1.set_xticks(pos[::step]); ax1.set_xticklabels(pos[::step], fontsize=7)
    title = short_id(r["assay_id"])
    if rho and rho["spearman"] is not None:
        title += f": ρ(pos_plm)=+{rho['spearman']:.2f}" if rho["spearman"] >= 0 \
            else f": ρ(pos_plm)={rho['spearman']:.2f}"
    ax1.set_title(title, fontsize=10)
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_validation_posstrip.png", dpi=150)
    plt.close(fig)


def fig_agreement(results: list[dict]) -> None:
    """Согласие каналов: ρ(margin_rmsd) на сфолднутых — PLM предсказывает
    структурный отклик до фолдинга (ожидание «−»)."""
    fig, ax = plt.subplots(figsize=(9, 4.2))
    labels = [short_id(r["assay_id"]) for r in results]
    xs = np.arange(len(results))
    ys, los, his, colors = [], [], [], []
    for r in results:
        c = corr(r, "margin_rmsd")
        rho = c["spearman"] if c else None
        ci = c["ci"] if c else None
        if rho is None:
            ys.append(0); los.append(0); his.append(0); colors.append(C_GRAY)
        else:
            ys.append(rho)
            los.append(max(0.0, min(1.0, rho - ci[0])) if ci else 0)
            his.append(max(0.0, min(1.0, ci[1] - rho)) if ci else 0)
            colors.append(C_DARK if rho <= 0 else C_RED)
    ax.bar(xs, ys, yerr=[los, his], capsize=3, color=colors)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(xs); ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("ρ(PLM-маргин, local RMSD), сфолднутые")
    ax.set_title("Согласие каналов: PLM-маргин предсказывает структурный отклик (ожидание «−»)",
                 fontsize=10)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_validation_agreement.png", dpi=150)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--allow-dummy", action="store_true",
                    help="включить dummy-результаты (только отладка)")
    ap.add_argument("--max-scatter", type=int, default=9,
                    help="максимум панелей в сетке scatter")
    args = ap.parse_args()

    results = load_results(args.allow_dummy)
    print(f"результатов: {len(results)}")
    for r in results:
        c = corr(r, "plm_all")
        rho = c["spearman"] if c else None
        print(f"  {r['assay_id']}: n={r['n_rows']} positions={r['n_positions']} "
              f"ρ(plm_all)={rho}")

    FIGS.mkdir(parents=True, exist_ok=True)
    fig_corr_bars(results)
    fig_scatter(results, max(1, args.max_scatter))
    fig_posstrip(results[0])
    fig_agreement(results)
    print(f"фигуры → {FIGS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())