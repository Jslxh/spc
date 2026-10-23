"""Automated unit tests for Shewhart and p-chart SPC monitoring module."""

from __future__ import annotations

import unittest
from pathlib import Path
import numpy as np
import pandas as pd

from src.spc.control_charts import (
    IndividualsLimits,
    PChartLimits,
    calibrate_individuals_chart,
    calibrate_p_chart,
    monitor_individuals,
    monitor_p_chart,
)


class TestControlCharts(unittest.TestCase):
    """Test suite for Phase I calibration and Phase II monitoring control charts."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.abrupt_cnt_path = (
            self.repo_root / "results" / "processed" / "daily_metrics_abrupt_shift_cnt.csv"
        )
        self.gradual_null_path = (
            self.repo_root / "results" / "processed" / "daily_metrics_gradual_null_temp.csv"
        )

    def test_hand_checkable_moving_range_and_individuals_limits(self) -> None:
        """Verify exact analytical values for MR-bar, sigma_hat, and unclamped Shewhart limits."""
        # 5-point hand-calculable dataset: [10.0, 14.0, 11.0, 17.0, 8.0]
        # Mean = (10 + 14 + 11 + 17 + 8) / 5 = 60 / 5 = 12.0
        # Differences: |14-10|=4, |11-14|=3, |17-11|=6, |8-17|=9
        # MR_bar = (4 + 3 + 6 + 9) / 4 = 22 / 4 = 5.5
        # sigma_hat = 5.5 / 1.128 = 4.8758865248...
        # UCL = 12.0 + 3 * (5.5 / 1.128) = 26.62765957...
        # LCL = 12.0 - 3 * (5.5 / 1.128) = -2.62765957... (strictly negative, unclamped!)
        dates = [f"2011-01-0{i}" for i in range(1, 6)]
        values = [10.0, 14.0, 11.0, 17.0, 8.0]
        df = pd.DataFrame({"batch_date": dates, "cnt_mean": values})

        limits = calibrate_individuals_chart(
            df=df,
            metric_column="cnt_mean",
            baseline_start="2011-01-01",
            baseline_end="2011-01-05",
            min_observations=5,
        )

        expected_mean = 12.0
        expected_mr_bar = 5.5
        expected_sigma = 5.5 / 1.128
        expected_ucl = expected_mean + 3.0 * expected_sigma
        expected_lcl = expected_mean - 3.0 * expected_sigma

        self.assertAlmostEqual(limits.center_line, expected_mean, places=5)
        self.assertAlmostEqual(limits.mr_bar, expected_mr_bar, places=5)
        self.assertAlmostEqual(limits.sigma_hat, expected_sigma, places=5)
        self.assertAlmostEqual(limits.ucl, expected_ucl, places=5)
        self.assertAlmostEqual(limits.lcl, expected_lcl, places=5)
        self.assertLess(limits.lcl, 0.0, "LCL must remain unclamped and negative per requirement")

    def test_individuals_three_sigma_violations(self) -> None:
        """Verify two-sided upper and lower 3-sigma violations on an Individuals chart."""
        # Baseline limits: CL=12.0, UCL ~ 26.63, LCL ~ -2.63
        dates = [f"2011-01-0{i}" for i in range(1, 6)]
        df_base = pd.DataFrame({"batch_date": dates, "cnt_mean": [10.0, 14.0, 11.0, 17.0, 8.0]})
        limits = calibrate_individuals_chart(
            df_base, "cnt_mean", "2011-01-01", "2011-01-05", min_observations=5
        )

        # Phase II points:
        # 1. 20.0 -> in-control (between -2.63 and 26.63)
        # 2. 30.0 -> upper violation (> 26.63)
        # 3. -5.0 -> lower violation (< -2.63)
        df_p2 = pd.DataFrame(
            {
                "batch_date": ["2012-01-01", "2012-01-02", "2012-01-03"],
                "cnt_mean": [20.0, 30.0, -5.0],
            }
        )

        res = monitor_individuals(
            df=df_p2,
            limits=limits,
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-03",
            two_sided=True,
        )

        self.assertEqual(res.total_observations, 3)
        self.assertEqual(res.total_alerts, 2)
        self.assertEqual(res.upper_alerts, 1)
        self.assertEqual(res.lower_alerts, 1)
        self.assertEqual(res.first_alert_date, "2012-01-02")

        rec = res.records_df
        # Point 1: in-control
        self.assertFalse(rec.loc[0, "is_alert"])
        self.assertEqual(rec.loc[0, "violation_type"], "none")
        # Point 2: upper alert
        self.assertTrue(rec.loc[1, "is_alert"])
        self.assertEqual(rec.loc[1, "violation_type"], "upper_limit")
        # Point 3: lower alert
        self.assertTrue(rec.loc[2, "is_alert"])
        self.assertEqual(rec.loc[2, "violation_type"], "lower_limit")

    def test_moving_range_missing_value_and_date_gap_adjacency(self) -> None:
        """Verify that NaNs and calendar date gaps are never bridged during moving-range calculation."""
        # 5 daily records with a NaN on Day 2:
        # Day 1: 10.0
        # Day 2: NaN
        # Day 3: 20.0
        # Day 4: 25.0
        # Day 5: 35.0
        # Valid consecutive pairs:
        # (Day 1, Day 2): Day 2 is NaN -> INVALID
        # (Day 2, Day 3): Day 2 is NaN -> INVALID
        # (Day 3, Day 4): |25 - 20| = 5.0 -> VALID
        # (Day 4, Day 5): |35 - 25| = 10.0 -> VALID
        # Expected MR_bar = (5.0 + 10.0) / 2 = 7.5
        # The non-adjacent gap |20 - 10| = 10.0 must NOT be computed!
        dates = [f"2011-01-0{i}" for i in range(1, 6)]
        values = [10.0, None, 20.0, 25.0, 35.0]
        df = pd.DataFrame({"batch_date": dates, "cnt_mean": values})

        limits = calibrate_individuals_chart(
            df=df,
            metric_column="cnt_mean",
            baseline_start="2011-01-01",
            baseline_end="2011-01-05",
            min_observations=4,
        )

        self.assertEqual(limits.valid_moving_ranges, 2)
        self.assertAlmostEqual(limits.mr_bar, 7.5, places=5)

        # Date gap test: Day 1 (2011-01-01) followed by Day 5 (2011-01-05), 4 days gap!
        df_gap = pd.DataFrame(
            {
                "batch_date": ["2011-01-01", "2011-01-05", "2011-01-06", "2011-01-07", "2011-01-08"],
                "cnt_mean": [10.0, 50.0, 52.0, 56.0, 60.0],
            }
        )
        # Pair (Day 1, Day 5): gap = 4 days -> INVALID (must not compute |50 - 10| = 40)
        # Valid pairs: (Day 5, 6): |52-50|=2, (Day 6, 7): |56-52|=4, (Day 7, 8): |60-56|=4
        # Expected MR_bar = (2 + 4 + 4) / 3 = 10 / 3 = 3.33333...
        limits_gap = calibrate_individuals_chart(
            df=df_gap,
            metric_column="cnt_mean",
            baseline_start="2011-01-01",
            baseline_end="2011-01-08",
            min_observations=4,
        )
        self.assertEqual(limits_gap.valid_moving_ranges, 3)
        self.assertAlmostEqual(limits_gap.mr_bar, 10.0 / 3.0, places=5)

    def test_p_chart_variable_sample_size_limits_manual(self) -> None:
        """Verify p-chart limits scale dynamically with batch sample size n_i."""
        # Baseline: 2 days with n=50 each, 5 events each -> total events = 10, total elig = 100
        # p_bar = 10 / 100 = 0.10
        df_base = pd.DataFrame(
            {
                "batch_date": [f"2011-01-{i:02d}" for i in range(1, 31)],
                "temp_null_rate": [0.10] * 30,
                "row_count": [50] * 30,
            }
        )
        limits = calibrate_p_chart(
            df=df_base,
            proportion_column="temp_null_rate",
            denominator_column="row_count",
            baseline_start="2011-01-01",
            baseline_end="2011-01-30",
            min_observations=30,
        )

        self.assertAlmostEqual(limits.p_bar, 0.10, places=6)
        self.assertFalse(limits.zero_defect_policy)

        # Phase II with variable batch sizes:
        # Batch 1: n = 100 -> sigma_p = sqrt(0.1 * 0.9 / 100) = sqrt(0.0009) = 0.03
        #   UCL = 0.10 + 3 * 0.03 = 0.19
        #   LCL = 0.10 - 3 * 0.03 = 0.01
        # Batch 2: n = 25 -> sigma_p = sqrt(0.1 * 0.9 / 25) = sqrt(0.0036) = 0.06
        #   UCL = 0.10 + 3 * 0.06 = 0.28
        #   LCL = max(0, 0.10 - 3 * 0.06) = 0.0
        df_p2 = pd.DataFrame(
            {
                "batch_date": ["2012-01-01", "2012-01-02"],
                "temp_null_rate": [0.15, 0.20],
                "row_count": [100, 25],
            }
        )

        res = monitor_p_chart(
            df=df_p2,
            limits=limits,
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-02",
        )

        rec = res.records_df
        # Check Batch 1 limits
        self.assertAlmostEqual(rec.loc[0, "ucl"], 0.19, places=5)
        self.assertAlmostEqual(rec.loc[0, "lcl"], 0.01, places=5)
        self.assertFalse(rec.loc[0, "is_alert"])

        # Check Batch 2 limits (wider due to smaller sample size n=25)
        self.assertAlmostEqual(rec.loc[1, "ucl"], 0.28, places=5)
        self.assertAlmostEqual(rec.loc[1, "lcl"], 0.0, places=5)
        self.assertFalse(rec.loc[1, "is_alert"])

    def test_zero_defect_baseline_p_chart(self) -> None:
        """Verify strict zero-defect policy: p_bar == 0 implies any p > 0 triggers an alert."""
        # Baseline with all 0 null rates
        dates = [f"2011-01-{i:02d}" for i in range(1, 31)]
        df_base = pd.DataFrame(
            {
                "batch_date": dates,
                "temp_null_rate": [0.0] * 30,
                "row_count": [24] * 30,
            }
        )

        limits = calibrate_p_chart(
            df=df_base,
            proportion_column="temp_null_rate",
            denominator_column="row_count",
            baseline_start="2011-01-01",
            baseline_end="2011-01-30",
            min_observations=30,
        )

        self.assertEqual(limits.p_bar, 0.0)
        self.assertTrue(limits.zero_defect_policy)

        # Phase II:
        # Day 1: p = 0.0 -> no alert, UCL = 0.0, LCL = 0.0
        # Day 2: p = 0.041667 (1 null out of 24) -> alert triggered!
        df_p2 = pd.DataFrame(
            {
                "batch_date": ["2012-01-01", "2012-01-02"],
                "temp_null_rate": [0.0, 1.0 / 24.0],
                "row_count": [24, 24],
            }
        )

        res = monitor_p_chart(
            df=df_p2,
            limits=limits,
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-02",
        )

        rec = res.records_df
        # Day 1
        self.assertFalse(rec.loc[0, "is_alert"])
        self.assertEqual(rec.loc[0, "ucl"], 0.0)
        self.assertEqual(rec.loc[0, "violation_type"], "none")

        # Day 2
        self.assertTrue(rec.loc[1, "is_alert"])
        self.assertEqual(rec.loc[1, "ucl"], 0.0)
        self.assertEqual(rec.loc[1, "violation_type"], "upper_limit")
        self.assertEqual(res.first_alert_date, "2012-01-02")

    def test_zero_variance_individuals_raises_error(self) -> None:
        """Verify that identical Phase I observations raise ValueError for degenerate variance."""
        dates = [f"2011-01-0{i}" for i in range(1, 6)]
        df_identical = pd.DataFrame({"batch_date": dates, "cnt_mean": [42.0] * 5})

        with self.assertRaises(ValueError) as ctx:
            calibrate_individuals_chart(
                df=df_identical,
                metric_column="cnt_mean",
                baseline_start="2011-01-01",
                baseline_end="2011-01-05",
                min_observations=5,
            )
        self.assertIn("zero-variance", str(ctx.exception).lower())

    def test_insufficient_observations_raises_error(self) -> None:
        """Verify ValueError when valid Phase I observations are below threshold."""
        df = pd.DataFrame({"batch_date": ["2011-01-01", "2011-01-02"], "cnt_mean": [10.0, 20.0]})
        with self.assertRaises(ValueError) as ctx:
            calibrate_individuals_chart(
                df=df,
                metric_column="cnt_mean",
                baseline_start="2011-01-01",
                baseline_end="2011-01-02",
                min_observations=30,
            )
        self.assertIn("insufficient", str(ctx.exception).lower())

    def test_duplicate_dates_raises_error(self) -> None:
        """Verify ValueError when Phase I baseline contains duplicate dates."""
        df = pd.DataFrame(
            {
                "batch_date": ["2011-01-01", "2011-01-01", "2011-01-02"],
                "cnt_mean": [10.0, 15.0, 20.0],
            }
        )
        with self.assertRaises(ValueError) as ctx:
            calibrate_individuals_chart(
                df=df,
                metric_column="cnt_mean",
                baseline_start="2011-01-01",
                baseline_end="2011-01-02",
                min_observations=2,
            )
        self.assertIn("duplicate dates", str(ctx.exception).lower())

    def test_invalid_date_range_raises_error(self) -> None:
        """Verify ValueError when baseline start date is after end date."""
        df = pd.DataFrame({"batch_date": ["2011-01-01"], "cnt_mean": [10.0]})
        with self.assertRaises(ValueError) as ctx:
            calibrate_individuals_chart(
                df=df,
                metric_column="cnt_mean",
                baseline_start="2011-12-31",
                baseline_end="2011-01-01",
            )
        self.assertIn("start", str(ctx.exception).lower())

    def test_missing_values_in_phase2(self) -> None:
        """Verify explicit handling of missing (NaN) values during Phase II monitoring."""
        dates = [f"2011-01-0{i}" for i in range(1, 6)]
        df_base = pd.DataFrame({"batch_date": dates, "cnt_mean": [10.0, 14.0, 11.0, 17.0, 8.0]})
        limits = calibrate_individuals_chart(
            df_base, "cnt_mean", "2011-01-01", "2011-01-05", min_observations=5
        )

        df_p2 = pd.DataFrame(
            {"batch_date": ["2012-01-01", "2012-01-02"], "cnt_mean": [12.0, None]}
        )

        res = monitor_individuals(
            df=df_p2,
            limits=limits,
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-02",
            alert_on_missing=True,
        )

        self.assertEqual(res.missing_observations, 1)
        rec = res.records_df
        self.assertTrue(rec.loc[1, "is_alert"])
        self.assertEqual(rec.loc[1, "violation_type"], "missing_value")
        self.assertTrue(np.isnan(rec.loc[1, "metric_value"]))

    def test_phase2_leakage_prevention(self) -> None:
        """Confirm that extreme Phase II values do not alter frozen Phase I control limits."""
        dates = [f"2011-01-0{i}" for i in range(1, 6)]
        df = pd.DataFrame(
            {
                "batch_date": dates + ["2012-01-01", "2012-01-02"],
                "cnt_mean": [10.0, 14.0, 11.0, 17.0, 8.0, 999999.0, 888888.0],
            }
        )

        limits_before = calibrate_individuals_chart(
            df=df,
            metric_column="cnt_mean",
            baseline_start="2011-01-01",
            baseline_end="2011-01-05",
            min_observations=5,
        )

        res = monitor_individuals(
            df=df,
            limits=limits_before,
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-02",
        )

        # Re-verify that limits_before was not mutated in any way
        self.assertEqual(limits_before.center_line, 12.0)
        self.assertAlmostEqual(limits_before.mr_bar, 5.5, places=5)
        self.assertAlmostEqual(limits_before.ucl, 12.0 + 3.0 * (5.5 / 1.128), places=5)

    def test_real_dataset_calibration_and_monitoring(self) -> None:
        """Verify calibration and Phase II monitoring on real project CSV files."""
        # 1. Individuals Chart on abrupt shift dataset (cnt_mean)
        df_cnt = pd.read_csv(self.abrupt_cnt_path)
        cnt_limits = calibrate_individuals_chart(
            df=df_cnt,
            metric_column="cnt_mean",
            baseline_start="2011-01-01",
            baseline_end="2011-12-31",
            min_observations=30,
        )

        self.assertEqual(cnt_limits.sample_size, 365)
        self.assertGreater(cnt_limits.center_line, 100.0)
        self.assertGreater(cnt_limits.sigma_hat, 10.0)

        cnt_res = monitor_individuals(
            df=df_cnt,
            limits=cnt_limits,
            monitoring_start="2012-01-01",
            monitoring_end="2012-12-31",
            two_sided=True,
        )

        self.assertEqual(cnt_res.total_observations, 366)  # 2012 leap year
        self.assertGreater(cnt_res.total_alerts, 0)
        self.assertIsNotNone(cnt_res.first_alert_date)

        # 2. Proportion p-Chart on gradual null drift dataset (temp_null_rate)
        df_null = pd.read_csv(self.gradual_null_path)
        null_limits = calibrate_p_chart(
            df=df_null,
            proportion_column="temp_null_rate",
            denominator_column="row_count",
            baseline_start="2011-01-01",
            baseline_end="2011-12-31",
            min_observations=30,
        )

        self.assertEqual(null_limits.sample_size, 365)
        self.assertEqual(null_limits.p_bar, 0.0)
        self.assertTrue(null_limits.zero_defect_policy)

        null_res = monitor_p_chart(
            df=df_null,
            limits=null_limits,
            monitoring_start="2012-01-01",
            monitoring_end="2012-12-31",
            two_sided=False,
        )

        self.assertEqual(null_res.total_observations, 366)
        # In gradual null drift, first alert should trigger exactly on onset date: 2012-06-01
        # Wait, on 2012-06-01 p=0.0 (start_null_rate=0.0), so first nonzero null batch is shortly after onset!
        self.assertIsNotNone(null_res.first_alert_date)
        self.assertGreaterEqual(null_res.first_alert_date, "2012-06-01")


if __name__ == "__main__":
    unittest.main()
