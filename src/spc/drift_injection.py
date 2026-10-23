"""Deterministic synthetic drift injection module with explicit ground truth.

This module provides reproducible, parameterized drift injection mechanisms for
data pipeline quality monitoring evaluation:
1. Gradual null-rate drift with a deterministic linear probability schedule.
2. Abrupt distribution shift (additive or multiplicative) with optional clipping.

Ground-truth records distinguish intended parameters from measured outcomes,
providing exact auditability at both the overall dataset and daily batch levels.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal
import json
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class GradualNullDriftConfig:
    """Configuration for gradual null-rate drift injection.

    Attributes
    ----------
    event_id : str
        Unique identifier for the drift event.
    affected_column : str
        Numeric column name to inject null values into.
    onset_date : str
        First date (YYYY-MM-DD) of the drift ramp.
    end_date : str | None
        Final date (YYYY-MM-DD) of the drift window. If None, extends to dataset end.
    start_null_rate : float
        Initial intended null probability at onset_date (must be >= 0.0).
    max_null_rate : float
        Final intended null probability at end_date (must be >= start_null_rate and <= 1.0).
    random_seed : int
        Seed for the independent deterministic random number generator.
    """

    event_id: str
    affected_column: str
    onset_date: str
    end_date: str | None = None
    start_null_rate: float = 0.0
    max_null_rate: float = 0.40
    random_seed: int = 42


@dataclass(frozen=True)
class AbruptShiftConfig:
    """Configuration for abrupt distribution shift injection.

    Attributes
    ----------
    event_id : str
        Unique identifier for the drift event.
    affected_column : str
        Numeric column name to apply distribution shift to.
    onset_date : str
        First date (YYYY-MM-DD) where the shift takes effect.
    end_date : str | None
        Final date (YYYY-MM-DD) of the shift window. If None, extends to dataset end.
    shift_type : Literal["additive", "multiplicative"]
        Type of transformation to apply.
    shift_value : float
        Magnitude of shift (added if additive, multiplied if multiplicative).
    clip_min : float | None
        Optional lower bound for domain constraints after transformation.
    clip_max : float | None
        Optional upper bound for domain constraints after transformation.
    random_seed : int
        Seed for deterministic tracking (consistent interface).
    """

    event_id: str
    affected_column: str
    onset_date: str
    end_date: str | None = None
    shift_type: Literal["additive", "multiplicative"] = "additive"
    shift_value: float = 50.0
    clip_min: float | None = None
    clip_max: float | None = None
    random_seed: int = 42


@dataclass
class GroundTruthRecord:
    """Machine-readable ground truth record for drift injection."""

    event_id: str
    scenario_type: str
    affected_column: str
    onset_date: str
    end_date: str
    seed: int
    intended_parameters: dict[str, Any]
    measured_outcome: dict[str, Any]
    batch_records: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """Convert ground truth record to a serializable dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert ground truth record to formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent)


