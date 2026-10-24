"""H1 -- soft bookmaker off Pinnacle (zlecenie section 4, H1; section 10.6-10.8).

Usage: .venv/bin/python backtest_h1.py   -> reports/h1_results.json, reports/h1_signals.csv
"""
import json
from pathlib import Path

import pandas as pd

import config
import snapshots
import stats

REPORTS = Path(__file__).resolve().parent / "reports"


def find_signal(match, books):
    """First qualifying soft-book snapshot of one match, or None.

    For every snapshot time t of a candidate book B inside the window, take the
    latest Pinnacle snapshot tau <= t with t - tau <= 30 min (none -> skip),
    value_X = o_B,X(t) * p_pin,X(tau) - 1. Earliest t across all books wins;
    same t: higher value; equal value on opposite sides: no signal; equal value
    on the same side: alphabetically first book.
    """
    pin = books.get(config.PINNACLE)
    if pin is None:
        return None
    lo = match.start_time - config.H1_WINDOW_START
    hi = match.start_time - config.H1_WINDOW_END

    candidates = []  # (t, value, side, book, o_taken, p_pin)
    for name in sorted(books):
        if name not in config.SOFT_BOOKS or name in config.SHARP_BOOKS:
            continue
        book = books[name]
        for t in book.times:
            if t < lo or t > hi:
                continue
            tau = pin.latest_event(t)
            if tau is None or t - tau > config.H1_PIN_MAX_AGE:
                continue
            pair = pin.both(tau)
            if pair is None:
                continue
            p_pin = dict(zip("ab", stats.devig(*pair)))
            for side in "ab":
                o = book.price(side, t)
                if o is None:
                    continue
                value = o * p_pin[side] - 1.0
                if value >= config.H1_VALUE_MIN:
                    candidates.append((t, value, side, name, o, p_pin[side]))
    if not candidates:
        return None

    t_first = min(c[0] for c in candidates)
    at_first = [c for c in candidates if c[0] == t_first]
    best = max(c[1] for c in at_first)
    top = [c for c in at_first if c[1] == best]
    if len({c[2] for c in top}) > 1:
        return None  # equal value on opposite sides -> no signal
    t, value, side, book, o, p_pin_t = sorted(top, key=lambda c: c[3])[0]
    return {"t": t, "value": value, "side": side, "book": book, "o_taken": o, "p_pin_t": p_pin_t}


def run(matches, snaps):
    by_match = snapshots.books_by_match(snaps)
    rows = []
    for m in matches.itertuples(index=False):
        books = by_match.get(m.match_id, {})
        sig = find_signal(m, books)
        if sig is None:
            continue
        close = books[config.PINNACLE].close(m.start_time)
        if close is None:
            continue  # no Pinnacle close -> CLV undefined (counted in the report)
        p_close = dict(zip("ab", stats.devig(*close)))[sig["side"]]
        won = None if pd.isna(m.winner) else (m.winner == sig["side"])
        rows.append({
            "match_id": m.match_id, "start_time": m.start_time, "signal_time": sig["t"],
            "book": sig["book"], "side": sig["side"], "o_taken": sig["o_taken"],
            "p_pin_t": sig["p_pin_t"], "value": sig["value"], "p_close": p_close,
            "clv": stats.clv(sig["o_taken"], p_close),
            "closed_toward_b": p_close < sig["p_pin_t"],
            "won": won, "pl": None if won is None else stats.flat_pl(sig["o_taken"], won),
        })
    return pd.DataFrame(rows)


def weekly(matches, signals):
    """Mean signals per week over weeks with >= H1_WEEK_MIN_MATCHES matches (all listed fixtures)."""
    week = lambda s: s.dt.strftime("%G-W%V")
    per_week = week(matches["start_time"]).value_counts()
    qualifying = set(per_week[per_week >= config.H1_WEEK_MIN_MATCHES].index)
    n_sig = int(week(signals["start_time"]).isin(qualifying).sum()) if len(signals) else 0
    return {"qualifying_weeks": len(qualifying), "signals_in_qualifying_weeks": n_sig,
            "mean_per_week": n_sig / len(qualifying) if qualifying else 0.0}


def verdict(signals, wk):
    n = len(signals)
    out = {"n": n, "mean_clv": None, "ci": None, "weekly": wk}
    if n:
        out["mean_clv"] = float(signals["clv"].mean())
        out["ci"] = stats.bootstrap_ci(signals["clv"])
    if n < config.H1_MIN_SIGNALS:
        out["verdict"] = config.UNDECIDABLE
    elif out["ci"][0] > 0 and wk["mean_per_week"] >= config.H1_MIN_SIGNALS_PER_WEEK:
        out["verdict"] = config.PASS
    else:
        out["verdict"] = config.FAIL
    return out


def descriptive(signals):
    if signals.empty:
        return {}
    settled = signals[signals["won"].notna()]
    q = signals["start_time"].dt.to_period("Q").astype(str)
    return {
        "pl_flat": {"n": len(settled), "sum_u": float(settled["pl"].sum()) if len(settled) else None,
                    "roi": float(settled["pl"].mean()) if len(settled) else None},
        "per_book": signals.groupby("book")["clv"].agg(["count", "mean"]).round(4).to_dict("index"),
        "per_quarter": signals.groupby(q)["clv"].agg(["count", "mean"]).round(4).to_dict("index"),
        "share_closed_toward_b": float(signals["closed_toward_b"].mean()),
    }


def main():
    matches, snaps = snapshots.load()
    signals = run(matches, snaps)
    result = verdict(signals, weekly(matches, signals))
    result["descriptive"] = descriptive(signals)
    REPORTS.mkdir(exist_ok=True)
    signals.to_csv(REPORTS / "h1_signals.csv", index=False)
    (REPORTS / "h1_results.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("n", "mean_clv", "ci", "verdict")}, default=str))


if __name__ == "__main__":
    main()
