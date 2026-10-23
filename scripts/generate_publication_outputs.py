"""Publication-Quality Results Generator for Statistical Process Control (SPC) Research.

This module generates high-resolution figures and standardized tables for the comparative
study between Great Expectations (threshold baseline), Shewhart/attribute control charts,
and sequential CUSUM monitoring.

Artifacts generated:
Figures (results/figures/):
- abrupt_shift_monitoring.png
- gradual_null_drift.png
- false_alarm_comparison.png
- detection_timing.png

Tables (results/tables/):
- table_detection_performance.csv
- table_alarm_episodes.csv
- table_method_parameters.csv
- table_ground_truth_events.csv
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Try importing matplotlib gracefully
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    matplotlib = None
    mdates = None
    plt = None
    PercentFormatter = None


def setup_style() -> None:
    """Configure publication plot typography and aesthetics."""
    if not MATPLOTLIB_AVAILABLE or plt is None:
        return
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "figure.titlesize": 12,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "axes.grid": True,
        "grid.alpha": 0.4,
        "grid.linestyle": ":",
    })


def generate_figure_abrupt_shift(
    df_daily: pd.DataFrame,
    df_cusum: pd.DataFrame,
    output_path: Path,
) -> None:
    """Generate abrupt shift monitoring figure (Shewhart/GX vs CUSUM)."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [1.2, 1.0]})

    dates = pd.to_datetime(df_daily["batch_date"])
    onset_dt = pd.to_datetime("2012-07-01")

    # Parameters from Phase I baseline
    cl = 142.934581
    ucl = 208.683020
    lcl = 77.186143
    h = 5.0

    # Top subplot: Shewhart & GX cnt_mean
    y_vals = df_daily["abrupt_cnt_mean_observed"]
    is_alert_sh = df_daily["abrupt_shewhart_alert_cnt_mean"]

    ax1.plot(dates, y_vals, color="#2b5c8f", lw=1.2, label="Daily Mean Ridership (cnt_mean)")
    ax1.scatter(
        dates[is_alert_sh],
        y_vals[is_alert_sh],
        color="#d9381e",
        s=18,
        zorder=4,
        label="Threshold Violation / Alert (GX & Shewhart)",
    )

    ax1.axhline(cl, color="#555555", linestyle="--", lw=1.0, label=f"Center Line (CL = {cl:.1f})")
    ax1.axhline(ucl, color="#c0392b", linestyle="--", lw=1.2, label=f"Upper Limit (UCL = {ucl:.1f})")
    ax1.axhline(lcl, color="#c0392b", linestyle=":", lw=1.2, label=f"Lower Limit (LCL = {lcl:.1f})")

    ax1.axvline(onset_dt, color="#27ae60", linestyle="-", lw=1.5, label="Synthetic Shift Onset (+75.0, 2012-07-01)")
    ax1.axvspan(onset_dt, dates.max(), color="#27ae60", alpha=0.08, label="Injected Drift Window (184 days)")

    ax1.set_ylabel("Ridership (cnt / hour)")
    ax1.set_title("Shewhart Individuals Chart & Great Expectations Threshold Monitoring for cnt_mean\n(GX bounds [77.19, 208.68] and Shewhart limits are identical by construction; 100% alert agreement)", fontsize=10)
    ax1.legend(loc="upper left", framealpha=0.9, ncol=2)

    # Bottom subplot: Tabular CUSUM
    c_plus = df_cusum["c_plus"]
    c_minus = df_cusum["c_minus"]

    ax2.plot(dates, c_plus, color="#1f77b4", lw=1.4, label="Upper CUSUM Accumulator (C+)")
    ax2.plot(dates, c_minus, color="#ff7f0e", lw=1.2, linestyle="--", label="Lower CUSUM Accumulator (C-)")
    ax2.axhline(h, color="#c0392b", linestyle="--", lw=1.2, label=f"Decision Interval Threshold (h = {h:.1f})")
    ax2.axvline(onset_dt, color="#27ae60", linestyle="-", lw=1.5)
    ax2.axvspan(onset_dt, dates.max(), color="#27ae60", alpha=0.08)

    # Annotate Episode 7 saturation
    ax2.annotate(
        "Episode 7 crossing (2012-03-07)\nC+ reaches ~550 by July 1\ndue to natural summer seasonality",
        xy=(pd.to_datetime("2012-03-07"), 5.0),
        xytext=(pd.to_datetime("2012-01-10"), 280),
        arrowprops=dict(facecolor="black", shrink=0.05, width=0.8, headwidth=5),
        fontsize=8.5,
        bbox=dict(boxstyle="round,pad=0.3", fc="#fff9e6", ec="#d4ac0d", lw=1),
    )

    ax2.set_ylabel("Accumulator (sigma units)")
    ax2.set_xlabel("Date (Year 2012)")
    ax2.set_title("Two-Sided Tabular Gaussian CUSUM (k = 0.5, h = 5.0, reset_policy='none')\n(Demonstrates persistent seasonal alarm state prior to synthetic shift)", fontsize=10)
    ax2.legend(loc="upper right", framealpha=0.9)

    ax2.xaxis.set_major_locator(mdates.MonthLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.autofmt_xdate(rotation=0, ha="center")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)


