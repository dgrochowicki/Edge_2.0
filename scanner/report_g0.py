"""Write the G0 report (zlecenie section 6) from backtest outputs and the dataset.

Usage: .venv/bin/python report_g0.py   -> reports/<today>-g0.md
Inputs: reports/h1_results.json, h1_signals.csv, h2_results.json, data/*.csv,
Edge predictions read-only from GitHub raw at a pinned commit (A7).
"""
import json
import re
import subprocess
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

import config
import results_vrs
import snapshots
import stats

HERE = Path(__file__).resolve().parent
REPORTS, DATA = HERE / "reports", HERE / "data"
RULES_COMMIT, CODE_COMMIT = "6c8f76f", "8bbfe46"
PL_BOOKS = ["efortuna.pl", "superbet.pl"]
LICENSE_PL = {"efortuna.pl": "tak", "superbet.pl": "tak", "betway": "niepewna", "bet365": "nie",
              "unibet": "nie", "stake": "nie", "1xbet": "nie (niepotwierdzone)"}


def pct(x, d=1):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:+.{d}f}%"


def ci(c):
    return "—" if not c or any(np.isnan(v) for v in c) else f"[{pct(c[0])}, {pct(c[1])}]"


def coverage(matches, snaps):
    books = snapshots.books_by_match(snaps)
    rows = []
    for m in matches.itertuples(index=False):
        bk = books.get(m.match_id, {})
        pin = bk.get(config.PINNACLE)
        oc = pin is not None and pin.open() is not None and pin.close(m.start_time) is not None
        lo, hi = m.start_time - config.H1_WINDOW_START, m.start_time - config.H1_WINDOW_END
        soft = [n for n in config.SOFT_BOOKS if n in bk and any(lo <= t <= hi for t in bk[n].times)]
        rows.append({"q": f"{m.start_time.year}Q{(m.start_time.month - 1) // 3 + 1}", "has_odds": bool(bk),
                     "pin_oc": oc, "soft_window": oc and bool(soft),
                     "n_snap": sum(len(b.times) for b in bk.values()) if bk else 0})
    return pd.DataFrame(rows)


def edge_check(matches, snaps):
    """Task G: STS de-vig from Edge predictions vs Pinnacle close de-vig (read-only, pinned commit)."""
    sha = subprocess.run(["git", "-C", str(HERE.parent.parent / "Edge"), "rev-parse", "origin/main"],
                         capture_output=True, text=True).stdout.strip()
    d = json.load(urllib.request.urlopen(f"https://raw.githubusercontent.com/dgrochowicki/Edge/{sha}/data/bets.json"))
    preds = sorted((p for p in d["predictions"] + d["archived_predictions"]
                    if p.get("market_odds_at_analysis") and p.get("market_odds_opponent") and " vs " in p.get("match", "")),
                   key=lambda p: (p["date"], p["id"]))
    books = snapshots.books_by_match(snaps)
    idx = {}
    for m in matches.itertuples(index=False):
        pin = books.get(m.match_id, {}).get(config.PINNACLE)
        close = pin.close(m.start_time) if pin else None
        if close:
            idx.setdefault((results_vrs.norm(m.team_a), results_vrs.norm(m.team_b)), []).append((m.start_time.date(), close))
    out, seen = [], set()
    for p in preds:
        a, b = [results_vrs.norm(x) for x in p["match"].split(" vs ", 1)]
        key = (p["date"], frozenset((a, b)))
        if key in seen:
            continue  # one entry per match: first by (date, id)
        seen.add(key)
        pick = results_vrs.norm(p["pick"])
        if pick not in (a, b):
            continue
        d0 = date.fromisoformat(p["date"])
        cands = [(c, False) for dd, c in idx.get((a, b), []) if abs((dd - d0).days) <= 1] + \
                [(c, True) for dd, c in idx.get((b, a), []) if abs((dd - d0).days) <= 1]
        if len(cands) != 1:
            continue
        close, flipped = cands[0]
        p_pin_a = stats.devig(*close)[1 if flipped else 0]          # Pinnacle close, team listed first in Edge
        o_pick, o_opp = p["market_odds_at_analysis"], p["market_odds_opponent"]
        o_a, o_b = (o_pick, o_opp) if pick == a else (o_opp, o_pick)
        p_sts_a = stats.devig(o_a, o_b)[0]
        pin_ov = 1 / close[0] + 1 / close[1]
        out.append({"p_sts": p_sts_a, "p_pin": p_pin_a, "margin_sts": 1 / o_a + 1 / o_b - 1, "margin_pin": pin_ov - 1})
    return sha, len(seen), pd.DataFrame(out)


