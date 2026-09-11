#!/usr/bin/env python
"""12_make_report_figures.py — Stage 5: report figures from bench JSONs.

Reads data/report/{bench_inference,bench_kernels}.json and renders PNG figures
into data/report/figs/ for the пояснительная записка:
  fig1_inference_latency.png  — latency vs length (log-y), IQR error bars
  fig2_kernel_bench.png       — engine bars per (B, N) sweep point
  fig3_vram.png               — VRAM peak per profile/length
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "data" / "report"
FIGS = REPORT / "figs"

COLORS = {"fp32-gpu": "#22d3ee", "fp16-gpu": "#a78bfa", "cpu": "#f59e0b",
          "dummy": "#94a3b8", "numpy": "#f59e0b", "cpp-openmp": "#34d399",
          "cuda-pcie": "#f472b6", "cuda-resident": "#22d3ee"}


def fig_inference(rows: list[dict]) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    for profile in dict.fromkeys(r["profile"] for r in rows):
        rr = sorted((r for r in rows if r["profile"] == profile),
                    key=lambda r: r["length"])
        x = [r["length"] for r in rr]
        y = [r["wall_median_s"] for r in rr]
        e = [r["wall_iqr_s"] / 2 for r in rr]
        ax1.errorbar(x, y, yerr=e, marker="o", capsize=3,
                     label=profile, color=COLORS.get(profile))
        vr = [r.get("vram_peak_mb") or 0 for r in rr]
        ax2.plot(x, vr, marker="s", label=profile, color=COLORS.get(profile))
    ax1.set_yscale("log")
    ax1.set_xlabel("длина последовательности, aa")
    ax1.set_ylabel("latency, с (median ± IQR/2)")
    ax1.set_title("Инференс: CPU vs GPU")
    ax1.grid(alpha=0.3)
    ax1.legend(fontsize=8)
    ax2.set_xlabel("длина последовательности, aa")
    ax2.set_ylabel("VRAM peak, МБ")
    ax2.set_title("Потребление VRAM")
    ax2.grid(alpha=0.3)
    ax2.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGS / "fig1_inference_latency.png", dpi=150)
    plt.close(fig)


def fig_kernels(rows: list[dict]) -> None:
    points = sorted({(r["pairs"], r["atoms"]) for r in rows})
    engines = list(dict.fromkeys(r["engine"] for r in rows))
    fig, ax = plt.subplots(figsize=(9, 4.2))
    import numpy as np

    width = 0.8 / len(engines)
    xs = np.arange(len(points))
    for i, eng in enumerate(engines):
        ys, es = [], []
        for B, N in points:
            r = next((r for r in rows if r["engine"] == eng
                      and r["pairs"] == B and r["atoms"] == N), None)
            ys.append(r["wall_median_s"] * 1000 if r else 0)
            es.append(r["wall_iqr_s"] / 2 * 1000 if r else 0)
        ax.bar(xs + i * width, ys, width, yerr=es, capsize=3,
               label=eng, color=COLORS.get(eng))
    ax.set_xticks(xs + width * (len(engines) - 1) / 2)
    ax.set_xticklabels([f"B={B}\nN={N}" for B, N in points])
    ax.set_ylabel("время, мс (median ± IQR/2)")
    ax.set_title("Kabsch-ядро: numpy vs C++ OpenMP vs CUDA")
    ax.set_yscale("log")
    ax.grid(alpha=0.3, axis="y")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGS / "fig2_kernel_bench.png", dpi=150)
    plt.close(fig)


def main() -> int:
    FIGS.mkdir(parents=True, exist_ok=True)
    inf = REPORT / "bench_inference.json"
    ker = REPORT / "bench_kernels.json"
    made = []
    if inf.exists():
        fig_inference(json.loads(inf.read_text())["rows"])
        made.append("fig1_inference_latency.png")
    if ker.exists():
        fig_kernels(json.loads(ker.read_text())["rows"])
        made.append("fig2_kernel_bench.png")
    print("written:", ", ".join(made) or "nothing (no bench JSONs yet)")
    print(f"dir: {FIGS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())