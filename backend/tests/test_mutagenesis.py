"""Unit tests for the mutagenesis dial primitives (no FastAPI, no model).

Grantham matrix sanity, the two-halves spectrum, the seeded variant sampler
and the distribution stats/headline — all pure stdlib, instant to run.
"""
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from backend.app.services.mutagenesis import (  # noqa: E402
    AA, GRANTHAM, apply_mutations, derived_seed, distribution_stats,
    exhaustive_mutations, grantham, mutation_label, sample_variants,
    sensitivity_headline, substitution_halves,
)

UBIQ = ("MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG")


class TestGranthamMatrix:
    def test_alphabet_and_diagonal(self):
        assert sorted(GRANTHAM) == sorted(AA)
        for a in AA:
            assert grantham(a, a) == 0

    def test_symmetric(self):
        for a in AA:
            for b in AA:
                assert grantham(a, b) == grantham(b, a)

    def test_values_in_range_max_215(self):
        for a in AA:
            for b in AA:
                assert isinstance(grantham(a, b), int)
                assert 0 <= grantham(a, b) <= 215

    def test_max_is_cysteine_tryptophan(self):
        assert max((grantham(a, b) for a in AA for b in AA), default=0) == 215
        assert grantham("C", "W") == 215

    def test_published_anchors(self):
        assert grantham("A", "R") == 112
        assert grantham("I", "L") == 5
        assert grantham("N", "D") == 23
        assert grantham("A", "P") == 27
        assert grantham("S", "E") == 80
        assert grantham("P", "E") == 93
        assert grantham("G", "R") == 125
        assert grantham("S", "R") == 110


class TestHalves:
    def test_shape_per_wt(self):
        for wt in AA:
            cons, rad = substitution_halves(wt)
            assert len(cons) == 10 and len(rad) == 9
            assert not set(cons) & set(rad)
            assert set(cons) | set(rad) == set(AA) - {wt}
            assert wt not in cons and wt not in rad

    def test_distance_ordering(self):
        for wt in AA:
            cons, rad = substitution_halves(wt)
            assert max(grantham(wt, a) for a in cons) <= \
                min(grantham(wt, a) for a in rad)

    def test_known_split_for_isoleucine(self):
        cons, rad = substitution_halves("I")
        assert set(cons) == set("LMFVYWTAHP")
        assert set(rad) == set("RKQEGSNDC")


class TestSampler:
    def test_tau_extremes_pick_only_one_half(self):
        cons, rad = substitution_halves("I")
        for tau, pool in ((0.0, cons), (1.0, rad)):
            var = sample_variants(UBIQ, 44, 1, tau, 8, seed=7)
            for muts in var:
                (p, w, m) = muts[0]
                assert (p, w) == (44, "I")
                assert m in pool and m != "I"

    def test_tau_half_uses_both_halves(self):
        # mu=1 → at most 19 distinct variants; k=19 draws all of them
        var = sample_variants(UBIQ, 44, 1, 0.5, 19, seed=7)
        cons, rad = substitution_halves("I")
        used = {muts[0][2] for muts in var}
        assert used & set(cons) and used & set(rad)

    def test_anchor_always_mutated(self):
        for mu in (1, 2, 3):
            var = sample_variants(UBIQ, 44, mu, 0.5, 10, seed=3)
            for muts in var:
                anchor = [m for m in muts if m[0] == 44]
                assert len(anchor) == 1
                assert anchor[0][1] == "I" and anchor[0][2] != "I"

    def test_background_sites_distinct_and_valid(self):
        for mu in (2, 3):
            var = sample_variants(UBIQ, 44, mu, 0.5, 12, seed=11)
            for muts in var:
                assert len(muts) == mu
                positions = [p for p, _, _ in muts]
                assert positions == sorted(positions)
                assert len(set(positions)) == mu and 44 in positions
                for p, w, m in muts:
                    assert w == UBIQ[p - 1]
                    assert m != w
                    assert m in AA

    def test_variants_distinct(self):
        var = sample_variants(UBIQ, 44, 2, 0.5, 15, seed=5)
        seqs = [apply_mutations(UBIQ, m) for m in var]
        assert len(set(seqs)) == 15

    def test_same_seed_same_result(self):
        a = sample_variants(UBIQ, 44, 2, 0.5, 10, seed=42)
        b = sample_variants(UBIQ, 44, 2, 0.5, 10, seed=42)
        assert a == b

    def test_different_seeds_differ(self):
        a = sample_variants(UBIQ, 44, 2, 0.5, 10, seed=1)
        b = sample_variants(UBIQ, 44, 2, 0.5, 10, seed=2)
        assert a != b

    def test_derived_seed_sensitivity(self):
        base = derived_seed(UBIQ, 44, 2, 0.5, 20)
        assert derived_seed(UBIQ, 44, 2, 0.5, 20) == base
        assert derived_seed(UBIQ, 45, 2, 0.5, 20) != base
        assert derived_seed(UBIQ, 44, 3, 0.5, 20) != base
        assert derived_seed(UBIQ, 44, 2, 0.6, 20) != base
        assert derived_seed(UBIQ, 44, 2, 0.5, 21) != base
        assert derived_seed(apply_mutations(UBIQ, [(44, "I", "A")]),
                            44, 2, 0.5, 20) != base