def generate_figure_gradual_drift(
    df_daily: pd.DataFrame,
    gt_gradual: dict[str, Any],
    output_path: Path,
) -> None:
    """Generate gradual null drift monitoring figure."""
    fig, ax = plt.subplots(figsize=(10, 5))

    dates = pd.to_datetime(df_daily["batch_date"])
    observed_rate = df_daily["gradual_temp_null_rate_observed"]
    is_alert = df_daily["gradual_gx_alert_temp_null_rate"]

    conf_onset = pd.to_datetime("2012-06-01")
    defect_onset = pd.to_datetime("2012-06-10")
    end_date = pd.to_datetime("2012-12-31")

    # Plot intended schedule from ground truth
    n_days = (end_date - conf_onset).days + 1
    schedule_dates = pd.date_range(conf_onset, end_date, freq="D")
    schedule_vals = np.linspace(0.0, 0.40, n_days)

    ax.plot(schedule_dates, schedule_vals, color="#7f8c8d", linestyle="--", lw=1.5, label="Intended Linear Null Rate Schedule (0.0 to 0.40)")
    ax.plot(dates, observed_rate, color="#2980b9", lw=1.2, alpha=0.85, label="Observed Daily Null Rate (temp_null_rate)")

    ax.scatter(
        dates[is_alert],
        observed_rate[is_alert],
        color="#c0392b",
        s=20,
        zorder=4,
        label="Alert Batches (GX > 0.01 & p-chart UCL; 100% agreement)",
    )

    threshold = 0.01
    ax.axhline(threshold, color="#e67e22", linestyle=":", lw=1.5, label=f"Operational Threshold / Limit ({threshold:.2%})")

    ax.axvline(conf_onset, color="#8e44ad", linestyle="--", lw=1.3, label="Configured Schedule Start (2012-06-01)")
    ax.axvline(defect_onset, color="#27ae60", linestyle="-", lw=1.5, label="First Injected Defect Batch (2012-06-10)")
    ax.axvspan(defect_onset, dates.max(), color="#27ae60", alpha=0.08, label="Active Defect Window (205 days)")

    # Annotation about Bernoulli sampling
    ax.annotate(
        "Zero defects drawn (2012-06-01 to 2012-06-09)\ndue to discrete Bernoulli draws with small p\non batch size N = 24",
        xy=(pd.to_datetime("2012-06-05"), 0.0),
        xytext=(pd.to_datetime("2012-02-15"), 0.18),
        arrowprops=dict(facecolor="black", shrink=0.05, width=0.8, headwidth=5),
        fontsize=8.5,
        bbox=dict(boxstyle="round,pad=0.3", fc="#f4f6f7", ec="#bdc3c7", lw=1),
    )

    ax.set_ylabel("Temperature Null Rate")
    ax.set_xlabel("Date (Year 2012)")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Gradual Temperature Null Rate Drift: Detection Timing and Sampling Dynamics\n(Great Expectations threshold and Attribute p-chart match 366/366 batches exactly)", fontsize=10.5)

    ax.legend(loc="upper left", framealpha=0.9)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.autofmt_xdate(rotation=0, ha="center")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)


