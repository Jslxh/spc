"""Dataset validation module for raw data quality inspection.

This module provides baseline schema validation and data quality metrics
calculation for datasets in the Statistical Process Control (SPC) data pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence
import pandas as pd

EXPECTED_HOURLY_COLUMNS: tuple[str, ...] = (
    "instant",
    "dteday",
    "season",
    "yr",
    "mnth",
    "hr",
    "holiday",
    "weekday",
    "workingday",
    "weathersit",
    "temp",
    "atemp",
    "hum",
    "windspeed",
    "casual",
    "registered",
    "cnt",
)


def inspect_dataset(
    csv_path: str | Path,
    expected_columns: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Inspect a CSV dataset for schema conformity and baseline quality metrics.

    Parameters
    ----------
    csv_path : str | Path
        Path to the CSV file to inspect.
    expected_columns : Sequence[str] | None, optional
        Collection of required column names. If None, defaults to
        EXPECTED_HOURLY_COLUMNS.

    Returns
    -------
    dict[str, Any]
        Dictionary containing quality metrics:
        - file_name: Name of the inspected file
        - row_count: Number of rows in dataset
        - column_count: Number of columns in dataset
        - total_missing_cells: Sum of null cells across all columns
        - duplicate_rows: Count of completely duplicate rows
        - duplicate_instant_identifiers: Count of duplicate 'instant' IDs
        - invalid_timestamps: Count of invalid or unparseable timestamps in 'dteday'
        - earliest_date: Minimum valid date string (YYYY-MM-DD) or None
        - latest_date: Maximum valid date string (YYYY-MM-DD) or None

    Raises
    ------
    FileNotFoundError
        If the specified csv_path does not exist or is not a file.
    ValueError
        If required columns are missing or unexpected columns are present.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    if expected_columns is None:
        expected = list(EXPECTED_HOURLY_COLUMNS)
    else:
        expected = list(expected_columns)

    df = pd.read_csv(path)

    # Validate schema: check for missing required columns and unexpected columns
    missing_cols = [col for col in expected if col not in df.columns]
    unexpected_cols = [col for col in df.columns if col not in expected]

    if missing_cols or unexpected_cols:
        error_msgs: list[str] = []
        if missing_cols:
            error_msgs.append(f"Missing required column(s): {missing_cols}")
        if unexpected_cols:
            error_msgs.append(f"Unexpected column(s): {unexpected_cols}")
        raise ValueError(f"Schema mismatch for '{path.name}': {'; '.join(error_msgs)}")

    # Calculate metrics
    row_count = int(len(df))
    column_count = int(len(df.columns))
    total_missing_cells = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())

    duplicate_instant_identifiers = (
        int(df["instant"].duplicated().sum()) if "instant" in df.columns else 0
    )

    if "dteday" in df.columns:
        parsed_dates = pd.to_datetime(df["dteday"], errors="coerce")
        invalid_timestamps = int(parsed_dates.isna().sum())
        valid_dates = parsed_dates.dropna()
        earliest_date = (
            str(valid_dates.min().date()) if not valid_dates.empty else None
        )
        latest_date = (
            str(valid_dates.max().date()) if not valid_dates.empty else None
        )
    else:
        invalid_timestamps = 0
        earliest_date = None
        latest_date = None

    return {
        "file_name": path.name,
        "row_count": row_count,
        "column_count": column_count,
        "total_missing_cells": total_missing_cells,
        "duplicate_rows": duplicate_rows,
        "duplicate_instant_identifiers": duplicate_instant_identifiers,
        "invalid_timestamps": invalid_timestamps,
        "earliest_date": earliest_date,
        "latest_date": latest_date,
    }


def main() -> None:
    """Entry point to inspect default hourly dataset and print metrics."""
    default_path = Path("data/raw/hour.csv")
    if not default_path.exists():
        repo_root = Path(__file__).resolve().parents[2]
        default_path = repo_root / "data" / "raw" / "hour.csv"

    print(f"Inspecting dataset: {default_path}")
    results = inspect_dataset(default_path)

    print("\nDataset Validation Report:")
    print("=" * 35)
    for key, value in results.items():
        print(f"  {key:<30}: {value}")
    print("=" * 35)


if __name__ == "__main__":
    main()

