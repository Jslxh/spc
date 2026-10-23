"""Automated tests for the baseline daily quality metrics module."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

from src.spc.quality_metrics import (
    METRIC_COLUMNS,
    REQUIRED_COLUMNS,
    calculate_daily_quality_metrics,
    compute_daily_quality_metrics,
    main as cli_main,
)


class TestDailyQualityMetrics(unittest.TestCase):
    """Test suite for compute_daily_quality_metrics."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.hour_csv_path = self.repo_root / "data" / "raw" / "hour.csv"

    # --- 8 Existing Tests (Preserved 100%) ---

    def test_grouping_row_counts_and_date_ordering(self) -> None:
        """Verify grouping, row counts, and strict ascending date ordering."""
        # Input provided intentionally in reverse chronological order
        df = pd.DataFrame(
            {
                "dteday": ["2023-01-02", "2023-01-01", "2023-01-01"],
                "cnt": [50, 10, 30],
                "season": [1, 1, 1],
                "weathersit": [1, 1, 2],
            }
        )

        metrics = compute_daily_quality_metrics(df)

        self.assertEqual(len(metrics), 2)
        # Check sorted order
        self.assertEqual(metrics.loc[0, "batch_date"], "2023-01-01")
        self.assertEqual(metrics.loc[0, "row_count"], 2)
        self.assertEqual(metrics.loc[1, "batch_date"], "2023-01-02")
        self.assertEqual(metrics.loc[1, "row_count"], 1)

    def test_null_rate_calculation(self) -> None:
        """Verify null rate calculation (missing cells / total cells in batch)."""
        # 2 rows x 4 columns = 8 total cells.
        # Exactly 2 cells are None (1 in cnt, 1 in weathersit) -> 2 / 8 = 0.25 (25%)
        df = pd.DataFrame(
            {
                "dteday": ["2023-05-01", "2023-05-01"],
                "cnt": [100.0, None],
                "season": [1, 1],
                "weathersit": [None, 2],
            }
        )

        metrics = compute_daily_quality_metrics(df)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics.loc[0, "row_count"], 2)
        self.assertAlmostEqual(metrics.loc[0, "null_rate"], 0.25, places=6)

    def test_mean_and_std_calculation(self) -> None:
        """Verify calculation of cnt_mean and cnt_std, including single-row batches."""
        # Day 1: cnt = [10, 20, 30] -> mean = 20.0, sample std = 10.0
        # Day 2: cnt = [42] -> single-row batch -> mean = 42.0, std = 0.0
        df = pd.DataFrame(
            {
                "dteday": ["2023-06-01", "2023-06-01", "2023-06-01", "2023-06-02"],
                "cnt": [10, 20, 30, 42],
                "season": [1, 1, 1, 1],
                "weathersit": [1, 1, 1, 1],
            }
        )

        metrics = compute_daily_quality_metrics(df)

        self.assertEqual(len(metrics), 2)
        # Day 1 checks
        self.assertEqual(metrics.loc[0, "batch_date"], "2023-06-01")
        self.assertAlmostEqual(metrics.loc[0, "cnt_mean"], 20.0, places=6)
        self.assertAlmostEqual(metrics.loc[0, "cnt_std"], 10.0, places=6)

        # Day 2 checks (single-row batch)
        self.assertEqual(metrics.loc[1, "batch_date"], "2023-06-02")
        self.assertAlmostEqual(metrics.loc[1, "cnt_mean"], 42.0, places=6)
        self.assertAlmostEqual(metrics.loc[1, "cnt_std"], 0.0, places=6)

    def test_cardinality_metrics(self) -> None:
        """Verify season and weathersit distinct non-null cardinality counts."""
        df = pd.DataFrame(
            {
                "dteday": ["2023-07-01", "2023-07-01", "2023-07-01", "2023-07-01"],
                "cnt": [10, 20, 30, 40],
                "season": [1, 2, 2, None],  # 2 distinct non-null seasons (1 and 2)
                "weathersit": [1, 2, 3, 4],  # 4 distinct non-null weathersits
            }
        )

        metrics = compute_daily_quality_metrics(df)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics.loc[0, "season_cardinality"], 2)
        self.assertEqual(metrics.loc[0, "weathersit_cardinality"], 4)

    def test_missing_required_columns(self) -> None:
        """Verify that missing required columns raise ValueError."""
        # Missing 'cnt'
        df_no_cnt = pd.DataFrame(
            {
                "dteday": ["2023-01-01"],
                "season": [1],
                "weathersit": [1],
            }
        )
        with self.assertRaises(ValueError) as ctx:
            compute_daily_quality_metrics(df_no_cnt)
        self.assertIn("Missing required column(s)", str(ctx.exception))
        self.assertIn("cnt", str(ctx.exception))

    def test_invalid_dates_and_empty_input(self) -> None:
        """Verify invalid date handling and explicit handling of empty inputs."""
        # Unparseable string date
        df_invalid = pd.DataFrame(
            {
                "dteday": ["invalid_date_str"],
                "cnt": [10],
                "season": [1],
                "weathersit": [1],
            }
        )
        with self.assertRaises(ValueError) as ctx:
            compute_daily_quality_metrics(df_invalid)
        self.assertIn("Invalid or unparseable dates", str(ctx.exception))

        # Valid empty input
        df_empty = pd.DataFrame(columns=list(REQUIRED_COLUMNS))
        metrics_empty = compute_daily_quality_metrics(df_empty)
        self.assertEqual(len(metrics_empty), 0)
        self.assertEqual(list(metrics_empty.columns), list(METRIC_COLUMNS))

    def test_raw_input_immutability(self) -> None:
        """Verify raw input DataFrame is not mutated."""
        df = pd.DataFrame(
            {
                "dteday": ["2023-01-01", "2023-01-01"],
                "cnt": [10, 20],
                "season": [1, 1],
                "weathersit": [1, 2],
            }
        )
        original_copy = df.copy(deep=True)

        _ = compute_daily_quality_metrics(df)

        pd.testing.assert_frame_equal(df, original_copy)

    def test_real_dataset_daily_metrics(self) -> None:
        """Verify daily metrics calculation against the actual hour.csv dataset."""
        df_hour = pd.read_csv(self.hour_csv_path)
        metrics = compute_daily_quality_metrics(df_hour)

        # 731 days (365 in 2011, 366 in leap year 2012)
        self.assertEqual(len(metrics), 731)
        self.assertEqual(metrics["batch_date"].min(), "2011-01-01")
        self.assertEqual(metrics["batch_date"].max(), "2012-12-31")
        self.assertEqual(metrics["null_rate"].max(), 0.0)

        # Hurricane Sandy day (2012-10-29): single-row batch
        sandy_metric = metrics[metrics["batch_date"] == "2012-10-29"].iloc[0]
        self.assertEqual(sandy_metric["row_count"], 1)
        self.assertAlmostEqual(sandy_metric["cnt_mean"], 22.0, places=6)
        self.assertAlmostEqual(sandy_metric["cnt_std"], 0.0, places=6)
        self.assertEqual(sandy_metric["season_cardinality"], 1)
        self.assertEqual(sandy_metric["weathersit_cardinality"], 1)

    # --- New Tests for Per-Column Null Rates and Generalization ---

    def test_per_column_null_rate_calculation(self) -> None:
        """Verify accurate calculation of per-column null rates alongside aggregate null_rate."""
        # 4 rows on 2023-01-01 with 5 columns
        # temp has 1 null out of 4 -> 0.25 (25%)
        # cnt has 2 nulls out of 4 -> 0.50 (50%)
        # total missing = 3 out of 20 cells -> 0.15 (15%)
        df = pd.DataFrame(
            {
                "dteday": ["2023-01-01"] * 4,
                "cnt": [10.0, None, 30.0, None],
                "temp": [0.2, None, 0.4, 0.5],
                "season": [1, 1, 1, 1],
                "weathersit": [1, 1, 2, 2],
            }
        )

        metrics = compute_daily_quality_metrics(
            df, null_rate_columns=["temp", "cnt"]
        )

        self.assertEqual(len(metrics), 1)
        self.assertAlmostEqual(metrics.loc[0, "null_rate"], 3 / 20, places=6)
        self.assertAlmostEqual(metrics.loc[0, "temp_null_rate"], 1 / 4, places=6)
        self.assertAlmostEqual(metrics.loc[0, "cnt_null_rate"], 2 / 4, places=6)
        # Expected column order
        expected = [
            "batch_date",
            "row_count",
            "null_rate",
            "temp_null_rate",
            "cnt_null_rate",
            "cnt_mean",
            "cnt_std",
            "season_cardinality",
            "weathersit_cardinality",
        ]
        self.assertEqual(list(metrics.columns), expected)

    def test_missing_requested_null_columns_raises_error(self) -> None:
        """Verify that requesting null rate for a nonexistent column raises ValueError."""
        df = pd.DataFrame(
            {
                "dteday": ["2023-01-01"],
                "cnt": [10],
                "season": [1],
                "weathersit": [1],
            }
        )
        with self.assertRaises(ValueError) as ctx:
            compute_daily_quality_metrics(df, null_rate_columns=["nonexistent_col"])
        self.assertIn("Requested null_rate column(s) not found", str(ctx.exception))
        self.assertIn("nonexistent_col", str(ctx.exception))

    def test_custom_date_target_and_cardinality_columns(self) -> None:
        """Verify configurable date, target, and cardinality column names."""
        df = pd.DataFrame(
            {
                "event_timestamp": ["2023-08-01", "2023-08-01", "2023-08-02"],
                "temperature": [20.0, 30.0, 25.0],
                "city": ["NYC", "NYC", "LA"],
            }
        )

        metrics = compute_daily_quality_metrics(
            df,
            date_column="event_timestamp",
            target_column="temperature",
            cardinality_columns=["city"],
            null_rate_columns=["temperature"],
        )

        self.assertEqual(len(metrics), 2)
        expected_cols = [
            "batch_date",
            "row_count",
            "null_rate",
            "temperature_null_rate",
            "temperature_mean",
            "temperature_std",
            "city_cardinality",
        ]
        self.assertEqual(list(metrics.columns), expected_cols)
        # Check temperature values
        self.assertAlmostEqual(metrics.loc[0, "temperature_mean"], 25.0)
        self.assertAlmostEqual(metrics.loc[0, "temperature_std"], float(np.std([20.0, 30.0], ddof=1)))
        self.assertEqual(metrics.loc[0, "city_cardinality"], 1)

    def test_all_missing_target_column_evaluates_to_nan(self) -> None:
        """Verify target mean and std evaluate to NaN when all target values in a batch are null."""
        df = pd.DataFrame(
            {
                "dteday": ["2023-09-01", "2023-09-01"],
                "cnt": [None, None],
                "season": [1, 1],
                "weathersit": [1, 1],
            }
        )

        metrics = compute_daily_quality_metrics(df)

        self.assertEqual(len(metrics), 1)
        self.assertTrue(np.isnan(metrics.loc[0, "cnt_mean"]))
        self.assertTrue(np.isnan(metrics.loc[0, "cnt_std"]))

    def test_public_alias_compatibility(self) -> None:
        """Verify calculate_daily_quality_metrics alias produces identical results."""
        df = pd.DataFrame(
            {
                "dteday": ["2023-01-01"],
                "cnt": [50],
                "season": [1],
                "weathersit": [1],
            }
        )
        res1 = compute_daily_quality_metrics(df)
        res2 = calculate_daily_quality_metrics(df)
        pd.testing.assert_frame_equal(res1, res2)

    def test_cli_execution_with_arguments(self) -> None:
        """Verify CLI main entry point accepts custom arguments and creates output files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_csv = Path(tmpdir) / "custom_input.csv"
            output_csv = Path(tmpdir) / "nested" / "custom_metrics.csv"

            # Create test dataset
            df = pd.DataFrame(
                {
                    "dteday": ["2023-01-01", "2023-01-02"],
                    "cnt": [10.0, 20.0],
                    "temp": [0.5, None],
                    "season": [1, 1],
                    "weathersit": [1, 1],
                }
            )
            df.to_csv(input_csv, index=False)

            # Run CLI via main()
            cli_main(
                [
                    "--input",
                    str(input_csv),
                    "--output",
                    str(output_csv),
                    "--null-columns",
                    "temp",
                    "cnt",
                ]
            )

            self.assertTrue(output_csv.exists())
            metrics = pd.read_csv(output_csv)
            self.assertEqual(len(metrics), 2)
            self.assertIn("temp_null_rate", metrics.columns)
            self.assertIn("cnt_null_rate", metrics.columns)
            self.assertAlmostEqual(metrics.loc[1, "temp_null_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
