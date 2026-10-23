"""Statistical Process Control (SPC) Cumulative Sum (CUSUM) monitoring module.

This module provides Phase I baseline calibration and Phase II prospective sequential
monitoring using two-sided tabular CUSUM for continuous quality metrics (e.g. cnt_mean).

Methodological Specifications:
------------------------------
1. Standardization:
   Observations are standardized against frozen Phase I baseline parameters:
     z[t] = (x[t] - mu_0) / sigma_0
   where mu_0 is the Phase I arithmetic mean and sigma_0 is estimated using the
   standard consecutive moving-range estimator:
     MR_bar = mean(|x[t] - x[t-1]|) for strictly adjacent, non-missing consecutive days
     sigma_0 = MR_bar / 1.128 (divisor d2 for subgroup size n=2).

2. Two-Sided Tabular Recursions:
   Upper and lower accumulators track positive and negative process shifts:
     C_plus[t]  = max(0, C_plus[t-1]  + z[t] - k)
     C_minus[t] = max(0, C_minus[t-1] - z[t] - k)
   where k is the reference value / slack parameter (in sigma units, default k=0.5).

3. Strict Decision Rule:
   An alarm is triggered if and only if an accumulator is strictly greater than h:
     is_alert = (C_plus[t] > h) or (two_sided and C_minus[t] > h)
   Threshold equality (C[t] == h) does NOT trigger an alert.

4. Missing Values & Gaps:
   Missing values (NaN) do not reset cumulative sums to zero; accumulators carry forward
   historical state (C[t] = C[t-1]) so accumulated evidence of process displacement is
   not erased by pipeline downtime. If alert_on_missing=True, an alert is raised with
   violation_type="missing_value". Calendar gaps are validated during moving-range estimation.

5. Parameter Freezing:
   Phase I parameters are frozen in an immutable CUSUMGaussianLimits dataclass to prevent
   data leakage from Phase II monitoring.

6. Seasonality & Baseline Instability Warning:
   Continuous metrics subject to strong macro-seasonality (such as bike rental cnt_mean)
   exhibit substantial non-stationary variation. Under static CUSUM with constant mu_0,
   natural seasonal warming causes continuous positive accumulation (C_plus > h) prior
   to any injected quality drift. These early signals reflect unmodeled seasonality rather
   than pipeline degradation and must be documented as potential false alarms.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal
import numpy as np
import pandas as pd

from src.spc.control_charts import _validate_date_window


@dataclass(frozen=True)
class CUSUMGaussianLimits:
    """Calibrated frozen baseline parameters for continuous tabular CUSUM.

    Attributes
    ----------
    metric_name : str
        Name of the monitored continuous metric column (e.g. 'cnt_mean').
    baseline_start : str
        Start date of Phase I calibration window (YYYY-MM-DD).
    baseline_end : str
        End date of Phase I calibration window (YYYY-MM-DD).
    sample_size : int
        Number of valid daily observations in Phase I.
    valid_moving_ranges : int
        Number of adjacent consecutive pairs used for MR-bar calculation.
    center_line : float
        Baseline arithmetic mean (CL = mu_0).
    mr_bar : float
        Average moving range across adjacent non-null days.
    sigma_hat : float
        Estimated process standard deviation (sigma_0 = MR-bar / 1.128).
    k : float
        Reference value / slack parameter in sigma units (default 0.5).
    h : float
        Decision interval threshold in sigma units (default 5.0).
    d2 : float
        Statistical divisor for subgroup size n=2 (1.128).
    baseline_stability : dict[str, Any]
        Audit dictionary recording baseline stability checks and seasonality warnings.
    """

    metric_name: str
    baseline_start: str
    baseline_end: str
    sample_size: int
    valid_moving_ranges: int
    center_line: float
    mr_bar: float
    sigma_hat: float
    k: float = 0.5
    h: float = 5.0
    d2: float = 1.128
    baseline_stability: dict[str, Any] = field(default_factory=dict)

    @property
    def mu_0(self) -> float:
        """Alias for center_line (Phase I target mean)."""
        return self.center_line

    @property
    def sigma_0(self) -> float:
        """Alias for sigma_hat (Phase I process standard deviation)."""
        return self.sigma_hat

    def to_dict(self) -> dict[str, Any]:
        """Convert limits to a serializable dictionary."""
        return asdict(self)


@dataclass
class CUSUMResult:
    """Phase II continuous CUSUM monitoring observations and alert signals.

    Attributes
    ----------
    chart_type : str
        Chart identifier (always 'gaussian_cusum').
    metric_name : str
        Name of the monitored metric column.
    records_df : pd.DataFrame
        DataFrame containing per-batch CUSUM observations and alerts.
    total_observations : int
        Total number of monitoring observations evaluated.
    total_alerts : int
        Total number of alert batches.
    upper_alerts : int
        Number of batches where C_plus > h.
    lower_alerts : int
        Number of batches where C_minus > h.
    missing_observations : int
        Number of batches with NaN or missing values.
    first_alert_date : str | None
        Date of the first alert, or None if no alerts occurred.
    k : float
        Slack parameter used for monitoring.
    h : float
        Decision interval threshold used for monitoring.
    reset_policy : str
        Reset policy used ('none').
    two_sided : bool
        Whether monitoring was two-sided or upper-only.
    """

    chart_type: str
    metric_name: str
    records_df: pd.DataFrame
    total_observations: int
    total_alerts: int
    upper_alerts: int
    lower_alerts: int
    missing_observations: int
    first_alert_date: str | None
    k: float
    h: float
    reset_policy: str
    two_sided: bool


def calibrate_gaussian_cusum(
    df: pd.DataFrame | str | Path,
    metric_column: str,
    baseline_start: str = "2011-01-01",
    baseline_end: str = "2011-12-31",
    date_column: str = "batch_date",
    k: float = 0.5,
    h: float = 5.0,
    min_observations: int = 30,
    min_moving_ranges: int | None = None,
) -> CUSUMGaussianLimits:
    """Calibrate frozen Phase I parameters for continuous tabular CUSUM.

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
    k : float, default 0.5
        Reference value / slack parameter in standard deviation units.
    h : float, default 5.0
        Decision interval threshold in standard deviation units.
    min_observations : int, default 30
        Minimum valid observations required for stable parameter estimation.
    min_moving_ranges : int | None, optional
        Minimum valid consecutive moving-range pairs required. Defaults to
        max(1, min_observations // 2).

    Returns
    -------
    CUSUMGaussianLimits
        Frozen calibrated Phase I parameters including mu_0, sigma_0, k, h, and stability audit.

    Raises
    ------
    ValueError
        If inputs, parameters, date ranges, observation counts, or variance are invalid.
    """
    if isinstance(df, (str, Path)):
        df = pd.read_csv(df)

    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df)}")

    if metric_column not in df.columns:
        raise ValueError(f"Metric column '{metric_column}' not found in DataFrame")

    if not np.isfinite(k) or k <= 0:
        raise ValueError(f"Slack parameter k must be positive and finite, got {k}")

    if not np.isfinite(h) or h <= 0:
        raise ValueError(f"Decision interval h must be positive and finite, got {h}")

    if min_observations < 2:
        raise ValueError(f"min_observations must be at least 2, got {min_observations}")

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
    # (day_diff == 1) and neither observation is NaN. Gaps and missing values do not bridge!
    moving_ranges: list[float] = []
    n_total = len(window_df)

    for i in range(1, n_total):
        date_prev = series_dates.iloc[i - 1]
        date_curr = series_dates.iloc[i]
        val_prev = series_values.iloc[i - 1]
        val_curr = series_values.iloc[i]

        day_diff = (date_curr - date_prev).days

        if day_diff == 1 and pd.notna(val_prev) and pd.notna(val_curr):
            moving_ranges.append(abs(float(val_curr) - float(val_prev)))

    valid_mr_count = len(moving_ranges)
    required_mr = (
        min_moving_ranges if min_moving_ranges is not None else max(1, min_observations // 2)
    )
    if valid_mr_count < required_mr:
        raise ValueError(
            f"Insufficient valid consecutive adjacent pairs for moving-range calculation: "
            f"found {valid_mr_count}, required at least {required_mr}"
        )

    mr_bar = float(np.mean(moving_ranges))
    d2 = 1.128  # Divisor for subgroup size n=2
    sigma_hat = float(mr_bar / d2)

    if np.isclose(sigma_hat, 0.0) or sigma_hat < 1e-12:
        raise ValueError(
            f"Degenerate zero-variance Phase I baseline for '{metric_column}' (sigma_hat={sigma_hat:.6f}). "
            f"CUSUM cannot be constructed from identical observations."
        )

    center_line = float(series_values.loc[valid_mask].mean())

    # Baseline stability check against static three-sigma bounds (audit of Phase I)
    valid_vals = series_values.loc[valid_mask].astype(float)
    ucl = center_line + 3.0 * sigma_hat
    lcl = center_line - 3.0 * sigma_hat
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
            f"Unmodeled seasonal cycles may induce Phase II false alarms under static tabular CUSUM."
        )
    )

    baseline_stability: dict[str, Any] = {
        "sample_size": sample_size,
        "valid_moving_ranges": valid_mr_count,
        "mr_bar": round(mr_bar, 6),
        "sigma_hat": round(sigma_hat, 6),
        "baseline_alerts_count": total_baseline_alerts,
        "baseline_upper_alerts": baseline_upper_alerts,
        "baseline_lower_alerts": baseline_lower_alerts,
        "baseline_violation_rate": round(violation_rate, 4),
        "is_stable": bool(violation_rate <= 0.05),
        "note": stability_note,
    }

    return CUSUMGaussianLimits(
        metric_name=metric_column,
        baseline_start=start_ts.strftime("%Y-%m-%d"),
        baseline_end=end_ts.strftime("%Y-%m-%d"),
        sample_size=sample_size,
        valid_moving_ranges=valid_mr_count,
        center_line=round(center_line, 6),
        mr_bar=round(mr_bar, 6),
        sigma_hat=round(sigma_hat, 6),
        k=k,
        h=h,
        d2=d2,
        baseline_stability=baseline_stability,
    )


def monitor_gaussian_cusum(
    df: pd.DataFrame | str | Path,
    limits: CUSUMGaussianLimits,
    date_column: str = "batch_date",
    monitoring_start: str = "2012-01-01",
    monitoring_end: str = "2012-12-31",
    two_sided: bool = True,
    alert_on_missing: bool = True,
    reset_policy: Literal["none"] = "none",
) -> CUSUMResult:
    """Evaluate Phase II observations against frozen Phase I tabular CUSUM limits.

    Parameters
    ----------
    df : pd.DataFrame | str | Path
        Input DataFrame or path containing monitoring observations.
    limits : CUSUMGaussianLimits
        Frozen calibrated Phase I parameters.
    date_column : str, default "batch_date"
        Column containing batch dates.
    monitoring_start : str, default "2012-01-01"
        Start date for Phase II monitoring window.
    monitoring_end : str, default "2012-12-31"
        End date for Phase II monitoring window.
    two_sided : bool, default True
        If True, tracks both upper (C_plus) and lower (C_minus) CUSUM accumulators.
        If False, tracks upper CUSUM only.
    alert_on_missing : bool, default True
        If True, missing (NaN) observations trigger an alert with violation_type="missing_value".
    reset_policy : Literal["none"], default "none"
        Reset policy for CUSUM accumulators. In this step, only persistent accumulation
        ("none") is supported.

    Returns
    -------
    CUSUMResult
        Container with per-batch records, cumulative sums, alert counts, and first alert date.

    Raises
    ------
    ValueError
        If inputs, columns, dates, or reset_policy are invalid.
    """
    if reset_policy != "none":
        raise ValueError(
            f"Unsupported reset_policy '{reset_policy}'. Only 'none' is supported in this step."
        )

    if isinstance(df, (str, Path)):
        df = pd.read_csv(df)

    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df)}")

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

    mu_0 = limits.mu_0
    sigma_0 = limits.sigma_0
    k = limits.k
    h = limits.h

    c_plus_current = 0.0
    c_minus_current = 0.0

    for _, row in window_df.iterrows():
        b_date = row["_parsed_date"].strftime("%Y-%m-%d")
        val = row[limits.metric_name]

        if pd.isna(val):
            missing_count += 1
            z_score = float("nan")
            metric_val = float("nan")

            # Missing observation handling:
            # Carry forward previous accumulator state; do NOT reset to zero, which would
            # erase accumulated evidence of drift due to pipeline downtime.
            c_plus = c_plus_current
            c_minus = c_minus_current if two_sided else float("nan")

            v_type = "missing_value"
            is_alert = bool(alert_on_missing)
        else:
            metric_val = float(val)
            z_score = float((metric_val - mu_0) / sigma_0)

            # Two-sided tabular CUSUM recursions
            c_plus = float(max(0.0, c_plus_current + z_score - k))
            c_plus_current = c_plus

            if two_sided:
                c_minus = float(max(0.0, c_minus_current - z_score - k))
                c_minus_current = c_minus
            else:
                c_minus = float("nan")

            # Strict inequality decision rule: alert if and only if C > h
            upper_violation = bool(c_plus > h)
            lower_violation = bool(two_sided and c_minus > h)

            if upper_violation and lower_violation:
                is_alert = True
                v_type = "two_sided"
                upper_alerts += 1
                lower_alerts += 1
            elif upper_violation:
                is_alert = True
                v_type = "upper_cusum"
                upper_alerts += 1
            elif lower_violation:
                is_alert = True
                v_type = "lower_cusum"
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
                "center_line": mu_0,
                "z_score": round(z_score, 4) if np.isfinite(z_score) else z_score,
                "c_plus": float(c_plus),
                "c_minus": float(c_minus) if np.isfinite(c_minus) else float("nan"),
                "k": k,
                "h": h,
                "is_alert": is_alert,
                "violation_type": v_type,
            }
        )

    records_df = pd.DataFrame(records)

    return CUSUMResult(
        chart_type="gaussian_cusum",
        metric_name=limits.metric_name,
        records_df=records_df,
        total_observations=len(records_df),
        total_alerts=total_alerts,
        upper_alerts=upper_alerts,
        lower_alerts=lower_alerts,
        missing_observations=missing_count,
        first_alert_date=first_alert_date,
        k=k,
        h=h,
        reset_policy=reset_policy,
        two_sided=two_sided,
    )