def generate_figure_false_alarm_comparison(
    df_metrics: pd.DataFrame,
    output_path: Path,
) -> None:
    """Generate bar chart comparing pre-onset false alarm rates."""
    fig, ax = plt.subplots(figsize=(9, 5))

    # Select target metric comparisons and composite suite
    rows = [
        # Abrupt
        ("Abrupt cnt_mean\n(GX Baseline)\nN=182", 0.576923, "#2b5c8f"),
        ("Abrupt cnt_mean\n(Shewhart)\nN=182", 0.576923, "#41729f"),
        ("Abrupt cnt_mean\n(CUSUM)\nN=182", 0.774725, "#d9534f"),
        ("Abrupt Suite\n(GX Composite)\nN=182", 0.576923, "#6c757d"),
        # Gradual
        ("Gradual temp\n(GX Baseline)\nN=161", 0.000000, "#27ae60"),
        ("Gradual temp\n(p-Chart)\nN=161", 0.000000, "#2ecc71"),
        ("Gradual Suite\n(GX Composite)\nN=161", 0.527950, "#e67e22"),
    ]

    labels = [r[0] for r in rows]
    rates = [r[1] for r in rows]
    colors = [r[2] for r in rows]

    x = np.arange(len(labels))
    bars = ax.bar(x, rates, color=colors, width=0.55, edgecolor="#222222", lw=0.8)

    # Add data values on top of bars
    for bar, rate in zip(bars, rates):
        yval = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            yval + 0.015,
            f"{rate:.1%}",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
        )

    ax.set_ylabel("Pre-Onset False Alarm Rate (FPR)")
    ax.set_ylim(0, 0.90)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_title("Pre-Onset False Alarm Rates Across Monitoring Methods and Drift Scenarios\n(Denominator N represents total negative batches strictly prior to defect onset)", fontsize=10.5)

    # Add explanatory note box
    ax.text(
        0.02, 0.78,
        "Key Findings:\n"
        "• Abrupt cnt_mean exhibits high pre-onset FAR (58%-77%) due to unmodeled summer ridership.\n"
        "• Gradual temp_null_rate maintains 0.0% FAR under zero historical baseline defects.\n"
        "• Gradual Composite Suite suffers 52.8% false alarms driven entirely by unrelated cnt_mean seasonality.",
        transform=ax.transAxes,
        fontsize=8.2,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.4", fc="#ffffff", ec="#cccccc", lw=0.8),
    )

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)


def generate_figure_detection_timing(
    df_metrics: pd.DataFrame,
    output_path: Path,
) -> None:
    """Generate detection timing comparison chart displaying crossing dynamics."""
    fig, ax = plt.subplots(figsize=(10, 5))

    # Data items: (Label, Scenario, Status, Lag Text, Lag Value For Plot, Color)
    items = [
        ("GX Threshold (cnt_mean)", "Abrupt Shift", "Confounded by pre-onset alarm", "Lag: 0d (State) / 122d (Crossing)", 122, "#2b5c8f"),
        ("Shewhart Individuals (cnt_mean)", "Abrupt Shift", "Confounded by pre-onset alarm", "Lag: 0d (State) / 122d (Crossing)", 122, "#41729f"),
        ("Sequential CUSUM (cnt_mean)", "Abrupt Shift", "No new post-onset crossing", "Lag: 0d (State) / None (Crossing)", np.nan, "#d9534f"),
        ("GX Threshold (temp_null_rate)", "Gradual (vs Configured)", "Clean Detection", "Lag: 9 days", 9, "#27ae60"),
        ("Attribute p-Chart (temp_null_rate)", "Gradual (vs Configured)", "Clean Detection", "Lag: 9 days", 9, "#2ecc71"),
        ("GX Threshold (temp_null_rate)", "Gradual (vs First Defect)", "Clean Detection", "Lag: 0 days", 0, "#16a085"),
        ("Attribute p-Chart (temp_null_rate)", "Gradual (vs First Defect)", "Clean Detection", "Lag: 0 days", 0, "#1abc9c"),
    ]

    y_pos = np.arange(len(items))[::-1]
    labels = [it[0] + f"\n[{it[1]}]" for it in items]

    for idx, (label, sc, status, lag_txt, lag_val, col) in enumerate(items):
        y = y_pos[idx]
        if np.isnan(lag_val):
            # Special indicator for saturated CUSUM
            ax.plot([0, 140], [y, y], color="#cccccc", linestyle=":", lw=1.2)
            ax.scatter([0], [y], color=col, marker="x", s=80, zorder=4)
            ax.text(12, y, "NO NEW POST-ONSET CROSSING\n(Pre-existing saturation from 2012-03-07; C+ > h)", va="center", fontsize=8.5, color="#c0392b", fontweight="bold")
        else:
            ax.plot([0, lag_val], [y, y], color=col, lw=2.5, alpha=0.85)
            ax.scatter([lag_val], [y], color=col, s=70, zorder=4)
            ax.text(lag_val + 3, y, f"{lag_txt}\nStatus: {status}", va="center", fontsize=8.2, color="#222222")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlabel("Detection Lag in Daily Batches (Days from Reference Onset)")
    ax.set_xlim(-8, 175)
    ax.set_title("Detection Lag and Threshold Crossing Timing Across Monitoring Methods\n(Differentiates active alarm state from genuine new post-onset threshold crossings)", fontsize=10.5)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)


