"""Execution and ground-truth evaluation runner for Great Expectations Phase II baseline.

This script executes the declarative Great Expectations threshold-monitoring suite on
both synthetic drift datasets in Phase II (2012-01-01 to 2012-12-31) using the isolated
Python 3.12 Great Expectations runtime.

Artifacts generated:
- results/raw/gx/abrupt_shift_cnt/
    - daily_summary.csv
    - detailed_records.csv
    - config.json
    - summary.json
    - runtime_info.json
    - execution.log
- results/raw/gx/gradual_null_temp/
    - daily_summary.csv
    - detailed_records.csv
    - config.json
    - summary.json
    - runtime_info.json
    - execution.log
- results/raw/gx/evaluation_summary.json
"""

from __future__ import annotations

import datetime
import io
import json
import logging
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.spc.gx_monitor import GXMonitoringConfig, is_gx_available, run_gx_monitoring

try:
    import great_expectations as gx
except ImportError:
    gx = None


def setup_logger(log_file: Path) -> tuple[logging.Logger, io.StringIO]:
    """Configure scenario-specific file and memory logger."""
    logger = logging.getLogger(str(log_file))
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # File handler
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # String stream handler for in-memory capture
    stream = io.StringIO()
    sh = logging.StreamHandler(stream)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger, stream


def collect_runtime_info() -> dict[str, Any]:
    """Capture precise runtime environment metadata."""
    return {
        "execution_timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
        "great_expectations_available": is_gx_available(),
        "great_expectations_version": gx.__version__ if gx is not None else None,
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
    }


def verify_scenario_output_integrity(
    records_df: pd.DataFrame,
    detailed_df: pd.DataFrame,
    expected_start: str = "2012-01-01",
    expected_end: str = "2012-12-31",
    expected_batches: int = 366,
    expected_expectations_per_batch: int = 6,
) -> None:
    """Verify integrity, date continuity, and record counts."""
    assert len(records_df) == expected_batches, (
        f"Expected {expected_batches} summary records, found {len(records_df)}"
    )
    assert len(detailed_df) == expected_batches * expected_expectations_per_batch, (
        f"Expected {expected_batches * expected_expectations_per_batch} detailed records, "
        f"found {len(detailed_df)}"
    )

    # Check distinct dates and chronological ordering
    dates = pd.to_datetime(records_df["batch_date"])
    expected_date_range = pd.date_range(expected_start, expected_end, freq="D")
    assert (dates.reset_index(drop=True) == expected_date_range).all(), (
        "Batch dates do not strictly match expected daily sequence."
    )
    assert records_df["batch_date"].is_monotonic_increasing, "Batch dates are not monotonic increasing."
    assert records_df["batch_date"].nunique() == expected_batches, "Duplicate batch dates detected."


def compute_contingency_metrics(
    y_true: pd.Series,
    y_pred: pd.Series,
) -> dict[str, Any]:
    """Compute rigorous batch-level confusion matrix and classification metrics."""
    positives = int((y_true == 1).sum())
    negatives = int((y_true == 0).sum())
    total = len(y_true)

    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())

    assert tp + fp + tn + fn == total, "Confusion matrix sum mismatch."

    tpr = float(tp / positives) if positives > 0 else 0.0
    fpr = float(fp / negatives) if negatives > 0 else 0.0
    fnr = float(fn / positives) if positives > 0 else 0.0
    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = tpr
    f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "condition_positives": positives,
        "condition_negatives": negatives,
        "total_batches": total,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "tpr_recall": round(tpr, 6),
        "fpr_fallout": round(fpr, 6),
        "fnr_miss_rate": round(fnr, 6),
        "precision": round(precision, 6),
        "f1_score": round(f1, 6),
    }


