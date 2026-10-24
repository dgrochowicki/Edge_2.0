"""H3 model: Elo on VRS match results (docs/decisions/2026-10-24-H3-zlecenie.md, sections 1-3).

Frozen with the H3 code commit. Constants here are the H3 rules; do not tune.
"""
from bisect import bisect_right
from datetime import timedelta

import results_vrs

START = 1500.0
K = 32.0
MIN_GAMES = 10                  # each team needs >= 10 prior matches in the rating history
CUTOFF_DAYS = 2                 # rating uses VRS matches dated <= d0 - 2 (section 1.4)
GAP_T1 = 0.01                   # T1: |gap| >= 1 pp
GAP_T2 = 0.10                   # T2: |gap| >= 10 pp
GAP_BUCKETS = [(0.01, 0.05), (0.05, 0.10), (0.10, 1.01)]
CI_PERCENTILES = (2.5, 97.5)    # 95% (one decisive test; G0 used 97.5%)
BOOTSTRAP_N = 20_000
BOOTSTRAP_SEED = 20261024
T1_MIN_N = 200
T1_NO_SIGNAL_UPPER = 0.1
SIGNAL, NO_SIGNAL, UNDECIDED = "SYGNAŁ", "BRAK SYGNAŁU", "NIEROZSTRZYGALNE"


def p_win(r_a, r_b):
    return 1.0 / (1.0 + 10.0 ** ((r_b - r_a) / 400.0))


def records(vrs=None):
    """Deduplicated VRS history: one record per (date, pair). Same pair same day with
    conflicting winners -> dropped. Returns (sorted [(date, a, b, winner)], n_conflicts)."""
    vrs = vrs if vrs is not None else results_vrs.vrs_matches()
    out, conflicts = [], 0
    for (d, pair), winners in vrs.items():
        if len(winners) != 1:
            conflicts += 1
            continue
        a, b = sorted(pair)
        out.append((d, a, b, next(iter(winners))))
    out.sort()
    return out, conflicts


class Ratings:
    """Elo replayed chronologically (date, then team names). as_of(c) = state after
    every record dated <= c."""

    def __init__(self, recs):
        self.dates, self.states = [], []
        r, n = {}, {}
        for i, (d, a, b, w) in enumerate(recs):
            ra, rb = r.get(a, START), r.get(b, START)
            pa = p_win(ra, rb)
            sa = 1.0 if w == a else 0.0
            r[a], r[b] = ra + K * (sa - pa), rb - K * (sa - pa)
            n[a], n[b] = n.get(a, 0) + 1, n.get(b, 0) + 1
            if i + 1 == len(recs) or recs[i + 1][0] != d:
                self.dates.append(d)
                self.states.append((dict(r), dict(n)))
        self.teams = set().union(*(s[1] for s in self.states[-1:])) if self.states else set()

    def as_of(self, cutoff):
        i = bisect_right(self.dates, cutoff)
        return self.states[i - 1] if i else ({}, {})


def cutoff_for(d0):
    return d0 - timedelta(days=CUTOFF_DAYS)


def team_key(name, short, teams):
    """First normalised variant (name, then short name) that exists in VRS."""
    for v in (results_vrs.norm(name), results_vrs.norm(short)):
        if v and v in teams:
            return v
    return None