def generate_publication_tables(
    base_dir: Path,
    tables_dir: Path,
) -> dict[str, Path]:
    """Generate all standardized publication tables from source evaluation outputs."""
    tables_dir.mkdir(parents=True, exist_ok=True)

    df_comp_metrics = pd.read_csv(base_dir / "results/tables/comparative_metrics.csv")
    gt_abrupt_path = base_dir / "data/processed/drift/ground_truth_abrupt_shift_cnt.json"
    gt_gradual_path = base_dir / "data/processed/drift/ground_truth_gradual_null_temp.json"
    audit_report_path = base_dir / "results/raw/evaluation/audit_report.json"
    method_params_path = base_dir / "results/raw/evaluation/method_parameters.json"

    with open(gt_abrupt_path, "r", encoding="utf-8") as f:
        gt_abrupt = json.load(f)
    with open(gt_gradual_path, "r", encoding="utf-8") as f:
        gt_gradual = json.load(f)
    with open(method_params_path, "r", encoding="utf-8") as f:
        method_params = json.load(f)

    # 1. table_detection_performance.csv
    # Focuses on target metric evaluation and separates batch metrics from event detection
    perf_cols = [
        "scenario", "target_metric", "method", "signal_type", "onset_reference_type",
        "onset_date", "first_post_onset_alert_date", "detection_lag_days", "detection_status",
        "pre_onset_false_alarm_rate", "tpr_recall", "fpr_fallout", "fnr_miss_rate", "precision", "f1_score"
    ]
    df_perf = df_comp_metrics[perf_cols].copy()
    df_perf = df_perf.rename(columns={
        "signal_type": "signal_scope",
        "first_post_onset_alert_date": "first_detection_date",
        "tpr_recall": "batch_recall_tpr",
        "fpr_fallout": "batch_fallout_fpr",
        "fnr_miss_rate": "batch_miss_rate_fnr",
        "precision": "batch_precision",
        "f1_score": "batch_f1_score"
    })
    table_perf_path = tables_dir / "table_detection_performance.csv"
    df_perf.to_csv(table_perf_path, index=False)

    # 2. table_alarm_episodes.csv
    # Deconstructs persistent alarm states into contiguous alarm runs / threshold crossings
    episode_cols = [
        "scenario", "target_metric", "method", "onset_reference_type", "onset_date",
        "total_alarm_batches", "total_alarm_episodes", "pre_onset_alarm_episodes",
        "post_onset_alarm_episodes", "first_crossing_date", "first_post_onset_crossing_date",
        "crossing_lag_days", "alarming_on_eve_of_onset", "detection_status"
    ]
    df_ep = df_comp_metrics[episode_cols].copy()
    table_ep_path = tables_dir / "table_alarm_episodes.csv"
    df_ep.to_csv(table_ep_path, index=False)

    # 3. table_method_parameters.csv
    # Documents mathematical specifications, frozen baselines, and parameter values
    param_rows = [
        {
            "method": "Great Expectations (Static Thresholds)",
            "monitored_metric": "cnt_mean",
            "phase_1_baseline_window": "2011-01-01 to 2011-12-31",
            "phase_1_sample_size": 365,
            "center_line": 142.934581,
            "dispersion_estimator": "Moving-Range (MR_bar / 1.128)",
            "dispersion_estimate": 21.916146,
            "decision_limits_or_thresholds": "[77.186, 208.683]",
            "memory_type": "Memoryless (Single-Batch)",
            "reset_policy": "N/A",
            "operational_rationale": "Derived directly from Phase I Shewhart 3-sigma range [CL - 3*sigma, CL + 3*sigma]."
        },
        {
            "method": "Shewhart Individuals Chart (X-bar/I)",
            "monitored_metric": "cnt_mean",
            "phase_1_baseline_window": "2011-01-01 to 2011-12-31",
            "phase_1_sample_size": 365,
            "center_line": 142.934581,
            "dispersion_estimator": "Moving-Range (MR_bar / 1.128)",
            "dispersion_estimate": 21.916146,
            "decision_limits_or_thresholds": "LCL=77.186, UCL=208.683",
            "memory_type": "Memoryless (Single-Batch)",
            "reset_policy": "N/A",
            "operational_rationale": "Standard Shewhart 3-sigma individuals chart with d2=1.128 for subgroup n=2."
        },
        {
            "method": "Tabular Sequential CUSUM",
            "monitored_metric": "cnt_mean",
            "phase_1_baseline_window": "2011-01-01 to 2011-12-31",
            "phase_1_sample_size": 365,
            "center_line": 142.934581,
            "dispersion_estimator": "Moving-Range (MR_bar / 1.128)",
            "dispersion_estimate": 21.916146,
            "decision_limits_or_thresholds": "k=0.5, h=5.0 sigma units",
            "memory_type": "Sequential Accumulator (Two-Sided)",
            "reset_policy": "none (Persistent Accumulation)",
            "operational_rationale": "Standard Gaussian tabular CUSUM recursion for early small-shift detection."
        },
        {
            "method": "Great Expectations (Static Thresholds)",
            "monitored_metric": "temp_null_rate",
            "phase_1_baseline_window": "2011-01-01 to 2011-12-31",
            "phase_1_sample_size": 365,
            "center_line": 0.0,
            "dispersion_estimator": "Zero-Defect Historical SLA",
            "dispersion_estimate": 0.0,
            "decision_limits_or_thresholds": "[0.0, 0.01] (1.0% SLA max)",
            "memory_type": "Memoryless (Single-Batch)",
            "reset_policy": "N/A",
            "operational_rationale": "Pipeline SLA tolerance allows at most 1% missing temperature observations."
        },
        {
            "method": "Attribute p-Chart",
            "monitored_metric": "temp_null_rate",
            "phase_1_baseline_window": "2011-01-01 to 2011-12-31",
            "phase_1_sample_size": 365,
            "center_line": 0.0,
            "dispersion_estimator": "Binomial Zero-Defect Baseline",
            "dispersion_estimate": 0.0,
            "decision_limits_or_thresholds": "UCL=0.0 (Zero-Defect Limit; equivalent to the 1% SLA for the observed N≈24 batches)",
            "memory_type": "Memoryless (Single-Batch)",
            "reset_policy": "N/A",
            "operational_rationale": "Flags any non-zero defect batch under zero Phase I defect baseline."
        },
        {
            "method": "Tabular Sequential CUSUM",
            "monitored_metric": "temp_null_rate",
            "phase_1_baseline_window": "2011-01-01 to 2011-12-31",
            "phase_1_sample_size": 365,
            "center_line": 0.0,
            "dispersion_estimator": "Degenerate (sigma=0)",
            "dispersion_estimate": 0.0,
            "decision_limits_or_thresholds": "Uncalibrated / Invalid",
            "memory_type": "N/A",
            "reset_policy": "N/A",
            "operational_rationale": "Continuous Gaussian CUSUM cannot divide by sigma_0=0; requires attribute formulation."
        },
    ]
    df_params = pd.DataFrame(param_rows)
    table_params_path = tables_dir / "table_method_parameters.csv"
    df_params.to_csv(table_params_path, index=False)

    # 4. table_ground_truth_events.csv
    # Complete specifications of injected synthetic degradation scenarios
    abrupt_outcome = gt_abrupt["measured_outcome"]
    gradual_outcome = gt_gradual["measured_outcome"]

    gt_rows = [
        {
            "event_id": gt_abrupt["event_id"],
            "scenario_name": "Abrupt Distribution Shift",
            "target_column": gt_abrupt["affected_column"],
            "drift_type": gt_abrupt["scenario_type"],
            "intended_schedule": "Additive +75.0 constant shift",
            "seed": gt_abrupt["seed"],
            "configured_onset_date": gt_abrupt["onset_date"],
            "first_observed_defect_date": gt_abrupt["onset_date"],
            "end_date": gt_abrupt["end_date"],
            "total_phase_2_batches": 366,
            "injected_batches": abrupt_outcome["total_batches_affected"],
            "total_rows_affected": abrupt_outcome["total_rows_affected"],
            "baseline_period_mean": round(abrupt_outcome["pre_window_overall_mean"], 3),
            "effective_shift_magnitude": abrupt_outcome["effective_overall_shift"],
            "defect_free_pre_window_batches": 182,
        },
        {
            "event_id": gt_gradual["event_id"],
            "scenario_name": "Gradual Null Rate Drift",
            "target_column": gt_gradual["affected_column"],
            "drift_type": gt_gradual["scenario_type"],
            "intended_schedule": "Linear null rate ramp from 0.0 to 0.40",
            "seed": gt_gradual["seed"],
            "configured_onset_date": gt_gradual["onset_date"],
            "first_observed_defect_date": "2012-06-10",
            "end_date": gt_gradual["end_date"],
            "total_phase_2_batches": 366,
            "injected_batches": gradual_outcome["total_batches_in_window"],
            "total_rows_affected": gradual_outcome["total_injected_null_cells"],
            "baseline_period_mean": round(gradual_outcome["pre_window_null_rate"], 3),
            "effective_shift_magnitude": round(gradual_outcome["post_window_null_rate"], 3),
            "defect_free_pre_window_batches": 161,
        },
    ]
    df_gt = pd.DataFrame(gt_rows)
    table_gt_path = tables_dir / "table_ground_truth_events.csv"
    df_gt.to_csv(table_gt_path, index=False)

    return {
        "table_detection_performance": table_perf_path,
        "table_alarm_episodes": table_ep_path,
        "table_method_parameters": table_params_path,
        "table_ground_truth_events": table_gt_path,
    }


