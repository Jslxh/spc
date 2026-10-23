"""Statistical Process Control (SPC) control-chart monitoring module.

This module provides Phase I baseline calibration and Phase II prospective monitoring
using Shewhart control charts:
1. Individuals (I-MR) Chart for continuous summary observations (e.g. cnt_mean).
   - Calibrated using the standard moving-range estimator sigma_hat = MR_bar / 1.128.
   - Unclamped mathematical three-sigma limits (CL +/- 3 * sigma_hat).
   - Strict adjacency validation for moving-range calculations across missing values and date gaps.
2. Attribute Proportion (p) Chart for defect rates (e.g. temp_null_rate).
   - Calibrated using pooled baseline proportion (total events / total eligible observations).
   - Variable three-sigma control limits adjusting dynamically to daily sample sizes n_i.
   - Strict zero-defect baseline policy: when p_bar == 0.0, any observed nonzero rate triggers an alert.

Phase I parameters are frozen upon calibration and applied immutably to Phase II.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class IndividualsLimits:
    """Calibrated frozen control limits for an Individuals (I) chart.

    Attributes
    ----------
    metric_name : str
        Name of the monitored metric column.
    baseline_start : str
        Start date of Phase I baseline (YYYY-MM-DD).
    baseline_end : str
        End date of Phase I baseline (YYYY-MM-DD).
    sample_size : int
        Number of valid daily observations in Phase I.
    valid_moving_ranges : int
        Number of adjacent consecutive pairs used to compute MR-bar.
    center_line : float
        Baseline arithmetic mean (CL = X-bar).
    mr_bar : float
        Average moving range across adjacent consecutive observations.
    sigma_hat : float
        Estimated process standard deviation (MR-bar / 1.128).
    ucl : float
        Upper control limit (CL + 3 * sigma_hat).
    lcl : float
        Lower control limit (CL - 3 * sigma_hat, unclamped).
    d2 : float
        Statistical divisor for subgroup size n=2 (1.128).
    baseline_stability : dict[str, Any]
        Audit dictionary recording baseline out-of-control counts and stability notes.
    """

    metric_name: str
    baseline_start: str
    baseline_end: str
    sample_size: int
    valid_moving_ranges: int
    center_line: float
    mr_bar: float
    sigma_hat: float
    ucl: float
    lcl: float
    d2: float = 1.128
    baseline_stability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert limits to a serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class PChartLimits:
    """Calibrated frozen baseline parameters for an attribute p-chart.

    Attributes
    ----------
    metric_name : str
        Name of the monitored proportion column (e.g. 'temp_null_rate').
    denominator_column : str
        Column representing eligible observation counts per batch (e.g. 'row_count').
    baseline_start : str
        Start date of Phase I baseline (YYYY-MM-DD).
    baseline_end : str
        End date of Phase I baseline (YYYY-MM-DD).
    sample_size : int
        Number of daily batches in Phase I.
    total_eligible_observations : int
        Sum of eligible observations across Phase I.
    total_events : int
        Sum of numerator events (e.g. missing cells) across Phase I.
    p_bar : float
        Pooled baseline proportion (total_events / total_eligible_observations).
    zero_defect_policy : bool
        True if p_bar == 0.0, indicating strict policy where any p > 0 triggers an alert.
    baseline_stability : dict[str, Any]
        Audit dictionary recording baseline stability notes.
    """

    metric_name: str
    denominator_column: str
    baseline_start: str
    baseline_end: str
    sample_size: int
    total_eligible_observations: int
    total_events: int
    p_bar: float
    zero_defect_policy: bool
    baseline_stability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert limits to a serializable dictionary."""
        return asdict(self)


@dataclass
class ControlChartResult:
    """Phase II monitoring observations, control limits, and alert signals."""

    chart_type: Literal["individuals", "p_chart"]
    metric_name: str
    records_df: pd.DataFrame
    total_observations: int
    total_alerts: int
    upper_alerts: int
    lower_alerts: int
    missing_observations: int
    first_alert_date: str | None


