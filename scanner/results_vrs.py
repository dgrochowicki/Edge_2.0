"""Match winners from Valve's public VRS data (free source; replaces paid OddsPapi
settlements -- decision by Dom 2026-10-24, CHANGELOG O9).

Source: github.com/ValveSoftware/counter-strike_regional_standings, cloned to
data/vrs_repo/ (git-ignored). Every snapshot's live/<year>/details/<date>/*.md
holds one roster's match table (Date, Opponent, W/L) for the previous 6 months.

Matching to OddsPapi fixtures: same team pair (normalised names, participant
name or short name) and VRS date within +/-1 day of the fixture's UTC date.
Several candidates with different winners -> ambiguous, no winner (conservative).

Usage: .venv/bin/python results_vrs.py   -> data/results_vrs.csv
"""
import re
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

import fetch_history

DATA = Path(__file__).resolve().parent / "data"
VRS = DATA / "vrs_repo"
ROW = re.compile(r"^\|\s*\d+\s*\|\s*\d+\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(.+?)\s*\|\s*([WL])\s*\|")


def norm(name):
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s).split()
    if s and s[0] == "team":
        s = s[1:]
    while s and s[-1] in ("esports", "esport", "gaming"):
        s = s[:-1]
    return "".join(s)


def vrs_matches():
    """{(date, frozenset{a, b}): set of winners} over every snapshot's detail tables."""
    out = defaultdict(set)
    for f in VRS.glob("live/*/details/*/*.md"):
        team = None
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("Team Name:"):
                team = norm(line.split(":", 1)[1].replace("<br />", ""))
                continue
            m = ROW.match(line)
            if m and team:
                d, opp, wl = date.fromisoformat(m.group(1)), norm(m.group(2)), m.group(3)
                if opp and opp != team:
                    out[(d, frozenset((team, opp)))].add(team if wl == "W" else opp)
    return out


def match_fixtures(fixtures, vrs):
    rows = []
    for f in fixtures:
        names_a = {norm(f.get("participant1Name")), norm(f.get("participant1ShortName"))} - {""}
        names_b = {norm(f.get("participant2Name")), norm(f.get("participant2ShortName"))} - {""}
        d0 = date.fromisoformat(f["startTime"][:10])
        found = []  # (vrs_date, winner side)
        for dd in (-1, 0, 1):
            d = d0 + timedelta(days=dd)
            for a in names_a:
                for b in names_b:
                    for w in vrs.get((d, frozenset((a, b))), ()):
                        found.append((d, "a" if w == a else "b"))
        sides = {s for _, s in found}
        status = "matched" if len(sides) == 1 else ("ambiguous" if sides else "unmatched")
        rows.append({"match_id": f["fixtureId"], "status": status,
                     "winner": sides.pop() if status == "matched" else "",
                     "vrs_dates": ";".join(sorted({str(d) for d, _ in found}))})
    return pd.DataFrame(rows)


def main():
    vrs = vrs_matches()
    last = max(d for d, _ in vrs)
    res = match_fixtures(fetch_history.all_fixtures(), vrs)
    res.to_csv(DATA / "results_vrs.csv", index=False)
    print(f"VRS: {len(vrs)} distinct (date, pair) entries, last date {last}")
    print(res["status"].value_counts().to_dict())


if __name__ == "__main__":
    main()
