"""Automated unit tests for Great Expectations threshold-monitoring module."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd

from src.spc.gx_monitor import (
    GXMetricThreshold,
    GXMonitoringConfig,
    GXMonitoringResult,
    is_gx_available,
    run_gx_monitoring,
    save_gx_results,
)


class TestGXMonitor(unittest.TestCase):
    """Test suite for Great Expectations threshold monitoring."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.config_path = self.repo_root / "configs" / "gx_thresholds_daily_metrics.json"

    def test_config_loading_and_serialization(self) -> None:
        """Verify GXMonitoringConfig loads from JSON and serializes correctly."""
        self.assertTrue(self.config_path.is_file(), f"Config file not found: {self.config_path}")
        config = GXMonitoringConfig.from_json(self.config_path)

        self.assertEqual(config.suite_name, "daily_quality_metrics_thresholds")
        self.assertEqual(len(config.thresholds), 3)

        cols = [t.column for t in config.thresholds]
        self.assertIn("row_count", cols)
        self.assertIn("temp_null_rate", cols)
        self.assertIn("cnt_mean", cols)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_json = Path(tmp_dir) / "test_config.json"
            config.to_json(tmp_json)
            reloaded = GXMonitoringConfig.from_json(tmp_json)
            self.assertEqual(config.suite_name, reloaded.suite_name)
            self.assertEqual(len(config.thresholds), len(reloaded.thresholds))

    @unittest.skipUnless(is_gx_available(), "great_expectations is not installed in this environment")
    def test_value_within_threshold_passes(self) -> None:
        """Verify an in-bounds metric observation passes validation without alerting."""
        config = GXMonitoringConfig(
            suite_name="test_in_bounds",
            thresholds=(
                GXMetricThreshold(column="cnt_mean", min_value=10.0, max_value=50.0),
            ),
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-01",
        )
        df = pd.DataFrame({"batch_date": ["2012-01-01"], "cnt_mean": [25.0]})

        res = run_gx_monitoring(df, config)

        self.assertEqual(res.total_batches, 1)
        self.assertEqual(res.alert_batches, 0)
        self.assertEqual(res.clean_batches, 1)
        self.assertIsNone(res.first_alert_date)

        rec = res.records_df.iloc[0]
        self.assertFalse(rec["is_alert"])
        self.assertEqual(rec["failed_expectations_count"], 0)
        self.assertEqual(rec["alert_reasons"], "none")

        det = res.detailed_records_df.iloc[0]
        self.assertTrue(det["passed"])
        self.assertFalse(det["is_alert"])
        self.assertEqual(det["alert_reason"], "none")

    @unittest.skipUnless(is_gx_available(), "great_expectations is not installed in this environment")
    def test_values_below_and_above_range_fail(self) -> None:
        """Verify observations below and above the permitted threshold range trigger alerts."""
        config = GXMonitoringConfig(
            suite_name="test_range_violations",
            thresholds=(
                GXMetricThreshold(column="cnt_mean", min_value=10.0, max_value=50.0),
            ),
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-02",
        )
        # Day 1: 5.0 (below min 10.0)
        # Day 2: 80.0 (above max 50.0)
        df = pd.DataFrame(
            {
                "batch_date": ["2012-01-01", "2012-01-02"],
                "cnt_mean": [5.0, 80.0],
            }
        )

        res = run_gx_monitoring(df, config)

        self.assertEqual(res.total_batches, 2)
        self.assertEqual(res.alert_batches, 2)
        self.assertEqual(res.first_alert_date, "2012-01-01")

        # Check day 1
        rec1 = res.records_df.iloc[0]
        self.assertTrue(rec1["is_alert"])
        self.assertIn("threshold_lower: cnt_mean=5.0 < 10.0", rec1["alert_reasons"])

        # Check day 2
        rec2 = res.records_df.iloc[1]
        self.assertTrue(rec2["is_alert"])
        self.assertIn("threshold_upper: cnt_mean=80.0 > 50.0", rec2["alert_reasons"])

    @unittest.skipUnless(is_gx_available(), "great_expectations is not installed in this environment")
    def test_missing_value_triggers_alert(self) -> None:
        """Verify missing (NaN) observations fail non-null expectation and raise an alert."""
        config = GXMonitoringConfig(
            suite_name="test_missing_alert",
            thresholds=(
                GXMetricThreshold(column="cnt_mean", min_value=10.0, max_value=50.0, allow_null=False),
            ),
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-01",
        )
        df = pd.DataFrame({"batch_date": ["2012-01-01"], "cnt_mean": [np.nan]})

        res = run_gx_monitoring(df, config)

        self.assertEqual(res.alert_batches, 1)
        rec = res.records_df.iloc[0]
        self.assertTrue(rec["is_alert"])
        self.assertIn("missing_value: cnt_mean is null", rec["alert_reasons"])

    @unittest.skipUnless(is_gx_available(), "great_expectations is not installed in this environment")
    def test_row_count_threshold(self) -> None:
        """Verify row_count volume monitoring flags batches with insufficient records."""
        config = GXMonitoringConfig(
            suite_name="test_row_count",
            thresholds=(
                GXMetricThreshold(column="row_count", min_value=20.0, max_value=24.0),
            ),
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-02",
        )
        df = pd.DataFrame(
            {
                "batch_date": ["2012-01-01", "2012-01-02"],
                "row_count": [15, 23],
            }
        )

        res = run_gx_monitoring(df, config)

        self.assertEqual(res.total_batches, 2)
        self.assertEqual(res.alert_batches, 1)

        # Day 1: 15 < 20 -> Alert
        rec1 = res.records_df.iloc[0]
        self.assertTrue(rec1["is_alert"])
        self.assertIn("threshold_lower: row_count=15.0 < 20.0", rec1["alert_reasons"])

        # Day 2: 23 in [20, 24] -> Clean
        rec2 = res.records_df.iloc[1]
        self.assertFalse(rec2["is_alert"])
        self.assertEqual(rec2["alert_reasons"], "none")

    @unittest.skipUnless(is_gx_available(), "great_expectations is not installed in this environment")
    def test_exact_threshold_boundary_behavior(self) -> None:
        """Verify exact threshold boundary behavior for inclusive vs. exclusive bounds."""
        # 1. Inclusive bounds (strict_min=False, strict_max=False): exactly on bounds must PASS
        config_inclusive = GXMonitoringConfig(
            suite_name="test_inclusive",
            thresholds=(
                GXMetricThreshold(column="cnt_mean", min_value=10.0, max_value=50.0, strict_min=False, strict_max=False),
            ),
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-02",
        )
        df_bounds = pd.DataFrame(
            {
                "batch_date": ["2012-01-01", "2012-01-02"],
                "cnt_mean": [10.0, 50.0],
            }
        )
        res_inc = run_gx_monitoring(df_bounds, config_inclusive)
        self.assertEqual(res_inc.alert_batches, 0, "Exact boundary values must pass under inclusive bounds")

        # 2. Strict / Exclusive bounds (strict_min=True, strict_max=True): exactly on bounds must FAIL
        config_strict = GXMonitoringConfig(
            suite_name="test_strict",
            thresholds=(
                GXMetricThreshold(column="cnt_mean", min_value=10.0, max_value=50.0, strict_min=True, strict_max=True),
            ),
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-02",
        )
        res_strict = run_gx_monitoring(df_bounds, config_strict)
        self.assertEqual(res_strict.alert_batches, 2, "Exact boundary values must fail under exclusive/strict bounds")

    def test_missing_metric_column_raises_error(self) -> None:
        """Verify run_gx_monitoring raises ValueError when configured metric column is missing."""
        config = GXMonitoringConfig(
            suite_name="test_missing_col",
            thresholds=(
                GXMetricThreshold(column="nonexistent_metric", min_value=10.0),
            ),
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-01",
        )
        df = pd.DataFrame({"batch_date": ["2012-01-01"], "cnt_mean": [25.0]})

        if is_gx_available():
            with self.assertRaises(ValueError) as ctx:
                run_gx_monitoring(df, config)
            self.assertIn("nonexistent_metric", str(ctx.exception))
        else:
            with self.assertRaises(ImportError):
                run_gx_monitoring(df, config)

    @unittest.skipUnless(is_gx_available(), "great_expectations is not installed in this environment")
    def test_deterministic_ordering_and_output_structure(self) -> None:
        """Verify batch output is deterministically ordered ascending by date."""
        config = GXMonitoringConfig(
            suite_name="test_ordering",
            thresholds=(
                GXMetricThreshold(column="cnt_mean", min_value=10.0, max_value=50.0),
            ),
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-03",
        )
        # Disordered input
        df = pd.DataFrame(
            {
                "batch_date": ["2012-01-03", "2012-01-01", "2012-01-02"],
                "cnt_mean": [30.0, 20.0, 25.0],
            }
        )

        res = run_gx_monitoring(df, config)

        dates = res.records_df["batch_date"].tolist()
        self.assertEqual(dates, ["2012-01-01", "2012-01-02", "2012-01-03"])

    @unittest.skipUnless(is_gx_available(), "great_expectations is not installed in this environment")
    def test_save_results_artifacts(self) -> None:
        """Verify machine-readable CSV and JSON artifacts are saved correctly."""
        config = GXMonitoringConfig(
            suite_name="test_save",
            thresholds=(
                GXMetricThreshold(column="cnt_mean", min_value=10.0, max_value=50.0),
            ),
            monitoring_start="2012-01-01",
            monitoring_end="2012-01-01",
        )
        df = pd.DataFrame({"batch_date": ["2012-01-01"], "cnt_mean": [25.0]})

        with tempfile.TemporaryDirectory() as tmp_dir:
            res = run_gx_monitoring(df, config, output_dir=tmp_dir)

            summary_csv = Path(tmp_dir) / "gx_monitoring_daily_summary.csv"
            detailed_csv = Path(tmp_dir) / "gx_monitoring_detailed_records.csv"
            summary_json = Path(tmp_dir) / "gx_monitoring_summary.json"

            self.assertTrue(summary_csv.is_file())
            self.assertTrue(detailed_csv.is_file())
            self.assertTrue(summary_json.is_file())

            with open(summary_json) as f:
                d = json.load(f)
                self.assertEqual(d["suite_name"], "test_save")
                self.assertEqual(d["total_batches"], 1)


if __name__ == "__main__":
    unittest.main()

