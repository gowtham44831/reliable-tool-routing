"""Binomial confidence intervals for single-scenario error/accept rates.

The query-grouped bootstrap in ``metrics.py`` is the right tool for paired
comparisons between scenarios/policies (it resamples whole queries so
correlated scenario variants move together). It is the wrong tool for
stating "this individual rate is probably 0" from a small, all-zero
sample: resampling a set of all-zero draws can only ever produce more
zeros, so a naive bootstrap CI on an all-correct/all-incorrect sample is
degenerate (``[0, 0]``) and is not evidence that the population rate is
actually 0.

This module provides a closed-form Wilson score interval (no scipy
dependency; matches this project's existing dependency set) for a single
binomial proportion ``k / n``, which:

* Is well-behaved at ``k == 0`` or ``k == n`` (unlike the normal/Wald
  interval, which collapses to a zero-width ``[rate, rate]`` there).
* Does not require independence across resamples of the *same* fixed
  sample, only that the ``n`` underlying trials are the unit of analysis
  -- callers are responsible for using query-level (not row-level) counts
  when rows are correlated (see ``evaluation/metrics.py`` docstring).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BinomialCI:
    k: int
    n: int
    rate: float | None
    ci_low: float | None
    ci_high: float | None
    alpha: float
    method: str = "wilson"

    def to_dict(self) -> dict:
        return {
            "k": self.k,
            "n": self.n,
            "rate": self.rate,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "alpha": self.alpha,
            "method": self.method,
        }


def wilson_ci(k: int, n: int, alpha: float = 0.05) -> BinomialCI:
    """Wilson score interval for ``k`` successes out of ``n`` trials.

    ``alpha=0.05`` gives a 95% interval. Returns an explicit
    ``rate=None``/``ci_low=None``/``ci_high=None`` triple when ``n == 0``
    (undefined), rather than 0.0, mirroring the "explicit undefined" style
    used elsewhere in this codebase (e.g. ``MetricsResult.selective_risk``).
    """
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"invalid k={k}, n={n}")
    if n == 0:
        return BinomialCI(k=k, n=n, rate=None, ci_low=None, ci_high=None, alpha=alpha)

    # z = inverse-CDF of the standard normal at 1 - alpha/2, via a closed
    # form rational approximation (Acklam-free, good to ~1e-9 over the
    # alpha ranges used here) -- avoids a scipy dependency for a single
    # two-sided quantile.
    z = _norm_ppf(1 - alpha / 2)
    p_hat = k / n
    denom = 1 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half_width = (z * math.sqrt((p_hat * (1 - p_hat) / n) + (z * z / (4 * n * n)))) / denom
    lo = max(0.0, center - half_width)
    hi = min(1.0, center + half_width)
    return BinomialCI(k=k, n=n, rate=p_hat, ci_low=lo, ci_high=hi, alpha=alpha)


def _norm_ppf(p: float) -> float:
    """Standard normal quantile function (inverse CDF).

    Peter Acklam's rational approximation, relative error < 1.15e-9 over
    (0, 1). Good enough for the alpha=0.01/0.05/0.1 interval widths used in
    this project; not a general-purpose stats library replacement.
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0, 1), got {p}")

    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]

    p_low = 0.02425
    p_high = 1 - p_low

    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
            (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
        )
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
    )
