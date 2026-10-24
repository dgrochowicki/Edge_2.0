# AGENTS.md — zasady dla agentów w Edge_2.0

Repo: księga kuponów CS2, dashboard kuponów (GitHub Pages) i skaner (`scanner/`).
Archiwum v1–v3: dgrochowicki/Edge (tylko do odczytu).

## Kupony
- Kupony loguje się wyłącznie w `data/bets.json` → `coupons`; pola bez zmian względem formatu z `Edge`.
- Każdy wpis i każda zmiana przechodzi `python3 scripts/validate_bets.py` (0 hard errors), łącznie z `summary` przeliczonym od zera z kuponów.
- Starych kuponów się nie edytuje.

## Sekrety
- Klucze tylko w `.env` (ignorowany przez git) lub w zmiennych środowiskowych / sekretach repo.
- Nigdy w kodzie, logach, plikach danych, cache API ani commitach.

## Reguły metody
- Reguły są zamrożone w `docs/decisions/`. Każda zmiana reguł = nowy plik decyzji z datą (`RRRR-MM-DD-*.md`), nigdy edycja istniejącego.
- Progi w kodzie tylko w `scanner/config.py`, zgodne z obowiązującymi decyzjami.
- Nie twórz `METHOD.md` przed werdyktem G0.
- Każda zmiana, odstępstwo od zlecenia lub przyjęta interpretacja → wpis w `CHANGELOG.md` z hashem commitu.

## API
- Budżet API z B0 obowiązuje także po etapie 0: limit liczy OddsPapi (`request_count`, tylko zapytania płatne), twardy limit 200 płatnych / miesiąc.
- Każde wywołanie logowane w `scanner/data/api_usage.json`; odpowiedzi w cache `scanner/data/raw/`, bez powtórek.

## Predykcje v1–v3
- Są tylko w repo `Edge`; czytane wyłącznie w trybie tylko do odczytu (adres raw), nigdy kopiowane ani zmieniane.
