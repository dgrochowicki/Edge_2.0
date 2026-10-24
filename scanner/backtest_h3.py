"""H3 -- does an Elo model on VRS results see something the market does not
(docs/decisions/2026-10-24-H3-zlecenie.md). Zero API calls.

Usage: .venv/bin/python backtest_h3.py   -> reports/h3_results.json, reports/h3_matches.csv
"""
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import config
import fetch_history
import h3_elo as h3
import snapshots
import stats

HERE = Path(__file__).resolve().parent
REPORTS, DATA = HERE / "reports", HERE / "data"


def ols2(gap, ctrl, move):
    """move = beta*gap + gamma*ctrl, no intercept. Returns (beta, gamma)."""
    X = np.column_stack([gap, ctrl])
    coef, *_ = np.linalg.lstsq(X, move, rcond=None)
    return float(coef[0]), float(coef[1])


def beta_ci(df, n_boot=h3.BOOTSTRAP_N, seed=h3.BOOTSTRAP_SEED):
    """Bootstrap over matches, refitting both coefficients each draw."""
    g, c, m = df["gap"].to_numpy(), (0.5 - df["p_open"]).to_numpy(), df["move"].to_numpy()
    if len(g) < 3:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    betas = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, len(g), len(g))
        betas[i] = ols2(g[idx], c[idx], m[idx])[0]
    lo, hi = np.percentile(betas, h3.CI_PERCENTILES)
    return float(lo), float(hi)


def mean_ci(values):
    return stats.bootstrap_ci(values, n_boot=h3.BOOTSTRAP_N, seed=h3.BOOTSTRAP_SEED, percentiles=h3.CI_PERCENTILES)


def t1_verdict(n, lo, hi):
    # Both conditions can hold (small but significant beta): conservative -> no signal (CHANGELOG).
    if hi < h3.T1_NO_SIGNAL_UPPER:
        return h3.NO_SIGNAL
    if n >= h3.T1_MIN_N and lo > 0:
        return h3.SIGNAL
    return h3.UNDECIDED


def build(matches, snaps):
    """One row per match with Pinnacle open + close; reasons for exclusion kept."""
    recs, conflicts = h3.records()
    ratings = h3.Ratings(recs)
    fx = {f["fixtureId"]: f for f in fetch_history.all_fixtures()}
    vrs_res = pd.read_csv(DATA / "results_vrs.csv", dtype=str).fillna("").set_index("match_id")
    books = snapshots.books_by_match(snaps)
    rows = []
    for m in matches.itertuples(index=False):
        pin = books.get(m.match_id, {}).get(config.PINNACLE)
        opened = pin.open() if pin else None
        close = pin.close(m.start_time) if pin else None
        if opened is None or close is None:
            continue
        f = fx[m.match_id]
        d0 = m.start_time.date()
        cutoff = h3.cutoff_for(d0)
        ka = h3.team_key(f.get("participant1Name"), f.get("participant1ShortName"), ratings.teams)
        kb = h3.team_key(f.get("participant2Name"), f.get("participant2ShortName"), ratings.teams)
        row = {"match_id": m.match_id, "start_time": m.start_time, "team_a": ka, "team_b": kb,
               "p_open": stats.devig(*opened[1])[0], "p_close": stats.devig(*close)[0],
               "o_open_a": opened[1][0], "o_open_b": opened[1][1], "winner": m.winner}
        if not ka or not kb or ka == kb:
            row["excluded"] = "drużyna poza VRS"
            rows.append(row)
            continue
        r, n = ratings.as_of(cutoff)
        if n.get(ka, 0) < h3.MIN_GAMES or n.get(kb, 0) < h3.MIN_GAMES:
            row["excluded"] = "< 10 meczów w historii"
            rows.append(row)
            continue
        # Explicit exclusion of the matched VRS record (section 1.4): it is dated d0 +/- 1,
        # i.e. after the cutoff, so it can never be in the rating; asserted here.
        vd = vrs_res.loc[m.match_id, "vrs_dates"] if m.match_id in vrs_res.index else ""
        assert all(date.fromisoformat(x) > cutoff for x in vd.split(";") if x), m.match_id
        row["p_elo"] = h3.p_win(r.get(ka, h3.START), r.get(kb, h3.START))
        row["frozen_ratings"] = cutoff > ratings.dates[-1]
        row["excluded"] = ""
        rows.append(row)
    df = pd.DataFrame(rows)
    ok = df["excluded"] == ""
    df.loc[ok, "gap"] = df.loc[ok, "p_elo"] - df.loc[ok, "p_open"]
    df.loc[ok, "move"] = df.loc[ok, "p_close"] - df.loc[ok, "p_open"]
    meta = {"vrs_matches": len(recs), "vrs_conflicts_dropped": conflicts,
            "vrs_from": str(recs[0][0]), "vrs_to": str(recs[-1][0])}
    return df, meta


