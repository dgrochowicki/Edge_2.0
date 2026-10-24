# Zlecenie dla repo agenta: Edge 2.0 — Etap 0 (backtest-bramka)

**Data:** 2026-10-24 · **Zleceniodawca:** Dom (operator) · **Autor zlecenia:** claude
**Status:** do wykonania po akceptacji operatora (commit tego pliku = akceptacja i zamrożenie reguł) · rewizja 2026-10-24 12:30: doprecyzowania po uwagach agenta (zakres commitu zamrażającego, H1 kolejność snapshotów, CI 97,5%, moc H2) · rewizja 2026-10-24 12:45: dwa commity zamrażające (reguły w A, kod po B0), B0 tylko struktura danych, 310 kuponów · rewizja 2026-10-24 po B0: plan free OddsPapi, przydział płatnych wyników, zestaw miękkich booków (sekcja 10)
**Kontekst:** propozycja planu „Edge 2.0" (dokument Doma), decyzja `Edge/docs/decisions/2026-10-24-simplify-to-opinions.md`
**Repo docelowe:** nowe `dgrochowicki/Edge_2.0` = księga kuponów + dashboard kuponów + nowy skaner (`scanner/`). Stare `dgrochowicki/Edge` = zamrożone archiwum v1–v3.

## 0. Cel w jednym zdaniu

Sprawdzić na danych historycznych dwie z góry zapisane hipotezy (H1, H2) i oddać raport z jednoznacznym werdyktem bramki **G0: PRZECHODZI / NIE PRZECHODZI**. Nic poza tym. Żadnego skanera na żywo, alertów ani nowych widoków dashboardu w tym etapie. Wcześniej, jako zadanie A, przenosisz kupony i dashboard kuponów do nowego repo.

## 1. Zasady nienegocjowalne

1. **Reguły z sekcji 4 są zamrożone.** Nie zmieniasz progów, filtrów ani definicji po zobaczeniu danych. Jeśli definicja okaże się niewykonalna (np. brak kursów otwarcia), zatrzymujesz się i opisujesz problem w raporcie; nie wymyślasz zamiennika.
2. **Kolejność i dwa commity zamrażające:**
   - **Commit reguł** — ten plik jako pierwszy commit repo (zadanie A). Reguły są zapisane w nim słownie, więc zamrożenie zaczyna się od tego commitu.
   - **Commit kodu** — po B0, przed pobraniem masowym (B): `scanner/config.py`, `scanner/stats.py`, `scanner/backtest_h1.py`, `scanner/backtest_h2.py`, `scanner/tests/test_stats.py`. Dokłada tylko kod implementujący reguły z pierwszego commitu, bez zmiany ich treści.
   - Kolejność: A → B0 (rozpoznanie, STOP) → commit kodu → B (pobieranie masowe) → C–G.
   - Oba hashe wpisujesz do raportu.
3. **Kupony przenosisz 1:1.** Każdy wpis z `coupons` w `Edge/data/bets.json` trafia do `Edge_2.0/data/bets.json` bez zmiany żadnego pola. Predykcje (`predictions`, `archived_predictions`) zostają tylko w `Edge` i są czytane stamtąd przez adres raw.
4. **Sekrety:** klucz API tylko ze zmiennej środowiskowej `ODDSPAPI_KEY` (lokalnie) lub sekretu repo. Nigdy w kodzie, logach, plikach danych ani commitach.
5. **W repo `Edge` niczego nie usuwasz.** Jedyna zmiana tam: nota o archiwum w README (zadanie A6).
6. Przy każdej niejasności, której nie rozstrzyga ten dokument: zapisz pytanie w raporcie, wybierz wariant bardziej konserwatywny (mniej sygnałów, gorsze kursy), oznacz to.

## 2. Zadania