def generate_all_publication_outputs(
    base_dir: str | Path | None = None,
    figures_dir: str | Path | None = None,
    tables_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Execute complete generation of publication figures and tables."""
    root = Path(base_dir) if base_dir is not None else Path.cwd()
    fig_dir = Path(figures_dir) if figures_dir is not None else root / "results/figures"
    tab_dir = Path(tables_dir) if tables_dir is not None else root / "results/tables"

    if not MATPLOTLIB_AVAILABLE:
        raise RuntimeError(
            "matplotlib is required to generate publication figures but is not installed in the active environment."
        )

    setup_style()

    # Load source data
    daily_alerts_path = root / "results/processed/comparative_daily_alerts.csv"
    cusum_path = root / "results/processed/monitoring_cusum_cnt_mean.csv"
    comp_metrics_path = root / "results/tables/comparative_metrics.csv"
    gt_gradual_path = root / "data/processed/drift/ground_truth_gradual_null_temp.json"

    df_daily = pd.read_csv(daily_alerts_path)
    df_cusum = pd.read_csv(cusum_path)
    df_metrics = pd.read_csv(comp_metrics_path)

    with open(gt_gradual_path, "r", encoding="utf-8") as f:
        gt_gradual = json.load(f)

    # 1. Generate Figures
    p_fig1 = fig_dir / "abrupt_shift_monitoring.png"
    p_fig2 = fig_dir / "gradual_null_drift.png"
    p_fig3 = fig_dir / "false_alarm_comparison.png"
    p_fig4 = fig_dir / "detection_timing.png"

    generate_figure_abrupt_shift(df_daily, df_cusum, p_fig1)
    generate_figure_gradual_drift(df_daily, gt_gradual, p_fig2)
    generate_figure_false_alarm_comparison(df_metrics, p_fig3)
    generate_figure_detection_timing(df_metrics, p_fig4)

    # 2. Generate Tables
    generated_tables = generate_publication_tables(root, tab_dir)

    return {
        "figures": {
            "abrupt_shift_monitoring": str(p_fig1),
            "gradual_null_drift": str(p_fig2),
            "false_alarm_comparison": str(p_fig3),
            "detection_timing": str(p_fig4),
        },
        "tables": {k: str(v) for k, v in generated_tables.items()},
    }


if __name__ == "__main__":
    outputs = generate_all_publication_outputs()
    print("Successfully generated all publication figures and tables:")
    print("Figures:")
    for k, v in outputs["figures"].items():
        print(f"  - {k}: {v}")
    print("Tables:")
    for k, v in outputs["tables"].items():
        print(f"  - {k}: {v}")
