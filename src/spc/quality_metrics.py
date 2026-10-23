"""Baseline quality metrics module for batch-wise data pipeline monitoring.

This module provides daily aggregation and quality metric calculation
over raw and processed data batches in the Statistical Process Control (SPC) framework.
Supports overall dataset null-rates, feature-specific per-column null rates,
configurable targets, and custom date/cardinality columns.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence
import numpy as np
import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = ("dteday", "cnt", "season", "weathersit")

METRIC_COLUMNS: tuple[str, ...] = (
    "batch_date",
    "row_count",
    "null_rate",
    "cnt_mean",
    "cnt_std",
    "season_cardinality",
    "weathersit_cardinality",
)


def compute_daily_quality_metrics(
    df: pd.DataFrame | str | Path,
    required_columns: Sequence[str] | None = None,
    date_column: str = "dteday",
    target_column: str = "cnt",
    cardinality_columns: Sequence[str] = ("season", "weathersit"),
    null_rate_columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Compute daily quality-metric observations grouped by date.

    For each day (batch_date), this function calculates:
    - batch_date: ISO date string (YYYY-MM-DD).
    - row_count: Total records observed for that day.
    - null_rate: Total missing cells across all columns divided by total cells (rows * cols).
    - Optional per-column null rates for columns specified in null_rate_columns:
      f"{col}_null_rate" = missing cells in that column / row_count.
    - Target mean and sample std (ddof=1) for target_column (e.g. cnt_mean, cnt_std):
      For single-row batches (N=1) or batches with exactly one valid target observation,
      within-batch variance is zero, so target_std is set to 0.0. If all target values
      in a batch are missing, both mean and std evaluate to np.nan.
    - Cardinality metrics for each column in cardinality_columns:
      f"{col}_cardinality" = distinct count of non-null values.

    Parameters
    ----------
    df : pd.DataFrame | str | Path
        Input DataFrame or path to CSV file containing observations.
    required_columns : Sequence[str] | None, optional
        Explicit columns required for metric computation. If None, automatically
        derived from date_column, target_column, cardinality_columns, and null_rate_columns.
    date_column : str, default "dteday"
        Column containing dates for daily grouping.
    target_column : str, default "cnt"
        Numeric target column for mean and standard deviation metrics.
    cardinality_columns : Sequence[str], default ("season", "weathersit")
        Columns for distinct non-null cardinality counts.
    null_rate_columns : Sequence[str] | None, optional
        Specific column names to calculate individual null rates for. If None,
        only the aggregate null_rate is included, preserving the default 7-column schema.

    Returns
    -------
    pd.DataFrame
        DataFrame with rows sorted chronologically by batch_date and columns
        containing calculated quality metrics.

    Raises
    ------
    ValueError
        If required columns or requested null_rate_columns are missing,
        or if unparseable/invalid dates are found in date_column.
    """
    if isinstance(df, (str, Path)):
        df = pd.read_csv(df)

    # Determine required columns
    if required_columns is not None:
        needed_cols = list(required_columns)
    else:
        needed_cols = list(
            dict.fromkeys(
                [
                    date_column,
                    target_column,
                    *cardinality_columns,
                ]
            )
        )

    # Validate required columns
    missing_cols = [col for col in needed_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Missing required column(s) for metric computation: {missing_cols}"
        )

    # Validate requested null_rate_columns
    if null_rate_columns is not None:
        missing_null_cols = [col for col in null_rate_columns if col not in df.columns]
        if missing_null_cols:
            raise ValueError(
                f"Requested null_rate column(s) not found in DataFrame: {missing_null_cols}"
            )

    # Define target mean and std column names
    target_mean_key = "cnt_mean" if target_column == "cnt" else f"{target_column}_mean"
    target_std_key = "cnt_std" if target_column == "cnt" else f"{target_column}_std"

    # Assemble expected output columns
    expected_cols = ["batch_date", "row_count", "null_rate"]
    if null_rate_columns:
        expected_cols.extend([f"{col}_null_rate" for col in null_rate_columns])
    expected_cols.extend([target_mean_key, target_std_key])
    expected_cols.extend([f"{col}_cardinality" for col in cardinality_columns])

    # Handle empty input DataFrame explicitly
    if df.empty:
        # Preserve exact METRIC_COLUMNS tuple when defaults are active
        if (
            null_rate_columns is None
            and target_column == "cnt"
            and list(cardinality_columns) == ["season", "weathersit"]
        ):
            return pd.DataFrame(columns=list(METRIC_COLUMNS))
        return pd.DataFrame(columns=expected_cols)

    # Validate timestamp parsing without mutating input DataFrame
    parsed_dates = pd.to_datetime(df[date_column], errors="coerce")
    if parsed_dates.isna().any():
        invalid_mask = parsed_dates.isna()
        invalid_indices = df.index[invalid_mask].tolist()
        invalid_sample = df.loc[invalid_mask, date_column].head(3).tolist()
        raise ValueError(
            f"Invalid or unparseable dates encountered in '{date_column}' at index/indices "
            f"{invalid_indices[:5]} (samples: {invalid_sample})"
        )

    # Format date as YYYY-MM-DD string for clean daily batch grouping
    date_series = parsed_dates.dt.strftime("%Y-%m-%d")

    records: list[dict[str, object]] = []

    # Group by formatted date string
    for batch_date, group in df.groupby(date_series, sort=True):
        n_rows = len(group)
        n_cols = len(group.columns)
        total_cells = n_rows * n_cols

        # Aggregate null rate across all cells in this day's batch
        missing_cells = int(group.isna().sum().sum())
        null_rate = float(missing_cells / total_cells) if total_cells > 0 else 0.0

        rec: dict[str, object] = {
            "batch_date": str(batch_date),
            "row_count": int(n_rows),
            "null_rate": null_rate,
        }

        # Optional per-column null rates
        if null_rate_columns:
            for col in null_rate_columns:
                col_missing = int(group[col].isna().sum())
                rec[f"{col}_null_rate"] = (
                    float(col_missing / n_rows) if n_rows > 0 else 0.0
                )

        # Target statistics
        valid_target = group[target_column].dropna()
        if len(valid_target) == 0:
            t_mean = float("nan")
            t_std = float("nan")
        elif len(valid_target) == 1:
            t_mean = float(valid_target.iloc[0])
            # Single-row batch handling: within-batch dispersion is 0.0
            t_std = 0.0
        else:
            t_mean = float(valid_target.mean())
            t_std = float(valid_target.std(ddof=1))

        rec[target_mean_key] = t_mean
        rec[target_std_key] = t_std

        # Cardinality metrics (non-null distinct counts)
        for col in cardinality_columns:
            rec[f"{col}_cardinality"] = int(group[col].dropna().nunique())

        records.append(rec)

    result_df = pd.DataFrame(records, columns=expected_cols)
    return result_df.sort_values("batch_date").reset_index(drop=True)