| # | Zadanie | Warunek startu | Wynik |
|---|---|---|---|
| A | Migracja: nowe repo, kupony, dashboard kuponów | repo `Edge_2.0` utworzone przez Doma | struktura z sekcji 7, działający dashboard kuponów |
| B | Klient danych i pobranie historii | A, B0 (rozpoznanie + zgoda Doma), commit kodu (1.2) | `scanner/data/raw/`, `scanner/data/matches.csv` |
| C | Raport pokrycia danych | B | sekcja „Pokrycie" w raporcie |
| D | Backtest H1 | C, pokrycie ≥ progu z sekcji 5 | wyniki H1 + werdykt |
| E | Backtest H2 | C, pokrycie ≥ progu z sekcji 5 | wyniki H2 + werdykt |
| F | Raport G0 | D, E | `scanner/reports/RRRR-MM-DD-g0.md` |
| G | Sprawdzenie krzyżowe na predykcjach `Edge` | F | sekcja „Zgodność z księgą Edge" |

### A. Migracja do `Edge_2.0` (przed backtestem)

Cel: w nowym repo działa to, czego Dom używa (kupony i ich dashboard), plus pusty katalog `scanner/` na nowe rozwiązanie. Wszystko inne zostaje w `Edge`.

**A1. Szkielet.** Struktura z sekcji 7. Ten plik jako `docs/decisions/2026-10-24-etap0-zlecenie.md`. Nowy `README.md`: co to za repo, gdzie archiwum (`Edge`), jak logować kupon, jak uruchomić backtest.

**A2. Kupony.** `Edge_2.0/data/bets.json` = kopia `Edge/data/bets.json` z kluczami `project`, `currency`, `unit_value_pln`, `bookmaker`, `updated_at`, `coupons`, `observed_passes`, `summary`. Bez `predictions` i `archived_predictions`. Pola `report` w kuponach wskazują pliki w `Edge` — zostaw wartości bez zmian; w dashboardzie link do raportu buduj jako `https://github.com/dgrochowicki/Edge/blob/main/<report>`.
Kontrola: liczba kuponów (310, stan `Edge` @ `a76ee86`) i suma `net_result_pln` (−174,37 PLN) identyczne przed i po; wynik kontroli i hash commitu `Edge`, z którego kopiowano, w opisie commitu. Do zakończenia migracji nie dodajemy nowych kuponów (ani w `Edge`, ani w `Edge_2.0`).

**A3. Walidator.** `scripts/validate_bets.py` przenieś i okrój do reguł kuponów (bez reguł v1/v2/v3 predykcji). Musi przejść na przeniesionym pliku.

**A4. Dashboard.** Przenieś `index.html` i z `dashboard/`: `dashboard.js`, `data.js`, `logs.html`, `logs.js`, `shared-metrics.js`, `sidebar.js`, `styles.css`, `favicon.svg`.
- **Nie przenoś:** `research.html`, `research.js`, `reports.html`, `reports.js` (predykcje i raporty dzienne v1–v3).
- `data.js`: `GITHUB_RAW_URL` → `https://raw.githubusercontent.com/dgrochowicki/Edge_2.0/main/data/bets.json`.
- `sidebar.js`: nawigacja tylko `Dashboard` i `Logs` (kupony) oraz `Signals` jako zaślepka (`dashboard/signals.html` z jednym zdaniem: „Skaner w budowie, etap 0 — backtest”).
- `shared-metrics.js` / `dashboard.js`: usuń kod i karty zależne od `predictions` oraz podziały na agentów `claude`/`gpt` w źródłach kuponów; zostaw podział „Edge (historyczne rekomendacje)” vs „Own bets”, wykres P/L, serię, statystyki kuponów. Strony muszą działać bez kluczy `predictions` w danych (bez błędów w konsoli).
- Sprawdzenie: otwórz lokalnie (`python -m http.server`) `index.html` i `dashboard/logs.html`; liczby w kafelkach zgodne z `summary` w `bets.json`.

**A5. GitHub Pages.** Dom włącza Pages w `Edge_2.0` (Settings → Pages → branch `main`, root). Podaj mu to jednym zdaniem po zakończeniu A4.

**A6. Stare repo `Edge`.** Na górze `README.md` blok: „Archiwum (v1–v3, lipiec–październik 2026). Aktywny projekt i księga kuponów: dgrochowicki/Edge_2.0.” Nic więcej nie zmieniasz i nie usuwasz. Od tej chwili kupony loguje się wyłącznie w `Edge_2.0`.

