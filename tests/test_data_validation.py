"""Automated tests for the dataset validation module."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.spc.data_validation import EXPECTED_HOURLY_COLUMNS, inspect_dataset


class TestDatasetValidation(unittest.TestCase):
    """Test suite for inspect_dataset function."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.hour_csv_path = self.repo_root / "data" / "raw" / "hour.csv"
        self.day_csv_path = self.repo_root / "data" / "raw" / "day.csv"

    def test_inspect_valid_hour_dataset(self) -> None:
        """Verify inspection of the actual data/raw/hour.csv dataset."""
        metrics = inspect_dataset(self.hour_csv_path)

        self.assertEqual(metrics["file_name"], "hour.csv")
        self.assertEqual(metrics["row_count"], 17379)
        self.assertEqual(metrics["column_count"], 17)
        self.assertEqual(metrics["total_missing_cells"], 0)
        self.assertEqual(metrics["duplicate_rows"], 0)
        self.assertEqual(metrics["duplicate_instant_identifiers"], 0)
        self.assertEqual(metrics["invalid_timestamps"], 0)
        self.assertEqual(metrics["earliest_date"], "2011-01-01")
        self.assertEqual(metrics["latest_date"], "2012-12-31")

    def test_missing_file_raises_error(self) -> None:
        """Verify that a non-existent file raises FileNotFoundError."""
        non_existent_path = self.repo_root / "data" / "raw" / "does_not_exist.csv"
        with self.assertRaises(FileNotFoundError) as ctx:
            inspect_dataset(non_existent_path)
        self.assertIn("not found", str(ctx.exception).lower())

    def test_schema_mismatch_day_csv(self) -> None:
        """Verify that day.csv (missing 'hr') raises ValueError for hourly schema."""
        with self.assertRaises(ValueError) as ctx:
            inspect_dataset(self.day_csv_path)
        self.assertIn("Missing required column(s)", str(ctx.exception))
        self.assertIn("hr", str(ctx.exception))

    def test_schema_mismatch_missing_columns(self) -> None:
        """Verify that missing expected columns trigger ValueError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "missing_cols.csv"
            # Exclude 'temp' and 'cnt'
            subset_cols = [c for c in EXPECTED_HOURLY_COLUMNS if c not in ("temp", "cnt")]
            df = pd.DataFrame(columns=subset_cols)
            df.to_csv(csv_path, index=False)

            with self.assertRaises(ValueError) as ctx:
                inspect_dataset(csv_path)
            err_msg = str(ctx.exception)
            self.assertIn("Missing required column(s)", err_msg)
            self.assertIn("temp", err_msg)
            self.assertIn("cnt", err_msg)

    def test_schema_mismatch_unexpected_columns(self) -> None:
        """Verify that extra unexpected columns trigger ValueError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "extra_cols.csv"
            extra_cols = list(EXPECTED_HOURLY_COLUMNS) + ["extra_feature"]
            df = pd.DataFrame(columns=extra_cols)
            df.to_csv(csv_path, index=False)

            with self.assertRaises(ValueError) as ctx:
                inspect_dataset(csv_path)
            err_msg = str(ctx.exception)
            self.assertIn("Unexpected column(s)", err_msg)
            self.assertIn("extra_feature", err_msg)

    def test_duplicate_detection(self) -> None:
        """Verify duplicate rows and duplicate instant identifiers are detected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "duplicates.csv"
            # 3 rows where row 1 and row 2 are identical, and instant has duplicates
            sample_row = {col: 1 for col in EXPECTED_HOURLY_COLUMNS}
            sample_row["dteday"] = "2011-01-01"
            sample_row["instant"] = 100

            df = pd.DataFrame([sample_row, sample_row, {**sample_row, "hr": 2}])
            df.to_csv(csv_path, index=False)

            metrics = inspect_dataset(csv_path)
            self.assertEqual(metrics["row_count"], 3)
            self.assertEqual(metrics["duplicate_rows"], 1)
            self.assertEqual(metrics["duplicate_instant_identifiers"], 2)

    def test_missing_cells_and_invalid_timestamps(self) -> None:
        """Verify missing cells and unparseable dates are detected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "corrupted.csv"
            row1 = {col: 1 for col in EXPECTED_HOURLY_COLUMNS}
            row1["dteday"] = "2011-05-10"

            row2 = {col: 1 for col in EXPECTED_HOURLY_COLUMNS}
            row2["dteday"] = "not_a_valid_date"
            row2["temp"] = None  # Missing cell
            row2["instant"] = 2

            df = pd.DataFrame([row1, row2])
            df.to_csv(csv_path, index=False)

            metrics = inspect_dataset(csv_path)
            self.assertEqual(metrics["row_count"], 2)
            self.assertEqual(metrics["total_missing_cells"], 1)
            self.assertEqual(metrics["invalid_timestamps"], 1)
            self.assertEqual(metrics["earliest_date"], "2011-05-10")
            self.assertEqual(metrics["latest_date"], "2011-05-10")


if __name__ == "__main__":
    unittest.main()

