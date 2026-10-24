# Changelog — Edge_2.0

Dziennik zmian, odstępstw od zlecenia i przyjętych interpretacji. Najnowsze na górze.
Reguły metody są w `docs/decisions/` (zmiana reguł = nowy plik decyzji); tu tylko ślad, co i dlaczego, z hashem commitu.

## Otwarte pytania

- Licencja PL dla `betway` i `1xbet` — do potwierdzenia w rejestrze MF.
- Czy kontynuować darmowe zbieranie kursów dla H1 (brakuje 37 sygnałów, ~35 dni) — decyzja Doma.

## Odstępstwa od zlecenia (do sekcji 7 raportu G0)

| # | Gdzie | Odstępstwo | Powód | Commit |
|---|---|---|---|---|
| O1 | A1 | `AGENTS.md` w osobnym commicie, nie w commicie migracji | migracja była już wypchnięta; wstawienie wymagałoby przepisania historii | `eb1a4c5` |
| O2 | A3 | walidator kuponów napisany od nowa zamiast „okrojony” | stary walidator sprawdzał tylko predykcje, nie miał reguł kuponów | `3446127` |
| O3 | 4/H1 | kandydaci na B: 7 booków (`bet365`, `1xbet`, `efortuna.pl`, `superbet.pl`, `betway`, `unibet`, `stake`) zamiast „wszystkie pozostałe” | 348 booków × 5 s / zapytanie, max 3 booki na zapytanie — niewykonalne czasowo; wariant konserwatywny (mniej sygnałów) | `d7264ec` |
| O4 | B | zakres danych: historia kursów od 2026-05-22 (zamiast od 2024-01-01); 1 364 mecze z `pinnacleId` sprzed tej daty oznaczone „brak historii u dostawcy” (`data/no_history.csv`), 813 w oknie z historią | źródło nie ma starszej historii (wyszukiwanie binarne: ostatnie 404 2026-05-22 14:00 UTC, pierwsze dane 23:00 UTC) | `d7264ec`, `bfb6dec` |
| O5 | 4/H2 | brak podziału BO1 vs BO3+ | źródło nie podaje formatu | `d7264ec` |
| O6 | C, G | brak wiersza STS w pokryciu | STS nie występuje w OddsPapi | `d7264ec` |
| O7 | 10.8 | wyniki z `settlements` zamiast `scores` | ten sam koszt; zwycięzca wprost z rynku 171 (WIN/LOSE) | `984e267` |
| O8 | rewizja | rewizja `d7264ec` edytowała plik zlecenia | zasada „nowy plik decyzji” (AGENTS.md) wprowadzona później | `eb1a4c5` |
| O9 | 10.8, B | wyniki meczów z publicznych danych Valve VRS (github.com/ValveSoftware/counter-strike_regional_standings @ `eec4853`, snapshoty do 2026-10-05) zamiast płatnych `settlements`; dopasowanie: para drużyn (nazwa lub skrót, znormalizowane) + data ±1 dzień; sprzeczne kandydaty → brak wyniku. Przydział płatnych wyników z 10.8 nie jest używany | decyzja Doma: 1 płatne zapytanie = 1 mecz (< 7), więc budżet nie wystarczy; źródło wyników nie zmienia reguł | `a340c81` |

## Interpretacje (zlecenie nie rozstrzygało)