class TestMutationUtils:
    def test_apply_matches_mutant_sequence_semantics(self):
        assert apply_mutations(UBIQ, [(44, "I", "A")]) == \
            UBIQ[:43] + "A" + UBIQ[44:]
        two = apply_mutations(UBIQ, [(3, "I", "A"), (20, "T", "G")])
        assert two[2] == "A" and two[19] == "G"
        assert two[43] == "I"  # untouched elsewhere

    def test_out_of_range_rejected(self):
        try:
            apply_mutations(UBIQ, [(200, "R", "A")])
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")

    def test_labels(self):
        assert mutation_label([(44, "I", "A")]) == "I44A"
        assert mutation_label([(3, "F", "L"), (44, "I", "A")]) == "F3L+I44A"

    def test_exhaustive_matches_scan_targets(self):
        muts = exhaustive_mutations(UBIQ, 44)
        assert len(muts) == 19
        assert [m[0][2] for m in muts] == [a for a in AA if a != "I"]
        assert all(m[0][:2] == (44, "I") for m in muts)


class TestStatsAndHeadline:
    def test_distribution_stats_pinned(self):
        s = distribution_stats([1, 2, 3, 4, 5, 6, 7, 8])
        assert s["mean"] == 4.5
        assert s["median"] == 4.5
        assert s["min"] == 1 and s["max"] == 8
        assert math.isclose(s["iqr"], 3.5)
        assert math.isclose(s["std"], math.sqrt(5.25))  # population std

    def test_quantile_interpolation_odd_n(self):
        s = distribution_stats([0.0, 1.0, 10.0])
        assert s["median"] == 1.0
        # linear convention: q25 = 0 + 0.5·1 = 0.5, q75 = 1 + 0.5·9 = 5.5
        assert math.isclose(s["iqr"], 5.0)

    def test_headline_level_bands(self):
        assert sensitivity_headline({"median": 0.9, "iqr": 0.1}, 0.9)["level"] == "quiet"
        assert sensitivity_headline({"median": 2.1, "iqr": 0.4}, 0.1)["level"] == "strong"
        assert sensitivity_headline({"median": 1.2, "iqr": 0.4}, 0.3)["level"] == "moderate"
        # |ΔpLDDT| alone can push to strong
        assert sensitivity_headline({"median": 0.5, "iqr": 0.1}, 2.0)["level"] == "strong"

    def test_headline_width_bands(self):
        assert sensitivity_headline({"median": 1.0, "iqr": 0.1}, 0.0)["width"] == "narrow"
        assert sensitivity_headline({"median": 1.0, "iqr": 0.4}, 0.0)["width"] == "moderate"
        assert sensitivity_headline({"median": 1.0, "iqr": 0.9}, 0.0)["width"] == "wide"