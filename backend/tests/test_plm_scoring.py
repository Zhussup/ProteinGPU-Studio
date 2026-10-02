"""Unit tests for the PLM scoring layer (no GPU, dummy scorer)."""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ml.folding.plm_scoring import (  # noqa: E402
    DummyPlmScorer, OF_RESIDX, OF_RESTYPES, OF_X, PlmScoreResult,
    get_plm_scorer, make_tokens, has_plm,
)
from ml.folding.base import AA_RE  # noqa: E402


def _score() -> PlmScoreResult:
    return DummyPlmScorer().score("ACDEFGHIKLMNPQRSTVWYVWYRND")


def test_of_index_mapping_covers_app_alphabet() -> None:
    """Every app-alphabet letter has exactly one vendored vocab index."""
    assert len(set(OF_RESTYPES)) == 20 and OF_X == 20
    for aa in AA_RE:
        assert aa in OF_RESIDX


def test_shapes_and_columns() -> None:
    r = _score()
    assert r.logprobs.shape == (len(r.seq), 20)
    assert r.margins.shape == (len(r.seq), 20)
    assert r.scorer == "dummy-plm"


def test_logprobs_are_normalized() -> None:
    """exp(lp).sum over the 20 columns == 1 per position (log-softmax)."""
    r = _score()
    assert np.allclose(np.exp(r.logprobs).sum(axis=1), 1.0, atol=1e-9)


def test_margins_wt_zero_and_deterministic() -> None:
    r = _score()
    for i, wt_aa in enumerate(r.seq):
        assert r.margin(i, wt_aa) == 0.0  # точный ноль, не эпсилон
    r2 = _score()
    assert np.array_equal(r.margins, r2.margins)
    assert np.array_equal(r.logprobs, r2.logprobs)


def test_margin_matches_logprobs() -> None:
    r = _score()
    for i, wt_aa in enumerate(r.seq):
        for alt in "AVILM":
            if alt == wt_aa:
                continue
            assert r.margin(i, alt) == r.logprob(i, alt) - r.logprob(i, wt_aa)


def test_has_plm_is_false_for_dummy() -> None:
    from ml.folding.dummy_model import get_model
    assert has_plm(get_model("dummy")) is False
    assert isinstance(get_plm_scorer(get_model("dummy")), DummyPlmScorer)


def test_make_tokens_shapes() -> None:
    tokens, mask = make_tokens("ACD", "cpu")
    import torch
    assert tokens.shape == (1, 3) and mask.shape == (1, 3)
    assert tokens.dtype == torch.int64 and mask.dtype == torch.float32
    # буквенные индексы по вендорному словарю: A=0, C=4, D=3
    assert tokens[0].tolist() == [OF_RESIDX[a] for a in "ACD"]


def test_scorer_name_never_confused_with_real() -> None:
    assert DummyPlmScorer.name == "dummy-plm"