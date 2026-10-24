"""Odds-only coverage before the backtest (Dom, 2026-10-24): no results, no CLV, no signals.

Reads only data/snapshots.csv and fixture start times from the fixtures cache.
Reports: (1) first date with odds history, (2) matches with Pinnacle and >= 1 soft
book snapshot inside the H1 window, (3) soft books with their match counts.

Usage: .venv/bin/python coverage_odds.py
"""
import json

import pandas as pd

import config
import fetch_history
import oddspapi
import snapshots


def main():
    start = {f["fixtureId"]: pd.Timestamp(f["startTime"]) for f in fetch_history.all_fixtures()}
    snaps = pd.read_csv(oddspapi.DATA_DIR / "snapshots.csv", dtype={"match_id": str})
    snaps["t"] = pd.to_datetime(snaps["t"], utc=True)
    snaps["start"] = snaps["match_id"].map(start)

    statuses = {}
    for p in (oddspapi.RAW_DIR / "historical-odds").glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        statuses.setdefault(d["params"]["fixtureId"], set()).add(d.get("status", 200))
    with_odds = sorted(start[m] for m, s in statuses.items() if 200 in s)

    pin = snaps[snaps["book"] == config.PINNACLE]
    pin_matches = set(pin["match_id"])
    in_window = (snaps["t"] >= snaps["start"] - config.H1_WINDOW_START) & (snaps["t"] <= snaps["start"] - config.H1_WINDOW_END)
    soft = snaps[snaps["book"].isin(config.SOFT_BOOKS) & in_window & snaps["match_id"].isin(pin_matches)]
    per_book = soft.groupby("book")["match_id"].nunique().reindex(config.SOFT_BOOKS, fill_value=0)

    # H1 pairing (as in backtest_h1.find_signal, without computing value): soft snapshot t
    # in the window, latest Pinnacle snapshot tau <= t with t - tau <= 30 min and both
    # Pinnacle sides active at tau, soft book active on >= 1 side at t.
    books = snapshots.books_by_match(snaps[snaps["match_id"].isin(set(soft["match_id"]))].drop(columns="start"))
    paired = {b: set() for b in config.SOFT_BOOKS}
    for mid, g in soft.groupby("match_id"):
        p = books[mid][config.PINNACLE]
        for name, t in zip(g["book"], g["t"]):
            tau = p.latest_event(t)
            if tau is None or t - tau > config.H1_PIN_MAX_AGE or p.both(tau) is None:
                continue
            if books[mid][name].price("a", t) is not None or books[mid][name].price("b", t) is not None:
                paired[name].add(mid)
    paired_any = set().union(*paired.values())

    print(f"historical-odds requested for {len(statuses)} fixtures; with data: {len(with_odds)}")
    print(f"(1) first match with odds history: {with_odds[0] if with_odds else '-'}; last: {with_odds[-1] if with_odds else '-'}")
    print(f"    matches with Pinnacle moneyline (pre-start): {len(pin_matches)}")
    print(f"(2) Pinnacle + >= 1 soft book in H1 window: {soft['match_id'].nunique()}; "
          f"with H1 pairing (Pinnacle <= 30 min before): {len(paired_any)}")
    print("(3) soft books: matches in H1 window / with H1 pairing")
    for b, n in per_book.items():
        print(f"    {b:12s} {n:5d} / {len(paired[b])}")
    months = pd.Series(with_odds).dt.strftime("%Y-%m").value_counts().sort_index() if with_odds else pd.Series(dtype=int)
    print("    fixtures with odds per month:", months.to_dict())


if __name__ == "__main__":
    main()
