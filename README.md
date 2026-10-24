# Edge 2.0

Księga kuponów CS2 (STS, 1u = 2 PLN), dashboard kuponów i nowy skaner w budowie (`scanner/`).

- **Archiwum v1–v3** (lipiec–październik 2026: predykcje, raporty dzienne, metody): [dgrochowicki/Edge](https://github.com/dgrochowicki/Edge). Nic tam już nie logujemy.
- **Aktualne zlecenie:** [docs/decisions/2026-10-24-etap0-zlecenie.md](docs/decisions/2026-10-24-etap0-zlecenie.md) — etap 0, backtest-bramka G0.
- **Dashboard:** GitHub Pages tego repo (`index.html`, `dashboard/logs.html`).

## Struktura

```
index.html               dashboard kuponów
dashboard/               logs, sidebar, styles, shared-metrics, data.js, signals.html (zaślepka)
data/bets.json           księga kuponów — jedyne źródło prawdy o kuponach
scripts/validate_bets.py walidacja kuponów
docs/decisions/          zlecenia i decyzje
scanner/                 skaner / backtest (etap 0)
```

## Jak zalogować kupon

1. Podaj agentowi kupon: data, typ (single/acca), stawka, kurs łączny, potencjalna wygrana, nogi (mecz, rynek, typ, kurs), źródło (`user_bet`).
2. Agent dopisuje wpis na końcu `coupons` w `data/bets.json` z kolejnym id `EDGE-NNN` (status `pending`, `gross_return_pln` i `net_result_pln` = 0, wynik nóg `pending`).
3. Po meczu: rozliczenie — `status`, `result` każdej nogi, `gross_return_pln`, `net_result_pln = gross − stake` (cash-out opisany w `notes`).
4. Po każdej zmianie: `summary` przeliczony od zera z `coupons`, `updated_at` = dzisiejsza data, potem

   ```
   python3 scripts/validate_bets.py
   ```

   musi skończyć się `hard errors: 0` (walidator sprawdza też zgodność `summary` z kuponami).
5. Commit `data: log EDGE-NNN (...)` / `data: settle EDGE-NNN (...)` i push. Dashboard czyta `data/bets.json` z `main`.

Starych kuponów nie edytujemy — rozbieżności w historycznych wpisach (cash-out, system, podatek) walidator tylko flaguje.

## Jak uruchomić backtest

Zob. [scanner/README.md](scanner/README.md). W etapie 0 skaner istnieje tylko jako backtest (bez trybu na żywo).

## Lokalnie

```
python3 -m http.server 8000
# http://localhost:8000/index.html — lokalnie dashboard czyta data/bets.json z dysku
```
