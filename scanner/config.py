"""Etap 0 rules as constants -- the single place backtest code reads thresholds from.

Source: docs/decisions/2026-10-24-etap0-zlecenie.md, sections 3, 4, 5 and 10.
Frozen: changing any value here after the code-freeze commit is a breach of
zlecenie 1.1 unless done as a revision commit of the zlecenie itself.
"""
from datetime import timedelta

# --- Section 3: shared definitions ---
BOOTSTRAP_N = 20_000
BOOTSTRAP_SEED = 20261024
CI_LEVEL = 0.975                       # two-sided; percentiles 1.25 and 98.75 (Bonferroni, section 4 G0)
CI_PERCENTILES = (1.25, 98.75)

# --- Section 4, H1: soft bookmaker off Pinnacle ---
H1_WINDOW_START = timedelta(hours=24)  # window [start_time - 24 h, start_time - 15 min]
H1_WINDOW_END = timedelta(minutes=15)
H1_PIN_MAX_AGE = timedelta(minutes=30) # Pinnacle snapshot at time <= t, not older than 30 min
H1_VALUE_MIN = 0.05                    # signal when value >= +0.05
H1_MIN_SIGNALS = 200                   # n >= 200 (also section 5: fewer -> NIEROZSTRZYGALNA)
H1_MIN_SIGNALS_PER_WEEK = 1.0          # mean >= 1 signal / qualifying week
H1_WEEK_MIN_MATCHES = 20               # tier unavailable (section 10.9): weeks with >= 20 matches

SHARP_BOOKS = {"pinnacle", "betfair-ex", "singbet", "singbet-b", "polymarket", "polymarket.us", "kalshi"}
# Section 10.6: frozen candidate set for B (conservative subset of "remaining books").
SOFT_BOOKS = ["bet365", "1xbet", "efortuna.pl", "superbet.pl", "betway", "unibet", "stake"]
PINNACLE = "pinnacle"

# --- Section 4, H2: overpriced heavy favourites ---
H2_PFAV_MIN = 0.75                     # signal on the underdog when p_fav (Pinnacle open, de-vig) >= 0.75
H2_MIN_N = 1_000                       # n >= 1000 signals with a result
H2_MIN_MATCHES_OPEN_CLOSE = 1_000      # section 5: fewer Pinnacle open+close matches -> NIEROZSTRZYGALNA
H2_CALIBRATION_BUCKETS = [0.50, 0.60, 0.70, 0.80, 0.90, 1.00]

# --- Section 10: source mapping (OddsPapi v4) ---
SPORT_ID_CS2 = 17
MONEYLINE_MARKET = "171"
OUTCOME_SIDE = {"171": "a", "172": "b"}  # participant1 -> a, participant2 -> b; checked via `markets` before fetch (10.5)
SEASON_FROM = "2026-01-01T00:00:00Z"
SEASON_TO = "2026-10-24T00:00:00Z"
FIXTURE_WINDOW_DAYS = 9                  # fixtures?sportId&from&to must be < 10 days apart

# Verdict labels (section 6)
PASS, FAIL, UNDECIDABLE = "PRZECHODZI", "NIE PRZECHODZI", "NIEROZSTRZYGALNA"