**A7. Odczyt starych predykcji (zadanie G).** Nie kopiujesz ich. Czytasz w locie: `https://raw.githubusercontent.com/dgrochowicki/Edge/main/data/bets.json` (sprawdź gałąź). W raporcie zapisz hash commitu `Edge`, z którego czytano.

### B0. Budżet API (OddsPapi free: 250 zapytań / miesiąc) — OBOWIĄZKOWE przed B

- **Twardy limit na etap 0: 200 zapytań** (50 rezerwy). Każde zapytanie logowane w `scanner/data/api_usage.json` (czas, endpoint, parametry bez klucza, status). Klient odmawia wywołania po przekroczeniu limitu.
- **Cache na dysku:** żadne zapytanie nie jest powtarzane; surowe odpowiedzi w `scanner/data/raw/`.
- **Rozpoznanie (max 10 zapytań):** ustal, ile meczów i snapshotów zwraca jedno zapytanie historyczne (per mecz, per turniej, per dzień?), czy są kursy otwarcia, ilu bukmacherów naraz (limit 3 na wywołanie wg dostawcy). Wynik + estymacja „ile meczów z Pinnacle open/close zmieści się w 190 zapytaniach” → **wiadomość do Doma i STOP**, zanim ruszy pobieranie masowe.
- **Rozpoznanie = tylko struktura danych:** pola, liczba snapshotów, bukmacherzy, obecność kursów otwarcia. Żadnych wyników meczów, trafień ani ROI na próbce, nawet „na szybko”. Jeśli odpowiedzi API zawierają wyniki, zapisujesz je w `raw/` bez analizowania.
- Jeśli estymacja < 1 000 meczów: nie pobierasz. Proponujesz w wiadomości warianty z kosztem: (a) płatny miesiąc OddsPapi, (b) darmowy plan odds-api.io (sprawdź limit i historię), (c) publiczne zbiory historyczne CS2 z kursami — tylko jeśli mają Pinnacle open i close. Decyzję podejmuje Dom.
- **Klucz lokalnie:** sekret GitHub nie jest widoczny w VS Code. Lokalnie klucz tylko w `.env` (w `.gitignore`) albo w zmiennej środowiskowej. Sprawdź `.gitignore` przed pierwszym commitem.

### B. Dane

- Źródło podstawowe: OddsPapi (CS2, Pinnacle + dostępne miękkie booki, historia). Zapasowe do porównania pokrycia: odds-api.io. Wybór dostawcy uzasadnij w raporcie liczbami pokrycia.
- Zakres: wszystkie mecze CS2 od 2024-01-01 do 2026-10-24 dostępne w źródle, bez filtrowania wyników.
- Dla każdego meczu zapisz: `match_id`, `start_time` (UTC), `tournament`, `tier` (jeśli źródło podaje), `team_a`, `team_b`, `winner`, `format` (BO1/BO3/BO5, jeśli dostępny), oraz dla każdego bukmachera i każdej strony: kurs **otwarcia** (pierwszy zapisany), kurs **zamknięcia** (ostatni przed `start_time`), wszystkie snapshoty z timestampem w `raw/`.
- Tylko rynek **moneyline / zwycięzca meczu**. Bez map, handicapów, totali.
- Mecze bez rozstrzygnięcia (void, walkower, remis) — wykluczone, z liczbą w raporcie.
- Kod: `scanner/fetch_history.py` (pobieranie, z cache na dysku i limitem zapytań), `scanner/build_dataset.py` (normalizacja). Surowe odpowiedzi zapisuj tak, żeby ponowne uruchomienie nie wymagało API.

### C. Pokrycie

Tabela: liczba meczów ogółem; z Pinnacle otwarcie+zamknięcie; z ≥ 1 miękkim bookiem w tym samym oknie; rozkład po kwartałach; mediana liczby snapshotów na mecz; lista bukmacherów z liczbą meczów. Jeśli STS pojawia się w źródle — osobny wiersz.

## 3. Definicje wspólne