# Alias for flexible naming conventions
calculate_daily_quality_metrics = compute_daily_quality_metrics


def main(args: Sequence[str] | None = None) -> None:
    """CLI entry point to calculate daily quality metrics and persist output."""
    repo_root = Path(__file__).resolve().parents[2]
    default_input = repo_root / "data" / "raw" / "hour.csv"
    if not default_input.exists():
        default_input = Path("data/raw/hour.csv")

    default_output = repo_root / "results" / "raw" / "daily_quality_metrics.csv"
    if not default_output.parent.exists():
        default_output = Path("results/raw/daily_quality_metrics.csv")

    parser = argparse.ArgumentParser(
        description="Compute daily data pipeline quality-metric observations."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=default_input,
        help="Path to input CSV dataset (raw or drift-injected).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=default_output,
        help="Path to save output daily metrics CSV.",
    )
    parser.add_argument(
        "--null-columns",
        "-n",
        nargs="*",
        default=None,
        help="Specific columns to compute individual null rates for.",
    )
    parser.add_argument(
        "--date-column",
        "-d",
        type=str,
        default="dteday",
        help="Column name containing batch dates.",
    )
    parser.add_argument(
        "--target-column",
        "-t",
        type=str,
        default="cnt",
        help="Target numeric column for mean and std statistics.",
    )
    parser.add_argument(
        "--cardinality-columns",
        "-c",
        nargs="*",
        default=["season", "weathersit"],
        help="Columns to compute distinct cardinality counts for.",
    )

    parsed_args = parser.parse_args(args)

    input_path: Path = parsed_args.input
    output_path: Path = parsed_args.output

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading dataset from: {input_path}")
    df = pd.read_csv(input_path)

    print("Computing daily quality-metric observations...")
    metrics_df = compute_daily_quality_metrics(
        df=df,
        date_column=parsed_args.date_column,
        target_column=parsed_args.target_column,
        cardinality_columns=parsed_args.cardinality_columns,
        null_rate_columns=parsed_args.null_columns,
    )

    metrics_df.to_csv(output_path, index=False)
    print(f"Saved daily metrics to: {output_path}")

    # Display summary statistics
    target_mean_key = (
        "cnt_mean"
        if parsed_args.target_column == "cnt"
        else f"{parsed_args.target_column}_mean"
    )
    target_std_key = (
        "cnt_std"
        if parsed_args.target_column == "cnt"
        else f"{parsed_args.target_column}_std"
    )

    print("\nSummary of Generated Observations:")
    print("=" * 50)
    print(f"  Total daily batches   : {len(metrics_df)}")
    if not metrics_df.empty:
        print(f"  Date range            : {metrics_df['batch_date'].min()} to {metrics_df['batch_date'].max()}")
        print(f"  Mean row count/day    : {metrics_df['row_count'].mean():.2f}")
        print(f"  Min / Max row count   : {metrics_df['row_count'].min()} / {metrics_df['row_count'].max()}")
        print(f"  Overall null rate     : {metrics_df['null_rate'].mean():.6f}")

        if parsed_args.null_columns:
            for col in parsed_args.null_columns:
                null_col_key = f"{col}_null_rate"
                if null_col_key in metrics_df.columns:
                    print(f"  Mean {null_col_key:<17}: {metrics_df[null_col_key].mean():.6f}")

        if target_mean_key in metrics_df.columns:
            print(f"  Mean {target_mean_key:<17}: {metrics_df[target_mean_key].mean():.2f}")
        if target_std_key in metrics_df.columns:
            print(f"  Mean {target_std_key:<17}: {metrics_df[target_std_key].mean():.2f}")
        print(f"  Single-row days (N=1) : {(metrics_df['row_count'] == 1).sum()}")
    print("=" * 50)


if __name__ == "__main__":
    main()
