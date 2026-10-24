# scanner — etap 0 (backtest-bramka G0)

Backtest dwóch zamrożonych hipotez (H1: miękki bukmacher odstaje od Pinnacle; H2: przewartościowani wysocy faworyci) na historii kursów CS2. Reguły: [../docs/decisions/2026-10-24-etap0-zlecenie.md](../docs/decisions/2026-10-24-etap0-zlecenie.md), sekcja 4.

**Stan:** w budowie. Kolejność: B0 (rozpoznanie API) → commit kodu (`config.py`, `stats.py`, `backtest_h1.py`, `backtest_h2.py`, `tests/`) → pobieranie danych → backtest → raport w `reports/`.

Klucz API tylko w zmiennej `ODDSPAPI_KEY` lub w `.env` (ignorowany przez git).

Instrukcja uruchomienia pojawi się tu razem z kodem.
