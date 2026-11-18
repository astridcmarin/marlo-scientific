"""Draws of published fixed-effect estimates from their printed precision, for papers that publish %RSE or a 90%
interval instead of a bootstrap 95% interval (decision 0004, 17 November 2026).

`parameter_draws` covers the papers that publish bootstrap 95% intervals (Hughes 2019, Kim 2026) and is unchanged.
This module adds what the extension of acceptance rule v2 needs, and nothing it does not:

- marginals built from a %RSE, on the scale the paper says the %RSE belongs to;
- correlation between estimates, as scenarios, through a Gaussian copula: correlated standard normal deviates, each
  then mapped through its own marginal, so a marginal's shape is the same whatever the correlation;
- an alternative shape, normal on the natural scale, for a sensitivity analysis.

Every choice of which parameter, which scale and which correlation is made in the locked plan, not here. Nothing in
this module is validated for clinical prediction.
"""
import math

LOG_NORMAL = 'log_normal'
NORMAL = 'normal'
SD_RULES = ('rse_of_log_estimate', 'rse_as_cv', 'rse_of_value')
SHAPES = ('as_planned', 'normal_on_natural_scale')
MAX_REDRAWS = 1000


def marginal(name, entry, distribution, sd_rule, rse_add=0.0):
    """One marginal from an extract entry ({'value', 'rse_percent', optionally 'log_estimate'}).

    log_normal: median at `value`; sd on the log scale is
      rse_of_log_estimate: RSE x |log_estimate| (the RSE belongs to the log-scale estimate the paper prints), or
      rse_as_cv: sqrt(ln(1 + RSE^2)) (the RSE is a coefficient of variation of the natural-scale estimate).
    normal: mean at `value`, sd = RSE x |value| (rse_of_value).
    rse_add: added to the printed RSE in percentage points (the upper end of its rounding), for a sensitivity analysis.
    """
    if distribution not in (LOG_NORMAL, NORMAL):
        raise ValueError(f'{name}: unknown distribution {distribution!r}')
    if sd_rule not in SD_RULES:
        raise ValueError(f'{name}: unknown sd rule {sd_rule!r}')
    value = float(entry['value'])
    rse = (float(entry['rse_percent']) + rse_add) / 100.0
    if rse <= 0:
        raise ValueError(f'{name}: a printed RSE of {entry["rse_percent"]}% cannot be drawn; leave it out in the plan.')
    if distribution == LOG_NORMAL:
        if value <= 0:
            raise ValueError(f'{name}: a log-normal needs a positive estimate.')
        if sd_rule == 'rse_of_log_estimate':
            if 'log_estimate' not in entry:
                raise ValueError(f'{name}: no printed log-scale estimate for rse_of_log_estimate.')
            sd = rse * abs(float(entry['log_estimate']))
        elif sd_rule == 'rse_as_cv':
            sd = math.sqrt(math.log(1.0 + rse * rse))
        else:
            raise ValueError(f'{name}: rse_of_value is for normal marginals.')
    else:
        if sd_rule != 'rse_of_value':
            raise ValueError(f'{name}: a normal marginal takes rse_of_value.')
        sd = rse * abs(value)
    return {'name': name, 'distribution': distribution, 'centre': value, 'sd': sd}


def correlation_matrix(names, pairs=(), uniform=None, uniform_among=()):
    """A correlation matrix over `names`: `uniform` between every pair in `uniform_among`, then each (a, b, rho) in
    `pairs`. Refuses a matrix that is not positive definite."""
    index = {n: i for i, n in enumerate(names)}
    k = len(names)
    r = [[1.0 if i == j else 0.0 for j in range(k)] for i in range(k)]
    if uniform is not None:
        among = [index[n] for n in uniform_among]
        for a in among:
            for b in among:
                if a != b:
                    r[a][b] = float(uniform)
    for a, b, rho in pairs:
        if a not in index or b not in index:
            raise ValueError(f'correlation names a parameter that is not drawn: {a}, {b}')
        r[index[a]][index[b]] = r[index[b]][index[a]] = float(rho)
    cholesky(r)
    return r


def cholesky(r):
    """Lower-triangular L with L L^T = r. Raises if r is not positive definite."""
    k = len(r)
    low = [[0.0] * k for _ in range(k)]
    for i in range(k):
        for j in range(i + 1):
            s = math.fsum(low[i][m] * low[j][m] for m in range(j))
            if i == j:
                d = r[i][i] - s
                if d <= 1e-12:
                    raise ValueError('The correlation matrix is not positive definite.')
                low[i][j] = math.sqrt(d)
            else:
                low[i][j] = (r[i][j] - s) / low[j][j]
    return low


def correlated_normals(rng, low):
    u = [rng.gauss(0.0, 1.0) for _ in low]
    return [math.fsum(low[i][m] * u[m] for m in range(i + 1)) for i in range(len(low))]


def draw(rng, marginals, low, shape='as_planned'):
    """One draw of every marginal, in order. Returns ({name: value}, redraws).

    shape 'normal_on_natural_scale' replaces each log-normal by a normal on the natural scale with sd = centre x
    log-scale sd (the delta method); a non-positive value is redrawn from a fresh correlated vector, and the number
    of redraws is returned so the report can show it."""
    if shape not in SHAPES:
        raise ValueError(f'unknown shape {shape!r}')
    redraws = 0
    for _ in range(MAX_REDRAWS):
        z = correlated_normals(rng, low)
        out, ok = {}, True
        for m, zi in zip(marginals, z):
            if m['distribution'] == LOG_NORMAL and shape == 'as_planned':
                v = m['centre'] * math.exp(m['sd'] * zi)
            elif m['distribution'] == LOG_NORMAL:
                v = m['centre'] * (1.0 + m['sd'] * zi)
                ok = ok and v > 0
            else:
                v = m['centre'] + m['sd'] * zi
            out[m['name']] = v
        if ok:
            return out, redraws
        redraws += 1
    raise ValueError(f'No positive draw in {MAX_REDRAWS} attempts.')
