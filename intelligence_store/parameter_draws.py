"""Draws of published fixed-effect estimates matched to their bootstrap 95% intervals (AI review F08, 12 November 2026).

Shared by the typical-curve uncertainty in Patient Lab (population_pk) and by acceptance rule v2 for the published-model
checks. Each estimate is drawn from a two-piece log-normal: median at the published estimate, log-scale SD below it set
so the 2.5th percentile is the interval's lower end, and above it so the 97.5th percentile is the upper end. Both
published percentiles are reproduced and an asymmetric interval stays asymmetric. Estimates are drawn independently
because the papers do not publish their covariance. Every draw is positive by construction.
"""
import math

Z975 = 1.959963984540054


def spreads(estimates):
    """{name: (estimate, [lo, hi])} -> {name: (estimate, sd_below, sd_above)}, in the given order."""
    out = {}
    for name, (estimate, interval) in estimates.items():
        lo, hi = interval
        if not 0 < lo < estimate < hi:
            raise ValueError(f'{name}: the bootstrap interval does not bracket a positive estimate.')
        out[name] = (estimate, math.log(estimate / lo) / Z975, math.log(hi / estimate) / Z975)
    return out


def draw(rng, spread):
    """One draw of every estimate, in order, from a random.Random."""
    d = {}
    for name, (estimate, below, above) in spread.items():
        z = rng.gauss(0.0, 1.0)
        d[name] = estimate * math.exp(z * (below if z < 0 else above))
    return d
