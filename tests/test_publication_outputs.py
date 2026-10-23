"""Tests for publication figures and tables generation.

Verifies:
1. All publication figures exist, are non-empty, and have valid PNG signatures.
2. All publication tables exist, are non-empty, and match source metrics and ground-truth files.
3. Generates cleanly in a temporary output directory without modifying raw outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from scripts.generate_publication_outputs import (
    MATPLOTLIB_AVAILABLE,
    generate_all_publication_outputs,
    generate_publication_tables,
)


class TestPublicationOutputs(unittest.TestCase):
    """Test suite for publication-ready figures and tables."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        cls.fig_dir = cls.root / "results/figures"
        cls.tab_dir = cls.root / "results/tables"

        # Ensure outputs are generated before running assertions
        cls.expected_figs = [
            "abrupt_shift_monitoring.png",
            "gradual_null_drift.png",
            "false_alarm_comparison.png",
            "detection_timing.png",
        ]
        cls.expected_tabs = [
            "table_detection_performance.csv",
            "table_alarm_episodes.csv",
            "table_method_parameters.csv",
            "table_ground_truth_events.csv",
        ]

        # Check if already generated or generate
        needs_figs = any(not (cls.fig_dir / f).is_file() for f in cls.expected_figs)
        needs_tabs = any(not (cls.tab_dir / t).is_file() for t in cls.expected_tabs)
        if needs_tabs:
            generate_publication_tables(cls.root, cls.tab_dir)
        if needs_figs and MATPLOTLIB_AVAILABLE:
            generate_all_publication_outputs(base_dir=cls.root)

    def test_figure_files_exist_and_are_valid_png(self):
        """Verify that all 4 publication figure files exist and have valid PNG headers."""
        png_magic = b"\x89PNG\r\n\x1a\n"
        for fname in self.expected_figs:
            fig_path = self.fig_dir / fname
            self.assertTrue(fig_path.is_file(), f"Missing figure file: {fig_path}")
            size = fig_path.stat().st_size
            self.assertGreater(size, 20_000, f"Figure file suspiciously small ({size} bytes): {fname}")
            with open(fig_path, "rb") as f:
                header = f.read(8)
            self.assertEqual(header, png_magic, f"File does not have valid PNG header: {fname}")

    def test_table_files_exist_and_schemas(self):
        """Verify that all 4 publication table files exist with required schemas."""
        for tname in self.expected_tabs:
            tab_path = self.tab_dir / tname
            self.assertTrue(tab_path.is_file(), f"Missing table file: {tab_path}")
            df = pd.read_csv(tab_path)
            self.assertGreater(len(df), 0, f"Table file is empty: {tname}")

    def test_table_metrics_match_source_data(self):
        """Verify numerical agreement between table_detection_performance and comparative_metrics."""
        df_perf = pd.read_csv(self.tab_dir / "table_detection_performance.csv")
        df_comp = pd.read_csv(self.tab_dir / "comparative_metrics.csv")

        self.assertEqual(len(df_perf), len(df_comp))
        for col in ["scenario", "target_metric", "method", "onset_reference_type", "onset_date"]:
            self.assertEqual(df_perf[col].tolist(), df_comp[col].tolist())

        # Check numerical agreement
        for num_col, orig_col in [
            ("pre_onset_false_alarm_rate", "pre_onset_false_alarm_rate"),
            ("batch_recall_tpr", "tpr_recall"),
            ("batch_fallout_fpr", "fpr_fallout"),
            ("batch_miss_rate_fnr", "fnr_miss_rate"),
            ("batch_precision", "precision"),
            ("batch_f1_score", "f1_score"),
        ]:
            s_perf = df_perf[num_col].dropna()
            s_comp = df_comp[orig_col].dropna()
            self.assertEqual(len(s_perf), len(s_comp))
            pd.testing.assert_series_equal(
                s_perf.reset_index(drop=True),
                s_comp.reset_index(drop=True),
                check_names=False,
            )

    def test_alarm_episodes_table_semantics(self):
        """Verify that table_alarm_episodes reflects CUSUM persistent state vs crossings."""
        df_ep = pd.read_csv(self.tab_dir / "table_alarm_episodes.csv")

        # CUSUM row
        row_cu = df_ep[
            (df_ep["scenario"] == "abrupt_shift_cnt") &
            (df_ep["method"] == "cusum")
        ].iloc[0]
        self.assertEqual(int(row_cu["total_alarm_batches"]), 325)
        self.assertEqual(int(row_cu["total_alarm_episodes"]), 7)
        self.assertEqual(int(row_cu["post_onset_alarm_episodes"]), 0)
        self.assertEqual(row_cu["first_post_onset_crossing_date"], "none")

        # Shewhart row
        row_sh = df_ep[
            (df_ep["scenario"] == "abrupt_shift_cnt") &
            (df_ep["method"] == "shewhart_individuals")
        ].iloc[0]
        self.assertEqual(int(row_sh["total_alarm_batches"]), 274)
        self.assertEqual(int(row_sh["total_alarm_episodes"]), 18)
        self.assertEqual(int(row_sh["post_onset_alarm_episodes"]), 3)

        # Gradual temp_null_rate (first defect onset)
        row_temp = df_ep[
            (df_ep["scenario"] == "gradual_null_temp") &
            (df_ep["method"] == "great_expectations") &
            (df_ep["onset_reference_type"] == "first_observed_defect")
        ].iloc[0]
        self.assertEqual(int(row_temp["total_alarm_batches"]), 192)
        self.assertEqual(int(row_temp["pre_onset_alarm_episodes"]), 0)
        self.assertEqual(int(row_temp["post_onset_alarm_episodes"]), 10)
        self.assertEqual(row_temp["first_post_onset_crossing_date"], "2012-06-10")
        self.assertEqual(float(row_temp["crossing_lag_days"]), 0.0)

    def test_ground_truth_events_table(self):
        """Verify ground-truth table values against authoritative JSON files."""
        df_gt = pd.read_csv(self.tab_dir / "table_ground_truth_events.csv")
        self.assertEqual(len(df_gt), 2)

        with open(self.root / "data/processed/drift/ground_truth_abrupt_shift_cnt.json", "r") as f:
            gt_abrupt = json.load(f)
        with open(self.root / "data/processed/drift/ground_truth_gradual_null_temp.json", "r") as f:
            gt_gradual = json.load(f)

        row_ab = df_gt[df_gt["scenario_name"] == "Abrupt Distribution Shift"].iloc[0]
        self.assertEqual(row_ab["event_id"], gt_abrupt["event_id"])
        self.assertEqual(row_ab["configured_onset_date"], gt_abrupt["onset_date"])
        self.assertEqual(int(row_ab["injected_batches"]), gt_abrupt["measured_outcome"]["total_batches_affected"])
        self.assertEqual(int(row_ab["total_rows_affected"]), gt_abrupt["measured_outcome"]["total_rows_affected"])

        row_gr = df_gt[df_gt["scenario_name"] == "Gradual Null Rate Drift"].iloc[0]
        self.assertEqual(row_gr["event_id"], gt_gradual["event_id"])
        self.assertEqual(row_gr["configured_onset_date"], gt_gradual["onset_date"])
        self.assertEqual(row_gr["first_observed_defect_date"], "2012-06-10")
        self.assertEqual(int(row_gr["injected_batches"]), gt_gradual["measured_outcome"]["total_batches_in_window"])
        self.assertEqual(int(row_gr["total_rows_affected"]), gt_gradual["measured_outcome"]["total_injected_null_cells"])

    def test_reproducible_generation_in_temp_directory(self):
        """Verify that generate_all_publication_outputs runs cleanly in temporary directories."""
        if not MATPLOTLIB_AVAILABLE:
            raise unittest.SkipTest("matplotlib is not installed in active environment; skipping figure generation test.")
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            tmp_figs = tmp_root / "figures"
            tmp_tabs = tmp_root / "tables"

            res = generate_all_publication_outputs(
                base_dir=self.root,
                figures_dir=tmp_figs,
                tables_dir=tmp_tabs,
            )

            for fname in self.expected_figs:
                self.assertTrue((tmp_figs / fname).is_file())
            for tname in self.expected_tabs:
                self.assertTrue((tmp_tabs / tname).is_file())


if __name__ == "__main__":
    unittest.main()