- **Otwarcie** = pierwszy moment, w którym obie strony Pinnacle mają aktywną cenę (pierwszy zapis OddsPapi, 3–14 h przed meczem). **Zamknięcie** = ostatnia aktywna cena przed `start_time`, osobno dla każdej strony. (`8bbfe46`, `snapshots.py`)
- **Nieaktywny snapshot** (`active: false`) = brak ceny od tej chwili do następnego zapisu. (`8bbfe46`)
- **„Snapshot Pinnacle”** w H1 = dowolny zapis Pinnacle (którejkolwiek strony); jego stan wymaga obu stron aktywnych; wiek liczony od tego zapisu. (`8bbfe46`)
- **Tydzień** = tydzień ISO wg `start_time`; „tygodnie z ≥ 20 meczami” liczone na wszystkich meczach z listy `fixtures` (wariant trudniejszy do spełnienia). (`8bbfe46`)
- **Kursy pobierane** tylko dla meczów z `pinnacleId` w `fixtures`; miękkie booki tylko gdy Pinnacle ma ≥ 1 zapis przed startem. (`984e267`)
- **Limit 200** liczy OddsPapi (`request_count`), tylko zapytania płatne; `historical-odds` i `account` bezpłatne — potwierdzone empirycznie (47 wywołań `historical-odds`, licznik bez zmian). (`d7264ec`)
- **Werdykt G0 a przejście do etapu 1** (Dom, 2026-10-24, zapisane **przed** uruchomieniem backtestu H1; reguły G0 bez zmian):
  - Werdykt G0 liczony dokładnie jak w zleceniu, na wszystkich 7 bookach z `config.SOFT_BOOKS`.
  - Decyzja o przejściu do etapu 1 wymaga **dodatkowo**, żeby podzbiór sygnałów H1 z booków licencjonowanych w PL — `efortuna.pl` i `superbet.pl` — miał **średni CLV > 0** (wartość punktowa).
  - Podzbiór = sygnały z `h1_signals.csv` z `book ∈ {efortuna.pl, superbet.pl}`; bez ponownego wyboru sygnałów (pierwszy snapshot w meczu wybrany na 7 bookach, zgodnie z regułą H1).
  - Jeśli podzbiór ma **< 50 sygnałów**: raportowany opisowo (n, średni CLV, 97,5% CI), oznaczony **„za mało, by decydować”** — warunek przejścia do etapu 1 nie jest wtedy spełniony.
  - Liczone poza `backtest_h1.py` (plik z commitu kodu `8bbfe46` bez zmian), w kroku raportu. (`65b6165`)
- **H3** (zapisane przed uruchomieniem, commit kodu H3):
  - **Werdykt T1, gdy oba warunki naraz** (dolna CI β > 0 i górna < 0,1, czyli małe, ale istotne β): **BRAK SYGNAŁU** — wariant konserwatywny; zlecenie H3 nie rozstrzyga kolejności.
  - **Kolejność Elo w obrębie dnia:** rekordy VRS z tej samej daty przetwarzane w kolejności nazw drużyn (deterministycznie); dla meczów testowych bez znaczenia, bo rating kończy się na d₀ − 2.
  - **Wykluczenie dopasowanego rekordu VRS:** rekord dopasowany do meczu testowego ma datę d₀ ± 1 > d₀ − 2, więc nie wchodzi do ratingu z konstrukcji; sprawdzane asercją w `backtest_h3.py`.
  - **Mapowanie drużyn:** pierwsza znormalizowana forma (nazwa, potem skrót z `fixtures`), która występuje w VRS; ta sama drużyna po obu stronach → mecz odrzucony.
  - **„Strona modelu = faworyt rynku”**: model wycenia wyżej stronę, która na otwarciu Pinnacle ma p > 0,5.

## 2026-10-24

