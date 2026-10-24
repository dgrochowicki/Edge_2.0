#!/usr/bin/env python3
"""Validate the coupon ledger in data/bets.json.

Migrated from Edge/scripts/validate_bets.py (zlecenie A3). The Edge validator
checked only `predictions` (v1/v2/v3); those stay in the Edge archive, so the
prediction rules were dropped and coupon rules written in their place.

Usage: python3 scripts/validate_bets.py [path-to-bets.json]

Exit code 0 if there are zero hard errors. Flags are informational: they mark
coupons whose numbers legitimately differ from the simple formula (cash-out,
system bets, voided legs, STS tax variants). Coupons are immutable, so a flag
is never "fixed" by editing an old entry.

Hard rules (every coupon):
    - id matches EDGE-NNN, unique, strictly increasing in file order
    - date is YYYY-MM-DD and non-decreasing in file order
    - type in {single, acca}; a single has exactly 1 selection, an acca >= 2
    - source in SOURCE_VALUES
    - status in {won, lost, void, pending}
    - stake_pln > 0; combined_odds > 1; gross_return_pln >= 0
    - net_result_pln == gross_return_pln - stake_pln   (+/- 0.005)
    - potential_return_pln <= stake_pln * combined_odds (+/- 0.01)
    - status pending -> gross_return_pln == 0 and net_result_pln == 0
    - every selection has match, market, pick, odds > 1,
      result in {won, lost, void, pending}

Hard rules (summary block):
    - summary == recomputed from coupons: coupons, won, lost, voided, pending,
      total_staked_pln, gross_return_pln, net_result_pln (2 dp),
      roi == round(net / staked, 4)

Flags (informational):
    - combined_odds_mismatch: combined_odds != product of selection odds (> 0.02)
    - cash_out: won with gross != potential, or lost with gross > 0
    - won_with_lost_leg: status won but a selection is lost (system bet)
"""
import json
import math
import re
import sys
from pathlib import Path

TYPE_VALUES = {"single", "acca"}
SOURCE_VALUES = {"user_bet", "recommendation_gpt", "recommendation_claude", "official_recommendation"}
STATUS_VALUES = {"won", "lost", "void", "pending"}
SELECTION_FIELDS = ["match", "market", "pick", "odds", "result"]
ID_RE = re.compile(r"^EDGE-(\d{3,})$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def expected_summary(coupons):
    staked = sum(c["stake_pln"] for c in coupons)
    gross = sum(c["gross_return_pln"] for c in coupons)
    net = sum(c["net_result_pln"] for c in coupons)
    count = lambda s: sum(1 for c in coupons if c.get("status") == s)
    return {
        "coupons": len(coupons),
        "won": count("won"),
        "lost": count("lost"),
        "voided": count("void"),
        "pending": count("pending"),
        "total_staked_pln": round(staked, 2),
        "gross_return_pln": round(gross, 2),
        "net_result_pln": round(net, 2),
        "roi": round(net / staked, 4) if staked else 0.0,
    }


def validate(coupons, summary):
    errors = []  # list of (id, message)
    flags = []   # list of (id, flag_name, detail)
    seen_ids = set()
    prev_num, prev_date = 0, ""

    for i, c in enumerate(coupons):
        cid = c.get("id") or f"(no id, index {i})"

        m = ID_RE.match(c.get("id") or "")
        if not m:
            errors.append((cid, "id does not match EDGE-NNN"))
        elif c["id"] in seen_ids:
            errors.append((cid, "duplicate id"))
        else:
            seen_ids.add(c["id"])
            if int(m.group(1)) <= prev_num:
                errors.append((cid, f"id not increasing (previous EDGE-{prev_num:03d})"))
            prev_num = int(m.group(1))

        date = c.get("date") or ""
        if not DATE_RE.match(date):
            errors.append((cid, f"bad date: {date!r}"))
        elif date < prev_date:
            errors.append((cid, f"date {date} earlier than previous coupon ({prev_date})"))
        else:
            prev_date = date

        sels = c.get("selections") or []
        ctype = c.get("type")
        if ctype not in TYPE_VALUES:
            errors.append((cid, f"bad type: {ctype!r}"))
        elif ctype == "single" and len(sels) != 1:
            errors.append((cid, f"single with {len(sels)} selections"))
        elif ctype == "acca" and len(sels) < 2:
            errors.append((cid, f"acca with {len(sels)} selections"))

        if c.get("source") not in SOURCE_VALUES:
            errors.append((cid, f"bad source: {c.get('source')!r}"))
        status = c.get("status")
        if status not in STATUS_VALUES:
            errors.append((cid, f"bad status: {status!r}"))

        stake, odds = c.get("stake_pln"), c.get("combined_odds")
        gross, net, pot = c.get("gross_return_pln"), c.get("net_result_pln"), c.get("potential_return_pln")
        if None in (stake, odds, gross, net, pot):
            errors.append((cid, "missing stake/odds/return fields"))
            continue
        if stake <= 0:
            errors.append((cid, f"stake_pln <= 0: {stake}"))
        if odds <= 1:
            errors.append((cid, f"combined_odds <= 1: {odds}"))
        if gross < 0:
            errors.append((cid, f"gross_return_pln < 0: {gross}"))
        if abs(gross - stake - net) > 0.005:
            errors.append((cid, f"net_result_pln {net} != gross - stake = {gross - stake:.2f}"))
        if pot > stake * odds + 0.01:
            errors.append((cid, f"potential_return_pln {pot} > stake * combined_odds = {stake * odds:.2f}"))
        if status == "pending" and (gross != 0 or net != 0):
            errors.append((cid, "pending coupon with non-zero gross/net"))

        for j, s in enumerate(sels):
            missing = [f for f in SELECTION_FIELDS if s.get(f) is None]
            if missing:
                errors.append((cid, f"selection {j} missing: {', '.join(missing)}"))
            if s.get("odds") is not None and s["odds"] <= 1:
                errors.append((cid, f"selection {j} odds <= 1: {s['odds']}"))
            if s.get("result") is not None and s["result"] not in STATUS_VALUES:
                errors.append((cid, f"selection {j} bad result: {s['result']!r}"))

        sel_odds = [s["odds"] for s in sels if s.get("odds")]
        if sel_odds and abs(math.prod(sel_odds) - odds) > 0.02:
            flags.append((cid, "combined_odds_mismatch", f"product {math.prod(sel_odds):.2f} vs {odds}"))
        if (status == "won" and abs(gross - pot) > 0.01) or (status == "lost" and gross > 0):
            flags.append((cid, "cash_out", f"{status}, gross {gross} vs potential {pot}"))
        if status == "won" and any(s.get("result") == "lost" for s in sels):
            flags.append((cid, "won_with_lost_leg", ""))

    exp = expected_summary(coupons)
    for k, v in exp.items():
        got = (summary or {}).get(k)
        if got != v:
            errors.append(("summary", f"{k} = {got!r}, recomputed from coupons = {v!r}"))

    return errors, flags


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = Path(args[0]) if args else Path(__file__).resolve().parent.parent / "data" / "bets.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    coupons = data.get("coupons", [])

    errors, flags = validate(coupons, data.get("summary"))

    print(f"Validated {len(coupons)} coupons.")
    by_flag = {}
    for _, name, _ in flags:
        by_flag[name] = by_flag.get(name, 0) + 1
    print(f"  flags (informational): {by_flag or 0}")
    print(f"  hard errors: {len(errors)}")
    for cid, msg in errors:
        print(f"    {cid}: {msg}")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
