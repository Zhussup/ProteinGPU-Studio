"""Tests for DNA→protein translation and the template-based summary."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for p in (str(REPO),):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.app.schemas import RmsdResult  # noqa: E402
from backend.app.services.summary import make_summary  # noqa: E402
from backend.app.services.translate import clean_dna, translate  # noqa: E402


# -- clean_dna ---------------------------------------------------------------
def test_clean_dna_strips_fasta_and_garbage():
    dna, warns = clean_dna(">sp|X|orf\natg aa g\nt5tt\n")
    assert dna == "ATGAAGTTT"
    assert any("удалены" in w for w in warns)


def test_clean_dna_uracil_to_thymine():
    dna, _ = clean_dna("AUGAAU")
    assert dna == "ATGAAT"


# -- translate ---------------------------------------------------------------
def test_translate_ubiquitin_start_codon():
    # GGGACC ATG AAA TTT CCC TAA → M K F
    res = translate("GGGACCATGAAATTTCCCTAA")
    assert res["orf_start"] == 6
    assert res["protein"] == "MKFP*"  # stop marker included, loop stops at TAA
    assert res["codons"][0] == {"index": 1, "codon": "ATG", "aa": "M"}
    assert res["codons"][4] == {"index": 5, "codon": "TAA", "aa": "*"}


def test_translate_no_start_codon_warns():
    res = translate("AAATTTCCCTAA")
    assert res["orf_start"] == 0
    assert res["protein"].endswith("*")
    assert any("ATG" in w for w in res["warnings"])


def test_translate_incomplete_tail():
    res = translate("ATGAAAT")
    assert len(res["codons"]) == 2  # ATG AAA; lone T ignored
    assert any("кратен 3" in w for w in res["warnings"])


# -- make_summary ------------------------------------------------------------
def _rmsd(local: float, tm: float, plddt_wt: float, plddt_mut: float,
          interp: str) -> RmsdResult:
    return RmsdResult(
        global_rmsd=local + 0.1, local_rmsd=local, local_window=(34, 54),
        tm_score=tm, plddt_wt=plddt_wt, plddt_mut=plddt_mut,
        interpretation=interp, engine="cuda")


def test_summary_stable_band():
    s = make_summary(_rmsd(0.21, 0.997, 92.0, 91.9, "stable"), "I", 44, "A")
    assert "Мутация I44A" in s
    assert "поглощена" in s
    assert "укладка сохранена" in s
    assert "±0.1" not in s  # no fake precision phrases
    assert "Итог: структура стабильна" in s
    assert "сравнением между собой" in s  # determinism caveat in stable band


def test_summary_moderate_band():
    s = make_summary(_rmsd(1.5, 0.8, 92.0, 90.5, "moderate"), "P", 19, "G")
    assert "умеренная локальная перестройка" in s
    assert "в целом сохранена, но деформирована" in s
    assert "менее уверена" in s  # ΔpLDDT = −1.5
    assert "Итог" in s


def test_summary_critical_band():
    s = make_summary(_rmsd(3.1, 0.4, 92.0, 88.0, "critical"), "P", 19, "G")
    assert "существенно изменена" in s
    assert "по-разному" in s
    assert "критическое изменение конформации" in s


def test_summary_never_mentions_engine():
    s = make_summary(_rmsd(0.2, 0.99, 90.0, 90.0, "stable"), "I", 3, "L")
    assert "cuda" not in s.lower()


@pytest.mark.parametrize("lr,expected", [(0.99, 0), (1.0, 1), (1.99, 1), (2.0, 2)])
def test_summary_band_edges(lr, expected):
    # band edges must match interpret_rmsd: <1 stable, 1–2 moderate, ≥2 critical
    interp = {0: "stable", 1: "moderate", 2: "critical"}[expected]
    s = make_summary(_rmsd(lr, 0.99, 90, 90, interp), "A", 1, "V")
    phrases = ["поглощена", "умеренная", "существенно"]
    assert phrases[expected] in s