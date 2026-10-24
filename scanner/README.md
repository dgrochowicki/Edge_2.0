# scanner — etap 0 (backtest-bramka G0)

Backtest dwóch zamrożonych hipotez (H1: miękki bukmacher odstaje od Pinnacle; H2: przewartościowani wysocy faworyci) na historii kursów CS2 z OddsPapi. Reguły: [zlecenie](../docs/decisions/2026-10-24-etap0-zlecenie.md), sekcje 3, 4, 10; progi w `config.py`.

Środowisko (raz): `~/.local/bin/uv venv --python 3.11 .venv && ~/.local/bin/uv pip install --python .venv/bin/python -r requirements.txt`. Klucz: `ODDSPAPI_KEY` w `../.env`.

Uruchomienie (z `scanner/`):
1. `.venv/bin/python -m unittest discover -s tests` — muszą być zielone.
2. `.venv/bin/python fetch_history.py` — lista meczów, kursy, wyniki (cache w `data/raw/`, log w `data/api_usage.json`).
3. `.venv/bin/python build_dataset.py` — `data/matches.csv`, `data/snapshots.csv`.
4. `.venv/bin/python backtest_h1.py` i `backtest_h2.py` — wyniki w `reports/`.
