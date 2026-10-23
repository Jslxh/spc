"""Unit and integration tests for the unified SPC evaluation layer.

Tests verify:
1. Exact date alignment across all monitoring artifacts in Phase II (366 days).
2. Ground-truth onset definitions and batch partitions.
3. Pre-onset false alarms and the "already alarming" eve-of-onset condition.
4. Detection lag sensitivity (configured onset vs. first observed defect).
5. Exact confusion-matrix arithmetic and edge cases.
6. Graceful handling of uncalibrated zero-variance CUSUM and invalid inputs.
7. 100% method agreement between GX threshold rules and corresponding SPC charts.
8. Reproducibility of all evaluation artifacts from identical inputs.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from src.spc.evaluation import (
    compute_alarm_episodes,
    compute_batch_metrics,
    evaluate_event_detection,
    generate_and_save_cusum_cnt_mean,
    run_unified_evaluation,
)
from src.spc.cusum import calibrate_gaussian_cusum


class TestUnifiedEvaluation(unittest.TestCase):
    """Test suite for comparative evaluation metrics and artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        cls.daily_alerts_path = cls.root / "results/processed/comparative_daily_alerts.csv"
        cls.metrics_csv_path = cls.root / "results/tables/comparative_metrics.csv"
        cls.summary_json_path = cls.root / "results/processed/comparative_evaluation_summary.json"
        cls.cusum_cnt_path = cls.root / "results/processed/monitoring_cusum_cnt_mean.csv"

        # Ensure artifacts exist before running assertions
        if not cls.daily_alerts_path.is_file() or not cls.summary_json_path.is_file():
            run_unified_evaluation(base_dir=cls.root)

        cls.df_daily = pd.read_csv(cls.daily_alerts_path)
        cls.df_metrics = pd.read_csv(cls.metrics_csv_path)
        with open(cls.summary_json_path, "r", encoding="utf-8") as f:
            cls.summary_json = json.load(f)

    def test_date_alignment_and_completeness(self):
        """Verify that comparative_daily_alerts.csv has exactly 366 monotonic days for 2012."""
        self.assertEqual(len(self.df_daily), 366)
        expected_dates = pd.date_range("2012-01-01", "2012-12-31", freq="D").strftime("%Y-%m-%d").tolist()
        actual_dates = self.df_daily["batch_date"].tolist()
        self.assertEqual(actual_dates, expected_dates)
        self.assertTrue(self.df_daily["batch_date"].is_monotonic_increasing)
        self.assertEqual(self.df_daily["batch_date"].nunique(), 366)

    def test_ground_truth_onset_partitions(self):
        """Verify condition positive/negative counts for abrupt and gradual drift."""
        # Abrupt: onset 2012-07-01 -> 182 pre-onset, 184 post-onset
        abrupt_win = self.df_daily["abrupt_ground_truth_window"]
        self.assertEqual((~abrupt_win).sum(), 182)
        self.assertEqual(abrupt_win.sum(), 184)
        self.assertEqual(self.df_daily.loc[~abrupt_win, "batch_date"].max(), "2012-06-30")
        self.assertEqual(self.df_daily.loc[abrupt_win, "batch_date"].min(), "2012-07-01")

        # Gradual Configured: onset 2012-06-01 -> 152 pre-onset, 214 post-onset
        grad_conf_win = self.df_daily["gradual_ground_truth_configured_window"]
        self.assertEqual((~grad_conf_win).sum(), 152)
        self.assertEqual(grad_conf_win.sum(), 214)
        self.assertEqual(self.df_daily.loc[~grad_conf_win, "batch_date"].max(), "2012-05-31")
        self.assertEqual(self.df_daily.loc[grad_conf_win, "batch_date"].min(), "2012-06-01")

        # Gradual First Defect: onset 2012-06-10 -> 161 pre-onset, 205 post-onset
        grad_def_win = self.df_daily["gradual_ground_truth_defect_window"]
        self.assertEqual((~grad_def_win).sum(), 161)
        self.assertEqual(grad_def_win.sum(), 205)
        self.assertEqual(self.df_daily.loc[~grad_def_win, "batch_date"].max(), "2012-06-09")
        self.assertEqual(self.df_daily.loc[grad_def_win, "batch_date"].min(), "2012-06-10")

    def test_pre_onset_alerts_and_already_alarming_condition(self):
        """Verify pre-onset false alarm detection and eve-of-onset alarming status."""
        # Abrupt cnt_mean: Shewhart and GX both have pre-onset alerts due to summer ridership
        row_gx_cnt = self.df_metrics[
            (self.df_metrics["scenario"] == "abrupt_shift_cnt") &
            (self.df_metrics["method"] == "great_expectations") &
            (self.df_metrics["signal_type"] == "target_metric")
        ].iloc[0]

        self.assertEqual(int(row_gx_cnt["pre_onset_alert_batches"]), 105)
        self.assertAlmostEqual(float(row_gx_cnt["pre_onset_false_alarm_rate"]), 105 / 182, places=5)
        self.assertEqual(str(row_gx_cnt["alarming_on_eve_of_onset"]).lower(), "true")
        self.assertEqual(str(row_gx_cnt["already_alarming_before_onset"]).lower(), "true")
        self.assertEqual(row_gx_cnt["detection_status"], "not distinguishable from pre-existing alarms")

        # CUSUM cnt_mean: persistent pre-onset alerts
        row_cu_cnt = self.df_metrics[
            (self.df_metrics["scenario"] == "abrupt_shift_cnt") &
            (self.df_metrics["method"] == "cusum") &
            (self.df_metrics["signal_type"] == "target_metric")
        ].iloc[0]
        self.assertEqual(int(row_cu_cnt["pre_onset_alert_batches"]), 141)
        self.assertEqual(str(row_cu_cnt["alarming_on_eve_of_onset"]).lower(), "true")
        self.assertEqual(row_cu_cnt["detection_status"], "not distinguishable from pre-existing alarms")

        # Gradual temp_null_rate: clean pre-onset baseline
        row_gx_temp = self.df_metrics[
            (self.df_metrics["scenario"] == "gradual_null_temp") &
            (self.df_metrics["method"] == "great_expectations") &
            (self.df_metrics["signal_type"] == "target_metric") &
            (self.df_metrics["onset_reference_type"] == "configured")
        ].iloc[0]
        self.assertEqual(int(row_gx_temp["pre_onset_alert_batches"]), 0)
        self.assertEqual(float(row_gx_temp["pre_onset_false_alarm_rate"]), 0.0)
        self.assertEqual(str(row_gx_temp["alarming_on_eve_of_onset"]).lower(), "false")
        self.assertEqual(str(row_gx_temp["already_alarming_before_onset"]).lower(), "false")
        self.assertEqual(row_gx_temp["detection_status"], "detected")

    def test_first_observed_defect_vs_configured_onset_lag(self):
        """Verify detection lag sensitivity for gradual drift under both onset references."""
        # Configured onset (2012-06-01): lag = 9 days (first alert on 2012-06-10)
        row_conf = self.df_metrics[
            (self.df_metrics["scenario"] == "gradual_null_temp") &
            (self.df_metrics["method"] == "great_expectations") &
            (self.df_metrics["signal_type"] == "target_metric") &
            (self.df_metrics["onset_reference_type"] == "configured")
        ].iloc[0]
        self.assertEqual(row_conf["first_post_onset_alert_date"], "2012-06-10")
        self.assertEqual(int(row_conf["detection_lag_days"]), 9)

        # First observed defect onset (2012-06-10): lag = 0 days
        row_def = self.df_metrics[
            (self.df_metrics["scenario"] == "gradual_null_temp") &
            (self.df_metrics["method"] == "great_expectations") &
            (self.df_metrics["signal_type"] == "target_metric") &
            (self.df_metrics["onset_reference_type"] == "first_observed_defect")
        ].iloc[0]
        self.assertEqual(row_def["first_post_onset_alert_date"], "2012-06-10")
        self.assertEqual(int(row_def["detection_lag_days"]), 0)

    def test_confusion_matrix_arithmetic(self):
        """Verify strict confusion-matrix arithmetic and boundary conditions."""
        # 1. Perfectly separating predictions
        y_true = pd.Series([0, 0, 0, 1, 1, 1])
        y_pred = pd.Series([0, 0, 0, 1, 1, 1])
        m = compute_batch_metrics(y_true, y_pred)
        self.assertEqual((m.tp, m.fp, m.tn, m.fn), (3, 0, 3, 0)) if hasattr(m, "tp") else self.assertEqual(
            (m.true_positives, m.false_positives, m.true_negatives, m.false_negatives), (3, 0, 3, 0)
        )
        self.assertEqual(m.tpr_recall, 1.0)
        self.assertEqual(m.fpr_fallout, 0.0)
        self.assertEqual(m.fnr_miss_rate, 0.0)
        self.assertEqual(m.precision, 1.0)
        self.assertEqual(m.f1_score, 1.0)

        # 2. Inverted predictions
        y_pred_inv = pd.Series([1, 1, 1, 0, 0, 0])
        m_inv = compute_batch_metrics(y_true, y_pred_inv)
        self.assertEqual(
            (m_inv.true_positives, m_inv.false_positives, m_inv.true_negatives, m_inv.false_negatives),
            (0, 3, 0, 3)
        )
        self.assertEqual(m_inv.tpr_recall, 0.0)
        self.assertEqual(m_inv.fpr_fallout, 1.0)
        self.assertEqual(m_inv.precision, 0.0)
        self.assertEqual(m_inv.f1_score, 0.0)

        # 3. All negative predictions
        y_pred_zero = pd.Series([0, 0, 0, 0, 0, 0])
        m_zero = compute_batch_metrics(y_true, y_pred_zero)
        self.assertEqual(m_zero.precision, 0.0)
        self.assertEqual(m_zero.f1_score, 0.0)

    def test_method_agreement(self):
        """Verify 100% agreement between GX threshold baselines and respective SPC control charts."""
        # GX cnt_mean vs Shewhart cnt_mean
        match_cnt = (
            self.df_daily["abrupt_gx_alert_cnt_mean"] == self.df_daily["abrupt_shewhart_alert_cnt_mean"]
        ).all()
        self.assertTrue(match_cnt)

        # GX temp_null_rate vs p-chart temp_null_rate
        match_temp = (
            self.df_daily["gradual_gx_alert_temp_null_rate"] == self.df_daily["gradual_p_chart_alert_temp_null_rate"]
        ).all()
        self.assertTrue(match_temp)

    def test_uncalibrated_cusum_handling(self):
        """Verify that zero-variance baseline raises ValueError in CUSUM calibration."""
        df_gradual = pd.read_csv(self.root / "results/processed/daily_metrics_gradual_null_temp.csv")
        with self.assertRaises(ValueError) as ctx:
            calibrate_gaussian_cusum(df_gradual, "temp_null_rate")
        self.assertIn("Degenerate zero-variance", str(ctx.exception))

        # Check that metrics table explicitly marks CUSUM temp_null_rate as not_applicable
        cu_temp_rows = self.df_metrics[
            (self.df_metrics["scenario"] == "gradual_null_temp") &
            (self.df_metrics["method"] == "cusum")
        ]
        self.assertEqual(len(cu_temp_rows), 2)
        for _, r in cu_temp_rows.iterrows():
            self.assertEqual(r["detection_status"], "not_applicable")
            self.assertTrue(pd.isna(r["detection_lag_days"]) or r["detection_lag_days"] == "N/A")

    def test_reproducible_evaluation_run(self):
        """Verify that run_unified_evaluation produces consistent outputs when run to a temp directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            out_alerts = tmp_path / "alerts.csv"
            out_summary = tmp_path / "summary.json"
            out_metrics = tmp_path / "metrics.csv"
            out_raw = tmp_path / "raw"

            res = run_unified_evaluation(
                base_dir=self.root,
                output_daily_alerts=out_alerts,
                output_summary_json=out_summary,
                output_metrics_csv=out_metrics,
                evaluation_raw_dir=out_raw,
            )

            self.assertTrue(out_alerts.is_file())
            self.assertTrue(out_summary.is_file())
            self.assertTrue(out_metrics.is_file())
            self.assertTrue((out_raw / "execution.log").is_file())

            # Check that content matches existing generated table
            df_new_metrics = pd.read_csv(out_metrics)
            pd.testing.assert_frame_equal(df_new_metrics, self.df_metrics)

    def test_alarm_episode_counting_hand_worked(self):
        """Verify alarm episode counting on a hand-checkable synthetic sequence."""
        # Sequence with 2 distinct episodes of length 2 and 3
        series = pd.Series([False, True, True, False, True, True, True, False])
        cross, eps, total = compute_alarm_episodes(series)
        self.assertEqual(cross.tolist(), [False, True, False, False, True, False, False, False])
        self.assertEqual(eps.tolist(), [0, 1, 1, 0, 2, 2, 2, 0])
        self.assertEqual(total, 2)

        # Edge case: all False
        c_zero, e_zero, tot_zero = compute_alarm_episodes(pd.Series([False, False, False]))
        self.assertEqual(tot_zero, 0)
        self.assertEqual(c_zero.sum(), 0)

        # Edge case: single True at boundary
        c_one, e_one, tot_one = compute_alarm_episodes(pd.Series([True, False, False]))
        self.assertEqual(tot_one, 1)
        self.assertTrue(c_one.iloc[0])

    def test_cusum_persistent_alarm_state_vs_crossing(self):
        """Audit CUSUM cnt_mean: verify 325 alarm batches vs 7 episodes (0 post-onset crossings)."""
        row_cu = self.df_metrics[
            (self.df_metrics["scenario"] == "abrupt_shift_cnt") &
            (self.df_metrics["method"] == "cusum") &
            (self.df_metrics["signal_type"] == "target_metric")
        ].iloc[0]

        # 325 total alarm batches across 366 days
        self.assertEqual(int(row_cu["total_alarm_batches"]), 325)
        self.assertEqual(int(row_cu["total_alarm_episodes"]), 7)
        self.assertEqual(int(row_cu["pre_onset_alarm_episodes"]), 7)
        self.assertEqual(int(row_cu["post_onset_alarm_episodes"]), 0)
        self.assertEqual(row_cu["first_crossing_date"], "2012-01-03")
        self.assertEqual(row_cu["first_post_onset_crossing_date"], "none")
        self.assertTrue(pd.isna(row_cu["crossing_lag_days"]) or row_cu["crossing_lag_days"] == "N/A")

        # Confirm Episode 7 started on 2012-03-07 and ran continuously through 2012-12-31 (300 days)
        df_cu = pd.read_csv(self.cusum_cnt_path)
        cross, eps, _ = compute_alarm_episodes(df_cu["is_alert"])
        ep7_dates = df_cu.loc[eps == 7, "batch_date"]
        self.assertEqual(ep7_dates.min(), "2012-03-07")
        self.assertEqual(ep7_dates.max(), "2012-12-31")
        self.assertEqual(len(ep7_dates), 300)

    def test_shewhart_and_gx_episodes(self):
        """Audit Shewhart & GX cnt_mean: verify 274 alarm batches across 18 episodes."""
        for mname in ["great_expectations", "shewhart_individuals"]:
            row = self.df_metrics[
                (self.df_metrics["scenario"] == "abrupt_shift_cnt") &
                (self.df_metrics["method"] == mname) &
                (self.df_metrics["signal_type"] == "target_metric")
            ].iloc[0]
            self.assertEqual(int(row["total_alarm_batches"]), 274)
            self.assertEqual(int(row["total_alarm_episodes"]), 18)
            self.assertEqual(int(row["pre_onset_alarm_episodes"]), 15)
            self.assertEqual(int(row["post_onset_alarm_episodes"]), 3)
            self.assertEqual(row["first_crossing_date"], "2012-01-21")
            self.assertEqual(row["first_post_onset_crossing_date"], "2012-10-31")

    def test_gradual_defect_episodes(self):
        """Audit gradual temp_null_rate: verify 192 alarm batches across 10 post-onset episodes."""
        for mname in ["great_expectations", "p_chart"]:
            row = self.df_metrics[
                (self.df_metrics["scenario"] == "gradual_null_temp") &
                (self.df_metrics["method"] == mname) &
                (self.df_metrics["signal_type"] == "target_metric") &
                (self.df_metrics["onset_reference_type"] == "first_observed_defect")
            ].iloc[0]
            self.assertEqual(int(row["total_alarm_batches"]), 192)
            self.assertEqual(int(row["total_alarm_episodes"]), 10)
            self.assertEqual(int(row["pre_onset_alarm_episodes"]), 0)
            self.assertEqual(int(row["post_onset_alarm_episodes"]), 10)
            self.assertEqual(row["first_crossing_date"], "2012-06-10")
            self.assertEqual(row["first_post_onset_crossing_date"], "2012-06-10")
            self.assertEqual(float(row["crossing_lag_days"]), 0.0)

    def test_independent_confusion_matrix_audit(self):
        """Independently audit confusion-matrix arithmetic across all rows in comparative_metrics."""
        for _, r in self.df_metrics.iterrows():
            if r["detection_status"] == "not_applicable":
                continue
            total = int(r["total_batches"])
            P = int(r["condition_positives"])
            N = int(r["condition_negatives"])
            TP = int(r["true_positives"])
            FP = int(r["false_positives"])
            TN = int(r["true_negatives"])
            FN = int(r["false_negatives"])

            self.assertEqual(P + N, total)
            self.assertEqual(TP + FP + TN + FN, total)
            self.assertEqual(TP + FN, P)
            self.assertEqual(FP + TN, N)

            expected_tpr = round(TP / P, 6) if P > 0 else 0.0
            expected_fpr = round(FP / N, 6) if N > 0 else 0.0
            expected_fnr = round(FN / P, 6) if P > 0 else 0.0
            expected_prec = round(TP / (TP + FP), 6) if (TP + FP) > 0 else 0.0

            self.assertAlmostEqual(float(r["tpr_recall"]), expected_tpr, places=5)
            self.assertAlmostEqual(float(r["fpr_fallout"]), expected_fpr, places=5)
            self.assertAlmostEqual(float(r["fnr_miss_rate"]), expected_fnr, places=5)
            self.assertAlmostEqual(float(r["precision"]), expected_prec, places=5)


if __name__ == "__main__":
    unittest.main()
