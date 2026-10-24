"""H2 -- overpriced heavy favourites (zlecenie section 4, H2; sections 5, 10.4, 10.8).

Usage: .venv/bin/python backtest_h2.py   -> reports/h2_results.json, reports/h2_signals.csv
"""
import json
from pathlib import Path

import pandas as pd

import config
import snapshots
import stats

REPORTS = Path(__file__).resolve().parent / "reports"


def signals_all(matches, snaps):
    """Every match with Pinnacle open + close; signal flag from the open (results not needed).
    Used by fetch_history.py to allocate paid results (10.8) and by run()."""
    by_match = snapshots.books_by_match(snaps)
    rows = []
    for m in matches.itertuples(index=False):
        books = by_match.get(m.match_id, {})
        pin = books.get(config.PINNACLE)
        if pin is None:
            continue
        opened, close = pin.open(), pin.close(m.start_time)
        if opened is None or close is None:
            continue
        p_open = stats.devig(*opened[1])
        fav = "a" if p_open[0] > p_open[1] else "b"
        dog = "b" if fav == "a" else "a"
        p_fav = max(p_open)
        o_close = dict(zip("ab", close))
        soft_close = [b.close(m.start_time) for n, b in books.items() if n in config.SOFT_BOOKS]
        best_soft_dog = max((dict(zip("ab", c))[dog] for c in soft_close if c), default=None)
        rows.append({
            "match_id": m.match_id, "start_time": m.start_time, "p_fav_open": p_fav,
            "fav": fav, "dog": dog, "p_close_fav": stats.devig(*close)[0 if fav == "a" else 1],
            "o_taken": o_close[dog], "best_soft_close_dog": best_soft_dog,
            "signal": p_fav >= config.H2_PFAV_MIN, "winner": m.winner,
        })
    return pd.DataFrame(rows)


def run(matches, snaps):
    allm = signals_all(matches, snaps)
    if allm.empty:
        return allm, allm
    allm["fav_won"] = [None if pd.isna(w) else w == f for w, f in zip(allm["winner"], allm["fav"])]
    sig = allm[allm["signal"]].copy()
    sig["won"] = [None if fw is None else not fw for fw in sig["fav_won"]]  # underdog bet
    sig["pl"] = [None if pd.isna(w) else stats.flat_pl(o, w) for o, w in zip(sig["o_taken"], sig["won"])]
    sig["pl_best_soft"] = [None if pd.isna(w) or pd.isna(o) else stats.flat_pl(o, w)
                           for o, w in zip(sig["best_soft_close_dog"], sig["won"])]
    return allm, sig


def verdict(allm, sig):
    settled = sig[sig["won"].notna()]
    n = len(settled)
    out = {"matches_open_close": len(allm), "signals": len(sig), "n": n, "roi": None, "ci": None}
    if n:
        out["roi"] = float(settled["pl"].astype(float).mean())
        out["ci"] = stats.bootstrap_ci(settled["pl"].astype(float))
    if len(allm) < config.H2_MIN_MATCHES_OPEN_CLOSE or n < config.H2_MIN_N:
        out["verdict"] = config.UNDECIDABLE
    elif out["ci"][0] > 0:
        out["verdict"] = config.PASS
    else:
        out["verdict"] = config.FAIL
        if out["roi"] > 0:
            out["note"] = "za słaby sygnał przy tej próbie"
    return out


def calibration(allm):
    """Pinnacle close calibration in p_fav buckets, on matches with a result only."""
    s = allm[allm["fav_won"].notna()].copy()
    if s.empty:
        return []
    edges = config.H2_CALIBRATION_BUCKETS
    s["bucket"] = pd.cut(s["p_fav_open"], edges, right=False, include_lowest=True)
    out = []
    for b, g in s.groupby("bucket", observed=True):
        won = g["fav_won"].astype(float)
        ci = stats.bootstrap_ci(won)
        out.append({"bucket": str(b), "n": len(g), "predicted_close": float(g["p_close_fav"].mean()),
                    "realized": float(won.mean()), "ci": ci})
    return out


def descriptive(allm, sig):
    settled = sig[sig["won"].notna()]
    if settled.empty:
        return {"calibration": calibration(allm)}
    q = settled["start_time"].dt.to_period("Q").astype(str)
    soft = settled["pl_best_soft"].dropna().astype(float)
    return {
        "calibration": calibration(allm),
        "roi_best_soft_close": {"n": len(soft), "roi": float(soft.mean()) if len(soft) else None},
        "per_quarter": settled.assign(pl=settled["pl"].astype(float)).groupby(q)["pl"].agg(["count", "mean"]).round(4).to_dict("index"),
        "bo_split": "niedostępne w źródle (zlecenie 10.9)",
    }


def main():
    matches, snaps = snapshots.load()
    allm, sig = run(matches, snaps)
    result = verdict(allm, sig)
    result["descriptive"] = descriptive(allm, sig)
    REPORTS.mkdir(exist_ok=True)
    sig.to_csv(REPORTS / "h2_signals.csv", index=False)
    (REPORTS / "h2_results.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("matches_open_close", "signals", "n", "roi", "ci", "verdict")}, default=str))


if __name__ == "__main__":
    main()