def main():
    h1 = json.loads((REPORTS / "h1_results.json").read_text())
    h2 = json.loads((REPORTS / "h2_results.json").read_text())
    sig = pd.read_csv(REPORTS / "h1_signals.csv")
    matches, snaps = snapshots.load()
    usage = json.loads((DATA / "api_usage.json").read_text())
    billable = sum(u["billable"] for u in usage)
    vrs = pd.read_csv(DATA / "results_vrs.csv", dtype=str)
    no_hist = pd.read_csv(DATA / "no_history.csv")

    g0_pass = config.PASS in (h1["verdict"], h2["verdict"])
    both_undecidable = h1["verdict"] == h2["verdict"] == config.UNDECIDABLE
    g0 = config.PASS if g0_pass else (f"{config.FAIL} (brak danych)" if both_undecidable else config.FAIL)

    cov = coverage(matches, snaps)
    pl = sig[sig["book"].isin(PL_BOOKS)]
    pl_ci = stats.bootstrap_ci(pl["clv"]) if len(pl) >= 2 else (float("nan"),) * 2
    pl_status = "za mało, by decydować" if len(pl) < 50 else ("średni CLV > 0" if pl["clv"].mean() > 0 else "średni CLV ≤ 0")
    days = (matches.loc[cov["pin_oc"].values, "start_time"].max() - matches.loc[cov["pin_oc"].values, "start_time"].min()).days or 1
    h1_rate, h2_rate = h1["n"] / days, h2["matches_open_close"] / days

    L = []
    w = L.append
    w(f"# Raport G0 — Edge 2.0, etap 0 ({date.today()})\n")
    w(f"**Werdykt G0: {g0}.** "
      + ("Obie hipotezy nierozstrzygalne z powodu za małej próby (zlecenie, sekcja 5). " if both_undecidable else "")
      + f"Brakuje historii kursów: OddsPapi przechowuje ją dla CS2 od 2026-05-22 (~5 mies.); przy obecnym tempie "
        f"(~{h1_rate:.2f} sygnału H1/dzień) brakujące {max(0, config.H1_MIN_SIGNALS - h1['n'])} sygnały H1 daje ten sam darmowy endpoint po ~{max(0, (config.H1_MIN_SIGNALS - h1['n']) / h1_rate):.0f} dniach dalszego zbierania, "
        f"pod warunkiem zachowania już pobranych danych, bo dostawca trzyma ruchome okno ~5 mies. (koszt: 0 zł + kilka płatnych zapytań `fixtures`), a próg H2 (≥ 1 000 sygnałów z wynikiem, ~{h2['signals'] / max(h2['matches_open_close'], 1):.0%} meczów daje sygnał) jest poza zasięgiem tego źródła; "
        f"dłuższej historii Pinnacle dla CS2 nie znalazłem — koszt nieznany.\n")
    w("| Hipoteza | n | Metryka | 97,5% CI | Werdykt |\n|---|---|---|---|---|")
    w(f"| H1 | {h1['n']} sygnałów (próg 200) | średni CLV {pct(h1['mean_clv'], 2)} | {ci(h1['ci'])} | **{h1['verdict']}** |")
    w(f"| H2 | {h2['n']} sygnałów z wynikiem; {h2['matches_open_close']} meczów z Pinnacle open+close (próg 1 000) | ROI 1u {pct(h2['roi'])} (opisowo) | {ci(h2['ci'])} | **{h2['verdict']}** |\n")
    w(f"**Warunek przejścia do etapu 1** (CHANGELOG, zapisany przed backtestem): podzbiór H1 z booków z licencją PL "
      f"({', '.join(PL_BOOKS)}): n = {len(pl)}, średni CLV {pct(pl['clv'].mean() if len(pl) else None, 2)}, 97,5% CI {ci(pl_ci)} → **{pl_status}**. "
      f"Warunek {'spełniony' if pl_status == 'średni CLV > 0' else 'niespełniony'}.\n")

    w("## 2. Wersje, dane, dostawca\n")
    w(f"- Reguły: commit `{RULES_COMMIT}` (zlecenie), rewizja `d7264ec` (sekcja 10); kod: commit `{CODE_COMMIT}` (pliki bez zmian do uruchomienia backtestu).")
    w(f"- Kursy: OddsPapi v4 (`historical-odds`, bezpłatne), pobrane 2026-10-24; lista meczów `fixtures` (płatne). Zużycie: {billable} płatnych zapytań / limit 200.")
    w(f"- Wyniki: publiczne dane Valve VRS (`ValveSoftware/counter-strike_regional_standings` @ `eec4853`, do 2026-10-05) — odstępstwo O9.")
    w("- Odtworzenie: `scanner/data/raw/` (659 MB) poza git; backtest odtwarzalny bez API z `data/matches.csv`, `data/snapshots.csv` "
      "(w repo) przez `backtest_h1.py` / `backtest_h2.py`. Surowe dane: `fetch_history.py fixtures|odds`, `results_vrs.py`, `build_dataset.py` — "
      "uwaga: dostawca trzyma ruchome okno ~5 mies., więc te same surowe kursy da się pobrać ponownie tylko do ok. 2026-11 (dla najstarszych meczów); "
      "kopia `raw/` lokalnie u Doma.")
    w(f"- Start historii kursów CS2 u dostawcy: **2026-05-22** (dokumentacja: „od stycznia 2026”; zmierzone wyszukiwaniem binarnym). {len(no_hist)} meczów z `pinnacleId` sprzed tej daty: „brak historii u dostawcy”.\n")

    w("## 3. Pokrycie (zadanie C)\n")
    w("| | Mecze |\n|---|---|")
    w(f"| Mecze CS2 2026 w `fixtures` (statusId=2) | {len(matches)} |")
    w(f"| z `pinnacleId` | {int(pd.read_csv(DATA / 'matches.csv')['has_pinnacle_id'].sum())} |")
    w(f"| z kursami w oknie historii (≥ 1 snapshot rynku 171) | {int(cov['has_odds'].sum())} |")
    w(f"| z Pinnacle otwarcie + zamknięcie | {int(cov['pin_oc'].sum())} |")
    w(f"| z Pinnacle open+close i ≥ 1 miękkim bookiem w oknie H1 | {int(cov['soft_window'].sum())} |")
    w(f"| z wynikiem (VRS) wśród meczów z Pinnacle open+close | {int(matches.loc[cov['pin_oc'].values, 'winner'].notna().sum())} |")
    w(f"| STS | brak w źródle |\n")
    q = cov[cov["pin_oc"]].groupby("q").size()
    w("Mecze z Pinnacle open+close po kwartałach: " + ", ".join(f"{k}: {v}" for k, v in q.items()) + ".")
    w(f"Mediana liczby snapshotów (wszystkie booki, rynek 171, przed startem) na mecz z kursami: {int(cov.loc[cov['has_odds'], 'n_snap'].median())}.\n")
    per_book = snaps.groupby("book")["match_id"].nunique()
    listed = [config.PINNACLE] + list(config.SOFT_BOOKS)
    w("| Bukmacher | Mecze ze snapshotem | Rola | Licencja PL |\n|---|---|---|---|")
    for b in sorted(listed, key=lambda b: -per_book.get(b, 0)):
        role = "ostry (punkt odniesienia)" if b == config.PINNACLE else "miękki, kandydat H1"
        w(f"| {b} | {per_book.get(b, 0)} | {role} | {LICENSE_PL.get(b, '—')} |")
    other = per_book.drop(labels=[b for b in listed if b in per_book.index])
    w(f"\nInne booki: {len(other)} slugów, łącznie ≤ {int(other.max()) if len(other) else 0} mecz(e) każdy — wyłącznie z przerwanej sondy "
      f"wykrywania booków (nie pobierane systematycznie, poza H1 zgodnie z decyzją Doma).\n")
    w(f"Dopasowanie wyników VRS: z `pinnacleId` i startem ≤ 2026-10-05 — 74,1% (1 493/2 015); walidacja na predykcjach `Edge`: 190/192 zgodnych (CHANGELOG O9).\n")

    w("## 4. H1 — miękki bukmacher odstaje od Pinnacle\n")
    w("| | Wartość |\n|---|---|")
    w(f"| Sygnały (n) | {h1['n']} (próg {config.H1_MIN_SIGNALS}) |")
    w(f"| Średni CLV vs zamknięcie Pinnacle | {pct(h1['mean_clv'], 2)} |")
    w(f"| 97,5% CI (bootstrap 20 000, seed {config.BOOTSTRAP_SEED}) | {ci(h1['ci'])} |")
    wk = h1["weekly"]
    w(f"| Sygnały / tydzień (tygodnie z ≥ 20 meczami: {wk['qualifying_weeks']}) | {wk['mean_per_week']:.2f} |")
    w(f"| Werdykt | **{h1['verdict']}** |\n")
    d = h1["descriptive"]
    w("Opisowo (nie rozstrzyga):\n")
    w(f"- P/L płaskiej stawki na sygnałach z wynikiem: n = {d['pl_flat']['n']}, suma {d['pl_flat']['sum_u']:+.2f} u, ROI {pct(d['pl_flat']['roi'])}.")
    w(f"- Odsetek sygnałów „domkniętych” (Pinnacle do zamknięcia przesunęło się w stronę B): {d['share_closed_toward_b']:.1%}.")
    w(f"- Średnia wartość w chwili sygnału {pct(sig['value'].mean(), 1)} vs średni CLV {pct(sig['clv'].mean(), 1)}: CLV w dużej mierze odtwarza próg wejścia (value ≥ 5%), Pinnacle średnio nie zbliża się do zamknięcia w stronę B ani od niej. Mediana kursu wejścia {sig['o_taken'].median():.2f}; mediana {((pd.to_datetime(sig['start_time']) - pd.to_datetime(sig['signal_time'])).dt.total_seconds() / 3600).median():.1f} h przed meczem.")
    w("- Kontrola danych (bez wyników): mediana |de-vig booka − de-vig Pinnacle| we wszystkich sparowanych snapshotach 0,3–2,3 pp, brak odwróconej orientacji stron. Nie weryfikowano, czy ceny były faktycznie grywalne (limity, opóźnienia aktualizacji).\n")
    w("| Book | Sygnały | Średni CLV | Licencja PL |\n|---|---|---|---|")
    for b, v in sorted(d["per_book"].items(), key=lambda kv: -kv[1]["count"]):
        w(f"| {b} | {v['count']} | {pct(v['mean'], 2)} | {LICENSE_PL.get(b, '—')} |")
    w("")
    w("Per kwartał: " + ", ".join(f"{k}: n={v['count']}, CLV {pct(v['mean'], 2)}" for k, v in d["per_quarter"].items()) + ".\n")

    w("## 5. H2 — przewartościowani wysocy faworyci\n")
    w("| | Wartość |\n|---|---|")
    w(f"| Mecze z Pinnacle open+close | {h2['matches_open_close']} (próg {config.H2_MIN_MATCHES_OPEN_CLOSE}) |")
    w(f"| Sygnały (p_fav ≥ 0,75 na otwarciu) | {h2['signals']} |")
    w(f"| Sygnały z wynikiem (n) | {h2['n']} (próg {config.H2_MIN_N}) |")
    w(f"| ROI 1u na zamknięciu Pinnacle (opisowo) | {pct(h2['roi'])} |")
    w(f"| 97,5% CI (opisowo) | {ci(h2['ci'])} |")
    w(f"| Werdykt | **{h2['verdict']}** (sekcja 5) |\n")
    w("Kalibracja zamknięcia Pinnacle w kubełkach p_fav (otwarcie), tylko mecze z wynikiem VRS — opisowo:\n")
    w("| p_fav | n | przewidziane (zamknięcie) | zrealizowane | 97,5% CI |\n|---|---|---|---|---|")
    for c in h2["descriptive"]["calibration"]:
        w(f"| {c['bucket']} | {c['n']} | {c['predicted_close']:.3f} | {c['realized']:.3f} | {ci(c['ci']).replace('+', '')} |")
    rs = h2["descriptive"].get("roi_best_soft_close", {})
    w(f"\nROI na najlepszym miękkim kursie zamknięcia: n = {rs.get('n', 0)}, {pct(rs.get('roi'))}. Podział BO1/BO3+: niedostępny (format nie występuje w źródle).")
    w("Zastrzeżenie: próg 0,75 wybrano po obejrzeniu księgi Edge (n = 53–74), więc ten backtest jest pierwszym niezależnym testem.\n")

    sha, n_preds, g = edge_check(matches, snaps)
    w("## 6. Zgodność z księgą Edge (zadanie G)\n")
    w(f"Źródło: predykcje `Edge` @ `{sha[:7]}` (tylko odczyt), wpisy z oboma kursami STS, jeden na mecz ({n_preds}); dopasowanie: znormalizowane nazwy drużyn + data ±1 dzień, tylko jednoznaczne.\n")
    if len(g) >= 3:
        w("| | Wartość |\n|---|---|")
        w(f"| Dopasowane mecze (z Pinnacle zamknięcie) | {len(g)} |")
        w(f"| Korelacja de-vig STS vs de-vig Pinnacle zamknięcie | {np.corrcoef(g['p_sts'], g['p_pin'])[0, 1]:.3f} |")
        w(f"| Średnia różnica STS − Pinnacle | {(g['p_sts'] - g['p_pin']).mean() * 100:+.2f} pp (śr. |różnica| {(g['p_sts'] - g['p_pin']).abs().mean() * 100:.2f} pp) |")
        w(f"| Mediana marży STS / Pinnacle | {g['margin_sts'].median():.1%} / {g['margin_pin'].median():.1%} |\n")
    else:
        w(f"Dopasowanych meczów: {len(g)} — za mało na statystyki (predykcje Edge kończą się przed lub krótko po starcie historii kursów 2026-05-22).\n")

    w("## 7. Odstępstwa od zlecenia i otwarte pytania\n")
    ch = (HERE.parent / "CHANGELOG.md").read_text(encoding="utf-8")
    block = ch.split("## Odstępstwa od zlecenia")[1].split("\n## ")[0]
    w("Pełna lista w `CHANGELOG.md` (sekcje „Odstępstwa” i „Interpretacje”). Skrót:\n")
    for line in block.splitlines():
        m = re.match(r"\| (O\d+) \| ([^|]+) \| ([^|]+) \|", line)
        if m:
            w(f"- **{m.group(1)}** ({m.group(2).strip()}): {m.group(3).strip()}")
    w("\nOtwarte pytania:\n")
    w("- Status licencji PL dla `betway` i `1xbet` do potwierdzenia w rejestrze MF (`scanner/reports/2026-10-24-booki-licencje-pl.md`).")
    w("- Czy kontynuować darmowe zbieranie kursów (H1) do osiągnięcia 200 sygnałów — decyzja Doma; zgodnie z sekcją 4 G0 werdykt dziś brzmi jak wyżej, bez „prawie”.")

    out = REPORTS / f"{date.today()}-g0.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
