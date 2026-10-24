"""Automated integration tests for end-to-end pipeline reproduction workflow."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

import pandas as pd

from scripts.reproduce_pipeline import reproduce_all
from scripts.generate_publication_outputs import MATPLOTLIB_AVAILABLE
from src.spc.gx_monitor import is_gx_available


class TestPipelineReproduction(unittest.TestCase):
    """Verify that reproduce_pipeline runs cleanly in an isolated temporary tree."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[1]
        cls.raw_hour = cls.repo_root / "data/raw/hour.csv"
        cls.gx_config = cls.repo_root / "configs/gx_thresholds_daily_metrics.json"

    def test_reproduce_pipeline_isolated_execution(self) -> None:
        """Run all reproducible pipeline stages in a fresh temporary directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)

            # Copy minimal inputs required: data/raw/hour.csv and configs/
            dest_raw = tmp_root / "data/raw"
            dest_raw.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.raw_hour, dest_raw / "hour.csv")

            dest_cfg = tmp_root / "configs"
            dest_cfg.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.gx_config, dest_cfg / "gx_thresholds_daily_metrics.json")

            # Determine whether GX can be executed
            skip_gx = not is_gx_available()

            # Execute pipeline
            result = reproduce_all(
                base_dir=tmp_root,
                skip_gx=skip_gx,
                skip_figures=not MATPLOTLIB_AVAILABLE,
            )

            self.assertEqual(result["status"], "success")

            # 1. Verify drift files
            drift_dir = tmp_root / "data/processed/drift"
            self.assertTrue((drift_dir / "hour_abrupt_shift_cnt.csv").is_file())
            self.assertTrue((drift_dir / "hour_gradual_null_temp.csv").is_file())
            self.assertTrue((drift_dir / "ground_truth_abrupt_shift_cnt.json").is_file())
            self.assertTrue((drift_dir / "ground_truth_gradual_null_temp.json").is_file())

            # 2. Verify daily quality metrics
            self.assertTrue((tmp_root / "results/raw/daily_quality_metrics.csv").is_file())
            self.assertTrue((tmp_root / "results/processed/daily_quality_metrics_raw_with_null_cols.csv").is_file())
            self.assertTrue((tmp_root / "results/processed/daily_metrics_abrupt_shift_cnt.csv").is_file())
            self.assertTrue((tmp_root / "results/processed/daily_metrics_gradual_null_temp.csv").is_file())

            # 3. Verify Shewhart and p-chart monitoring tables
            sh_csv = tmp_root / "results/processed/monitoring_shewhart_cnt_mean.csv"
            p_csv = tmp_root / "results/processed/monitoring_p_chart_temp_null_rate.csv"
            self.assertTrue(sh_csv.is_file())
            self.assertTrue(p_csv.is_file())

            df_sh = pd.read_csv(sh_csv)
            df_p = pd.read_csv(p_csv)
            self.assertEqual(len(df_sh), 366)
            self.assertEqual(len(df_p), 366)

            # Compare Shewhart and p-chart with committed baselines
            expected_sh = pd.read_csv(self.repo_root / "results/processed/monitoring_shewhart_cnt_mean.csv")
            expected_p = pd.read_csv(self.repo_root / "results/processed/monitoring_p_chart_temp_null_rate.csv")
            pd.testing.assert_frame_equal(df_sh, expected_sh)
            pd.testing.assert_frame_equal(df_p, expected_p)

            # 4. Verify CUSUM monitoring table
            cusum_csv = tmp_root / "results/processed/monitoring_cusum_cnt_mean.csv"
            self.assertTrue(cusum_csv.is_file())
            df_cusum = pd.read_csv(cusum_csv)
            self.assertEqual(len(df_cusum), 366)
            expected_cusum = pd.read_csv(self.repo_root / "results/processed/monitoring_cusum_cnt_mean.csv")
            pd.testing.assert_frame_equal(df_cusum, expected_cusum, atol=1e-12, rtol=1e-12)

            # If GX was executed, verify comparative alerts and metrics
            if not skip_gx:
                alerts_csv = tmp_root / "results/processed/comparative_daily_alerts.csv"
                metrics_csv = tmp_root / "results/tables/comparative_metrics.csv"
                self.assertTrue(alerts_csv.is_file())
                self.assertTrue(metrics_csv.is_file())

                df_alerts = pd.read_csv(alerts_csv)
                df_metrics = pd.read_csv(metrics_csv)
                expected_alerts = pd.read_csv(self.repo_root / "results/processed/comparative_daily_alerts.csv")
                expected_metrics = pd.read_csv(self.repo_root / "results/tables/comparative_metrics.csv")

                pd.testing.assert_frame_equal(df_alerts, expected_alerts)
                pd.testing.assert_frame_equal(df_metrics, expected_metrics)


if __name__ == "__main__":
    unittest.main()