def _validate_common_inputs(
    df: pd.DataFrame,
    affected_column: str,
    onset_date: str,
    end_date: str | None,
) -> tuple[pd.Series, pd.Timestamp, pd.Timestamp]:
    """Validate DataFrame, target column, timestamps, and date window."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df)}")

    if df.empty:
        raise ValueError("Cannot inject drift into an empty DataFrame")

    if affected_column not in df.columns:
        raise ValueError(
            f"Target column '{affected_column}' not found in DataFrame columns"
        )

    if not pd.api.types.is_numeric_dtype(df[affected_column]):
        raise ValueError(
            f"Target column '{affected_column}' must be numeric, got dtype {df[affected_column].dtype}"
        )

    if "dteday" not in df.columns:
        raise ValueError("Input DataFrame must contain 'dteday' column for date grouping")

    parsed_dates = pd.to_datetime(df["dteday"], errors="coerce")
    if parsed_dates.isna().any():
        raise ValueError("Invalid or unparseable dates encountered in 'dteday'")

    min_date = parsed_dates.min().floor("D")
    max_date = parsed_dates.max().floor("D")

    try:
        onset_ts = pd.to_datetime(onset_date).floor("D")
    except Exception as e:
        raise ValueError(f"Invalid onset_date format: '{onset_date}'") from e

    if onset_ts < min_date or onset_ts > max_date:
        raise ValueError(
            f"onset_date '{onset_date}' falls outside dataset date range "
            f"[{min_date.strftime('%Y-%m-%d')}, {max_date.strftime('%Y-%m-%d')}]"
        )

    if end_date is not None:
        try:
            end_ts = pd.to_datetime(end_date).floor("D")
        except Exception as e:
            raise ValueError(f"Invalid end_date format: '{end_date}'") from e

        if end_ts < onset_ts:
            raise ValueError(
                f"end_date '{end_date}' cannot be earlier than onset_date '{onset_date}'"
            )
        if end_ts > max_date:
            raise ValueError(
                f"end_date '{end_date}' exceeds dataset max date {max_date.strftime('%Y-%m-%d')}"
            )
    else:
        end_ts = max_date

    return parsed_dates, onset_ts, end_ts


def inject_gradual_null_drift(
    df: pd.DataFrame,
    config: GradualNullDriftConfig,
) -> tuple[pd.DataFrame, GroundTruthRecord]:
    """Inject gradual null-rate drift into a numeric column following a linear schedule.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame (preserved immutably; a deep copy is modified).
    config : GradualNullDriftConfig
        Drift configuration parameters.

    Returns
    -------
    tuple[pd.DataFrame, GroundTruthRecord]
        Modified DataFrame with injected nulls, and detailed ground-truth record.

    Raises
    ------
    ValueError
        If inputs, probabilities, or date ranges are invalid.
    """
    if not (0.0 <= config.start_null_rate <= 1.0):
        raise ValueError(
            f"start_null_rate must be between 0.0 and 1.0, got {config.start_null_rate}"
        )
    if not (0.0 <= config.max_null_rate <= 1.0):
        raise ValueError(
            f"max_null_rate must be between 0.0 and 1.0, got {config.max_null_rate}"
        )
    if config.start_null_rate > config.max_null_rate:
        raise ValueError(
            f"start_null_rate ({config.start_null_rate}) cannot exceed max_null_rate ({config.max_null_rate})"
        )

    parsed_dates, onset_ts, end_ts = _validate_common_inputs(
        df=df,
        affected_column=config.affected_column,
        onset_date=config.onset_date,
        end_date=config.end_date,
    )

    # Immutable copy: do not modify original DataFrame
    injected_df = df.copy(deep=True)
    rng = np.random.default_rng(config.random_seed)

    # Identify all distinct calendar dates sorted chronologically
    daily_dates = sorted(parsed_dates.dt.floor("D").unique())
    event_dates = [d for d in daily_dates if onset_ts <= d <= end_ts]
    num_event_days = len(event_dates)

    # Compute deterministic linear probability schedule for each event day
    if num_event_days <= 1:
        probability_schedule = {
            event_dates[0]: float(config.max_null_rate)
        } if num_event_days == 1 else {}
    else:
        probability_schedule = {
            d: float(
                config.start_null_rate
                + i * (config.max_null_rate - config.start_null_rate) / (num_event_days - 1)
            )
            for i, d in enumerate(event_dates)
        }

    batch_records: list[dict[str, Any]] = []
    total_injected_missing = 0
    total_rows_in_window = 0

    col = config.affected_column
    day_series = parsed_dates.dt.floor("D")

    for current_day in daily_dates:
        day_str = current_day.strftime("%Y-%m-%d")
        day_mask = day_series == current_day
        batch_indices = injected_df.index[day_mask]
        batch_size = len(batch_indices)

        in_window = onset_ts <= current_day <= end_ts
        intended_prob = probability_schedule.get(current_day, 0.0)

        # Baseline count of eligible non-null cells before injection
        pre_null_mask = injected_df.loc[batch_indices, col].isna()
        eligible_indices = batch_indices[~pre_null_mask]
        eligible_count = len(eligible_indices)

        injected_count = 0
        if in_window and eligible_count > 0 and intended_prob > 0.0:
            total_rows_in_window += batch_size
            # Bernoulli trials for each eligible cell
            mask = rng.uniform(0.0, 1.0, size=eligible_count) < intended_prob
            null_target_indices = eligible_indices[mask]
            injected_count = len(null_target_indices)
            injected_df.loc[null_target_indices, col] = np.nan
            total_injected_missing += injected_count

        total_missing = int(injected_df.loc[batch_indices, col].isna().sum())
        actual_rate = float(total_missing / batch_size) if batch_size > 0 else 0.0

        batch_records.append(
            {
                "batch_date": day_str,
                "in_drift_window": bool(in_window),
                "intended_null_rate": float(intended_prob),
                "eligible_count": int(eligible_count),
                "injected_missing_count": int(injected_count),
                "total_missing_count": int(total_missing),
                "batch_row_count": int(batch_size),
                "actual_null_rate": round(actual_rate, 6),
            }
        )

    # Measured summary outcome
    total_rows = len(injected_df)
    pre_window_missing = sum(
        b["total_missing_count"] for b in batch_records if not b["in_drift_window"]
    )
    pre_window_rows = sum(
        b["batch_row_count"] for b in batch_records if not b["in_drift_window"]
    )
    post_window_missing = sum(
        b["total_missing_count"] for b in batch_records if b["in_drift_window"]
    )
    post_window_rows = sum(
        b["batch_row_count"] for b in batch_records if b["in_drift_window"]
    )

    measured_outcome = {
        "total_dataset_rows": int(total_rows),
        "total_rows_in_window": int(total_rows_in_window),
        "total_injected_null_cells": int(total_injected_missing),
        "total_batches_in_window": int(num_event_days),
        "pre_window_null_rate": round(
            float(pre_window_missing / pre_window_rows) if pre_window_rows > 0 else 0.0,
            6,
        ),
        "post_window_null_rate": round(
            float(post_window_missing / post_window_rows) if post_window_rows > 0 else 0.0,
            6,
        ),
        "first_event_batch_actual_rate": batch_records[
            daily_dates.index(event_dates[0])
        ]["actual_null_rate"] if event_dates else 0.0,
        "final_event_batch_actual_rate": batch_records[
            daily_dates.index(event_dates[-1])
        ]["actual_null_rate"] if event_dates else 0.0,
    }

    ground_truth = GroundTruthRecord(
        event_id=config.event_id,
        scenario_type="gradual_null_rate",
        affected_column=config.affected_column,
        onset_date=onset_ts.strftime("%Y-%m-%d"),
        end_date=end_ts.strftime("%Y-%m-%d"),
        seed=config.random_seed,
        intended_parameters={
            "start_null_rate": config.start_null_rate,
            "max_null_rate": config.max_null_rate,
            "schedule": "linear",
        },
        measured_outcome=measured_outcome,
        batch_records=batch_records,
    )

    return injected_df, ground_truth


def inject_abrupt_distribution_shift(
    df: pd.DataFrame,
    config: AbruptShiftConfig,
) -> tuple[pd.DataFrame, GroundTruthRecord]:
    """Inject an abrupt distribution shift into a numeric column within an event window.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame (preserved immutably; a deep copy is modified).
    config : AbruptShiftConfig
        Drift configuration parameters.

    Returns
    -------
    tuple[pd.DataFrame, GroundTruthRecord]
        Modified DataFrame with shifted distribution, and detailed ground-truth record.

    Raises
    ------
    ValueError
        If inputs, shift parameters, or clipping bounds are invalid.
    """
    if config.shift_type not in ("additive", "multiplicative"):
        raise ValueError(
            f"Invalid shift_type: '{config.shift_type}'. Expected 'additive' or 'multiplicative'."
        )

    if not np.isfinite(config.shift_value):
        raise ValueError(f"shift_value must be finite, got {config.shift_value}")

    if config.clip_min is not None and config.clip_max is not None:
        if config.clip_min > config.clip_max:
            raise ValueError(
                f"clip_min ({config.clip_min}) cannot exceed clip_max ({config.clip_max})"
            )

    parsed_dates, onset_ts, end_ts = _validate_common_inputs(
        df=df,
        affected_column=config.affected_column,
        onset_date=config.onset_date,
        end_date=config.end_date,
    )

    # Immutable copy: do not modify original DataFrame
    injected_df = df.copy(deep=True)
    col = config.affected_column
    day_series = parsed_dates.dt.floor("D")

    daily_dates = sorted(day_series.unique())
    event_dates = [d for d in daily_dates if onset_ts <= d <= end_ts]
    num_event_days = len(event_dates)

    batch_records: list[dict[str, Any]] = []
    total_clipped_count = 0

    for current_day in daily_dates:
        day_str = current_day.strftime("%Y-%m-%d")
        day_mask = day_series == current_day
        batch_indices = injected_df.index[day_mask]
        batch_size = len(batch_indices)

        in_window = onset_ts <= current_day <= end_ts

        pre_values = injected_df.loc[batch_indices, col].copy()
        pre_mean = float(pre_values.mean()) if not pre_values.empty else float("nan")

        clipped_in_batch = 0

        if in_window:
            # Apply configured transformation
            if config.shift_type == "additive":
                transformed = pre_values + config.shift_value
            else:  # multiplicative
                transformed = pre_values * config.shift_value

            # Measure clipping effects if configured
            if config.clip_min is not None:
                clipped_low = transformed < config.clip_min
                clipped_in_batch += int(clipped_low.sum())
                transformed = transformed.clip(lower=config.clip_min)

            if config.clip_max is not None:
                clipped_high = transformed > config.clip_max
                clipped_in_batch += int(clipped_high.sum())
                transformed = transformed.clip(upper=config.clip_max)

            injected_df.loc[batch_indices, col] = transformed
            total_clipped_count += clipped_in_batch

        post_values = injected_df.loc[batch_indices, col]
        post_mean = float(post_values.mean()) if not post_values.empty else float("nan")
        actual_shift = (
            float(post_mean - pre_mean)
            if (np.isfinite(post_mean) and np.isfinite(pre_mean))
            else 0.0
        )

        batch_records.append(
            {
                "batch_date": day_str,
                "in_drift_window": bool(in_window),
                "batch_row_count": int(batch_size),
                "pre_injection_mean": round(pre_mean, 6),
                "post_injection_mean": round(post_mean, 6),
                "actual_mean_shift": round(actual_shift, 6),
                "clipped_count": int(clipped_in_batch),
            }
        )

    # Aggregate measured summary outcomes
    pre_window_batches = [b for b in batch_records if not b["in_drift_window"]]
    post_window_batches = [b for b in batch_records if b["in_drift_window"]]

    pre_window_mean = float(
        np.mean([b["pre_injection_mean"] for b in pre_window_batches])
    ) if pre_window_batches else float("nan")

    post_window_orig_mean = float(
        np.mean([b["pre_injection_mean"] for b in post_window_batches])
    ) if post_window_batches else float("nan")

    post_window_shifted_mean = float(
        np.mean([b["post_injection_mean"] for b in post_window_batches])
    ) if post_window_batches else float("nan")

    effective_shift = (
        post_window_shifted_mean - post_window_orig_mean
        if (np.isfinite(post_window_shifted_mean) and np.isfinite(post_window_orig_mean))
        else 0.0
    )

    measured_outcome = {
        "total_dataset_rows": int(len(injected_df)),
        "total_rows_affected": int(sum(b["batch_row_count"] for b in post_window_batches)),
        "total_batches_affected": int(num_event_days),
        "pre_window_overall_mean": round(pre_window_mean, 6),
        "post_window_original_mean": round(post_window_orig_mean, 6),
        "post_window_effective_mean": round(post_window_shifted_mean, 6),
        "effective_overall_shift": round(effective_shift, 6),
        "total_clipped_cells": int(total_clipped_count),
    }

    ground_truth = GroundTruthRecord(
        event_id=config.event_id,
        scenario_type="abrupt_distribution_shift",
        affected_column=config.affected_column,
        onset_date=onset_ts.strftime("%Y-%m-%d"),
        end_date=end_ts.strftime("%Y-%m-%d"),
        seed=config.random_seed,
        intended_parameters={
            "shift_type": config.shift_type,
            "shift_value": config.shift_value,
            "clip_min": config.clip_min,
            "clip_max": config.clip_max,
        },
        measured_outcome=measured_outcome,
        batch_records=batch_records,
    )

    return injected_df, ground_truth


def save_injection_artifacts(
    modified_df: pd.DataFrame,
    ground_truth: GroundTruthRecord,
    output_dir: Path | str,
    csv_filename: str,
    json_filename: str,
) -> tuple[Path, Path]:
    """Persist modified dataset and associated ground truth JSON.

    Parameters
    ----------
    modified_df : pd.DataFrame
        Injected DataFrame to write to CSV.
    ground_truth : GroundTruthRecord
        Audit record to write to JSON.
    output_dir : Path | str
        Destination directory.
    csv_filename : str
        Filename for the CSV output.
    json_filename : str
        Filename for the ground truth JSON.

    Returns
    -------
    tuple[Path, Path]
        Paths to the saved CSV and JSON files.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / csv_filename
    json_path = out_dir / json_filename

    modified_df.to_csv(csv_path, index=False)
    json_path.write_text(ground_truth.to_json(indent=2), encoding="utf-8")

    return csv_path, json_path


