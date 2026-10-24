"""De-vig, CLV, flat-stake P/L and bootstrap CI (zlecenie section 3)."""
import numpy as np

import config


def devig(o_a, o_b):
    """Multiplicative de-vig: p_A = (1/o_A) / (1/o_A + 1/o_B). Returns (p_a, p_b)."""
    ia, ib = 1.0 / o_a, 1.0 / o_b
    return ia / (ia + ib), ib / (ia + ib)


def clv(o_taken, p_close):
    """CLV of a signal = o_taken * p_close_X - 1 (p_close: Pinnacle close, de-vigged, side X)."""
    return o_taken * p_close - 1.0


def flat_pl(o, won):
    """P/L of a flat 1u stake: (o - 1) if X won, else -1."""
    return (o - 1.0) if won else -1.0


def bootstrap_ci(values, n_boot=config.BOOTSTRAP_N, seed=config.BOOTSTRAP_SEED,
                 percentiles=config.CI_PERCENTILES):
    """Percentile bootstrap CI of the mean. One value per match, so resampling
    values = resampling matches. Returns (lo, hi), or (nan, nan) for n < 2."""
    x = np.asarray(values, dtype=float)
    if len(x) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for start in range(0, n_boot, 1000):  # chunks keep memory flat for large n
        stop = min(start + 1000, n_boot)
        idx = rng.integers(0, len(x), size=(stop - start, len(x)))
        means[start:stop] = x[idx].mean(axis=1)
    lo, hi = np.percentile(means, percentiles)
    return float(lo), float(hi)