def evaluate_scenario(
    records_df: pd.DataFrame,
    detailed_df: pd.DataFrame,
    ground_truth_path: str | Path,
    scenario_type: str,
) -> dict[str, Any]:
    """Evaluate alerts against authoritative ground truth."""
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        gt = json.load(f)

    # Distinguish metric-specific alerts from composite suite alerts
    target_metric = "cnt_mean" if scenario_type == "abrupt" else "temp_null_rate"
    metric_alerts = detailed_df[detailed_df["metric_name"] == target_metric].groupby("batch_date")["is_alert"].any()
    records_with_metric = records_df.copy()
    records_with_metric["metric_specific_alert"] = records_with_metric["batch_date"].map(metric_alerts).fillna(False)

    outcomes: dict[str, Any] = {
        "scenario_type": scenario_type,
        "ground_truth_artifact": str(ground_truth_path),
        "event_id": gt.get("event_id"),
        "target_metric": target_metric,
    }

    if scenario_type == "abrupt":
        onset_date = gt["onset_date"]  # "2012-07-01"
        outcomes["configured_onset"] = onset_date
        outcomes["reference_onset_used"] = onset_date

        # Metric-specific evaluation
        y_true = (records_with_metric["batch_date"] >= onset_date).astype(int)
        y_pred_metric = records_with_metric["metric_specific_alert"].astype(int)
        y_pred_composite = records_with_metric["is_alert"].astype(int)

        post_metric_alerts = records_with_metric[
            (records_with_metric["batch_date"] >= onset_date) & (records_with_metric["metric_specific_alert"])
        ]
        first_post_alert = post_metric_alerts["batch_date"].min() if not post_metric_alerts.empty else None

        pre_metric_alerts = records_with_metric[
            (records_with_metric["batch_date"] < onset_date) & (records_with_metric["metric_specific_alert"])
        ]

        if first_post_alert is not None:
            lag_days = (pd.to_datetime(first_post_alert) - pd.to_datetime(onset_date)).days
        else:
            lag_days = None

        outcomes["metric_specific_evaluation"] = {
            "first_detection_date_on_or_after_onset": first_post_alert,
            "detection_lag_days": lag_days,
            "total_alerts": int(y_pred_metric.sum()),
            "pre_onset_alerts": len(pre_metric_alerts),
            "pre_onset_false_alarm_rate": round(len(pre_metric_alerts) / int((y_true == 0).sum()), 6),
            "post_onset_alerts": len(post_metric_alerts),
            "classification_metrics": compute_contingency_metrics(y_true, y_pred_metric),
        }

        # Composite suite evaluation
        post_comp_alerts = records_with_metric[
            (records_with_metric["batch_date"] >= onset_date) & (records_with_metric["is_alert"])
        ]
        first_post_comp = post_comp_alerts["batch_date"].min() if not post_comp_alerts.empty else None
        pre_comp_alerts = records_with_metric[
            (records_with_metric["batch_date"] < onset_date) & (records_with_metric["is_alert"])
        ]

        outcomes["composite_suite_evaluation"] = {
            "first_detection_date_on_or_after_onset": first_post_comp,
            "detection_lag_days": (pd.to_datetime(first_post_comp) - pd.to_datetime(onset_date)).days if first_post_comp else None,
            "total_alerts": int(y_pred_composite.sum()),
            "pre_onset_alerts": len(pre_comp_alerts),
            "pre_onset_false_alarm_rate": round(len(pre_comp_alerts) / int((y_true == 0).sum()), 6),
            "post_onset_alerts": len(post_comp_alerts),
            "classification_metrics": compute_contingency_metrics(y_true, y_pred_composite),
        }

    else:
        # Gradual scenario: configured onset 2012-06-01 vs first observed defect 2012-06-10
        configured_onset = gt["onset_date"]  # "2012-06-01"

        # Locate first observed defect from ground truth batch records
        gt_batches = gt["batch_records"]
        defect_batches = [
            b["batch_date"]
            for b in gt_batches
            if b.get("injected_missing_count", 0) > 0 or b.get("total_missing_count", 0) > 0
        ]
        first_defect_date = min(defect_batches) if defect_batches else None

        outcomes["configured_onset"] = configured_onset
        outcomes["first_defect_onset"] = first_defect_date

        for onset_label, onset_ref in [
            ("configured_onset_2012_06_01", configured_onset),
            ("first_defect_onset_2012_06_10", first_defect_date),
        ]:
            y_true = (records_with_metric["batch_date"] >= onset_ref).astype(int)
            y_pred_metric = records_with_metric["metric_specific_alert"].astype(int)
            y_pred_composite = records_with_metric["is_alert"].astype(int)

            post_metric_alerts = records_with_metric[
                (records_with_metric["batch_date"] >= onset_ref) & (records_with_metric["metric_specific_alert"])
            ]
            first_post_alert = post_metric_alerts["batch_date"].min() if not post_metric_alerts.empty else None

            pre_metric_alerts = records_with_metric[
                (records_with_metric["batch_date"] < onset_ref) & (records_with_metric["metric_specific_alert"])
            ]

            if first_post_alert is not None:
                lag_days = (pd.to_datetime(first_post_alert) - pd.to_datetime(onset_ref)).days
            else:
                lag_days = None

            outcomes[f"metric_specific_{onset_label}"] = {
                "onset_date_reference": onset_ref,
                "first_detection_date_on_or_after_onset": first_post_alert,
                "detection_lag_days": lag_days,
                "total_alerts": int(y_pred_metric.sum()),
                "pre_onset_alerts": len(pre_metric_alerts),
                "pre_onset_false_alarm_rate": round(len(pre_metric_alerts) / int((y_true == 0).sum()), 6),
                "post_onset_alerts": len(post_metric_alerts),
                "classification_metrics": compute_contingency_metrics(y_true, y_pred_metric),
            }

            post_comp_alerts = records_with_metric[
                (records_with_metric["batch_date"] >= onset_ref) & (records_with_metric["is_alert"])
            ]
            first_post_comp = post_comp_alerts["batch_date"].min() if not post_comp_alerts.empty else None
            pre_comp_alerts = records_with_metric[
                (records_with_metric["batch_date"] < onset_ref) & (records_with_metric["is_alert"])
            ]

            outcomes[f"composite_suite_{onset_label}"] = {
                "onset_date_reference": onset_ref,
                "first_detection_date_on_or_after_onset": first_post_comp,
                "detection_lag_days": (pd.to_datetime(first_post_comp) - pd.to_datetime(onset_ref)).days if first_post_comp else None,
                "total_alerts": int(y_pred_composite.sum()),
                "pre_onset_alerts": len(pre_comp_alerts),
                "pre_onset_false_alarm_rate": round(len(pre_comp_alerts) / int((y_true == 0).sum()), 6),
                "post_onset_alerts": len(post_comp_alerts),
                "classification_metrics": compute_contingency_metrics(y_true, y_pred_composite),
            }

    return outcomes