def model_side_split(df):
    """'faworyt' when the side the model prefers is the market favourite at the open."""
    fav = ((df["gap"] > 0) & (df["p_open"] > 0.5)) | ((df["gap"] < 0) & (df["p_open"] < 0.5))
    return np.where(fav, "strona modelu = faworyt rynku", "strona modelu = underdog rynku")


def gap_bucket(g):
    a = g.abs()
    return pd.cut(a, [b[0] for b in h3.GAP_BUCKETS] + [h3.GAP_BUCKETS[-1][1]], right=False,
                  labels=["1–5 pp", "5–10 pp", "≥ 10 pp"])


def t1(df):
    d = df[(df["excluded"] == "") & (df["gap"].abs() >= h3.GAP_T1)]
    def fit(x):
        if len(x) < 3:
            return {"n": len(x), "beta": None, "gamma": None, "ci": None}
        b, gm = ols2(x["gap"].to_numpy(), (0.5 - x["p_open"]).to_numpy(), x["move"].to_numpy())
        return {"n": len(x), "beta": b, "gamma": gm, "ci": beta_ci(x)}
    main = fit(d)
    main["verdict"] = t1_verdict(main["n"], *(main["ci"] or (float("nan"),) * 2))
    naive = float((d["gap"] * d["move"]).sum() / (d["gap"] ** 2).sum()) if len(d) else None
    splits = {}
    for name, key in (("strona", model_side_split(d)), ("gap", gap_bucket(d["gap"]).astype(str))):
        splits[name] = {k: fit(g) for k, g in d.groupby(key)}
    return {**main, "naive_beta_without_control": naive, "frozen_ratings_n": int(d["frozen_ratings"].sum()),
            "splits": splits}


def t2(df):
    d = df[(df["excluded"] == "") & df["winner"].isin(["a", "b"]) & (df["gap"].abs() >= h3.GAP_T2)].copy()
    d["side"] = np.where(d["gap"] > 0, "a", "b")
    d["odds"] = np.where(d["side"] == "a", d["o_open_a"], d["o_open_b"])
    d["p_open_side"] = np.where(d["side"] == "a", d["p_open"], 1 - d["p_open"])
    d["p_close_side"] = np.where(d["side"] == "a", d["p_close"], 1 - d["p_close"])
    d["won"] = d["winner"] == d["side"]
    d["pl"] = np.where(d["won"], d["odds"] - 1, -1.0)
    d["clv"] = d["odds"] * d["p_close_side"] - 1

    def summ(x):
        return {"n": len(x), "hits": int(x["won"].sum()), "expected_hits_p_open": float(x["p_open_side"].sum()),
                "roi": float(x["pl"].mean()) if len(x) else None, "roi_ci": mean_ci(x["pl"]) if len(x) > 1 else None,
                "clv": float(x["clv"].mean()) if len(x) else None, "clv_ci": mean_ci(x["clv"]) if len(x) > 1 else None}
    out = summ(d)
    out["splits"] = {}
    if len(d):
        for name, key in (("strona", model_side_split(d)), ("gap", gap_bucket(d["gap"]).astype(str))):
            out["splits"][name] = {k: summ(g) for k, g in d.groupby(key)}
    return out


def t3(df):
    d = df[(df["excluded"] == "") & df["winner"].isin(["a", "b"])]
    y = (d["winner"] == "a").astype(float).to_numpy()
    out = {"n": len(d)}
    for col in ("p_elo", "p_open", "p_close"):
        p = np.clip(d[col].to_numpy(), 1e-6, 1 - 1e-6)
        out[col] = {"log_loss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
                    "brier": float(np.mean((p - y) ** 2))}
    return out


def main():
    matches, snaps = snapshots.load()
    df, meta = build(matches, snaps)
    t1_set = df[df["excluded"] == ""]
    res = {"meta": {**meta,
                    "pinnacle_open_close": len(df),
                    "excluded": df.loc[df["excluded"] != "", "excluded"].value_counts().to_dict(),
                    "set_t1": len(t1_set),
                    "set_t2t3": int(t1_set["winner"].isin(["a", "b"]).sum())},
           "T1": t1(df), "T2": t2(df), "T3": t3(df)}
    REPORTS.mkdir(exist_ok=True)
    df.to_csv(REPORTS / "h3_matches.csv", index=False)
    (REPORTS / "h3_results.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({"meta": res["meta"], "T1": {k: res["T1"][k] for k in ("n", "beta", "ci", "verdict")}},
                     ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
