# B0 — rozpoznanie OddsPapi (2026-10-24)

Tylko struktura danych (zlecenie B0). Żadnych wyników meczów, trafień ani ROI. Odpowiedzi w `scanner/data/raw/` (nieanalizowane), log w `scanner/data/api_usage.json`.

**Zużycie:** 10 wywołań, z czego 4 płatne (`sports`, 3× `fixtures`); `account` i `historical-odds` są bezpłatne wg dokumentacji (Requests & Quota). Konto: plan `free`, `request_limit` 250.

## Ustalenia

| Pytanie | Odpowiedź |
|---|---|
| CS2 | `sportId = 17` (ESport Counter-Strike) |
| Lista meczów | `GET fixtures?sportId=17&statusId=2&from&to`, okno < 10 dni, 1 zapytanie płatne na okno, zwraca wszystkie mecze okna (213 / 196 / 50 meczów w trzech oknach) |
| Pola meczu | `fixtureId`, `startTime`, `trueStartTime`, `tournamentName`, `categoryName`, uczestnicy, `externalProviders.pinnacleId`; **brak tieru**, **brak formatu BO**, **brak wyniku** |
| Mecze z `pinnacleId` | 114/213 (luty), 80/196 (październik), 24/50 (lipiec) |
| Historia kursów | `GET historical-odds?fixtureId&bookmakers` — **1 mecz na zapytanie, max 3 bukmacherów**, bezpłatne, cooldown 5 s |
| Rynek moneyline | `marketId 171`, wyniki `171` / `172` (do potwierdzenia mapowania na uczestnika 1/2 przez `markets`) |
| Snapshot | `createdAt`, `price`, `limit`, `active`, `exchangeMeta`; zawiera też notowania **w trakcie meczu** (filtrować do `startTime`) |
| Kurs otwarcia | Brak osobnego pola; „otwarcie" = pierwszy zapisany snapshot. Pinnacle: pierwszy zapis 3,1 h przed startem (PGL Bucharest, paźdź.), 14 h (CCT SA, lipiec); 7–40 snapshotów przed startem |
| Miękkie booki | bet365, 1xbet, superbet.pl, efortuna.pl, betway, unibet, betsson, stake… (348 w planie). **STS: brak w źródle** |
| Głębokość historii | Dokumentacja: „od stycznia 2026". Próba na meczu z 2026-02-02: 404 (brak danych, także dla samego Pinnacle). Lipiec i październik: dane są. **Zakres 2024-01-01 – 2025-12-31 niedostępny w tym źródle.** |
| Pokrycie Pinnacle | 3 sondy z `pinnacleId`: 2 z kursami Pinnacle, 1 bez (ESL Challenger League NA, tylko bet365) |
| Wynik meczu | Nie ma go w `fixtures`; osobne `scores` (lub `settlements`) — **1 zapytanie płatne na mecz** |

## Estymacja: ile meczów z Pinnacle open/close w 190 zapytaniach

Koszt jednego meczu = 0 (kursy, bezpłatne) + 1 (wynik, płatny) + udział w liście meczów (~1 zapytanie / 9 dni).

- Lista meczów 2026-01-01 – 2026-10-24: ~33 okna = ~33 zapytania.
- Zostaje ~157 zapytań na wyniki → **~157 meczów z wynikiem**.
- **Estymacja < 1 000 → zgodnie z B0 nie pobieram masowo.**

Pula meczów z `pinnacleId` w dostępnym oknie (sty–paź 2026): ~24–114 na 9 dni → rząd **1 500–3 500**; ile z nich ma faktycznie kursy Pinnacle przed startem — do zmierzenia (bezpłatnie, przez `historical-odds`).

## Warianty (decyzja Doma)

| Wariant | Koszt | Pokrycie |
|---|---|---|
| (a) Płatny miesiąc OddsPapi, CS2, wszystkie booki, 5 000 zapytań | 3 USD / mies. (wg Doma) | ~33 listy + wyniki dla wszystkich meczów z kursami Pinnacle (szac. 1 500–3 500); mieści się w 5 000. Historia tylko 2026. |
| (a') Jak (a), wyniki tylko dla meczów z Pinnacle przed startem (sprawdzone bezpłatnie najpierw) | 3 USD | jak (a), mniej zapytań |
| (b) odds-api.io (darmowy plan) | nie sprawdzone | do rozpoznania |
| (c) Publiczne zbiory CS2 z Pinnacle open/close | nie sprawdzone | do rozpoznania |

## Zastrzeżenia do reguł (bez zmiany reguł — do decyzji Doma)

1. **Zakres danych:** zlecenie B zakłada 2024-01-01 – 2026-10-24; źródło daje najwyżej ~10 miesięcy 2026. Czy próg n ≥ 1 000 dla H2 jest osiągalny — zależy od pokrycia Pinnacle (po pobraniu kursów, przed wynikami).
2. **„Otwarcie" Pinnacle** to pierwszy zapis OddsPapi (3–14 h przed meczem), nie rzeczywiste otwarcie linii. Definicja z zlecenia („pierwszy zapisany") jest spełniona dosłownie; H2 testuje więc „p_fav z pierwszego zapisu OddsPapi".
3. **Okno H1** `[−24 h, −15 min]`: miękkie booki zaczynają się 1–24 h przed meczem, więc efektywne okno bywa krótkie.
4. **Tier i format BO** niedostępne → H1 używa progu zastępczego „tygodnie z ≥ 20 meczami"; podział H2 BO1 vs BO3+ niewykonalny z tego źródła.
5. **Limit 200 zapytań**: proponuję liczyć tylko zapytania płatne (`historical-odds` jest bezpłatne). Klient już tak robi i loguje wszystkie wywołania.
6. **Python 3.11+** nie jest zainstalowany (jest 3.9.6, brak Homebrew/uv); potrzebny przed backtestem.
