"""Bookmaker price state over time, built from pre-start snapshots.

Input (written by build_dataset.py):
  data/matches.csv    match_id, start_time (UTC ISO), tournament, team_a, team_b, winner ('a'/'b'/empty)
  data/snapshots.csv  match_id, book, side ('a'/'b'), t (UTC ISO), price, active (bool)
                      -- moneyline only, only snapshots with t < start_time (zlecenie 10.3)

Interpretations (recorded in the report, section 7):
  - The state of (book, side) at time t is its last snapshot with time <= t.
    If that snapshot is inactive (suspended), the side has no price at t.
  - A "Pinnacle snapshot" is any time a Pinnacle entry was recorded for
    either side; its state needs both sides active.
  - Open = Pinnacle state at the earliest moment both sides are active.
    Close = last active snapshot before start_time, per side.
"""
from bisect import bisect_right
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"


def load(data_dir=DATA_DIR):
    matches = pd.read_csv(data_dir / "matches.csv", dtype={"match_id": str, "winner": str})
    matches["start_time"] = pd.to_datetime(matches["start_time"], utc=True)
    matches["winner"] = matches["winner"].where(matches["winner"].isin(["a", "b"]))
    snaps = pd.read_csv(data_dir / "snapshots.csv", dtype={"match_id": str, "book": str, "side": str})
    snaps["t"] = pd.to_datetime(snaps["t"], utc=True)
    snaps["active"] = snaps["active"].astype(str).str.lower().isin(["true", "1"])
    return matches, snaps


class Side:
    """Price history of one (book, side), sorted by time."""

    def __init__(self, rows):
        rows = sorted(rows, key=lambda r: r[0])
        self.times = [r[0] for r in rows]
        self.rows = rows  # (t, price, active)

    def at(self, t):
        i = bisect_right(self.times, t)
        if i == 0:
            return None
        _, price, active = self.rows[i - 1]
        return price if active else None

    def last_active_before(self, t):
        for ts, price, active in reversed(self.rows[:bisect_right(self.times, t)]):
            if active and ts < t:
                return price
        return None


class Book:
    def __init__(self, df):
        self.side = {s: Side(list(zip(g["t"], g["price"], g["active"]))) for s, g in df.groupby("side")}
        for s in ("a", "b"):
            self.side.setdefault(s, Side([]))
        self.times = sorted(set(df["t"]))

    def price(self, side, t):
        return self.side[side].at(t)

    def both(self, t):
        pa, pb = self.price("a", t), self.price("b", t)
        return (pa, pb) if pa is not None and pb is not None else None

    def latest_event(self, t):
        i = bisect_right(self.times, t)
        return self.times[i - 1] if i else None

    def open(self):
        """(t_open, (o_a, o_b)) at the earliest time both sides are active, or None."""
        for t in self.times:
            pair = self.both(t)
            if pair:
                return t, pair
        return None

    def close(self, start_time):
        pa = self.side["a"].last_active_before(start_time)
        pb = self.side["b"].last_active_before(start_time)
        return (pa, pb) if pa is not None and pb is not None else None


def books_by_match(snaps):
    """{match_id: {book: Book}}"""
    out = {}
    for (mid, book), g in snaps.groupby(["match_id", "book"]):
        out.setdefault(mid, {})[book] = Book(g)
    return out
