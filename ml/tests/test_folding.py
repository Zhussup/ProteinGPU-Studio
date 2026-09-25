"""Tests for the folding layer (no GPU needed — dummy model only)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.folding.base import (  # noqa: E402
    ca_coords_from_pdb, local_window, mutant_sequence, validate_sequence)
from ml.folding.dummy_model import DummyModel, get_model  # noqa: E402
from ml.telemetry import TelemetrySampler  # noqa: E402

UBIQ = ("MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG")


class TestBase:
    def test_validate_ok(self):
        assert validate_sequence(" mqifvktltgk ") == "MQIFVKTLTGK"

    def test_validate_rejects_bad_aa(self):
        with pytest.raises(ValueError, match="non-standard"):
            validate_sequence("ACBXZAAAAA")

    def test_validate_rejects_length(self):
        with pytest.raises(ValueError, match="length"):
            validate_sequence("ACDEFGHIK")

    def test_mutant_sequence(self):
        assert mutant_sequence("AAA", 2, "C") == "ACA"
        assert mutant_sequence("MQL", 1, "G") == "GQL"

    def test_mutant_position_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            mutant_sequence("AA", 5, "C")

    def test_local_window(self):
        assert local_window(3, 10) == (0, 10)  # зажато с обоих концов | 两端都被钳制
        assert local_window(50, 76) == (39, 60)
        assert local_window(5, 100, radius=2) == (2, 7)


class TestDummyModel:
    def test_predict_shape_and_pdb(self):
        m = DummyModel()
        res = m.predict(UBIQ)
        n = len(UBIQ)
        assert res.coords_backbone.shape == (n, 4, 3)
        assert res.coords_ca.shape == (n, 3)
        assert res.plddt.shape == (n,)
        assert np.all((res.plddt >= 0) & (res.plddt <= 100))
        assert res.pdb_text.startswith("ATOM  ")
        assert res.pdb_text.rstrip().endswith("END")

    def test_ca_extractable_from_pdb(self):
        res = DummyModel().predict(UBIQ)
        ca = ca_coords_from_pdb(res.pdb_text)
        assert np.abs(ca - res.coords_ca).max() < 1e-3

    def test_deterministic_and_sequence_sensitive(self):
        m = DummyModel()
        a = m.predict(UBIQ)
        b = m.predict(UBIQ)
        assert np.abs(a.coords_ca - b.coords_ca).max() == 0
        mut = m.predict(mutant_sequence(UBIQ, 44, "A"))  # I44A | I44A
        assert np.abs(mut.coords_ca - a.coords_ca).max() > 0.01

    def test_protocol_conformance(self):
        m = get_model(profile="dummy")
        assert m.name == "dummy"
        assert callable(m.predict) and callable(m.close)


class TestTelemetry:
    def test_measure_and_summary(self):
        import time
        s = TelemetrySampler()
        for i in range(5):
            with s.measure(rep=i):
                time.sleep(0.02)
        summ = s.summary(drop_warmup=1)
        assert summ["n"] == 4
        assert 0.015 < summ["wall_median_s"] < 0.2
        assert summ["wall_iqr_s"] >= 0

    def test_summary_empty(self):
        assert TelemetrySampler().summary() == {"n": 0}