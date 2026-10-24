"""Download CS2 history from OddsPapi (zlecenie B, section 10). Resumable: every
response is cached in data/raw/, so re-running never repeats a request.

Usage (from scanner/):
  .venv/bin/python fetch_history.py fixtures   # paid, ~1 call / 9 days of season
  .venv/bin/python fetch_history.py markets    # paid, 1 call: checks moneyline outcome mapping (10.5)
  .venv/bin/python fetch_history.py odds       # free, 5 s per call: Pinnacle + SOFT_BOOKS
  .venv/bin/python fetch_history.py results    # paid, 1 call / match: allocation per 10.8
"""
import json
import sys
from datetime import datetime, timedelta, timezone

import config
import oddspapi

ISO = "%Y-%m-%dT%H:%M:%SZ"


def _dt(s):
    return datetime.strptime(s, ISO).replace(tzinfo=timezone.utc)


def cached_fixture_windows():
    """(from, to) of fixture windows already in the cache (B0), so they are reused."""
    out = []
    for p in (oddspapi.RAW_DIR / "fixtures").glob("*.json"):
        params = json.loads(p.read_text(encoding="utf-8"))["params"]
        if params.get("sportId") == config.SPORT_ID_CS2 and params.get("statusId") == 2:
            out.append((_dt(params["from"]), _dt(params["to"])))
    return sorted(out)


def fixture_windows():
    """Cover [SEASON_FROM, SEASON_TO) with cached windows plus gap windows of <= 9 days."""
    start, end = _dt(config.SEASON_FROM), _dt(config.SEASON_TO)
    step = timedelta(days=config.FIXTURE_WINDOW_DAYS)
    windows, cursor = [], start
    for a, b in cached_fixture_windows() + [(end, end)]:
        while cursor < min(a, end):
            nxt = min(cursor + step, a, end)
            windows.append((cursor, nxt))
            cursor = nxt
        if a < end:
            windows.append((a, b))
        cursor = max(cursor, b)
    return windows


def fixtures(client):
    seen = {}
    for a, b in fixture_windows():
        body, cached = client.get("fixtures", sportId=config.SPORT_ID_CS2, statusId=2,
                                  **{"from": a.strftime(ISO), "to": b.strftime(ISO)})
        for f in body:
            seen[f["fixtureId"]] = f
        print(f"{a:%Y-%m-%d}..{b:%Y-%m-%d}: {len(body)} fixtures{' (cache)' if cached else ''}")
    return list(seen.values())


def all_fixtures():
    """Fixtures from the cache only (no network)."""
    seen = {}
    for p in (oddspapi.RAW_DIR / "fixtures").glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d["params"].get("sportId") == config.SPORT_ID_CS2 and d.get("status", 200) == 200:
            for f in d["body"]:
                seen[f["fixtureId"]] = f
    start, end = config.SEASON_FROM.replace("Z", ".000Z"), config.SEASON_TO.replace("Z", ".000Z")
    return sorted((f for f in seen.values() if start <= f["startTime"] < end),
                  key=lambda f: (f["startTime"], f["fixtureId"]))


def markets(client):
    body, _ = client.get("markets")
    ml = [m for m in body if str(m["marketId"]) == config.MONEYLINE_MARKET]
    if not ml:
        sys.exit(f"market {config.MONEYLINE_MARKET} not found")
    m = ml[0]
    print(json.dumps({k: m.get(k) for k in ("marketId", "marketName", "marketType", "sportId", "period", "outcomes")}, ensure_ascii=False))
    names = {str(o["outcomeId"]): str(o["outcomeName"]) for o in m["outcomes"]}
    expected = {"171": "1", "172": "2"}
    if names != expected:
        sys.exit(f"STOP: outcome mapping {names} != {expected} assumed in config.OUTCOME_SIDE")
    print("mapping OK: 171 -> participant1 (a), 172 -> participant2 (b)")


def has_pinnacle_prestart(body, start_time):
    out = ((body.get("bookmakers") or {}).get(config.PINNACLE) or {}).get("markets", {}).get(config.MONEYLINE_MARKET)
    if not out:
        return False
    for o in out.get("outcomes", {}).values():
        for entries in o.get("players", {}).values():
            if any(e["createdAt"] < start_time for e in entries):
                return True
    return False


def odds(client):
    soft = config.SOFT_BOOKS
    groups = [[config.PINNACLE] + soft[:2], soft[2:5], soft[5:8]]
    fx = [f for f in all_fixtures() if (f.get("externalProviders") or {}).get("pinnacleId")]
    print(f"{len(fx)} fixtures with pinnacleId")
    stats = {"pinnacle_prestart": 0, "no_pinnacle": 0, "not_found": 0}
    for i, f in enumerate(fx, 1):
        try:
            body, _ = client.get("historical-odds", fixtureId=f["fixtureId"], bookmakers=",".join(groups[0]))
        except oddspapi.NotFound:
            stats["not_found"] += 1
            continue
        if not has_pinnacle_prestart(body, f["startTime"]):
            stats["no_pinnacle"] += 1
            continue
        stats["pinnacle_prestart"] += 1
        for g in groups[1:]:
            try:
                client.get("historical-odds", fixtureId=f["fixtureId"], bookmakers=",".join(g))
            except oddspapi.NotFound:
                pass
        if i % 50 == 0:
            print(f"{i}/{len(fx)} {stats}", flush=True)
    print(f"done {stats}")


def results(client):
    """Paid settlements, allocated per zlecenie 10.8: all H2 signals by
    (start_time, fixtureId), then H1 signals in the same order, until the limit."""
    import backtest_h1
    import backtest_h2
    import build_dataset
    import snapshots

    build_dataset.main()
    matches, snaps = snapshots.load()
    h2 = backtest_h2.signals_all(matches, snaps)
    h2 = h2[h2["signal"]].sort_values(["start_time", "match_id"])
    h1 = backtest_h1.run(matches.assign(winner=None), snaps).sort_values(["start_time", "match_id"])
    order = list(dict.fromkeys(list(h2["match_id"]) + list(h1["match_id"])))
    print(f"allocation: {len(h2)} H2 signals, {len(h1)} H1 signals, {len(order)} matches to settle")
    done = 0
    for mid in order:
        try:
            _, cached = client.get("settlements", fixtureId=mid)
            done += 0 if cached else 1
        except oddspapi.LimitExceeded as e:
            print(f"stop: {e}")
            break
        except oddspapi.NotFound:
            pass
    print(f"settlements fetched this run: {done}")
    build_dataset.main()


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    client = oddspapi.Client()
    if step == "fixtures":
        print(f"{len(fixtures(client))} unique fixtures")
    elif step == "markets":
        markets(client)
    elif step == "odds":
        odds(client)
    elif step == "results":
        results(client)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