```
de-vig (multiplikatywny):  p_A = (1/o_A) / (1/o_A + 1/o_B)
fair_close_X             = 1 / p_close_X           (Pinnacle, zamknięcie, de-vig)
CLV sygnału              = o_taken × p_close_X − 1
P/L płaskiej stawki 1u   = (o − 1) jeśli X wygrał, inaczej −1
CI                       = bootstrap 97,5% (dwustronny, percentyle 1,25 i 98,75), 20 000 losowań po meczach (seed 20261024)
```

Jeden mecz = co najwyżej jeden sygnał na hipotezę (przy dwóch kandydatach — strona z wyższym value, przy remisie — brak sygnału).

## 4. Reguły hipotez (ZAMROŻONE)

### H1 — miękki bukmacher odstaje od Pinnacle

- Dla każdego snapshotu miękkiego booka B o czasie t, w oknie `[start_time − 24 h, start_time − 15 min]`:
  weź najbliższy snapshot Pinnacle w czasie **≤ t**, nie starszy niż 30 min. Brak takiego → snapshot pomijany.
- `value = o_B,X × p_pin,X(t) − 1`. **Sygnał**, gdy `value ≥ +0,05`. Bierzemy **najwcześniejszy** snapshot spełniający warunek **spośród wszystkich booków B łącznie** (nie najlepszy, nie pierwszy w każdym booku). Kilka snapshotów o tym samym czasie: wyższe value; równe value po przeciwnych stronach: brak sygnału; równe value po tej samej stronie: bukmacher pierwszy alfabetycznie.
- Książki „ostre" (Pinnacle, Betfair Exchange, Singbet, Polymarket, Kalshi) nie są kandydatami na B. Kandydaci = pozostałe booki ze źródła.
- `o_taken = o_B,X` z tego snapshotu.
- **Metryka rozstrzygająca:** średni CLV vs zamknięcie Pinnacle.
- **H1 PRZECHODZI**, gdy jednocześnie: n sygnałów ≥ 200; dolna granica 97,5% CI średniego CLV > 0; średnio ≥ 1 sygnał na tydzień w tygodniach, w których odbywał się turniej tier-1/2 (jeśli źródło nie podaje tieru — w tygodniach z ≥ 20 meczami).
- Raportowane opisowo (nie rozstrzyga): P/L płaskiej stawki, wyniki per bukmacher B, per kwartał, odsetek sygnałów, które do zamknięcia „domknęły się" (p_pin przesunęło się w stronę B).

### H2 — przewartościowani wysocy faworyci

- `p_fav = max(p_open_A, p_open_B)` z Pinnacle **otwarcia**. **Sygnał** na underdoga, gdy `p_fav ≥ 0,75`.
- `o_taken` = kurs underdoga na **zamknięciu Pinnacle** (wariant konserwatywny: wejście po cenie, której rynek już nie poprawi).
- **Metryka rozstrzygająca:** ROI płaskiej stawki 1u.
- **H2 PRZECHODZI**, gdy: n ≥ 1 000; dolna granica 97,5% CI ROI > 0. n = wszystkie mecze spełniające regułę w zbiorze (1 000 to minimum, nie limit).
- **Świadomie przyjęta moc testu:** przy kursach underdogów ok. 4–5 odchylenie P/L to ok. 1,9u na zakład, więc przy n = 1 000 błąd standardowy ROI wynosi ok. 6 pp, a przejście wymaga ROI rzędu +13–14%. Wynik dodatni, ale z CI obejmującym zero, raportujesz jako **NIE PRZECHODZI (za słaby sygnał przy tej próbie)**, z wartością i CI, bez komentarza „obiecujące”.
- Raportowane opisowo: kalibracja Pinnacle zamknięcia w kubełkach p_fav (0,50–0,60 … 0,90–1,00): przewidziane vs zrealizowane z CI; ROI na najlepszym dostępnym miękkim kursie zamknięcia; podział BO1 vs BO3+, per kwartał.
- Zastrzeżenie do wpisania w raport: próg 0,75 wybrano po obejrzeniu księgi Edge (n=53–74), więc ten backtest jest pierwszym niezależnym testem.

### G0

