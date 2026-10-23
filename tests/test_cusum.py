"""Automated unit tests for continuous tabular CUSUM monitoring module."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

from src.spc.cusum import (
    CUSUMGaussianLimits,
    CUSUMResult,
    calibrate_gaussian_cusum,
    monitor_gaussian_cusum,
)


class TestCUSUM(unittest.TestCase):
    """Test suite for continuous tabular CUSUM baseline calibration and Phase II monitoring."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.abrupt_cnt_path = (
            self.repo_root / "results" / "processed" / "daily_metrics_abrupt_shift_cnt.csv"
        )
        self.gradual_null_path = (
            self.repo_root / "results" / "processed" / "daily_metrics_gradual_null_temp.csv"
        )

    def test_hand_checkable_sequence_and_strict_threshold(self) -> None:
        """Verify exact hand-calculated CUSUM arithmetic, decay, and strict inequality thresholding.

        Hand-calculated 6-point test case:
        ---------------------------------
        mu_0 = 10.0, sigma_0 = 2.0, k = 0.5, h = 3.0
        Initialization: C_plus[0] = 0.0, C_minus[0] = 0.0

        t=1: x=12.0 -> z = (12-10)/2 = +1.0
             C_plus[1]  = max(0, 0.0 + 1.0 - 0.5) = 0.5  (<= 3.0 -> no alert)
             C_minus[1] = max(0, 0.0 - 1.0 - 0.5) = 0.0  (<= 3.0 -> no alert)

        t=2: x=14.0 -> z = (14-10)/2 = +2.0
             C_plus[2]  = max(0, 0.5 + 2.0 - 0.5) = 2.0  (<= 3.0 -> no alert)
             C_minus[2] = max(0, 0.0 - 2.0 - 0.5) = 0.0  (<= 3.0 -> no alert)

        t=3: x=15.0 -> z = (15-10)/2 = +2.5
             C_plus[3]  = max(0, 2.0 + 2.5 - 0.5) = 4.0  (> 3.0 -> UPPER ALERT!)
             C_minus[3] = max(0, 0.0 - 2.5 - 0.5) = 0.0

        t=4: x=8.0  -> z = (8-10)/2 = -1.0
             C_plus[4]  = max(0, 4.0 + (-1.0) - 0.5) = 2.5 (<= 3.0 -> cleared)
             C_minus[4] = max(0, 0.0 - (-1.0) - 0.5) = 0.5

        t=5: x=4.0  -> z = (4-10)/2 = -3.0
             C_plus[5]  = max(0, 2.5 + (-3.0) - 0.5) = 0.0
             C_minus[5] = max(0, 0.5 - (-3.0) - 0.5) = 3.0
             STRICT INEQUALITY TEST: C_minus == h (3.0 == 3.0) does NOT alert!

        t=6: x=2.0  -> z = (2-10)/2 = -4.0
             C_plus[6]  = 0.0
             C_minus[6] = max(0, 3.0 - (-4.0) - 0.5) = 6.5 (> 3.0 -> LOWER ALERT!)
        """
        limits = CUSUMGaussianLimits(
            metric_name="cnt_mean",
            baseline_start="2011-01-01",
            baseline_end="2011-01-05",
            sample_size=5,
            valid_moving_ranges=4,
            center_line=10.0,
            mr_bar=2.256,
            sigma_hat=2.0,
            k=0.5,
            h=3.0,
        )

        dates = [f"2012-01-0{i}" for i in range(1, 7)]
        values = [12.0, 14.0, 15.0, 8.0, 4.0, 2.0]
        df_p2 = pd.DataFrame({"batch_date": dates, "cnt_mean": values})

        res = monitor_gaussian_cusum(
            df=df_p2,
            limits=limits,
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-06",
            two_sided=True,
        )

        self.assertEqual(res.chart_type, "gaussian_cusum")
        self.assertEqual(res.total_observations, 6)
        self.assertEqual(res.total_alerts, 2)
        self.assertEqual(res.upper_alerts, 1)
        self.assertEqual(res.lower_alerts, 1)
        self.assertEqual(res.first_alert_date, "2012-01-03")

        rec = res.records_df
        # Expected analytical values
        expected_z = [1.0, 2.0, 2.5, -1.0, -3.0, -4.0]
        expected_cp = [0.5, 2.0, 4.0, 2.5, 0.0, 0.0]
        expected_cm = [0.0, 0.0, 0.0, 0.5, 3.0, 6.5]
        expected_alerts = [False, False, True, False, False, True]
        expected_types = ["none", "none", "upper_cusum", "none", "none", "lower_cusum"]

        for i in range(6):
            self.assertAlmostEqual(rec["z_score"].iloc[i], expected_z[i], places=4)
            self.assertAlmostEqual(rec["c_plus"].iloc[i], expected_cp[i], places=6)
            self.assertAlmostEqual(rec["c_minus"].iloc[i], expected_cm[i], places=6)
            self.assertEqual(rec["is_alert"].iloc[i], expected_alerts[i])
            self.assertEqual(rec["violation_type"].iloc[i], expected_types[i])

        # Confirm strict inequality on batch 5 (t=5): C_minus is exactly 3.0, h=3.0, must NOT alert
        self.assertAlmostEqual(rec["c_minus"].iloc[4], 3.0, places=6)
        self.assertFalse(rec["is_alert"].iloc[4], "Threshold equality (C == h) must not trigger an alert")

    def test_one_sided_monitoring(self) -> None:
        """Verify one-sided upper monitoring disables lower accumulator and ignores downward shifts."""
        limits = CUSUMGaussianLimits(
            metric_name="cnt_mean",
            baseline_start="2011-01-01",
            baseline_end="2011-01-05",
            sample_size=5,
            valid_moving_ranges=4,
            center_line=10.0,
            mr_bar=2.256,
            sigma_hat=2.0,
            k=0.5,
            h=3.0,
        )

        dates = [f"2012-01-0{i}" for i in range(1, 7)]
        values = [12.0, 14.0, 15.0, 8.0, 4.0, 2.0]
        df_p2 = pd.DataFrame({"batch_date": dates, "cnt_mean": values})

        res = monitor_gaussian_cusum(
            df=df_p2,
            limits=limits,
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-06",
            two_sided=False,
        )

        self.assertEqual(res.total_observations, 6)
        self.assertEqual(res.total_alerts, 1)
        self.assertEqual(res.upper_alerts, 1)
        self.assertEqual(res.lower_alerts, 0)
        self.assertEqual(res.first_alert_date, "2012-01-03")

        rec = res.records_df
        # C_minus should be NaN throughout
        self.assertTrue(rec["c_minus"].isna().all())

        # Batch 6 (downward shift) does not trigger an alert under one-sided monitoring
        self.assertFalse(rec["is_alert"].iloc[5])
        self.assertEqual(rec["violation_type"].iloc[5], "none")

    def test_missing_values_hold_state_and_alert(self) -> None:
        """Verify missing observations carry forward accumulator state and alert without erasing evidence."""
        limits = CUSUMGaussianLimits(
            metric_name="cnt_mean",
            baseline_start="2011-01-01",
            baseline_end="2011-01-05",
            sample_size=5,
            valid_moving_ranges=4,
            center_line=10.0,
            mr_bar=2.256,
            sigma_hat=2.0,
            k=0.5,
            h=3.0,
        )

        # Batch 1: 14.0 -> z = +2.0, C_plus = 1.5
        # Batch 2: NaN  -> missing, C_plus carried forward as 1.5, alert=True (missing_value)
        # Batch 3: 15.0 -> z = +2.5, C_plus = max(0, 1.5 + 2.5 - 0.5) = 3.5 (> 3.0 -> upper_cusum alert!)
        df_p2 = pd.DataFrame(
            {
                "batch_date": ["2012-01-01", "2012-01-02", "2012-01-03"],
                "cnt_mean": [14.0, np.nan, 15.0],
            }
        )

        res = monitor_gaussian_cusum(
            df=df_p2,
            limits=limits,
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-03",
            alert_on_missing=True,
        )

        self.assertEqual(res.missing_observations, 1)
        self.assertEqual(res.total_alerts, 2)  # NaN day + batch 3
        rec = res.records_df

        # Batch 2 check: NaN carried forward C_plus=1.5
        self.assertAlmostEqual(rec["c_plus"].iloc[1], 1.5, places=6)
        self.assertTrue(np.isnan(rec["z_score"].iloc[1]))
        self.assertTrue(rec["is_alert"].iloc[1])
        self.assertEqual(rec["violation_type"].iloc[1], "missing_value")

        # Batch 3 check: accumulated on top of carried-forward 1.5 to reach 3.5 > 3.0
        self.assertAlmostEqual(rec["c_plus"].iloc[2], 3.5, places=6)
        self.assertTrue(rec["is_alert"].iloc[2])
        self.assertEqual(rec["violation_type"].iloc[2], "upper_cusum")

        # When alert_on_missing=False, missing value does not alert, but still carries forward state
        res_no_alert = monitor_gaussian_cusum(
            df=df_p2,
            limits=limits,
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-03",
            alert_on_missing=False,
        )
        self.assertFalse(res_no_alert.records_df["is_alert"].iloc[1])
        self.assertEqual(res_no_alert.records_df["violation_type"].iloc[1], "missing_value")
        self.assertAlmostEqual(res_no_alert.records_df["c_plus"].iloc[2], 3.5, places=6)
        self.assertTrue(res_no_alert.records_df["is_alert"].iloc[2])

    def test_moving_range_missing_value_and_date_gap_adjacency(self) -> None:
        """Verify moving ranges are computed ONLY on strictly adjacent non-NaN consecutive days."""
        # Baseline series:
        # 2011-01-01: 10.0
        # 2011-01-02: 14.0 -> consecutive (1 day), valid MR = |14-10| = 4.0
        # 2011-01-03: NaN  -> invalid MR (NaN involved)
        # 2011-01-04: 12.0 -> invalid MR (prev was NaN)
        # 2011-01-07: 16.0 -> invalid MR (date gap: 3 days apart)
        # 2011-01-08: 20.0 -> consecutive (1 day), valid MR = |20-16| = 4.0
        df = pd.DataFrame(
            {
                "batch_date": [
                    "2011-01-01",
                    "2011-01-02",
                    "2011-01-03",
                    "2011-01-04",
                    "2011-01-07",
                    "2011-01-08",
                ],
                "cnt_mean": [10.0, 14.0, np.nan, 12.0, 16.0, 20.0],
            }
        )

        limits = calibrate_gaussian_cusum(
            df=df,
            metric_column="cnt_mean",
            baseline_start="2011-01-01",
            baseline_end="2011-01-08",
            min_observations=5,
            min_moving_ranges=2,
        )

        self.assertEqual(limits.sample_size, 5)
        self.assertEqual(limits.valid_moving_ranges, 2)
        self.assertAlmostEqual(limits.mr_bar, 4.0, places=5)
        expected_sigma = 4.0 / 1.128
        self.assertAlmostEqual(limits.sigma_hat, expected_sigma, places=5)

    def test_zero_variance_raises_error(self) -> None:
        """Verify calibrate_gaussian_cusum raises ValueError when baseline variance is zero."""
        df = pd.DataFrame(
            {
                "batch_date": [f"2011-01-0{i}" for i in range(1, 6)],
                "cnt_mean": [5.0, 5.0, 5.0, 5.0, 5.0],
            }
        )

        with self.assertRaises(ValueError) as ctx:
            calibrate_gaussian_cusum(
                df=df,
                metric_column="cnt_mean",
                baseline_start="2011-01-01",
                baseline_end="2011-01-05",
                min_observations=5,
            )
        self.assertIn("zero-variance", str(ctx.exception).lower())

    def test_invalid_parameters_raise_error(self) -> None:
        """Verify strict input validation and descriptive ValueErrors for invalid CUSUM configurations."""
        df = pd.DataFrame(
            {
                "batch_date": [f"2011-01-0{i}" for i in range(1, 6)],
                "cnt_mean": [10.0, 12.0, 11.0, 13.0, 10.0],
            }
        )

        # Invalid k (<= 0)
        with self.assertRaises(ValueError):
            calibrate_gaussian_cusum(df, "cnt_mean", k=0.0, min_observations=5)
        with self.assertRaises(ValueError):
            calibrate_gaussian_cusum(df, "cnt_mean", k=-0.5, min_observations=5)

        # Invalid h (<= 0)
        with self.assertRaises(ValueError):
            calibrate_gaussian_cusum(df, "cnt_mean", h=0.0, min_observations=5)
        with self.assertRaises(ValueError):
            calibrate_gaussian_cusum(df, "cnt_mean", h=-1.0, min_observations=5)

        # Invalid min_observations (< 2)
        with self.assertRaises(ValueError):
            calibrate_gaussian_cusum(df, "cnt_mean", min_observations=1)

        # Invalid date range (start > end)
        with self.assertRaises(ValueError):
            calibrate_gaussian_cusum(
                df, "cnt_mean", baseline_start="2011-01-05", baseline_end="2011-01-01"
            )

        # Missing metric column
        with self.assertRaises(ValueError):
            calibrate_gaussian_cusum(df, "nonexistent_column", min_observations=5)

        # Unsupported reset policy in monitor
        limits = calibrate_gaussian_cusum(
            df, "cnt_mean", "2011-01-01", "2011-01-05", min_observations=5
        )
        with self.assertRaises(ValueError):
            monitor_gaussian_cusum(
                df, limits, "batch_date", "2011-01-01", "2011-01-05", reset_policy="zero"  # type: ignore
            )

    def test_phase1_frozen_and_leakage_prevention(self) -> None:
        """Confirm Phase I parameters are frozen and extreme Phase II values cannot alter them."""
        df_base = pd.DataFrame(
            {
                "batch_date": [f"2011-01-0{i}" for i in range(1, 6)],
                "cnt_mean": [10.0, 14.0, 11.0, 17.0, 8.0],
            }
        )
        limits = calibrate_gaussian_cusum(
            df_base, "cnt_mean", "2011-01-01", "2011-01-05", min_observations=5
        )

        # Verify frozen immutability
        with self.assertRaises(FrozenInstanceError):
            limits.center_line = 999.0  # type: ignore

        # Monitor Phase II with extreme outliers
        df_p2 = pd.DataFrame(
            {
                "batch_date": ["2012-01-01", "2012-01-02"],
                "cnt_mean": [1_000_000.0, 2_000_000.0],
            }
        )
        monitor_gaussian_cusum(df_p2, limits, "batch_date", "2012-01-01", "2012-01-02")

        # Baseline parameters remain unchanged
        self.assertAlmostEqual(limits.center_line, 12.0, places=5)
        self.assertAlmostEqual(limits.sigma_hat, 5.5 / 1.128, places=5)

    def test_real_dataset_cnt_mean_cusum_and_seasonality_audit(self) -> None:
        """Verify calibration and prospective monitoring on the real project dataset with seasonality audit."""
        self.assertTrue(self.abrupt_cnt_path.exists(), f"File not found: {self.abrupt_cnt_path}")

        # Calibrate Phase I on 2011 baseline
        limits = calibrate_gaussian_cusum(
            df=self.abrupt_cnt_path,
            metric_column="cnt_mean",
            baseline_start="2011-01-01",
            baseline_end="2011-12-31",
            k=0.5,
            h=5.0,
        )

        self.assertEqual(limits.sample_size, 365)
        self.assertEqual(limits.valid_moving_ranges, 364)
        self.assertAlmostEqual(limits.center_line, 142.934581, places=5)
        self.assertAlmostEqual(limits.mr_bar, 24.721413, places=5)
        self.assertAlmostEqual(limits.sigma_hat, 21.916146, places=5)
        self.assertEqual(limits.k, 0.5)
        self.assertEqual(limits.h, 5.0)

        # Baseline stability audit: cnt_mean exhibits strong seasonality
        stability = limits.baseline_stability
        self.assertFalse(stability["is_stable"], "Phase I baseline is seasonal and unstable")
        self.assertAlmostEqual(stability["baseline_violation_rate"], 0.2795, places=3)
        self.assertEqual(stability["baseline_alerts_count"], 102)
        self.assertIn("substantial variation/seasonality", stability["note"])

        # Monitor Phase II (2012)
        res = monitor_gaussian_cusum(
            df=self.abrupt_cnt_path,
            limits=limits,
            monitoring_start="2012-01-01",
            monitoring_end="2012-12-31",
            two_sided=True,
        )

        self.assertEqual(res.total_observations, 366)
        self.assertGreater(res.total_alerts, 0)
        # Seasonal false alarm: winter trough drives lower CUSUM alert in early January
        self.assertEqual(res.first_alert_date, "2012-01-03")
        first_alert = res.records_df[res.records_df["is_alert"]].iloc[0]
        self.assertEqual(first_alert["violation_type"], "lower_cusum")
        self.assertGreater(first_alert["c_minus"], 5.0)

    def test_zero_baseline_null_rate_rejection(self) -> None:
        """Verify Gaussian CUSUM rejects temp_null_rate because Phase I has zero variance (sigma_0 == 0)."""
        self.assertTrue(self.gradual_null_path.exists(), f"File not found: {self.gradual_null_path}")

        # In 2011, all temp_null_rate values are exactly 0.0 -> zero variance
        with self.assertRaises(ValueError) as ctx:
            calibrate_gaussian_cusum(
                df=self.gradual_null_path,
                metric_column="temp_null_rate",
                baseline_start="2011-01-01",
                baseline_end="2011-12-31",
            )
        self.assertIn("zero-variance", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()

