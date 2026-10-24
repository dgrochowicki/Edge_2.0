"""Tests for stats.py (zlecenie section 7) plus rule checks for H1/H2 on synthetic snapshots.

Run: .venv/bin/python -m unittest discover -s tests   (from scanner/)
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backtest_h1  # noqa: E402
import backtest_h2  # noqa: E402
import config  # noqa: E402
import stats  # noqa: E402

START = pd.Timestamp("2026-06-01T18:00:00Z")


def snap(book, side, minutes_before, price, active=True, match="m1"):
    return {"match_id": match, "book": book, "side": side,
            "t": START - pd.Timedelta(minutes=minutes_before), "price": price, "active": active}


def matches(winner=None, match="m1"):
    return pd.DataFrame([{"match_id": match, "start_time": START, "tournament": "T",
                          "team_a": "A", "team_b": "B", "winner": winner}])


class TestStats(unittest.TestCase):
    def test_devig_required_case(self):
        pa, pb = stats.devig(1.50, 2.70)
        self.assertAlmostEqual(pa, 0.6429, places=4)
        self.assertAlmostEqual(pb, 0.3571, places=4)

    def test_clv_required_case(self):
        self.assertAlmostEqual(stats.clv(2.10, 0.50), 0.05, places=10)

    def test_flat_pl(self):
        self.assertAlmostEqual(stats.flat_pl(2.5, True), 1.5)
        self.assertEqual(stats.flat_pl(2.5, False), -1.0)

    def test_bootstrap_deterministic_and_covers_mean(self):
        x = np.random.default_rng(1).normal(0.02, 0.1, 500)
        a, b = stats.bootstrap_ci(x), stats.bootstrap_ci(x)
        self.assertEqual(a, b)
        self.assertLess(a[0], x.mean())
        self.assertGreater(a[1], x.mean())

    def test_bootstrap_uses_975_two_sided(self):
        self.assertEqual(config.CI_PERCENTILES, (1.25, 98.75))
        x = np.random.default_rng(2).normal(0, 1, 400)
        lo, hi = stats.bootstrap_ci(x)
        se = x.std(ddof=1) / np.sqrt(len(x))
        self.assertAlmostEqual((hi - lo) / 2 / se, 2.24, delta=0.15)  # z_{0.9875} = 2.24


class TestH1(unittest.TestCase):
    def pin(self, minutes_before, a=1.80, b=2.10):
        return [snap("pinnacle", "a", minutes_before, a), snap("pinnacle", "b", minutes_before, b)]

    def test_signal_and_clv(self):
        # Pinnacle 1.80/2.10 -> p_b = 0.4615; bet365 b @ 2.30 -> value = 0.0615 >= 0.05
        rows = self.pin(120) + [snap("bet365", "a", 100, 1.60), snap("bet365", "b", 100, 2.30)]
        rows += self.pin(10, 1.70, 2.25)  # close (after the H1 window ends, still pre-start)
        sig = backtest_h1.run(matches("b"), pd.DataFrame(rows))
        self.assertEqual(len(sig), 1)
        s = sig.iloc[0]
        self.assertEqual((s.book, s.side, s.o_taken), ("bet365", "b", 2.30))
        p_close_b = stats.devig(1.70, 2.25)[1]
        self.assertAlmostEqual(s.clv, 2.30 * p_close_b - 1)
        self.assertTrue(s.won)

    def test_pinnacle_older_than_30_min_skipped(self):
        rows = self.pin(140) + [snap("bet365", "b", 100, 2.30)] + self.pin(10)
        self.assertTrue(backtest_h1.run(matches(), pd.DataFrame(rows)).empty)

    def test_outside_window_skipped(self):
        rows = self.pin(25 * 60) + [snap("bet365", "b", 24 * 60 + 5, 2.30)] + self.pin(10)
        self.assertTrue(backtest_h1.run(matches(), pd.DataFrame(rows)).empty)
        rows = self.pin(20) + [snap("bet365", "b", 14, 2.30)] + self.pin(10)
        self.assertTrue(backtest_h1.run(matches(), pd.DataFrame(rows)).empty)

    def test_earliest_across_books_not_best(self):
        rows = self.pin(120) + [snap("unibet", "b", 110, 2.28), snap("bet365", "b", 100, 2.60)] + self.pin(10)
        s = backtest_h1.run(matches(), pd.DataFrame(rows)).iloc[0]
        self.assertEqual((s.book, s.o_taken), ("unibet", 2.28))

    def test_sharp_and_unlisted_books_ignored(self):
        rows = self.pin(120) + [snap("betfair-ex", "b", 100, 2.50), snap("somebook", "b", 100, 2.50)] + self.pin(10)
        self.assertTrue(backtest_h1.run(matches(), pd.DataFrame(rows)).empty)

    def test_inactive_price_ignored(self):
        rows = self.pin(120) + [snap("bet365", "b", 100, 2.50, active=False)] + self.pin(10)
        self.assertTrue(backtest_h1.run(matches(), pd.DataFrame(rows)).empty)

    def test_tie_same_time_alphabetical_book(self):
        rows = self.pin(120) + [snap("unibet", "b", 100, 2.30), snap("bet365", "b", 100, 2.30)] + self.pin(10)
        self.assertEqual(backtest_h1.run(matches(), pd.DataFrame(rows)).iloc[0].book, "bet365")

    def test_weekly_criterion(self):
        m = pd.DataFrame({"start_time": pd.to_datetime(["2026-06-01T10:00Z"] * 20 + ["2026-06-08T10:00Z"] * 5, utc=True)})
        s = pd.DataFrame({"start_time": pd.to_datetime(["2026-06-01T10:00Z", "2026-06-08T10:00Z"], utc=True)})
        wk = backtest_h1.weekly(m, s)
        self.assertEqual((wk["qualifying_weeks"], wk["signals_in_qualifying_weeks"]), (1, 1))


class TestH2(unittest.TestCase):
    def test_signal_from_open_taken_at_close(self):
        rows = [snap("pinnacle", "a", 600, 1.25), snap("pinnacle", "b", 600, 4.20),   # p_fav = 0.7706
                snap("pinnacle", "a", 5, 1.35), snap("pinnacle", "b", 5, 3.40)]       # close
        allm, sig = backtest_h2.run(matches("b"), pd.DataFrame(rows))
        self.assertEqual(len(sig), 1)
        s = sig.iloc[0]
        self.assertAlmostEqual(s.p_fav_open, stats.devig(1.25, 4.20)[0])
        self.assertEqual((s.dog, s.o_taken, s.won, s.pl), ("b", 3.40, True, 2.40))

    def test_below_threshold_no_signal(self):
        rows = [snap("pinnacle", "a", 600, 1.40), snap("pinnacle", "b", 600, 3.10),
                snap("pinnacle", "a", 5, 1.40), snap("pinnacle", "b", 5, 3.10)]
        _, sig = backtest_h2.run(matches("a"), pd.DataFrame(rows))
        self.assertTrue(sig.empty)

    def test_open_needs_both_sides_active(self):
        rows = [snap("pinnacle", "a", 600, 1.10),                      # one side only -> not the open
                snap("pinnacle", "a", 500, 1.60), snap("pinnacle", "b", 500, 2.40),
                snap("pinnacle", "a", 5, 1.60), snap("pinnacle", "b", 5, 2.40)]
        allm, sig = backtest_h2.run(matches("a"), pd.DataFrame(rows))
        self.assertAlmostEqual(allm.iloc[0].p_fav_open, stats.devig(1.60, 2.40)[0])
        self.assertTrue(sig.empty)

    def test_verdict_undecidable_below_1000(self):
        allm = pd.DataFrame({"x": range(10)})
        sig = pd.DataFrame({"won": [True, False], "pl": [3.0, -1.0]})
        self.assertEqual(backtest_h2.verdict(allm, sig)["verdict"], config.UNDECIDABLE)


if __name__ == "__main__":
    unittest.main()
