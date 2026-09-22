"""Unit tests for the sensitivity map math (no FastAPI, no model).

The fixed compass, quadrant classification edge cases, percentile
normalization and the CSV projection — all pure stdlib, instant to run.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from backend.app.services.sensitivity import (  # noqa: E402
    AA, PETAL_DIRS, SECTOR_OF, build_csv, normalize_protein, petal_dirs,
    percentile_rank, position_stats, quadrant_counts,
)

UBIQ = ("MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG")


class TestCompass:
    def test_petal_dirs_cover_20_letters_once(self):
        assert len(PETAL_DIRS) == 20 and len(set(PETAL_DIRS)) == 20
        assert set(PETAL_DIRS) == set(AA)

    def test_petal_dirs_skip_wt(self):
        for wt in AA:
            dirs = petal_dirs(wt)
            assert len(dirs) == 19 and wt not in dirs
            assert set(dirs) == set(AA) - {wt}

    def test_order_is_position_independent(self):
        """Dropping WT must not reshuffle the compass: the common letters of
        two positions' petal lists keep the same relative order."""
        a = petal_dirs("A")
        v = petal_dirs("V")
        common = [aa for aa in a if aa in set(v)]
        assert common == [aa for aa in v if aa in set(a)]

    def test_sectors(self):
        assert SECTOR_OF["A"] == "hydrophobic"
        assert SECTOR_OF["W"] == "aromatic"
        assert SECTOR_OF["E"] == "acidic"
        assert SECTOR_OF["K"] == "basic"
        assert SECTOR_OF["P"] == "special"


class TestPositionStats:
    def _stats(self, lr, dp=None):
        dp = dp or [0.0] * 19
        return position_stats(lr, [abs(v) for v in dp])

    def test_hedgehog_all_long_uniform(self):
        s = self._stats([1.5] * 19)
        assert s["quadrant"] == "hedgehog"
        assert s["median_local_rmsd"] == 1.5
        assert s["sharpness"] == 1.0

    def test_disk_all_short(self):
        s = self._stats([0.1] * 19)
        assert s["quadrant"] == "disk"

    def test_disk_zero_guard(self):
        """Nothing moves at all -> disk; sharpness floors to 0 via 0/1e-9."""
        s = self._stats([0.0] * 19)
        assert s["quadrant"] == "disk"
        assert s["sharpness"] == 0.0

    def test_needle_one_long_rest_short(self):
        lr = [0.1] * 19
        lr[7] = 1.5
        s = self._stats(lr)
        assert s["quadrant"] == "needle"
        assert s["max_local_rmsd"] == 1.5

    def test_clover_strong_and_ragged(self):
        lr = [1.2] * 19
        lr[7] = 3.5
        s = self._stats(lr)
        assert s["quadrant"] == "clover"

    def test_quiet_bump_is_not_needle(self):
        """max/median ratio >= 2 but max below the stable band -> disk."""
        lr = [0.4] * 19
        lr[3] = 0.9
        assert self._stats(lr)["quadrant"] == "disk"

    def test_vector_must_have_19(self):
        try:
            position_stats([0.1] * 18, [0.0] * 18)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for an 18-vector")


class TestPercentiles:
    def test_convention_matches_frontend(self):
        # fraction strictly below, over (n - 1) — SensitivityCompare.rank();
        # ties sit at the bottom (a constant array maps everything to 0.0)
        assert percentile_rank(2.0, [1.0, 2.0, 3.0]) == 0.5
        assert percentile_rank(1.0, [1.0] * 5) == 0.0
        assert percentile_rank(3.0, [1.0, 2.0, 3.0]) == 1.0
        assert percentile_rank(1.0, [1.0]) == 0.5

    def test_normalize_protein_adds_pctls(self):
        def pos(p, lr):
            return {"pos": p, "wt_aa": "A",
                    "rows": [{"mut_aa": aa, "abs_dplddt_local": abs(v)}
                             for aa, v in zip(petal_dirs("A"), [lr] * 19)],
                    "stats": position_stats([lr] * 19, [abs(lr)] * 19)}
        positions = [pos(1, 0.2), pos(2, 0.5), pos(3, 1.5)]
        normalize_protein(positions)
        assert positions[0]["stats"]["pctl_v_max"] == 0.0
        assert positions[2]["stats"]["pctl_v_max"] == 1.0
        # every row got a pctl within [0, 1]
        for p in positions:
            assert all(0.0 <= r["pctl"] <= 1.0 for r in p["rows"])


class TestCSV:
    def test_shape_and_header(self):
        lr = 0.3
        p = {"pos": 5, "wt_aa": "A",
             "rows": [{"mut_aa": aa, "grantham": 7, "local_rmsd": lr,
                       "global_rmsd": lr, "tm_score": 0.99, "plddt_mut": 90.0,
                       "dplddt": -0.1, "dplddt_local": -0.2,
                       "abs_dplddt_local": 0.2, "pctl": 0.5, "engine": "numpy"}
                      for aa in petal_dirs("A")],
             "stats": {}}
        csv = build_csv([p])
        lines = csv.strip().splitlines()
        assert len(lines) == 20  # header + 19 rows
        assert lines[0].startswith("position,wt_aa,mut_aa,sector,grantham,")
        assert lines[1].split(",")[:4] == ["5", "A", "V", "hydrophobic"]

    def test_quadrant_counts(self):
        def pos(q):
            return {"stats": {"quadrant": q}}
        counts = quadrant_counts([pos("hedgehog"), pos("needle"), pos("hedgehog")])
        assert counts == {"hedgehog": 2, "needle": 1, "disk": 0, "clover": 0}