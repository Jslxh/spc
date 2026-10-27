# Early Detection of Data Pipeline Quality Degradation Using Statistical Process Control

## Project Overview

This project investigates the early detection of data pipeline quality degradation by comparing declarative threshold-based data validation against classical and sequential statistical process control (SPC) methods.

The evaluation compares three monitoring paradigms:
1. **Threshold-Based Pipeline Monitoring**: Declarative single-batch assertions using [Great Expectations](https://greatexpectations.io/) (v1.24.0).
2. **Shewhart Control Charts**: Memoryless statistical process control utilizing Shewhart individuals ($X/MR$) charts with moving-range dispersion for continuous metrics, and attribute $p$-charts for proportion/defect metrics.
3. **Sequential CUSUM Monitoring**: Standardized two-sided tabular cumulative sum control charts ($C^+, C^-$) with persistent history tracking (`reset_policy="none"`).

The primary objective is to evaluate how these monitoring approaches behave under controlled synthetic quality degradation (abrupt distribution shifts and gradual missing-data drift) while rigorously measuring false alarm rates under natural unadjusted seasonal variation.

> **Project Status**: Phase I baseline calibration, Phase II drift experiments, unified comparative evaluations, and publication outputs (tables, figures, and research paper drafts) are complete and audited.

---

## Research Questions & Scope

1. **Threshold Equivalence**: How does single-batch declarative validation (Great Expectations) compare mathematically and empirically to memoryless Shewhart control charts when both use matching three-sigma control limits?
2. **Sequential Memory vs. Macro Seasonality**: Can sequential CUSUM detect small sustained shifts faster than Shewhart charts in data pipeline volume metrics, or does natural seasonal variation cause accumulator saturation and false alarm cascades?
3. **Zero-Defect Baseline Telemetry**: How do attribute control charts and static SLA limits perform on clean pipeline invariants (such as zero missing values) where baseline variance is zero ($\sigma_0 = 0$)?
4. **Alert Semantics in Pipeline Observability**: What are the operational differences between point-in-time *daily alarm states*, rising-edge *threshold crossings*, and *event-level incident detections*?

---

## Dataset & Synthetic Drift Scenarios

Experiments are conducted on the public **Bike Sharing Dataset** (Capital Bikeshare system, Washington D.C., 2011–2012; Fanaee-T and Gama, 2013), provided in [`data/raw/`](file:///home/jslxh/PROJETCS/spc/data/raw/):
- **Phase I Calibration Baseline**: Calendar year 2011 (365 daily batches, 2011-01-01 to 2011-12-31).
- **Phase II Monitoring Evaluation**: Calendar year 2012 (366 daily batches, 2012-01-01 to 2012-12-31).

### Injected Drift Scenarios

Deterministic degradation was injected into Phase II data using [`src/spc/drift_injection.py`](file:///home/jslxh/PROJETCS/spc/src/spc/drift_injection.py), producing ground-truth metadata in [`data/processed/drift/`](file:///home/jslxh/PROJETCS/spc/data/processed/drift/):

1. **Abrupt Distribution Shift (`abrupt_shift_cnt`)**:
   - **Target Metric**: Daily mean ridership (`cnt_mean`).
   - **Drift Type**: Constant additive shift of $+75.0$ riders/hour injected into hourly `cnt`.
   - **Timing**: Configured onset `2012-07-01` through `2012-12-31` (184 post-onset batches, 182 defect-free pre-window batches, 4,376 rows affected, random seed 42).
   - **Artifact**: [`data/processed/drift/ground_truth_abrupt_shift_cnt.json`](file:///home/jslxh/PROJETCS/spc/data/processed/drift/ground_truth_abrupt_shift_cnt.json).
2. **Gradual Missing-Data Drift (`gradual_null_temp`)**:
   - **Target Metric**: Daily missingness proportion in temperature telemetry (`temp_null_rate`).
   - **Drift Type**: Linear ramp in defect probability ($0.0 \to 0.40$) injected into hourly `temp` via Bernoulli draws.
   - **Timing**: Configured schedule start `2012-06-01` through `2012-12-31` (214 window batches, 1,033 null cells, random seed 42).
   - **Realized Onset**: Because daily batches contain discrete integer rows ($N \approx 24$ rows/day), the first 9 days (June 1–9) realized zero missing cells. The first defective batch materialized on **`2012-06-10`** (1 missing cell, null rate $4.17\% > 1.0\%$ SLA; 205 post-onset batches, 161 defect-free pre-window batches).
   - **Artifact**: [`data/processed/drift/ground_truth_gradual_null_temp.json`](file:///home/jslxh/PROJETCS/spc/data/processed/drift/ground_truth_gradual_null_temp.json).

---

## Architecture & Implemented Modules

```text
Raw Dataset (hourly/daily CSV)
   ↓
[src/spc/quality_metrics.py]  → Aggregates daily batches (row count, temp_null_rate, cnt_mean, cnt_std)
   ↓
[src/spc/drift_injection.py]   → Injects synthetic drift & outputs authoritative ground-truth JSON
   ↓
┌────────────────────────────────────────────────────────────────────────┐
│ Monitoring Paradigms (Phase II Daily Batches)                          │
│                                                                        │
│ 1. [src/spc/gx_monitor.py]      → Great Expectations v1.24.0 suites    │
│ 2. [src/spc/control_charts.py]  → Shewhart X/MR & attribute p-charts   │
│ 3. [src/spc/cusum.py]           → Standardized two-sided tabular CUSUM │
└────────────────────────────────────────────────────────────────────────┘
   ↓
[src/spc/evaluation.py]        → Unified evaluation, episode resolution, contingency matrices
   ↓
[scripts/generate_publication_outputs.py] → Generates 300 DPI figures & publication tables
```

### Core Source Components (`src/spc/`)
- [`quality_metrics.py`](file:///home/jslxh/PROJETCS/spc/src/spc/quality_metrics.py): Daily aggregation engine converting hourly sensor data into daily quality batches.
- [`control_charts.py`](file:///home/jslxh/PROJETCS/spc/src/spc/control_charts.py): Calibrates Shewhart individuals ($X/MR$) charts using moving-range dispersion ($\sigma_0 = \bar{MR}/1.128$) and attribute $p$-charts.
- [`cusum.py`](file:///home/jslxh/PROJETCS/spc/src/spc/cusum.py): Implements standardized tabular CUSUM ($C^+_t, C^-_t$) with allowance $k = 0.5$ and decision interval $h = 5.0$.
- [`gx_monitor.py`](file:///home/jslxh/PROJETCS/spc/src/spc/gx_monitor.py): Programmatic interface to Great Expectations 1.24.0 executing declarative validation suites.
- [`drift_injection.py`](file:///home/jslxh/PROJETCS/spc/src/spc/drift_injection.py): Injects step and ramp degradation, recording exact ground-truth outcome metadata.
- [`evaluation.py`](file:///home/jslxh/PROJETCS/spc/src/spc/evaluation.py): Aligns multi-method daily alert series, resolves contiguous alarm episodes, and computes classification metrics.
- [`data_validation.py`](file:///home/jslxh/PROJETCS/spc/src/spc/data_validation.py): Lightweight schema validation and constraint checking.

*Note on Orchestration*: Early planning documents referenced Apache Airflow. Airflow was intentionally excluded from the final implementation to keep experiments lightweight, reproducible, and isolated without heavy daemon dependencies.

---

## Environment Requirements & Dual-Runtime Setup

Because Great Expectations 1.x currently requires Python $\le 3.12$, while modern Linux environments (such as Arch/EndeavourOS) run Python 3.14+, the project utilizes a dual-environment architecture:

1. **Host Environment (Python 3.14)**:
   - Contains `pandas`, `numpy`, and `scipy`.
   - Executes core statistical modules (`control_charts.py`, `cusum.py`, `quality_metrics.py`, `drift_injection.py`, `evaluation.py`).
   - Automated tests run via standard `unittest`. Tests requiring Great Expectations or matplotlib gracefully skip when those libraries are absent.
2. **Isolated Python 3.12 Container Runtime**:
   - Uses containerized Python 3.12 (`public.ecr.aws/lambda/python:3.12` or standard `python:3.12-slim`).
   - Installs pinned dependencies from [`requirements-gx.txt`](file:///home/jslxh/PROJETCS/spc/requirements-gx.txt) (`great_expectations==1.24.0`, `pandas==3.1.0`, `numpy==2.5.4`) along with `matplotlib` for figure rendering.
   - Executes the Great Expectations baseline and the complete 78-test suite with 100% test pass rate.

*Note on Container Runtime*: The verified container workflow runs directly via the `docker run` commands documented below using `public.ecr.aws/lambda/python:3.12` (or standard `python:3.12-slim`).

---

## Verified Execution Commands

### 1. Run Automated Unit Tests

**On Host (Python 3.14 virtual environment)**:
```bash
.venv/bin/python -m unittest discover -s tests -p "test_*.py"
```
*(Expected: 82 tests ran — 74 passed, 8 skipped due to environment boundaries).*

**In Isolated Python 3.12 Container**:
```bash
# Setup persistent isolated virtualenv in host /tmp (one-time setup)
docker run --rm -v /tmp/spc-gx-test:/env --entrypoint python public.ecr.aws/lambda/python:3.12 -m venv /env/venv
docker run --rm -v $(pwd):/workspace -v /tmp/spc-gx-test:/env --entrypoint /env/venv/bin/pip public.ecr.aws/lambda/python:3.12 install -r /workspace/requirements-gx.txt matplotlib

# Run full test suite
docker run --rm -e PYTHONPATH=/workspace -v $(pwd):/workspace -v /tmp/spc-gx-test/venv:/env/venv -w /workspace --entrypoint /env/venv/bin/python public.ecr.aws/lambda/python:3.12 -m unittest discover -s tests -p "test_*.py"
```
*(Expected: 82 tests ran — 82 passed, 0 skipped, 100% passing).*

---

### 2. End-to-End Pipeline Reproduction (Single-Command)

Execute all pipeline stages in dependency order (synthetic drift injection, daily quality metrics aggregation, Great Expectations Phase II baseline, Shewhart and $p$-chart calibration and monitoring, CUSUM and unified evaluation, and publication tables/figures):

**In Isolated Python 3.12 Container (Full Reproduction)**:
```bash
docker run --rm -e PYTHONPATH=/workspace -v $(pwd):/workspace -v /tmp/spc-gx-test/venv:/env/venv -w /workspace --entrypoint /env/venv/bin/python public.ecr.aws/lambda/python:3.12 scripts/reproduce_pipeline.py
```

**On Host (Statistical & Classical SPC Reproduction; skips GX)**:
```bash
.venv/bin/python scripts/reproduce_pipeline.py --skip-gx
```

---

### 3. Regenerate Shewhart and p-Chart Monitoring Series
```bash
.venv/bin/python -m src.spc.control_charts
```
Calibrates Phase I baselines and generates [`results/processed/monitoring_shewhart_cnt_mean.csv`](file:///home/jslxh/PROJETCS/spc/results/processed/monitoring_shewhart_cnt_mean.csv) and [`results/processed/monitoring_p_chart_temp_null_rate.csv`](file:///home/jslxh/PROJETCS/spc/results/processed/monitoring_p_chart_temp_null_rate.csv).

---

### 4. Execute Great Expectations Phase II Baseline
```bash
docker run --rm -e PYTHONPATH=/workspace -v $(pwd):/workspace -v /tmp/spc-gx-test/venv:/env/venv -w /workspace --entrypoint /env/venv/bin/python public.ecr.aws/lambda/python:3.12 scripts/run_gx_baseline.py
```
Outputs execution logs, daily summaries, detailed assertion records, and `evaluation_summary.json` into [`results/raw/gx/`](file:///home/jslxh/PROJETCS/spc/results/raw/gx/).

---

### 5. Run Unified Comparative Evaluation
```bash
.venv/bin/python -m src.spc.evaluation
```
Generates master aligned alerts [`results/processed/comparative_daily_alerts.csv`](file:///home/jslxh/PROJETCS/spc/results/processed/comparative_daily_alerts.csv) and [`results/tables/comparative_metrics.csv`](file:///home/jslxh/PROJETCS/spc/results/tables/comparative_metrics.csv).

---

### 6. Generate Publication Figures and Tables (300 DPI)
```bash
docker run --rm -e PYTHONPATH=/workspace -v $(pwd):/workspace -v /tmp/spc-gx-test/venv:/env/venv -w /workspace --entrypoint /env/venv/bin/python public.ecr.aws/lambda/python:3.12 scripts/generate_publication_outputs.py
```
Produces all 4 publication figures in [`results/figures/`](file:///home/jslxh/PROJETCS/spc/results/figures/) and all 4 publication tables in [`results/tables/`](file:///home/jslxh/PROJETCS/spc/results/tables/).

---

## Repository Structure

```text
spc/
├── configs/
│   └── gx_thresholds_daily_metrics.json    # Great Expectations threshold configuration
├── data/
│   ├── raw/                                # UCI Bike Sharing source datasets (day.csv, hour.csv)
│   └── processed/
│       └── drift/                          # Injected drift datasets & ground-truth JSON files
├── docs/
│   ├── evidence_manifest.sha256            # Authoritative SHA-256 checksums protecting all 44 scientific evidence artifacts
│   ├── final_results_audit.md              # Independent audit and verification report
│   └── results_and_discussion_draft.md     # Peer-reviewed research paper draft (versioned via Git)
├── results/
│   ├── figures/                            # 300 DPI publication plots (PNG)
│   │   ├── abrupt_shift_monitoring.png
│   │   ├── gradual_null_drift.png
│   │   ├── false_alarm_comparison.png
│   │   └── detection_timing.png
│   ├── tables/                             # Publication-ready CSV summary tables
│   │   ├── table_detection_performance.csv
│   │   ├── table_alarm_episodes.csv
│   │   ├── table_method_parameters.csv
│   │   ├── table_ground_truth_events.csv
│   │   └── comparative_metrics.csv
│   ├── processed/                          # Daily metrics & aligned monitoring time series
│   │   ├── comparative_daily_alerts.csv
│   │   ├── monitoring_shewhart_cnt_mean.csv
│   │   ├── monitoring_cusum_cnt_mean.csv
│   │   └── monitoring_p_chart_temp_null_rate.csv
│   └── raw/
│       ├── gx/                             # Raw Great Expectations 1.24.0 run outputs
│       └── evaluation/                     # Final publication audit JSON & runtime snapshots
├── scripts/
│   ├── reproduce_pipeline.py               # End-to-end orchestration runner (all stages in dependency order)
│   ├── run_gx_baseline.py                  # Standalone Great Expectations Phase II runner
│   └── generate_publication_outputs.py     # Publication figures and tables generator
├── src/
│   └── spc/                                # Core SPC and monitoring package
├── tests/                                  # 82 unit and integration tests
├── requirements-gx.txt                     # Pinned dependencies for isolated Python 3.12 runtime
├── README.md                               # Project documentation and reproduction guide
└── .gitignore
```

---

## Key Experimental Findings

1. **Threshold Equivalence Between GX and Shewhart**:
   When configured with static bounds derived from Phase I moving-range three-sigma limits ($[77.186, 208.683]$), Great Expectations and Shewhart Individuals charts produce **bitwise identical daily alert series** (100% agreement across all 366 Phase II batches).
2. **CUSUM Saturation Under Unmodeled Seasonality**:
   On continuous ridership (`cnt_mean`), warm-season volume increases systematically breached the static Phase I baseline ($\mu_0 = 142.93$). Under `reset_policy="none"`, positive residuals accumulated monotonically ($C^+ = 548.72$ on June 30). Upper CUSUM Episode 7 crossed $h = 5.0$ on `2012-03-07` and remained continuously active for **300 consecutive days** through year-end. Consequently, **zero new threshold crossings occurred on or after the July 1 shift injection**. The reported 100% recall is an artifact of pre-existing seasonal saturation, not event discrimination.
3. **Clean Attribute Monitoring on Zero-Defect Baseline**:
   Because the Phase I defect rate was zero, the implemented attribute $p$-chart uses a zero-defect limit ($\text{UCL} = 0.0$) and flags any non-zero observed defect rate, while Great Expectations enforces a 1% operational SLA ($\max = 0.01$). For daily batches of approximately 24 observations, a single defect corresponds to about $4.17\%$, exceeding the SLA; consequently, both methods produced identical alert classifications in this experiment (**0.0% pre-onset false alarm rate**, $0/161$ days, and real-time detection on `2012-06-10`, detection lag = 0.0 days, $F_1 = 0.967$). This equivalence is specific to the observed batch size and baseline, and does not imply identical control-limit formulations.
4. **Failure Propagation in Composite Validation Suites**:
   Production validation suites evaluate multiple assertions as a logical disjunction ($\text{Alert}_{\text{composite}} = \bigvee_i \text{Alert}_i$). Because seasonal volume on `cnt_mean` produced 105 false alarms, the composite suite suffered a **50.66%–52.80% pre-onset false alarm rate** on the telemetry scenario, masking clean sensor signals behind unrelated volume noise.

---

## Limitations & Reproducibility Statement

- **Experimental Scope**: All quantitative findings are derived from deterministic synthetic drift experiments injected into the 2011–2012 Capital Bikeshare dataset. Performance under real-world stochastic variance shifts or alternate seasonal structures may vary.
- **No Universal Superiority**: No single monitoring paradigm is universally superior. Declarative threshold validation and attribute control charts excel on zero-defect pipeline quality invariants, while sequential CUSUM requires explicit seasonal decomposition (or dynamic baselining) to prevent accumulator saturation on volume metrics.
- **Continuous CUSUM Limitation**: Standard continuous Gaussian CUSUM requires division by baseline standard deviation $\sigma_0$; it cannot be calibrated on clean zero-variance baselines ($\sigma_0 = 0.0$) without specialized discrete attribute formulations.
- **No Statistical Significance Claims**: Consistent with empirical benchmarking standards on deterministic synthetic drift runs, no p-values, hypothesis tests, or confidence intervals are claimed.
- **Evidence Integrity Verification**: All 44 genuine experimental evidence artifacts across `configs/`, `data/`, and `results/` are cryptographically verified via [`docs/evidence_manifest.sha256`](file:///home/jslxh/PROJETCS/spc/docs/evidence_manifest.sha256). The manifest strictly protects immutable scientific evidence; editable manuscript drafts in `docs/` are intentionally decoupled and versioned directly through Git history.
- **Audit Verification**: All reported values, tables, and figures have been audited and verified in [`results/raw/evaluation/final_publication_audit.json`](file:///home/jslxh/PROJETCS/spc/results/raw/evaluation/final_publication_audit.json).
