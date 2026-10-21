from tool_routing.evaluation.binomial_ci import wilson_ci


def test_zero_n_is_explicitly_undefined():
    ci = wilson_ci(0, 0)
    assert ci.rate is None
    assert ci.ci_low is None
    assert ci.ci_high is None


def test_zero_successes_has_nonzero_upper_bound():
    # 0/20 correct (or incorrect) should NOT be reported as a point-mass
    # at 0 -- the Wilson interval's upper bound must be > 0, unlike a
    # naive bootstrap of an all-zero sample.
    ci = wilson_ci(0, 20)
    assert ci.rate == 0.0
    assert ci.ci_low == 0.0
    assert ci.ci_high > 0.0


def test_all_successes_has_nonone_lower_bound():
    ci = wilson_ci(20, 20)
    assert ci.rate == 1.0
    assert ci.ci_high == 1.0
    assert ci.ci_low < 1.0


def test_midpoint_interval_is_symmetric_ish_and_contains_point_estimate():
    ci = wilson_ci(50, 100)
    assert ci.rate == 0.5
    assert ci.ci_low < 0.5 < ci.ci_high


def test_wider_n_gives_narrower_interval():
    small = wilson_ci(5, 10)
    large = wilson_ci(500, 1000)
    assert large.rate == small.rate == 0.5
    assert (large.ci_high - large.ci_low) < (small.ci_high - small.ci_low)


def test_rejects_invalid_counts():
    import pytest

    with pytest.raises(ValueError):
        wilson_ci(5, 2)
    with pytest.raises(ValueError):
        wilson_ci(-1, 5)


def test_known_wilson_value_matches_reference():
    # Reference value for 95% Wilson interval, k=0, n=20: commonly cited
    # as approximately (0, 0.161) (e.g. Newcombe 1998, Table II analogue).
    ci = wilson_ci(0, 20, alpha=0.05)
    assert abs(ci.ci_high - 0.161) < 0.01
