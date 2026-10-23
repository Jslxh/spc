"""Great Expectations (GX) threshold-monitoring baseline module.

This module provides declarative threshold validation for data pipeline quality metrics
using genuine Great Expectations 1.x expectations and validation results.

Methodological Specifications:
------------------------------
1. Static Threshold Baseline:
   Evaluates business/SLA thresholds on daily quality-metric batches (e.g. row_count,
   temp_null_rate, cnt_mean) to serve as a threshold-based comparator against statistical
   process control (Shewhart Individuals and tabular CUSUM).

2. Declarative Separation:
   Threshold specifications (columns, bounds, strictness, null policies, rationales)
   are managed in structured configuration objects and JSON suites separate from implementation.

3. Genuine GX Execution:
   Uses Great Expectations 1.x fluent Data Sources, Data Assets, Batch Definitions,
   Expectation Suites, and programmatic Validation Results (ExpectColumnValuesToBeBetween,
   ExpectColumnValuesToNotBeNull, ExpectTableRowCountToBeBetween).

4. Explicit Missing-Value & Alert Policies:
   Missing (NaN) observations are not silently ignored; unless allow_null=True is explicitly
   configured, nulls trigger an alert with violation_type="missing_value".
   Individual expectation results are distinguished from the overall date-level alert decision.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Sequence
import numpy as np
import pandas as pd

from src.spc.control_charts import _validate_date_window

try:
    import great_expectations as gx
    import great_expectations.expectations as gxe
    GX_AVAILABLE = True
except ImportError:
    GX_AVAILABLE = False
    gx = None  # type: ignore
    gxe = None  # type: ignore


def is_gx_available() -> bool:
    """Check if Great Expectations is installed and available in the current environment."""
    return GX_AVAILABLE


@dataclass(frozen=True)
class GXMetricThreshold:
    """Specification of threshold bounds and validation rules for a single metric column.

    Attributes
    ----------
    column : str
        Name of the DataFrame column to monitor (e.g. 'cnt_mean', 'temp_null_rate', 'row_count').
    min_value : float | None
        Lower bound threshold (inclusive by default). None indicates no lower bound.
    max_value : float | None
        Upper bound threshold (inclusive by default). None indicates no upper bound.
    strict_min : bool, default False
        If True, requires value > min_value (exclusive). If False, requires value >= min_value.
    strict_max : bool, default False
        If True, requires value < max_value (exclusive). If False, requires value <= max_value.
    allow_null : bool, default False
        If False (default), missing (NaN) values fail validation and raise an alert.
    rationale : str, default ""
        Documented operational or statistical rationale for this threshold.
    """

    column: str
    min_value: float | None = None
    max_value: float | None = None
    strict_min: bool = False
    strict_max: bool = False
    allow_null: bool = False
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert threshold to serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class GXMonitoringConfig:
    """Configuration suite for multi-metric threshold monitoring.

    Attributes
    ----------
    suite_name : str
        Name identifier for the Great Expectations suite.
    thresholds : tuple[GXMetricThreshold, ...]
        Collection of metric threshold rules to evaluate.
    date_column : str, default "batch_date"
        Column containing batch dates.
    monitoring_start : str, default "2012-01-01"
        Start date for monitoring window (YYYY-MM-DD).
    monitoring_end : str, default "2012-12-31"
        End date for monitoring window (YYYY-MM-DD).
    description : str, default ""
        Human-readable summary of the monitoring suite purpose.
    """

    suite_name: str
    thresholds: tuple[GXMetricThreshold, ...]
    date_column: str = "batch_date"
    monitoring_start: str = "2012-01-01"
    monitoring_end: str = "2012-12-31"
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GXMonitoringConfig:
        """Construct configuration from dictionary."""
        thresholds = tuple(
            GXMetricThreshold(
                column=t["column"],
                min_value=t.get("min_value"),
                max_value=t.get("max_value"),
                strict_min=bool(t.get("strict_min", False)),
                strict_max=bool(t.get("strict_max", False)),
                allow_null=bool(t.get("allow_null", False)),
                rationale=str(t.get("rationale", "")),
            )
            for t in data.get("thresholds", [])
        )
        return cls(
            suite_name=data.get("suite_name", "gx_threshold_suite"),
            thresholds=thresholds,
            date_column=data.get("date_column", "batch_date"),
            monitoring_start=data.get("monitoring_start", "2012-01-01"),
            monitoring_end=data.get("monitoring_end", "2012-12-31"),
            description=data.get("description", ""),
        )

    @classmethod
    def from_json(cls, json_path: str | Path) -> GXMonitoringConfig:
        """Load configuration from a JSON file."""
        path = Path(json_path)
        if not path.is_file():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_json(self, json_path: str | Path) -> None:
        """Save configuration to a JSON file."""
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "suite_name": self.suite_name,
            "description": self.description,
            "date_column": self.date_column,
            "monitoring_start": self.monitoring_start,
            "monitoring_end": self.monitoring_end,
            "thresholds": [t.to_dict() for t in self.thresholds],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


@dataclass
class GXMonitoringResult:
    """Outcome of prospective Great Expectations threshold monitoring.

    Attributes
    ----------
    suite_name : str
        Name of the evaluated expectation suite.
    records_df : pd.DataFrame
        Daily summary DataFrame with 1 row per batch_date, containing alert status,
        counts, and combined alert reasons.
    detailed_records_df : pd.DataFrame
        Detailed DataFrame with 1 row per (batch_date, metric_column) evaluation,
        containing observed values, bounds, unexpected counts, and failure details.
    total_batches : int
        Number of daily batches evaluated.
    alert_batches : int
        Number of batches where at least one threshold was violated or missing.
    clean_batches : int
        Number of batches where all expectations passed.
    first_alert_date : str | None
        Date of the first alert, or None if all batches passed.
    config : GXMonitoringConfig
        Configuration suite used for monitoring.
    raw_validation_results : list[Any]
        Raw Great Expectations ExpectationSuiteValidationResult objects per batch.
    """

    suite_name: str
    records_df: pd.DataFrame
    detailed_records_df: pd.DataFrame
    total_batches: int
    alert_batches: int
    clean_batches: int
    first_alert_date: str | None
    config: GXMonitoringConfig
    raw_validation_results: list[Any] = field(default_factory=list)


def build_gx_suite(context: Any, config: GXMonitoringConfig) -> Any:
    """Construct a Great Expectations 1.x ExpectationSuite from a monitoring configuration.

    Parameters
    ----------
    context : gx.DataContext
        Active Great Expectations data context.
    config : GXMonitoringConfig
        Monitoring configuration defining threshold rules.

    Returns
    -------
    gx.ExpectationSuite
        Populated expectation suite.
    """
    if not GX_AVAILABLE:
        raise ImportError(
            "Great Expectations is not installed. To build expectation suites, "
            "run within the isolated Python 3.12 Docker environment."
        )

    suite = context.suites.add(gx.ExpectationSuite(name=config.suite_name))

    for rule in config.thresholds:
        # Non-null expectation
        if not rule.allow_null:
            suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=rule.column))

        # Range expectation if at least one bound is specified
        if rule.min_value is not None or rule.max_value is not None:
            suite.add_expectation(
                gxe.ExpectColumnValuesToBeBetween(
                    column=rule.column,
                    min_value=rule.min_value,
                    max_value=rule.max_value,
                    strict_min=rule.strict_min,
                    strict_max=rule.strict_max,
                )
            )

    return suite


def run_gx_monitoring(
    df: pd.DataFrame | str | Path,
    config: GXMonitoringConfig,
    output_dir: str | Path | None = None,
) -> GXMonitoringResult:
    """Execute prospective Great Expectations threshold monitoring over daily batches.

    Parameters
    ----------
    df : pd.DataFrame | str | Path
        Input DataFrame or path containing daily quality metrics.
    config : GXMonitoringConfig
        Monitoring configuration defining thresholds, dates, and columns.
    output_dir : str | Path | None, optional
        Directory to save machine-readable CSV and JSON validation artifacts.

    Returns
    -------
    GXMonitoringResult
        Structured results with per-date summaries and detailed expectation traces.

    Raises
    ------
    ImportError
        If great_expectations is not installed.
    ValueError
        If input columns, date ranges, or configurations are invalid.
    """
    if not GX_AVAILABLE:
        raise ImportError(
            "Great Expectations is not installed in the current Python environment. "
            "To execute genuine Great Expectations monitoring, run using the isolated "
            "Python 3.12 Docker environment (see requirements-gx.txt and documentation)."
        )

    if isinstance(df, (str, Path)):
        df = pd.read_csv(df)

    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df)}")

    # Validate that monitored columns exist in the DataFrame
    required_cols = [rule.column for rule in config.thresholds]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Monitored column(s) not found in DataFrame: {missing_cols}"
        )

    # Filter and validate date window
    window_df, start_ts, end_ts = _validate_date_window(
        df=df,
        date_column=config.date_column,
        start_date=config.monitoring_start,
        end_date=config.monitoring_end,
        phase_name="GX threshold monitoring",
    )

    # Initialize Great Expectations ephemeral context and suite
    context = gx.get_context(mode="ephemeral")
    suite = build_gx_suite(context, config)

    # Set up fluent Pandas data source, asset, and batch definition
    source = context.data_sources.add_pandas("gx_ephemeral_pandas_source")
    asset = source.add_dataframe_asset("gx_daily_batch_asset")
    bdef = asset.add_batch_definition_whole_dataframe("gx_daily_batch_def")

    daily_summary_records: list[dict[str, Any]] = []
    detailed_records: list[dict[str, Any]] = []
    raw_results: list[Any] = []

    total_batches = len(window_df)
    alert_batches = 0
    first_alert_date: str | None = None

    for _, row in window_df.iterrows():
        b_date = row["_parsed_date"].strftime("%Y-%m-%d")
        batch_df = pd.DataFrame([row])

        # Execute genuine Great Expectations validation
        batch = bdef.get_batch(batch_parameters={"dataframe": batch_df})
        val_result = batch.validate(suite)
        raw_results.append(val_result)

        date_has_alert = False
        date_reasons: list[str] = []
        failed_exp_count = 0

        # Evaluate each expectation result programmatically
        for exp_res in val_result.results:
            exp_type = exp_res.expectation_config.type
            kwargs = exp_res.expectation_config.kwargs
            col = kwargs.get("column", "")
            success = bool(exp_res.success)
            res_dict = exp_res.result or {}

            # Find matching threshold rule
            matching_rules = [r for r in config.thresholds if r.column == col]
            rule = matching_rules[0] if matching_rules else None

            val = row.get(col)
            val_float = float(val) if pd.notna(val) else float("nan")

            unexpected_count = res_dict.get("unexpected_count", 0)

            # Determine specific violation reason
            if not success:
                failed_exp_count += 1
                date_has_alert = True

                if exp_type == "expect_column_values_to_not_be_null":
                    reason = f"missing_value: {col} is null"
                elif exp_type == "expect_column_values_to_be_between":
                    min_val = kwargs.get("min_value")
                    max_val = kwargs.get("max_value")
                    if pd.isna(val):
                        reason = f"missing_value: {col} is null"
                    elif min_val is not None and val_float < min_val:
                        reason = f"threshold_lower: {col}={val_float} < {min_val}"
                    elif max_val is not None and val_float > max_val:
                        reason = f"threshold_upper: {col}={val_float} > {max_val}"
                    else:
                        reason = f"threshold_violation: {col}={val_float}"
                else:
                    reason = f"expectation_failed: {exp_type} on {col}"

                date_reasons.append(reason)
            else:
                reason = "none"

            detailed_records.append(
                {
                    "batch_date": b_date,
                    "metric_name": col,
                    "expectation_type": exp_type,
                    "min_value": kwargs.get("min_value"),
                    "max_value": kwargs.get("max_value"),
                    "strict_min": kwargs.get("strict_min", False),
                    "strict_max": kwargs.get("strict_max", False),
                    "observed_value": val_float,
                    "passed": success,
                    "unexpected_count": unexpected_count,
                    "is_alert": not success,
                    "alert_reason": reason,
                }
            )

        if date_has_alert:
            alert_batches += 1
            if first_alert_date is None:
                first_alert_date = b_date

        combined_reason = "; ".join(date_reasons) if date_reasons else "none"

        daily_summary_records.append(
            {
                "batch_date": b_date,
                "is_alert": date_has_alert,
                "failed_expectations_count": failed_exp_count,
                "total_expectations_evaluated": len(val_result.results),
                "alert_reasons": combined_reason,
            }
        )

    records_df = pd.DataFrame(daily_summary_records)
    detailed_df = pd.DataFrame(detailed_records)

    result = GXMonitoringResult(
        suite_name=config.suite_name,
        records_df=records_df,
        detailed_records_df=detailed_df,
        total_batches=total_batches,
        alert_batches=alert_batches,
        clean_batches=total_batches - alert_batches,
        first_alert_date=first_alert_date,
        config=config,
        raw_validation_results=raw_results,
    )

    # Save artifacts if requested
    if output_dir is not None:
        save_gx_results(result, output_dir)

    return result


def save_gx_results(result: GXMonitoringResult, output_dir: str | Path) -> None:
    """Save Great Expectations monitoring summaries and traces to disk.

    Parameters
    ----------
    result : GXMonitoringResult
        Monitoring result to save.
    output_dir : str | Path
        Directory to write CSV and JSON summary artifacts.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Daily summary CSV (1 row per batch_date)
    records_csv = out_path / "gx_monitoring_daily_summary.csv"
    result.records_df.to_csv(records_csv, index=False)

    # 2. Detailed expectation evaluations CSV (1 row per batch_date x expectation)
    detailed_csv = out_path / "gx_monitoring_detailed_records.csv"
    result.detailed_records_df.to_csv(detailed_csv, index=False)

    # 3. JSON summary metadata
    summary_json = out_path / "gx_monitoring_summary.json"
    summary_data = {
        "suite_name": result.suite_name,
        "total_batches": result.total_batches,
        "alert_batches": result.alert_batches,
        "clean_batches": result.clean_batches,
        "first_alert_date": result.first_alert_date,
        "monitoring_start": result.config.monitoring_start,
        "monitoring_end": result.config.monitoring_end,
        "monitored_metrics": [t.column for t in result.config.thresholds],
    }
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

