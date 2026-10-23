"""Automated tests for deterministic synthetic drift injection."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

from src.spc.drift_injection import (
    AbruptShiftConfig,
    GradualNullDriftConfig,
    GroundTruthRecord,
    inject_abrupt_distribution_shift,
    inject_gradual_null_drift,
    save_injection_artifacts,
)


class TestDriftInjection(unittest.TestCase):
    """Test suite for deterministic drift injection module."""

    def _create_synthetic_df(self) -> pd.DataFrame:
        """Create a clean 3-day synthetic DataFrame for testing."""
        dates = ["2023-01-01"] * 10 + ["2023-01-02"] * 10 + ["2023-01-03"] * 10
        return pd.DataFrame(
            {
                "instant": list(range(1, 31)),
                "dteday": dates,
                "cnt": [100.0] * 30,
                "temp": [0.5] * 30,
                "season": [1] * 30,
            }
        )

    def test_gradual_null_drift_synthetic(self) -> None:
        """Verify gradual null drift schedule, ground-truth accuracy, and target isolation."""
        df = self._create_synthetic_df()
        config = GradualNullDriftConfig(
            event_id="test_gradual_null",
            affected_column="temp",
            onset_date="2023-01-02",
            end_date="2023-01-03",
            start_null_rate=0.20,
            max_null_rate=0.80,
            random_seed=123,
        )

        modified_df, gt = inject_gradual_null_drift(df, config)

        # 1. Day 1 (pre-onset) must have 0 nulls injected
        day1_mask = modified_df["dteday"] == "2023-01-01"
        self.assertEqual(modified_df.loc[day1_mask, "temp"].isna().sum(), 0)

        # 2. Days 2 and 3 must have nulls injected in 'temp'
        day2_nulls = modified_df.loc[modified_df["dteday"] == "2023-01-02", "temp"].isna().sum()
        day3_nulls = modified_df.loc[modified_df["dteday"] == "2023-01-03", "temp"].isna().sum()
        self.assertGreater(day2_nulls, 0)
        self.assertGreater(day3_nulls, 0)

        # 3. Non-target columns and timestamps must remain 100% non-null and untouched
        self.assertEqual(modified_df["cnt"].isna().sum(), 0)
        self.assertEqual(modified_df["season"].isna().sum(), 0)
        pd.testing.assert_series_equal(modified_df["dteday"], df["dteday"])
        pd.testing.assert_series_equal(modified_df["cnt"], df["cnt"])

        # 4. Ground truth records match actual DataFrame counts
        self.assertEqual(gt.measured_outcome["total_injected_null_cells"], int(day2_nulls + day3_nulls))
        batch_dict = {b["batch_date"]: b for b in gt.batch_records}
        self.assertEqual(batch_dict["2023-01-01"]["injected_missing_count"], 0)
        self.assertEqual(batch_dict["2023-01-02"]["injected_missing_count"], day2_nulls)
        self.assertEqual(batch_dict["2023-01-03"]["injected_missing_count"], day3_nulls)
        self.assertEqual(batch_dict["2023-01-02"]["intended_null_rate"], 0.20)
        self.assertEqual(batch_dict["2023-01-03"]["intended_null_rate"], 0.80)

    def test_gradual_null_drift_reproducibility(self) -> None:
        """Verify identical seed produces bit-exact output, different seed alters mask."""
        df = self._create_synthetic_df()
        config1 = GradualNullDriftConfig(
            event_id="test_reproducibility_1",
            affected_column="cnt",
            onset_date="2023-01-02",
            start_null_rate=0.10,
            max_null_rate=0.50,
            random_seed=999,
        )
        config2 = GradualNullDriftConfig(
            event_id="test_reproducibility_2",
            affected_column="cnt",
            onset_date="2023-01-02",
            start_null_rate=0.10,
            max_null_rate=0.50,
            random_seed=999,
        )
        config_diff = GradualNullDriftConfig(
            event_id="test_reproducibility_diff",
            affected_column="cnt",
            onset_date="2023-01-02",
            start_null_rate=0.10,
            max_null_rate=0.50,
            random_seed=111,
        )

        mod1, _ = inject_gradual_null_drift(df, config1)
        mod2, _ = inject_gradual_null_drift(df, config2)
        mod_diff, _ = inject_gradual_null_drift(df, config_diff)

        # Same seed produces bit-exact identical DataFrames
        pd.testing.assert_frame_equal(mod1, mod2)

        # Different seed produces different mask (with high probability on 20 rows)
        self.assertFalse(mod1["cnt"].isna().equals(mod_diff["cnt"].isna()))

    def test_abrupt_shift_additive_synthetic(self) -> None:
        """Verify abrupt additive distribution shift within event window."""
        df = self._create_synthetic_df()
        config = AbruptShiftConfig(
            event_id="test_abrupt_additive",
            affected_column="cnt",
            onset_date="2023-01-02",
            end_date="2023-01-03",
            shift_type="additive",
            shift_value=50.0,
            random_seed=42,
        )

        modified_df, gt = inject_abrupt_distribution_shift(df, config)

        # Day 1: unchanged (all 100.0)
        day1_cnt = modified_df.loc[modified_df["dteday"] == "2023-01-01", "cnt"]
        self.assertTrue((day1_cnt == 100.0).all())

        # Days 2 and 3: shifted by +50.0 (all 150.0)
        day2_cnt = modified_df.loc[modified_df["dteday"] == "2023-01-02", "cnt"]
        day3_cnt = modified_df.loc[modified_df["dteday"] == "2023-01-03", "cnt"]
        self.assertTrue((day2_cnt == 150.0).all())
        self.assertTrue((day3_cnt == 150.0).all())

        # Ground truth measured outcome
        self.assertEqual(gt.measured_outcome["total_rows_affected"], 20)
        self.assertAlmostEqual(gt.measured_outcome["effective_overall_shift"], 50.0, places=5)
        self.assertEqual(gt.measured_outcome["total_clipped_cells"], 0)

        # Unrelated columns preserved
        pd.testing.assert_series_equal(modified_df["temp"], df["temp"])
        pd.testing.assert_series_equal(modified_df["season"], df["season"])

    def test_abrupt_shift_multiplicative_and_clipping(self) -> None:
        """Verify multiplicative shift and clipping bounds."""
        df = pd.DataFrame(
            {
                "dteday": ["2023-01-01", "2023-01-02", "2023-01-02"],
                "temp": [0.4, 0.4, 0.8],
            }
        )
        config = AbruptShiftConfig(
            event_id="test_abrupt_clip",
            affected_column="temp",
            onset_date="2023-01-02",
            shift_type="multiplicative",
            shift_value=2.0,
            clip_max=1.0,  # 0.4 * 2.0 = 0.8, 0.8 * 2.0 = 1.6 -> clipped to 1.0
            random_seed=42,
        )

        modified_df, gt = inject_abrupt_distribution_shift(df, config)

        self.assertEqual(modified_df.loc[0, "temp"], 0.4)
        self.assertEqual(modified_df.loc[1, "temp"], 0.8)
        self.assertEqual(modified_df.loc[2, "temp"], 1.0)  # Clipped

        self.assertEqual(gt.measured_outcome["total_clipped_cells"], 1)

    def test_abrupt_shift_event_duration_window(self) -> None:
        """Verify shift only applies within [onset_date, end_date] and reverts outside."""
        df = pd.DataFrame(
            {
                "dteday": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"],
                "cnt": [10.0, 10.0, 10.0, 10.0],
            }
        )
        config = AbruptShiftConfig(
            event_id="test_window",
            affected_column="cnt",
            onset_date="2023-01-02",
            end_date="2023-01-03",
            shift_type="additive",
            shift_value=20.0,
        )

        modified_df, gt = inject_abrupt_distribution_shift(df, config)

        self.assertEqual(modified_df.loc[0, "cnt"], 10.0)  # Before onset
        self.assertEqual(modified_df.loc[1, "cnt"], 30.0)  # Inside window
        self.assertEqual(modified_df.loc[2, "cnt"], 30.0)  # Inside window
        self.assertEqual(modified_df.loc[3, "cnt"], 10.0)  # After end_date

        self.assertEqual(gt.measured_outcome["total_rows_affected"], 2)

    def test_input_immutability(self) -> None:
        """Verify original DataFrame is never mutated during injection."""
        df = self._create_synthetic_df()
        orig_copy = df.copy(deep=True)

        config_null = GradualNullDriftConfig(
            event_id="test_immutability_null",
            affected_column="temp",
            onset_date="2023-01-02",
        )
        _ = inject_gradual_null_drift(df, config_null)
        pd.testing.assert_frame_equal(df, orig_copy)

        config_shift = AbruptShiftConfig(
            event_id="test_immutability_shift",
            affected_column="cnt",
            onset_date="2023-01-02",
        )
        _ = inject_abrupt_distribution_shift(df, config_shift)
        pd.testing.assert_frame_equal(df, orig_copy)

    def test_invalid_configurations_raise_error(self) -> None:
        """Verify strict input validation and descriptive ValueErrors."""
        df = self._create_synthetic_df()

        # Nonexistent column
        with self.assertRaises(ValueError) as ctx:
            inject_gradual_null_drift(
                df,
                GradualNullDriftConfig(
                    event_id="bad_col",
                    affected_column="nonexistent",
                    onset_date="2023-01-02",
                ),
            )
        self.assertIn("not found", str(ctx.exception))

        # Onset date outside dataset range
        with self.assertRaises(ValueError) as ctx:
            inject_gradual_null_drift(
                df,
                GradualNullDriftConfig(
                    event_id="bad_date",
                    affected_column="cnt",
                    onset_date="2020-01-01",
                ),
            )
        self.assertIn("outside dataset date range", str(ctx.exception))

        # end_date earlier than onset_date
        with self.assertRaises(ValueError) as ctx:
            inject_gradual_null_drift(
                df,
                GradualNullDriftConfig(
                    event_id="bad_window",
                    affected_column="cnt",
                    onset_date="2023-01-03",
                    end_date="2023-01-01",
                ),
            )
        self.assertIn("cannot be earlier", str(ctx.exception))

        # start_null_rate > max_null_rate
        with self.assertRaises(ValueError) as ctx:
            inject_gradual_null_drift(
                df,
                GradualNullDriftConfig(
                    event_id="bad_rates",
                    affected_column="cnt",
                    onset_date="2023-01-02",
                    start_null_rate=0.9,
                    max_null_rate=0.2,
                ),
            )
        self.assertIn("cannot exceed max_null_rate", str(ctx.exception))

        # Invalid shift_type
        with self.assertRaises(ValueError) as ctx:
            inject_abrupt_distribution_shift(
                df,
                AbruptShiftConfig(
                    event_id="bad_shift_type",
                    affected_column="cnt",
                    onset_date="2023-01-02",
                    shift_type="invalid_type",  # type: ignore
                ),
            )
        self.assertIn("Invalid shift_type", str(ctx.exception))

        # clip_min > clip_max
        with self.assertRaises(ValueError) as ctx:
            inject_abrupt_distribution_shift(
                df,
                AbruptShiftConfig(
                    event_id="bad_clips",
                    affected_column="cnt",
                    onset_date="2023-01-02",
                    clip_min=100.0,
                    clip_max=50.0,
                ),
            )
        self.assertIn("cannot exceed clip_max", str(ctx.exception))

    def test_save_injection_artifacts(self) -> None:
        """Verify saving dataset and ground truth JSON artifacts to disk."""
        df = self._create_synthetic_df()
        config = AbruptShiftConfig(
            event_id="test_save",
            affected_column="cnt",
            onset_date="2023-01-02",
            shift_value=25.0,
        )
        modified_df, gt = inject_abrupt_distribution_shift(df, config)

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path, json_path = save_injection_artifacts(
                modified_df=modified_df,
                ground_truth=gt,
                output_dir=tmpdir,
                csv_filename="test_out.csv",
                json_filename="test_gt.json",
            )

            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())

            # Load and verify JSON content
            with open(json_path, "r", encoding="utf-8") as f:
                loaded_gt = json.load(f)
            self.assertEqual(loaded_gt["event_id"], "test_save")
            self.assertEqual(loaded_gt["scenario_type"], "abrupt_distribution_shift")
            self.assertEqual(loaded_gt["affected_column"], "cnt")
            self.assertEqual(len(loaded_gt["batch_records"]), 3)


if __name__ == "__main__":
    unittest.main()

