"""Normalise cached OddsPapi responses into data/matches.csv and data/snapshots.csv
(zlecenie B, section 10). Reads data/raw/ only -- never calls the API.

snapshots.csv: moneyline (market 171) only, only createdAt < start_time (10.3).
matches.csv:   every listed fixture; winner from settlements when fetched
               ('a'/'b'; void/cancelled/unknown -> empty); open/close per book and side.
"""
import json
from collections import Counter

import pandas as pd

import config
import fetch_history
import oddspapi
import snapshots


def raw(endpoint):
    for p in sorted((oddspapi.RAW_DIR / endpoint).glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("status", 200) == 200:
            yield d


def snapshot_rows(fixtures):
    start = {f["fixtureId"]: f["startTime"] for f in fixtures}
    rows, seen = [], set()
    for d in raw("historical-odds"):
        mid = d["params"]["fixtureId"]
        if mid not in start:
            continue
        for book, bdata in (d["body"].get("bookmakers") or {}).items():
            market = (bdata.get("markets") or {}).get(config.MONEYLINE_MARKET)
            if not market:
                continue
            for oid, o in market.get("outcomes", {}).items():
                side = config.OUTCOME_SIDE.get(str(oid))
                if side is None:
                    continue
                for entries in o.get("players", {}).values():
                    for e in entries:
                        if e["createdAt"] >= start[mid]:
                            continue  # in-play / post-start (10.3)
                        key = (mid, book, side, e["createdAt"], e["price"])
                        if key in seen:
                            continue  # same book fetched twice in different groups
                        seen.add(key)
                        rows.append({"match_id": mid, "book": book, "side": side, "t": e["createdAt"],
                                     "price": e["price"], "active": bool(e.get("active", True))})
    return pd.DataFrame(rows, columns=["match_id", "book", "side", "t", "price", "active"])


def winners():
    """{fixtureId: 'a'|'b'|None} from settlements; anything but a clean WIN/LOSE pair -> None."""
    out, kinds = {}, Counter()
    for d in raw("settlements"):
        mid = d["params"]["fixtureId"]
        market = ((d["body"] or {}).get("markets") or {}).get(config.MONEYLINE_MARKET) or {}
        res = {}
        for oid, o in market.get("outcomes", {}).items():
            side = config.OUTCOME_SIDE.get(str(oid))
            players = o.get("players", {})
            if side and players:
                res[side] = next(iter(players.values())).get("result")
        if res == {"a": "WIN", "b": "LOSE"}:
            out[mid] = "a"
        elif res == {"a": "LOSE", "b": "WIN"}:
            out[mid] = "b"
        else:
            out[mid] = None
            kinds["/".join(f"{k}={v}" for k, v in sorted(res.items())) or "no market 171"] += 1
    return out, kinds


def main():
    fixtures = fetch_history.all_fixtures()
    snaps = snapshot_rows(fixtures)
    win, unsettled = winners()

    snaps_t = snaps.assign(t=pd.to_datetime(snaps["t"], utc=True))
    books = snapshots.books_by_match(snaps_t) if len(snaps_t) else {}
    rows = []
    for f in fixtures:
        mid = f["fixtureId"]
        start = pd.Timestamp(f["startTime"])
        row = {"match_id": mid, "start_time": f["startTime"], "tournament": f.get("tournamentName"),
               "category": f.get("categoryName"), "tier": "", "format": "",
               "team_a": f.get("participant1Name"), "team_b": f.get("participant2Name"),
               "has_pinnacle_id": bool((f.get("externalProviders") or {}).get("pinnacleId")),
               "settled": mid in win, "winner": win.get(mid) or ""}
        for name, b in books.get(mid, {}).items():
            opened, close = b.open(), b.close(start)
            row[f"{name}_n_snap"] = len(b.times)
            if opened:
                row[f"{name}_open_a"], row[f"{name}_open_b"] = opened[1]
            if close:
                row[f"{name}_close_a"], row[f"{name}_close_b"] = close
        rows.append(row)

    data = oddspapi.DATA_DIR
    pd.DataFrame(rows).to_csv(data / "matches.csv", index=False)
    snaps.to_csv(data / "snapshots.csv", index=False)
    print(f"matches.csv: {len(rows)} fixtures, {snaps['match_id'].nunique()} with moneyline snapshots, "
          f"{sum(1 for r in rows if r['winner'])} with winner; snapshots.csv: {len(snaps)} rows; "
          f"settlements without clean winner: {dict(unsettled)}")


if __name__ == "__main__":
    main()
