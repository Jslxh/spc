"""End-to-End Orchestration Script for SPC Data Pipeline Monitoring Reproduction.

This script executes all experiment stages in dependency order:
1. Synthetic Drift Injections (Abrupt distribution shift & Gradual null ramp)
2. Daily Quality Metrics Aggregation (Raw baseline, Raw with null cols, Abrupt, Gradual)
3. Great Expectations Declarative Monitoring (Phase II baseline across 366 daily batches)
4. Statistical Process Control Monitoring (Shewhart individuals X/mR and attribute p-chart)
5. Sequential CUSUM Monitoring and Unified Comparative Evaluation
6. Publication Figures (300 DPI PNG) and Standardized Tables (CSV)

Usage:
------
# Full pipeline inside Python 3.12 container runtime:
docker run --rm -e PYTHONPATH=/workspace -v $(pwd):/workspace -v /tmp/spc-gx-test/venv:/env/venv -w /workspace \\
    --entrypoint /env/venv/bin/python public.ecr.aws/lambda/python:3.12 scripts/reproduce_pipeline.py

# Skip Great Expectations when running outside container (e.g. host Python virtualenv):
.venv/bin/python scripts/reproduce_pipeline.py --skip-gx
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from src.spc.drift_injection import (
    AbruptShiftConfig,
    GradualNullDriftConfig,
    inject_abrupt_distribution_shift,
    inject_gradual_null_drift,
    save_injection_artifacts,
)
from src.spc.quality_metrics import compute_daily_quality_metrics
from src.spc.control_charts import (
    generate_and_save_shewhart_cnt_mean,
    generate_and_save_p_chart_temp_null_rate,
)
from src.spc.evaluation import run_unified_evaluation
from src.spc.gx_monitor import is_gx_available

# Optional script imports
try:
    from scripts.run_gx_baseline import run_full_phase2_experiment
except ImportError:
    run_full_phase2_experiment = None

try:
    from scripts.generate_publication_outputs import (
        MATPLOTLIB_AVAILABLE,
        generate_all_publication_outputs,
    )
except ImportError:
    generate_all_publication_outputs = None
    MATPLOTLIB_AVAILABLE = False


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s]: %(message)s",
)
logger = logging.getLogger("spc.reproduce_pipeline")


def reproduce_all(
    base_dir: str | Path | None = None,
    skip_gx: bool = False,
    skip_figures: bool = False,
) -> dict[str, Any]:
    """Execute all pipeline stages in strict dependency order.

    Parameters
    ----------
    base_dir : str | Path | None, optional
        Project root directory. Defaults to Path.cwd().
    skip_gx : bool, optional
        Whether to skip the Great Expectations stage, default False.
    skip_figures : bool, optional
        Whether to skip publication figures generation, default False.

    Returns
    -------
    dict[str, Any]
        Dictionary with execution status and stage summaries.
    """
    root = Path(base_dir).resolve() if base_dir is not None else Path.cwd().resolve()
    logger.info(f"Starting end-to-end SPC reproduction pipeline at root: {root}")

    # Stage 1: Synthetic Drift Injections
    logger.info("=== Stage 1: Synthetic Drift Injections ===")
    raw_hour_path = root / "data/raw/hour.csv"
    if not raw_hour_path.is_file():
        raise FileNotFoundError(f"Source raw dataset missing: {raw_hour_path}")
    raw_df = pd.read_csv(raw_hour_path)
    drift_dir = root / "data/processed/drift"
    drift_dir.mkdir(parents=True, exist_ok=True)

    # 1A: Gradual null drift
    config_null = GradualNullDriftConfig(
        event_id="drift_gradual_null_temp_2012-06-01",
        affected_column="temp",
        onset_date="2012-06-01",
        end_date="2012-12-31",
        start_null_rate=0.0,
        max_null_rate=0.40,
        random_seed=42,
    )
    df_null, gt_null = inject_gradual_null_drift(raw_df, config_null)
    save_injection_artifacts(
        modified_df=df_null,
        ground_truth=gt_null,
        output_dir=drift_dir,
        csv_filename="hour_gradual_null_temp.csv",
        json_filename="ground_truth_gradual_null_temp.json",
    )

    # 1B: Abrupt distribution shift
    config_shift = AbruptShiftConfig(
        event_id="drift_abrupt_shift_cnt_2012-07-01",
        affected_column="cnt",
        onset_date="2012-07-01",
        end_date="2012-12-31",
        shift_type="additive",
        shift_value=75.0,
        clip_min=0.0,
        random_seed=42,
    )
    df_shift, gt_shift = inject_abrupt_distribution_shift(raw_df, config_shift)
    save_injection_artifacts(
        modified_df=df_shift,
        ground_truth=gt_shift,
        output_dir=drift_dir,
        csv_filename="hour_abrupt_shift_cnt.csv",
        json_filename="ground_truth_abrupt_shift_cnt.json",
    )
    logger.info("Stage 1 completed: drift datasets and ground-truth manifests saved.")

    # Stage 2: Daily Quality Metrics Aggregation
    logger.info("=== Stage 2: Daily Quality Metrics Aggregation ===")
    raw_metrics_path = root / "results/raw/daily_quality_metrics.csv"
    raw_metrics_path.parent.mkdir(parents=True, exist_ok=True)
    df_raw_m = compute_daily_quality_metrics(raw_df)
    df_raw_m.to_csv(raw_metrics_path, index=False)

    raw_null_path = root / "results/processed/daily_quality_metrics_raw_with_null_cols.csv"
    raw_null_path.parent.mkdir(parents=True, exist_ok=True)
    df_raw_null = compute_daily_quality_metrics(raw_df, null_rate_columns=["temp", "cnt"])
    df_raw_null.to_csv(raw_null_path, index=False)

    abrupt_metrics_path = root / "results/processed/daily_metrics_abrupt_shift_cnt.csv"
    df_abrupt_m = compute_daily_quality_metrics(df_shift, null_rate_columns=["temp", "cnt"])
    df_abrupt_m.to_csv(abrupt_metrics_path, index=False)

    gradual_metrics_path = root / "results/processed/daily_metrics_gradual_null_temp.csv"
    df_gradual_m = compute_daily_quality_metrics(df_null, null_rate_columns=["temp", "cnt"])
    df_gradual_m.to_csv(gradual_metrics_path, index=False)
    logger.info("Stage 2 completed: all 4 daily quality metrics tables saved.")

    # Stage 3: Great Expectations Baseline Monitoring
    logger.info("=== Stage 3: Great Expectations Baseline Monitoring ===")
    gx_executed = False
    if not skip_gx:
        if is_gx_available() and run_full_phase2_experiment is not None:
            run_full_phase2_experiment(base_dir=root)
            gx_executed = True
            logger.info("Stage 3 completed: Great Expectations Phase II baseline evaluated.")
        else:
            logger.warning(
                "Great Expectations is not available in the active environment. "
                "Skipping Stage 3 (run with containerized Python 3.12 runtime for full GX baseline)."
            )
    else:
        logger.info("Stage 3 skipped per --skip-gx flag.")

    # Stage 4: Shewhart Individuals and Attribute p-Chart Monitoring
    logger.info("=== Stage 4: Shewhart and p-Chart Monitoring ===")
    shewhart_path = root / "results/processed/monitoring_shewhart_cnt_mean.csv"
    pchart_path = root / "results/processed/monitoring_p_chart_temp_null_rate.csv"
    generate_and_save_shewhart_cnt_mean(abrupt_metrics_path, shewhart_path)
    generate_and_save_p_chart_temp_null_rate(gradual_metrics_path, pchart_path)
    logger.info("Stage 4 completed: Shewhart individuals and p-chart CSVs saved.")

    # Stage 5: Sequential CUSUM and Unified Comparative Evaluation
    logger.info("=== Stage 5: CUSUM Monitoring and Unified Comparative Evaluation ===")
    from src.spc.evaluation import generate_and_save_cusum_cnt_mean
    cusum_path = root / "results/processed/monitoring_cusum_cnt_mean.csv"
    generate_and_save_cusum_cnt_mean(abrupt_metrics_path, cusum_path)
    logger.info("Stage 5A: Sequential CUSUM monitoring table saved.")

    eval_summary = None
    gx_outputs_present = (
        (root / "results/raw/gx/abrupt_shift_cnt/daily_summary.csv").is_file() and
        (root / "results/raw/gx/gradual_null_temp/daily_summary.csv").is_file()
    )
    if gx_outputs_present:
        eval_summary = run_unified_evaluation(base_dir=root)
        logger.info("Stage 5B: Unified comparative evaluation summary and metrics saved.")
    else:
        logger.warning(
            "Great Expectations outputs are not present in results/raw/gx/; "
            "skipping cross-method comparative evaluation table generation. "
            "To generate comparative evaluation, run in Python 3.12 container with GX enabled."
        )

    # Stage 6: Publication Outputs
    pub_outputs = None
    comp_alerts_present = (root / "results/processed/comparative_daily_alerts.csv").is_file()
    if not skip_figures and comp_alerts_present:
        logger.info("=== Stage 6: Publication Figures and Tables ===")
        if generate_all_publication_outputs is not None:
            pub_outputs = generate_all_publication_outputs(base_dir=root)
            logger.info("Stage 6 completed: 4 publication figures and 4 publication tables saved.")
        else:
            logger.warning("Publication generator module not available; skipping Stage 6.")
    elif not comp_alerts_present:
        logger.info("Stage 6 skipped: comparative alerts table not present (requires GX evaluation).")

    logger.info("=== End-to-End SPC Pipeline Reproduction Finished Successfully ===")
    return {
        "status": "success",
        "gx_executed": gx_executed,
        "evaluation_summary": eval_summary,
        "publication_outputs": pub_outputs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute reproducible end-to-end SPC data pipeline monitoring workflow."
    )
    parser.add_argument(
        "--base-dir",
        "-b",
        type=Path,
        default=None,
        help="Project root directory (default: current working directory or /workspace).",
    )
    parser.add_argument(
        "--skip-gx",
        action="store_true",
        help="Skip Great Expectations stage (useful when running outside Python 3.12 container).",
    )
    parser.add_argument(
        "--skip-figures",
        action="store_true",
        help="Skip publication figures generation.",
    )
    args = parser.parse_args()

    reproduce_all(
        base_dir=args.base_dir,
        skip_gx=args.skip_gx,
        skip_figures=args.skip_figures,
    )


if __name__ == "__main__":
    main()