def _validate_date_window(
    df: pd.DataFrame,
    date_column: str,
    start_date: str,
    end_date: str,
    phase_name: str,
) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    """Validate date column, parse timestamps, and filter to chronological window."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df)}")

    if df.empty:
        raise ValueError(f"Input DataFrame is empty for {phase_name}")

    if date_column not in df.columns:
        raise ValueError(f"Date column '{date_column}' not found in DataFrame")

    parsed_dates = pd.to_datetime(df[date_column], errors="coerce")
    if parsed_dates.isna().any():
        raise ValueError(f"Invalid or unparseable dates encountered in '{date_column}'")

    try:
        start_ts = pd.to_datetime(start_date).floor("D")
        end_ts = pd.to_datetime(end_date).floor("D")
    except Exception as e:
        raise ValueError(f"Invalid date format in {phase_name}: start='{start_date}', end='{end_date}'") from e

    if start_ts > end_ts:
        raise ValueError(
            f"Invalid {phase_name} date range: start '{start_date}' is after end '{end_date}'"
        )

    # Filter within date window
    date_floor = parsed_dates.dt.floor("D")
    mask = (date_floor >= start_ts) & (date_floor <= end_ts)
    window_df = df.loc[mask].copy()

    if window_df.empty:
        raise ValueError(
            f"No observations found in {phase_name} window [{start_date}, {end_date}]"
        )

    # Check for duplicate dates
    window_dates = date_floor.loc[mask]
    if window_dates.duplicated().any():
        dup_samples = window_dates[window_dates.duplicated()].dt.strftime("%Y-%m-%d").unique().tolist()
        raise ValueError(f"Duplicate dates found in {phase_name}: {dup_samples[:5]}")

    # Sort strictly by date ascending
    window_df["_parsed_date"] = window_dates
    window_df = window_df.sort_values("_parsed_date").reset_index(drop=True)

    return window_df, start_ts, end_ts


def calibrate_individuals_chart(
    df: pd.DataFrame | str | Path,
    metric_column: str,
    baseline_start: str = "2011-01-01",
    baseline_end: str = "2011-12-31",
    date_column: str = "batch_date",
    min_observations: int = 30,
    min_moving_ranges: int | None = None,
) -> IndividualsLimits:
    """Calibrate frozen Phase I parameters for an Individuals (I) chart.

    Parameters
    ----------
    df : pd.DataFrame | str | Path
        Input DataFrame or path containing baseline observations.
    metric_column : str
        Continuous summary metric column to calibrate (e.g. 'cnt_mean').
    baseline_start : str, default "2011-01-01"
        Start date for Phase I baseline window.
    baseline_end : str, default "2011-12-31"
        End date for Phase I baseline window.
    date_column : str, default "batch_date"
        Column containing batch dates.
    min_observations : int, default 30
        Minimum valid observations required for stable parameter estimation.

    Returns
    -------
    IndividualsLimits
        Frozen Phase I limits including center line, sigma_hat, UCL, LCL, and stability audit.

    Raises
    ------
    ValueError
        If inputs, dates, observation counts, or variance are invalid.
    """
    if isinstance(df, (str, Path)):
        df = pd.read_csv(df)

    if metric_column not in df.columns:
        raise ValueError(f"Metric column '{metric_column}' not found in DataFrame")

    window_df, start_ts, end_ts = _validate_date_window(
        df=df,
        date_column=date_column,
        start_date=baseline_start,
        end_date=baseline_end,
        phase_name="Phase I baseline",
    )

    series_dates = window_df["_parsed_date"]
    series_values = window_df[metric_column]

    valid_mask = series_values.notna()
    sample_size = int(valid_mask.sum())

    if sample_size < min_observations:
        raise ValueError(
            f"Insufficient valid observations in Phase I baseline for '{metric_column}': "
            f"found {sample_size}, required at least {min_observations}"
        )

    # Moving-range calculation with strict adjacency validation:
    # A moving range is valid ONLY when two observations are strictly consecutive calendar days
    # (delta_days == 1) and neither observation is NaN. Gaps and missing values do not bridge!
    moving_ranges: list[float] = []
    n_total = len(window_df)

    for i in range(1, n_total):
        date_prev = series_dates.iloc[i - 1]
        date_curr = series_dates.iloc[i]
        val_prev = series_values.iloc[i - 1]
        val_curr = series_values.iloc[i]

        day_diff = (date_curr - date_prev).days

        # Strict adjacency: must be exactly 1 day apart, both non-NaN
        if day_diff == 1 and pd.notna(val_prev) and pd.notna(val_curr):
            moving_ranges.append(abs(float(val_curr) - float(val_prev)))

    valid_mr_count = len(moving_ranges)
    required_mr = min_moving_ranges if min_moving_ranges is not None else max(1, min_observations // 2)
    if valid_mr_count < required_mr:
        raise ValueError(
            f"Insufficient valid consecutive adjacent pairs for moving-range calculation: "
            f"found {valid_mr_count}, required at least {required_mr}"
        )

    mr_bar = float(np.mean(moving_ranges))
    d2 = 1.128  # Constant for subgroup size n=2
    sigma_hat = float(mr_bar / d2)

    if np.isclose(sigma_hat, 0.0) or sigma_hat < 1e-12:
        raise ValueError(
            f"Degenerate zero-variance Phase I baseline for '{metric_column}' (sigma_hat={sigma_hat:.6f}). "
            f"Shewhart control limits cannot be constructed from identical observations."
        )

    center_line = float(series_values.loc[valid_mask].mean())
    ucl = float(center_line + 3.0 * sigma_hat)
    # Note: LCL is mathematically unconstrained and NOT clamped to zero as per standard Shewhart design
    lcl = float(center_line - 3.0 * sigma_hat)

    # Baseline stability check (audit of Phase I against calibrated limits)
    valid_vals = series_values.loc[valid_mask].astype(float)
    baseline_upper_alerts = int((valid_vals > ucl).sum())
    baseline_lower_alerts = int((valid_vals < lcl).sum())
    total_baseline_alerts = baseline_upper_alerts + baseline_lower_alerts
    violation_rate = float(total_baseline_alerts / sample_size) if sample_size > 0 else 0.0

    stability_note = (
        "Phase I baseline is stable."
        if violation_rate <= 0.05
        else (
            f"Phase I baseline exhibits substantial variation/seasonality "
            f"({violation_rate:.2%} baseline points exceed static 3-sigma limits). "
            f"Unmodeled seasonal cycles may induce Phase II false alarms under static Shewhart limits."
        )
    )

    baseline_stability: dict[str, Any] = {
        "sample_size": sample_size,
        "valid_moving_ranges": valid_mr_count,
        "baseline_alerts_count": total_baseline_alerts,
        "baseline_upper_alerts": baseline_upper_alerts,
        "baseline_lower_alerts": baseline_lower_alerts,
        "baseline_violation_rate": round(violation_rate, 4),
        "is_stable": bool(violation_rate <= 0.05),
        "note": stability_note,
    }

    return IndividualsLimits(
        metric_name=metric_column,
        baseline_start=start_ts.strftime("%Y-%m-%d"),
        baseline_end=end_ts.strftime("%Y-%m-%d"),
        sample_size=sample_size,
        valid_moving_ranges=valid_mr_count,
        center_line=round(center_line, 6),
        mr_bar=round(mr_bar, 6),
        sigma_hat=round(sigma_hat, 6),
        ucl=round(ucl, 6),
        lcl=round(lcl, 6),
        d2=d2,
        baseline_stability=baseline_stability,
    )


def calibrate_p_chart(
    df: pd.DataFrame | str | Path,
    proportion_column: str,
    denominator_column: str = "row_count",
    count_column: str | None = None,
    baseline_start: str = "2011-01-01",
    baseline_end: str = "2011-12-31",
    date_column: str = "batch_date",
    min_observations: int = 30,
) -> PChartLimits:
    """Calibrate frozen Phase I parameters for an attribute p-chart (proportions).

    Parameters
    ----------
    df : pd.DataFrame | str | Path
        Input DataFrame or path containing baseline observations.
    proportion_column : str
        Proportion metric column (e.g. 'temp_null_rate').
    denominator_column : str, default "row_count"
        Column representing eligible observation counts per batch (e.g. row_count).
    count_column : str | None, optional
        Explicit count column of numerator events (e.g. missing temp cells). If None,
        derived as round(proportion * denominator).
    baseline_start : str, default "2011-01-01"
        Start date for Phase I baseline window.
    baseline_end : str, default "2011-12-31"
        End date for Phase I baseline window.
    date_column : str, default "batch_date"
        Column containing batch dates.
    min_observations : int, default 30
        Minimum valid batches required.

    Returns
    -------
    PChartLimits
        Frozen Phase I parameters including pooled proportion p_bar and zero-defect status.

    Raises
    ------
    ValueError
        If inputs, denominators, or date ranges are invalid.
    """
    if isinstance(df, (str, Path)):
        df = pd.read_csv(df)

    if proportion_column not in df.columns:
        raise ValueError(f"Proportion column '{proportion_column}' not found in DataFrame")

    if denominator_column not in df.columns:
        raise ValueError(f"Denominator column '{denominator_column}' not found in DataFrame")

    window_df, start_ts, end_ts = _validate_date_window(
        df=df,
        date_column=date_column,
        start_date=baseline_start,
        end_date=baseline_end,
        phase_name="Phase I baseline",
    )

    sample_size = len(window_df)
    if sample_size < min_observations:
        raise ValueError(
            f"Insufficient observations in Phase I baseline: found {sample_size}, required at least {min_observations}"
        )

    # Validate denominators
    denominators = window_df[denominator_column]
    if (denominators <= 0).any() or denominators.isna().any():
        raise ValueError(f"Denominator column '{denominator_column}' contains non-positive or NaN values")

    total_eligible = int(denominators.sum())

    # Calculate pooled baseline proportion: sum(events) / sum(eligible)
    if count_column is not None and count_column in window_df.columns:
        events = window_df[count_column].astype(int)
    else:
        # Reconstruct event counts from proportion and denominator
        events = (window_df[proportion_column] * denominators).round().astype(int)

    total_events = int(events.sum())
    p_bar = float(total_events / total_eligible) if total_eligible > 0 else 0.0

    if not (0.0 <= p_bar <= 1.0):
        raise ValueError(f"Calculated pooled proportion p_bar is invalid: {p_bar}")

    # Strict zero-defect baseline handling:
    # When p_bar == 0.0, sigma_p collapses to 0. Any observed nonzero rate p > 0 triggers an alert.
    # No arbitrary epsilon is added.
    zero_defect_policy = bool(p_bar == 0.0)

    baseline_stability: dict[str, Any] = {
        "sample_size": sample_size,
        "total_eligible_observations": total_eligible,
        "total_events": total_events,
        "p_bar": round(p_bar, 8),
        "zero_defect_policy": zero_defect_policy,
        "note": (
            "Strict zero-defect baseline: all historical observations had zero nonconformance. "
            "Any nonzero null rate in Phase II will immediately trigger an upper-limit alert."
            if zero_defect_policy
            else "Standard p-chart baseline calibrated with non-zero historical defect rate."
        ),
    }

    return PChartLimits(
        metric_name=proportion_column,
        denominator_column=denominator_column,
        baseline_start=start_ts.strftime("%Y-%m-%d"),
        baseline_end=end_ts.strftime("%Y-%m-%d"),
        sample_size=sample_size,
        total_eligible_observations=total_eligible,
        total_events=total_events,
        p_bar=round(p_bar, 8),
        zero_defect_policy=zero_defect_policy,
        baseline_stability=baseline_stability,
    )


def monitor_individuals(
    df: pd.DataFrame | str | Path,
    limits: IndividualsLimits,
    date_column: str = "batch_date",
    monitoring_start: str = "2012-01-01",
    monitoring_end: str = "2012-12-31",
    two_sided: bool = True,
    alert_on_missing: bool = True,
) -> ControlChartResult:
    """Evaluate Phase II observations against frozen Phase I Individuals limits.

    Parameters
    ----------
    df : pd.DataFrame | str | Path
        Input DataFrame or path containing monitoring observations.
    limits : IndividualsLimits
        Frozen calibrated Phase I limits.
    date_column : str, default "batch_date"
        Column containing batch dates.
    monitoring_start : str, default "2012-01-01"
        Start date for Phase II monitoring window.
    monitoring_end : str, default "2012-12-31"
        End date for Phase II monitoring window.
    two_sided : bool, default True
        If True, checks both UCL and LCL; if False, checks UCL only.
    alert_on_missing : bool, default True
        If True, missing (NaN) observations trigger an alert with violation_type="missing_value".

    Returns
    -------
    ControlChartResult
        Container with per-batch records, alert counts, and first alert date.
    """
    if isinstance(df, (str, Path)):
        df = pd.read_csv(df)

    if limits.metric_name not in df.columns:
        raise ValueError(f"Monitored column '{limits.metric_name}' not found in DataFrame")

    window_df, _, _ = _validate_date_window(
        df=df,
        date_column=date_column,
        start_date=monitoring_start,
        end_date=monitoring_end,
        phase_name="Phase II monitoring",
    )

    records: list[dict[str, Any]] = []
    total_alerts = 0
    upper_alerts = 0
    lower_alerts = 0
    missing_count = 0
    first_alert_date: str | None = None

    cl = limits.center_line
    ucl = limits.ucl
    lcl = limits.lcl
    sigma = limits.sigma_hat

    for _, row in window_df.iterrows():
        b_date = row["_parsed_date"].strftime("%Y-%m-%d")
        val = row[limits.metric_name]

        if pd.isna(val):
            missing_count += 1
            is_alert = bool(alert_on_missing)
            v_type = "missing_value"
            z_score = float("nan")
            metric_val = float("nan")
        else:
            metric_val = float(val)
            z_score = float((metric_val - cl) / sigma)

            if metric_val > ucl:
                is_alert = True
                v_type = "upper_limit"
                upper_alerts += 1
            elif two_sided and metric_val < lcl:
                is_alert = True
                v_type = "lower_limit"
                lower_alerts += 1
            else:
                is_alert = False
                v_type = "none"

        if is_alert:
            total_alerts += 1
            if first_alert_date is None:
                first_alert_date = b_date

        records.append(
            {
                "batch_date": b_date,
                "metric_value": metric_val,
                "center_line": cl,
                "ucl": ucl,
                "lcl": lcl,
                "z_score": round(z_score, 4) if np.isfinite(z_score) else float("nan"),
                "is_alert": is_alert,
                "violation_type": v_type,
            }
        )

    records_df = pd.DataFrame(records)

    return ControlChartResult(
        chart_type="individuals",
        metric_name=limits.metric_name,
        records_df=records_df,
        total_observations=len(records_df),
        total_alerts=total_alerts,
        upper_alerts=upper_alerts,
        lower_alerts=lower_alerts,
        missing_observations=missing_count,
        first_alert_date=first_alert_date,
    )


def monitor_p_chart(
    df: pd.DataFrame | str | Path,
    limits: PChartLimits,
    date_column: str = "batch_date",
    monitoring_start: str = "2012-01-01",
    monitoring_end: str = "2012-12-31",
    two_sided: bool = False,  # Default upper-only monitoring for defect/null rates
    alert_on_missing: bool = True,
) -> ControlChartResult:
    """Evaluate Phase II observations against frozen Phase I p-chart parameters.

    Parameters
    ----------
    df : pd.DataFrame | str | Path
        Input DataFrame or path containing monitoring observations.
    limits : PChartLimits
        Frozen calibrated Phase I parameters.
    date_column : str, default "batch_date"
        Column containing batch dates.
    monitoring_start : str, default "2012-01-01"
        Start date for Phase II monitoring window.
    monitoring_end : str, default "2012-12-31"
        End date for Phase II monitoring window.
    two_sided : bool, default False
        If False (default), evaluates upper limit only (spikes in nulls); if True, also checks LCL.
    alert_on_missing : bool, default True
        If True, missing (NaN) observations trigger an alert with violation_type="missing_value".

    Returns
    -------
    ControlChartResult
        Container with per-batch records, dynamic sample-size limits, alert counts, and first alert date.
    """
    if isinstance(df, (str, Path)):
        df = pd.read_csv(df)

    if limits.metric_name not in df.columns:
        raise ValueError(f"Proportion column '{limits.metric_name}' not found in DataFrame")

    if limits.denominator_column not in df.columns:
        raise ValueError(f"Denominator column '{limits.denominator_column}' not found in DataFrame")

    window_df, _, _ = _validate_date_window(
        df=df,
        date_column=date_column,
        start_date=monitoring_start,
        end_date=monitoring_end,
        phase_name="Phase II monitoring",
    )

    records: list[dict[str, Any]] = []
    total_alerts = 0
    upper_alerts = 0
    lower_alerts = 0
    missing_count = 0
    first_alert_date: str | None = None

    p_bar = limits.p_bar
    is_zero_defect = limits.zero_defect_policy

    for _, row in window_df.iterrows():
        b_date = row["_parsed_date"].strftime("%Y-%m-%d")
        val = row[limits.metric_name]
        n_i = row[limits.denominator_column]

        if pd.isna(val):
            missing_count += 1
            is_alert = bool(alert_on_missing)
            v_type = "missing_value"
            z_score = float("nan")
            metric_val = float("nan")
            ucl_i = float("nan")
            lcl_i = float("nan")
        elif pd.isna(n_i) or n_i <= 0:
            is_alert = bool(alert_on_missing)
            v_type = "invalid_sample_size"
            z_score = float("nan")
            metric_val = float(val)
            ucl_i = float("nan")
            lcl_i = float("nan")
        else:
            metric_val = float(val)
            batch_size = float(n_i)

            if is_zero_defect:
                # Strict zero-defect policy: p_bar == 0.0, sigma_p == 0.0
                # UCL = 0.0, LCL = 0.0; any positive proportion p > 0 is an upper violation
                ucl_i = 0.0
                lcl_i = 0.0
                if metric_val > 0.0:
                    is_alert = True
                    v_type = "upper_limit"
                    upper_alerts += 1
                    z_score = float("inf")
                else:
                    is_alert = False
                    v_type = "none"
                    z_score = 0.0
            else:
                sigma_p = np.sqrt(p_bar * (1.0 - p_bar) / batch_size)
                ucl_i = float(min(1.0, p_bar + 3.0 * sigma_p))
                lcl_i = float(max(0.0, p_bar - 3.0 * sigma_p))

                z_score = float((metric_val - p_bar) / sigma_p) if sigma_p > 0 else 0.0

                if metric_val > ucl_i:
                    is_alert = True
                    v_type = "upper_limit"
                    upper_alerts += 1
                elif two_sided and metric_val < lcl_i:
                    is_alert = True
                    v_type = "lower_limit"
                    lower_alerts += 1
                else:
                    is_alert = False
                    v_type = "none"

        if is_alert:
            total_alerts += 1
            if first_alert_date is None:
                first_alert_date = b_date

        records.append(
            {
                "batch_date": b_date,
                "metric_value": metric_val,
                "center_line": p_bar,
                "ucl": round(ucl_i, 6) if np.isfinite(ucl_i) else ucl_i,
                "lcl": round(lcl_i, 6) if np.isfinite(lcl_i) else lcl_i,
                "z_score": round(z_score, 4) if np.isfinite(z_score) else z_score,
                "is_alert": is_alert,
                "violation_type": v_type,
            }
        )

    records_df = pd.DataFrame(records)

    return ControlChartResult(
        chart_type="p_chart",
        metric_name=limits.metric_name,
        records_df=records_df,
        total_observations=len(records_df),
        total_alerts=total_alerts,
        upper_alerts=upper_alerts,
        lower_alerts=lower_alerts,
        missing_observations=missing_count,
        first_alert_date=first_alert_date,
    )