- **Raport H3** (`scanner/reports/2026-10-24-h3.md`): **„Za mało danych” — T1 NIEROZSTRZYGALNE** (n = 461, β = +0,050, 95% CI [−0,003, +0,103]). T2 opisowo: n = 101, ROI −36,4%, CLV −4,7%; T3: Elo gorsze od Pinnacle (log-loss 0,643 vs 0,598/0,587). Reguły `2131816`, kod `f081a89` bez zmian przy uruchomieniu; 0 zapytań API. Werdykt G0 bez zmian. (`COMMIT_H3`)
- **Raport G0** (`scanner/reports/2026-10-24-g0.md`): **G0 = NIE PRZECHODZI (brak danych)**. H1: n = 163 < 200 → NIEROZSTRZYGALNA (średni CLV +10,1%, 97,5% CI [+6,7%, +13,8%] — opisowo). H2: 668 meczów z Pinnacle open+close < 1 000 → NIEROZSTRZYGALNA. Warunek etapu 1 (podzbiór PL): n = 42 < 50 → „za mało, by decydować”. Pliki `config/stats/snapshots/backtest_h1/backtest_h2` identyczne z `8bbfe46` przy uruchomieniu; testy zielone. (`9f9aece`)
- **Pokrycie przed backtestem** (`coverage_odds.py`, bez wyników/CLV): 718 meczów z kursami, 668 z Pinnacle przed startem, 654 z ≥ 1 miękkim bookiem w oknie H1, **625 ze sparowanym snapshotem** (≥ ~600 → backtest H1 uruchomiony zgodnie z dyspozycją Doma). (`9f9aece`)
- **Kontrola danych H1 (bez wyników):** orientacja stron u wszystkich 7 booków poprawna (mediana |różnicy de-vig| vs Pinnacle 0,3–2,3 pp); średni CLV ≈ średnia value w chwili sygnału (+10,1% vs +10,9%). (`9f9aece`)
- **`scanner/data/raw/` poza git** (659 MB > 50 MB, zlecenie sekcja 7); w repo `matches.csv`, `snapshots.csv`, `results_vrs.csv`, `no_history.csv`. (`9f9aece`)
- **Walidator kuponów — poprawka:** reguła `net = gross − stake` dotyczyła też kuponów `pending`, co przeczyło regule `pending → net = 0`; teraz tylko kupony rozliczone. Ujawnione przy EDGE-312 (pierwszy `pending` w Edge_2.0); EDGE-312 został zacommitowany (`35d875a`) przed poprawką, bo kod wyjścia walidatora był ukryty w potoku — od teraz walidator uruchamiany bez potoku. (`47e7256`)
- **Kolejność pobierania kursów** (decyzja Doma): start historii ustalony wyszukiwaniem binarnym (sondy tylko Pinnacle, darmowe) → **2026-05-22, 14:00–23:00 UTC**; mecze wcześniejsze pominięte; pozostałe 813 pobierane od najnowszych. Booki: Pinnacle + 7 z `config.SOFT_BOOKS` (wykrywanie wszystkich 348 booków przerwane na polecenie Doma — zostajemy przy zamrożonym zestawie, bez nowej decyzji). Konsekwencja: < 1 000 meczów z Pinnacle open+close → **H2 NIEROZSTRZYGALNA** (sekcja 5) niezależnie od danych. Dalej: `coverage_odds.py`; jeśli ≥ ~600 meczów ze sparowanym snapshotem (warunek H1) → backtest H1 bez czekania na Doma, inaczej STOP. (`bfb6dec`)
- **Wyniki z Valve VRS** (O9). Dopasowanie do `fixtures`: wszystkie 3 636/5 806 (62,6%); z `pinnacleId` 1 493/2 177 (68,6%); z `pinnacleId` i startem ≤ 2026-10-05 (zasięg VRS) 1 493/2 015 (74,1%); niejednoznaczne 12. Walidacja na rozliczonych predykcjach `Edge@483374c` (tylko odczyt): zgodne 190/192 (99,0%), niedopasowane 63, niejednoznaczne 3. Mecze po 2026-10-05 bez wyniku. (`a340c81`)
- **Historia kursów:** wszystkie mecze ze stycznia 2026 zwracają 404 (166 kolejnych) — historia zaczyna się później niż „styczeń 2026” z dokumentacji (zob. wpis o kolejności pobierania).

- **B w toku.** `fixtures` 2026: 5 806 meczów CS2, 2 177 z `pinnacleId`; `markets`: 171 = Winner, 171 → uczestnik 1, 172 → uczestnik 2. Zużycie 37/200 płatnych. Kursy pobierane w tle. (`984e267`)
- **Python 3.11** przez `uv` w `scanner/.venv` (systemowy 3.9.6, brak Homebrew). Zależności: numpy, pandas, requests; testy na `unittest`. (`d7264ec`)
- **AGENTS.md** i linki w README. (`eb1a4c5`)
- **Commit kodu** (drugi zamrażający): `config.py`, `stats.py`, `snapshots.py`, `backtest_h1.py`, `backtest_h2.py`, 17 testów zielonych. Przed pobraniem jakichkolwiek wyników. (`8bbfe46`)
- **Rewizja po B0** (decyzja Doma: plan free) — sekcja 10 zlecenia. (`d7264ec`)
- **Nowy klucz OddsPapi** po tym, jak stary pojawił się w wyjściu narzędzia (`/v4/account` zwraca klucz). Klient wycina `api_key` z odpowiedzi przed zapisem; klucz tylko w `.env` i sekretach repo. (`78d7558`)
- **B0 rozpoznanie**: 10 wywołań (4 płatne). Estymacja < 1 000 meczów → STOP, decyzja Doma. Nota: `scanner/reports/2026-10-24-b0-rozpoznanie.md`. (`78d7558`)
- **A6**: nota o archiwum w README repo `Edge` (`Edge@483374c`).
- **Migracja A1–A4**: 310 kuponów / −174,37 PLN 1:1 z `Edge@a76ee86`; walidator kuponów; dashboard bez predykcji. (`3446127`)
- **Commit reguł** (pierwszy zamrażający): zlecenie etapu 0 + `.gitignore`. (`6c8f76f`)
- **`summary` w `Edge`** poprawione przez Doma (licznik `won` przesunięty o 1; kwoty były poprawne) przed migracją (`Edge@a76ee86`).
