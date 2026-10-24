"""Tests for H3 (h3_elo.py, backtest_h3.py). Run: .venv/bin/python -m unittest discover -s tests"""
import sys
import unittest
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backtest_h3  # noqa: E402
import h3_elo as h3  # noqa: E402


class TestElo(unittest.TestCase):
    def test_p_win(self):
        self.assertAlmostEqual(h3.p_win(1500, 1500), 0.5)
        self.assertAlmostEqual(h3.p_win(1600, 1500), 1 / (1 + 10 ** (-100 / 400)))

    def test_update_k32(self):
        r = h3.Ratings([(date(2026, 1, 1), "x", "y", "x")])
        rat, n = r.as_of(date(2026, 1, 1))
        self.assertAlmostEqual(rat["x"], 1516.0)
        self.assertAlmostEqual(rat["y"], 1484.0)
        self.assertEqual(n, {"x": 1, "y": 1})

    def test_as_of_cutoff_excludes_later_days(self):
        recs = [(date(2026, 1, 1), "x", "y", "x"), (date(2026, 1, 3), "x", "y", "y")]
        r = h3.Ratings(recs)
        self.assertEqual(r.as_of(date(2026, 1, 2))[1]["x"], 1)
        self.assertEqual(r.as_of(date(2025, 12, 31)), ({}, {}))
        # match on d0 = 2026-01-03 uses cutoff d0 - 2 = 2026-01-01: day-before records excluded
        self.assertEqual(h3.cutoff_for(date(2026, 1, 3)), date(2026, 1, 1))

    def test_dedup_conflicts_dropped(self):
        vrs = {(date(2026, 1, 1), frozenset(("x", "y"))): {"x"},
               (date(2026, 1, 2), frozenset(("x", "y"))): {"x", "y"}}
        recs, conflicts = h3.records(vrs)
        self.assertEqual((len(recs), conflicts), (1, 1))
        self.assertEqual(recs[0], (date(2026, 1, 1), "x", "y", "x"))


class TestT1(unittest.TestCase):
    def test_control_removes_open_noise_artifact(self):
        rng = np.random.default_rng(0)
        true = rng.uniform(0.3, 0.7, 3000)
        p_open = np.clip(true + rng.normal(0, 0.04, 3000), 0.05, 0.95)
        p_close = true
        p_model = np.full(3000, 0.5)                      # model with no information
        gap, move = p_model - p_open, p_close - p_open
        naive = (gap * move).sum() / (gap ** 2).sum()
        beta, _ = backtest_h3.ols2(gap, 0.5 - p_open, move)
        self.assertGreater(naive, 0.05)                   # the artifact the control fixes
        self.assertAlmostEqual(beta, 0.0, delta=0.05)

    def test_control_keeps_real_information(self):
        rng = np.random.default_rng(1)
        true = rng.uniform(0.3, 0.7, 3000)
        p_open = np.clip(true + rng.normal(0, 0.04, 3000), 0.05, 0.95)
        p_model = true + rng.normal(0, 0.02, 3000)        # model knows the close
        beta, _ = backtest_h3.ols2(p_model - p_open, 0.5 - p_open, true - p_open)
        self.assertGreater(beta, 0.5)

    def test_verdict(self):
        self.assertEqual(backtest_h3.t1_verdict(250, 0.2, 0.6), h3.SIGNAL)
        self.assertEqual(backtest_h3.t1_verdict(150, 0.2, 0.6), h3.UNDECIDED)
        self.assertEqual(backtest_h3.t1_verdict(250, -0.2, 0.05), h3.NO_SIGNAL)
        self.assertEqual(backtest_h3.t1_verdict(250, 0.01, 0.08), h3.NO_SIGNAL)  # both hold -> conservative
        self.assertEqual(backtest_h3.t1_verdict(250, -0.1, 0.3), h3.UNDECIDED)


if __name__ == "__main__":
    unittest.main()