def run_full_phase2_experiment(base_dir: str | Path | None = None) -> None:
    """Execute complete Phase II monitoring and evaluation for Great Expectations."""
    if base_dir is None:
        base_dir = Path("/workspace") if Path("/workspace").exists() else Path.cwd()
    base_dir = Path(base_dir)
    config_path = base_dir / "configs/gx_thresholds_daily_metrics.json"
    results_root = base_dir / "results/raw/gx"
    results_root.mkdir(parents=True, exist_ok=True)

    runtime_info = collect_runtime_info()

    config = GXMonitoringConfig.from_json(config_path)

    scenarios = [
        {
            "name": "abrupt_shift_cnt",
            "type": "abrupt",
            "data_path": base_dir / "results/processed/daily_metrics_abrupt_shift_cnt.csv",
            "ground_truth_path": base_dir / "data/processed/drift/ground_truth_abrupt_shift_cnt.json",
            "output_dir": results_root / "abrupt_shift_cnt",
        },
        {
            "name": "gradual_null_temp",
            "type": "gradual",
            "data_path": base_dir / "results/processed/daily_metrics_gradual_null_temp.csv",
            "ground_truth_path": base_dir / "data/processed/drift/ground_truth_gradual_null_temp.json",
            "output_dir": results_root / "gradual_null_temp",
        },
    ]

    all_evaluations: dict[str, Any] = {
        "execution_runtime": runtime_info,
        "scenarios": {},
    }

    for sc in scenarios:
        out_dir: Path = sc["output_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)
        log_file = out_dir / "execution.log"
        logger, _ = setup_logger(log_file)

        logger.info(f"=== Starting GX Baseline Monitoring: {sc['name']} ===")
        logger.info(f"Input data: {sc['data_path']}")
        logger.info(f"Config suite: {config.suite_name}")
        logger.info(f"Date range: {config.monitoring_start} to {config.monitoring_end}")

        # Run Great Expectations monitoring
        result = run_gx_monitoring(
            df=sc["data_path"],
            config=config,
            output_dir=None,  # We handle saving directly to ensure exact filenames
        )

        logger.info(f"Evaluated {result.total_batches} daily batches.")
        logger.info(f"Alert batches: {result.alert_batches}, Clean batches: {result.clean_batches}")
        logger.info(f"First alert date (suite-level): {result.first_alert_date}")

        # Integrity verification
        verify_scenario_output_integrity(result.records_df, result.detailed_records_df)
        logger.info("Output integrity verified: exactly 366 daily batches, 2196 expectation records.")

        # Save artifacts
        daily_summary_path = out_dir / "daily_summary.csv"
        detailed_records_path = out_dir / "detailed_records.csv"
        config_save_path = out_dir / "config.json"
        summary_save_path = out_dir / "summary.json"
        runtime_save_path = out_dir / "runtime_info.json"

        result.records_df.to_csv(daily_summary_path, index=False)
        result.detailed_records_df.to_csv(detailed_records_path, index=False)
        config.to_json(config_save_path)

        summary_data = {
            "scenario_name": sc["name"],
            "suite_name": result.suite_name,
            "total_batches": result.total_batches,
            "alert_batches": result.alert_batches,
            "clean_batches": result.clean_batches,
            "first_alert_date": result.first_alert_date,
            "monitoring_start": result.config.monitoring_start,
            "monitoring_end": result.config.monitoring_end,
            "monitored_metrics": [t.column for t in result.config.thresholds],
        }
        with open(summary_save_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)

        with open(runtime_save_path, "w", encoding="utf-8") as f:
            json.dump(runtime_info, f, indent=2)

        # Ground truth evaluation
        eval_metrics = evaluate_scenario(
            records_df=result.records_df,
            detailed_df=result.detailed_records_df,
            ground_truth_path=sc["ground_truth_path"],
            scenario_type=sc["type"],
        )
        all_evaluations["scenarios"][sc["name"]] = eval_metrics

        logger.info(f"=== Completed Scenario: {sc['name']} ===")

    # Save overall evaluation summary
    eval_json_path = results_root / "evaluation_summary.json"
    with open(eval_json_path, "w", encoding="utf-8") as f:
        json.dump(all_evaluations, f, indent=2)

    print("\n=======================================================")
    print("ALL GREAT EXPECTATIONS PHASE II RUNS COMPLETED SUCCESSFULLY")
    print(f"Summary written to: {eval_json_path}")
    print("=======================================================")


if __name__ == "__main__":
    run_full_phase2_experiment()