def main() -> None:
    """Run baseline drift injection scenarios on the real hourly dataset."""
    repo_root = Path(__file__).resolve().parents[2]
    raw_path = repo_root / "data" / "raw" / "hour.csv"
    output_dir = repo_root / "data" / "processed" / "drift"

    if not raw_path.exists():
        raw_path = Path("data/raw/hour.csv")
        output_dir = Path("data/processed/drift")

    print(f"Loading raw hourly dataset from: {raw_path}")
    raw_df = pd.read_csv(raw_path)

    # Scenario 1: Gradual null drift on 'temp'
    print("\n--- Running Scenario 1: Gradual Null-Rate Drift on 'temp' ---")
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
    csv_null, json_null = save_injection_artifacts(
        modified_df=df_null,
        ground_truth=gt_null,
        output_dir=output_dir,
        csv_filename="hour_gradual_null_temp.csv",
        json_filename="ground_truth_gradual_null_temp.json",
    )
    print(f"Saved injected dataset to : {csv_null}")
    print(f"Saved ground truth JSON to: {json_null}")
    print(f"  Total null cells injected: {gt_null.measured_outcome['total_injected_null_cells']}")
    print(f"  Post-window null rate    : {gt_null.measured_outcome['post_window_null_rate']:.4f}")

    # Scenario 2: Abrupt distribution shift on 'cnt'
    print("\n--- Running Scenario 2: Abrupt Distribution Shift on 'cnt' ---")
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
    csv_shift, json_shift = save_injection_artifacts(
        modified_df=df_shift,
        ground_truth=gt_shift,
        output_dir=output_dir,
        csv_filename="hour_abrupt_shift_cnt.csv",
        json_filename="ground_truth_abrupt_shift_cnt.json",
    )
    print(f"Saved injected dataset to : {csv_shift}")
    print(f"Saved ground truth JSON to: {json_shift}")
    print(f"  Total rows affected      : {gt_shift.measured_outcome['total_rows_affected']}")
    print(f"  Effective overall shift  : {gt_shift.measured_outcome['effective_overall_shift']:.2f}")


if __name__ == "__main__":
    main()