**G0 PRZECHODZI**, jeśli przechodzi H1 **lub** H2. Poziom 97,5% dla każdej hipotezy (korekta Bonferroniego) utrzymuje łączne ryzyko fałszywie pozytywnego G0 na ok. 5% — decyzja świadoma. Inaczej **NIE PRZECHODZI** i rekomendacja raportu brzmi: zamknięcie projektu. Żadnych „prawie", „obiecujący trend", przesuwania progów ani dodatkowych podziałów jako podstawy werdyktu.

## 5. Kiedy się zatrzymać przed werdyktem

- < 1 000 meczów z Pinnacle otwarcie+zamknięcie → H2 **nierozstrzygalna** (nie „przechodzi").
- < 200 sygnałów H1 → H1 **nierozstrzygalna**.
- Obie nierozstrzygalne → G0 = **NIE PRZECHODZI (brak danych)**, plus jedno zdanie, jakiego źródła brakuje i ile by kosztowało.

## 6. Raport (`scanner/reports/RRRR-MM-DD-g0.md`)

Kolejność sekcji, krótko, liczby z jednostkami:

1. **Werdykt G0** w pierwszym zdaniu + H1 i H2 jednym wierszem każda (n, metryka, 97,5% CI, PRZECHODZI/NIE/NIEROZSTRZYGALNA).
2. Hashe obu commitów zamrażających (reguły, kod — 1.2); data pobrania danych; dostawca.
3. Pokrycie (zadanie C).
4. H1 — tabela wyników + opisowe.
5. H2 — tabela wyników + kalibracja + opisowe.
6. Zgodność z księgą `Edge` (zadanie G): źródłem są **predykcje `Edge`** (A7), tylko wpisy z oboma kursami (`market_odds_at_analysis` i `market_odds_opponent`), jeden wpis na mecz (pierwszy wg `date`, potem `id`). Kupony się nie nadają, bo mają kurs tylko jednej strony. Dla meczów obecnych w obu zbiorach: korelacja de-vig STS z de-vig Pinnacle zamknięcia, średnia różnica w pp, mediana marży STS vs Pinnacle, liczba dopasowanych meczów i sposób dopasowania (nazwy drużyn + data ±1 dzień).
7. Odstępstwa od zlecenia i otwarte pytania (lista; pusta, jeśli brak).

Wykresy opcjonalne, jako PNG obok raportu; nie zastępują tabel z liczbami.

## 7. Struktura repo `Edge_2.0`

```
Edge_2.0/
  README.md
  index.html                 — dashboard kuponów (z Edge, okrojony)
  dashboard/                 — logs, sidebar, styles, shared-metrics, data.js, signals.html (zaślepka)
  data/bets.json             — księga kuponów (jedyne źródło prawdy o kuponach)
  scripts/validate_bets.py   — walidacja kuponów
  docs/decisions/            — ten plik i kolejne decyzje
  scanner/                   — nowe rozwiązanie
    README.md                — 10 linii: co to, jak uruchomić backtest
    config.py                — progi z sekcji 4 jako stałe (jedno miejsce)
    fetch_history.py
    build_dataset.py
    backtest_h1.py
    backtest_h2.py
    stats.py                 — de-vig, CLV, bootstrap
    tests/test_stats.py
    requirements.txt
    data/raw/                — w .gitignore, jeśli > 50 MB; wtedy w raporcie jak odtworzyć
    data/matches.csv
    reports/
```

Python 3.11+, zależności w `scanner/requirements.txt` (pandas, numpy, requests; nic więcej bez powodu). Testy `stats.py` muszą przejść przed uruchomieniem backtestu: de-vig dla kursów 1,50/2,70 → 0,6429/0,3571; CLV dla o=2,10 i p_close=0,50 → +0,05.

## 8. Definicja „zrobione"

- [ ] Commit reguł (ten plik) jako pierwszy commit `Edge_2.0`
- [ ] Commit kodu (`scanner/config.py`, `stats.py`, `backtest_h1.py`, `backtest_h2.py`, `tests/test_stats.py`) po B0, **przed** pobraniem masowym
- [ ] Migracja A zakończona: kupony 1:1 (zgodna liczba i suma `net_result_pln`), dashboard kuponów działa na GitHub Pages `Edge_2.0`, `Edge` bez zmian poza README
- [ ] Dane pobrane, pokrycie opisane
- [ ] Testy `stats.py` zielone
- [ ] Raport G0 z werdyktem w pierwszym zdaniu
- [ ] Żadnego klucza API w historii git (`git log -p | grep -i key` czysto)
- [ ] Wiadomość do Doma: werdykt + link do raportu, 3 zdania maksymalnie

## 9. Czego nie robisz w tym etapie

- Nie budujesz skanera na żywo, cronu w GitHub Actions ani bota Telegram (to etap 1–2, osobne zlecenie po G0).
- Nie implementujesz H3 (rating VRS).
- Nie budujesz widoku sygnałów w dashboardzie (najwyżej pusta zakładka-zaślepka, A4).
- Nie zmieniasz niczego w repo `Edge` poza notą w README.
- Nie piszesz raportów dziennych i nie prosisz Doma o kursy STS.

## 10. Rewizja po B0 (2026-10-24, decyzja Doma: plan free)

Podstawa: `scanner/reports/2026-10-24-b0-rozpoznanie.md`. Progi, metryki i warunki przejścia z sekcji 4 bez zmian; poniżej tylko to, czego zlecenie nie rozstrzygało lub czego źródło nie umożliwia.

1. **Źródło i budżet.** OddsPapi, plan free. Limit liczy OddsPapi (`request_count` z `/v4/account`) i obejmuje tylko zapytania płatne. Twardy limit etapu 0: **200 płatnych** (z dotychczasowym zużyciem). `historical-odds` i `account` są bezpłatne, ale też logowane w `api_usage.json`. Klient sprawdza `request_count` przed każdym płatnym zapytaniem.
2. **Zakres.** Wszystkie mecze CS2 dostępne w źródle; historia kursów istnieje de facto tylko w 2026 (sonda z lutego bez danych). Lista meczów: `fixtures?sportId=17&statusId=2`, okna < 10 dni, 2026-01-01 – 2026-10-24.
3. **`start_time` = `startTime` z `fixtures`.** Snapshoty z `createdAt ≥ start_time` (notowania w trakcie meczu) są ignorowane we wszystkich obliczeniach.
4. **Otwarcie** = pierwszy snapshot OddsPapi przed `start_time` (w sondach 3–14 h przed meczem, nie rzeczywiste otwarcie linii) — przyjęte świadomie; H2 testuje p_fav z tego snapshotu.
5. **Rynek:** moneyline = `marketId 171`; mapowanie wyników `171`/`172` na uczestnika 1/2 potwierdzone jednym zapytaniem `markets` przed pobieraniem.
6. **Kandydaci na B w H1 (odstępstwo od „pozostałe booki ze źródła”, wariant konserwatywny wg 1.6):** pobieranie wszystkich 348 booków przy 5 s na zapytanie i 3 bookach na zapytanie jest niewykonalne czasowo. Zestaw zamrożony: `bet365`, `1xbet`, `efortuna.pl`, `superbet.pl`, `betway`, `unibet`, `stake`. Miękkie booki pobierane tylko dla meczów, w których Pinnacle ma ≥ 1 snapshot przed `start_time`.
7. **H1 nie wymaga wyników** (metryka rozstrzygająca: CLV). P/L płaskiej stawki dla H1 raportowany opisowo tylko na sygnałach z pobranym wynikiem, z podaną liczbą.
8. **Przydział płatnych wyników (`scores`), ustalony przed pobraniem danych:** najpierw wszystkie sygnały H2 w kolejności `start_time`, potem `fixtureId`; jeśli budżet zostanie, sygnały H1 w tej samej kolejności. Mecze bez wyniku nie wchodzą do metryk opartych na wyniku. H2 liczona na sygnałach z wynikiem; n < 1 000 → **NIEROZSTRZYGALNA** (sekcja 5), bez ekstrapolacji.
9. **Niedostępne w źródle:** tier (H1: próg zastępczy „tygodnie z ≥ 20 meczami”), format BO (podział H2 BO1 vs BO3+ pominięty), STS (sekcja Pokrycie bez wiersza STS; zadanie G bez zmian — STS z predykcji `Edge`).
10. **Środowisko:** Python 3.11 przez `uv` w `scanner/.venv` (poza git); testy na `unittest`.
