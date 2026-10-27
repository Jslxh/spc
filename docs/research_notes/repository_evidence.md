# Repository Evidence: Empirical Benchmarking and Implementation Settings

**Repository**: `/home/jslxh/PROJETCS/spc`  
**Baseline Commit**: `edd6295` (`feat: document reproducible monitoring workflow`)  
**Evidence Checksum Status**: 44/44 passed (`docs/evidence_manifest.sha256`)  
**Date**: October 2026  
**Document Purpose**: Internal research reference documenting the verified dataset attributes, monitoring configurations, drift injections, ground-truth evaluations, timing metrics, and environment reproduction commands preserved in this repository.

---

## 1. Dataset and Batching Specifications

### 1.1 Dataset Identification, Source, and Citation
- **Dataset Name**: Capital Bikeshare Hourly Ridership Dataset (Washington D.C. bike-sharing system).
- **Public Repository Source**: UCI Machine Learning Repository (`http://archive.ics.uci.edu/ml/datasets/Bike+Sharing+Dataset`).
- **Original Data Source**: Capital Bikeshare (`http://capitalbikeshare.com/system-data`).
- **Mandatory Academic Attribution**: Specified in repository license file [`data/raw/Readme.txt`](file:///home/jslxh/PROJETCS/spc/data/raw/Readme.txt) (lines 90–105):
  > Fanaee-T, Hadi, and Gama, Joao, "Event labeling combining ensemble detectors and background knowledge", *Progress in Artificial Intelligence*, 2(2-3):113–127, 2013. Springer Berlin Heidelberg. DOI: `10.1007/s13748-013-0040-3`.

### 1.2 Raw Files and Schema Structure
- **Primary Hourly Dataset**: [`data/raw/hour.csv`](file:///home/jslxh/PROJETCS/spc/data/raw/hour.csv)
  - Total records: **17,379 rows**, **17 columns**.
  - Missing values: **0 nulls** across all rows and columns.
  - Complete date range: `2011-01-01` to `2012-12-31` (731 consecutive calendar days).
  - Columns (17): `instant`, `dteday`, `season`, `yr`, `mnth`, `hr`, `holiday`, `weekday`, `workingday`, `weathersit`, `temp`, `atemp`, `hum`, `windspeed`, `casual`, `registered`, `cnt`.
- **Secondary Daily Dataset**: [`data/raw/day.csv`](file:///home/jslxh/PROJETCS/spc/data/raw/day.csv) (731 rows, 16 columns; used for reference verification).

### 1.3 Batch Construction and Operational Partitioning
- **Batching Method**: Natural daily operational batches partitioned by calendar date (`dteday`).
- **Hourly Records per Daily Batch**:
  - Minimum rows: 1 (e.g., partial weather sensor outages / system maintenance).
  - Maximum rows: 24 (complete 24-hour cycle).
  - Mean rows: 23.774.
  - Median rows: 24.
- **Phase I Baseline Period**:
  - Exact dates: `2011-01-01` through `2011-12-31`.
  - Batch count: **365 daily batches**.
  - Row count: **8,645 hourly observations**.
  - Operational role: Clean in-control reference distribution used for parameter calibration, control chart limit estimation, and Great Expectations baseline calculation.
- **Phase II Evaluation (Test) Period**:
  - Exact dates: `2012-01-01` through `2012-12-31`.
  - Batch count: **366 daily batches** (calendar year 2012 is a leap year).
  - Row count: **8,734 hourly observations**.
  - Operational role: Out-of-sample monitoring test bed evaluated under synthetic drift injection.

### 1.4 Drift-Injected Datasets
1. **Abrupt Distribution Shift**: [`data/processed/drift/hour_abrupt_shift_cnt.csv`](file:///home/jslxh/PROJETCS/spc/data/processed/drift/hour_abrupt_shift_cnt.csv)
   - Total rows: 17,379.
   - Phase II batches: 366.
   - Injected drift window: `2012-07-01` to `2012-12-31` (184 batches, 4,376 rows affected).
   - Pre-onset window: `2012-01-01` to `2012-06-30` (182 batches, 4,358 rows clean).
2. **Gradual Null-Rate Drift**: [`data/processed/drift/hour_gradual_null_temp.csv`](file:///home/jslxh/PROJETCS/spc/data/processed/drift/hour_gradual_null_temp.csv)
   - Total rows: 17,379.
   - Phase II batches: 366.
   - Configured drift window: `2012-06-01` to `2012-12-31` (214 batches, 5,114 rows).
   - Realized defect window: `2012-06-10` to `2012-12-31` (205 batches affected, 1,033 total null cells injected).
   - Realized clean pre-defect window: `2012-01-01` to `2012-06-09` (161 batches completely defect-free).

---

## 2. Actual Monitoring Configurations and Method Parameters

All parameter values below are preserved in [`results/tables/table_method_parameters.csv`](file:///home/jslxh/PROJETCS/spc/results/tables/table_method_parameters.csv) and [`results/raw/evaluation/method_parameters.json`](file:///home/jslxh/PROJETCS/spc/results/raw/evaluation/method_parameters.json).

### 2.1 Great Expectations (Declarative Data Assertions)
- **Configuration File**: [`configs/gx_thresholds_daily_metrics.json`](file:///home/jslxh/PROJETCS/spc/configs/gx_thresholds_daily_metrics.json) (lines 1–37).
- **Implementation**: `build_gx_suite` in [`src/spc/gx_monitor.py`](file:///home/jslxh/PROJETCS/spc/src/spc/gx_monitor.py) (lines 205–246).
- **Evaluated Daily Quality Metrics**:
  1. `row_count`: Subgroup size assertion.
     - `expect_column_values_to_not_be_null`
     - `expect_column_values_to_be_between`: `min_value = 20.0`, `max_value = 24.0`, `strict_min = False`, `strict_max = False`.
  2. `temp_null_rate`: Proportion of missing temperature sensor observations.
     - `expect_column_values_to_not_be_null`
     - `expect_column_values_to_be_between`: `min_value = 0.0`, `max_value = 0.01` (1.0% pipeline SLA maximum defect tolerance), `strict_min = False`, `strict_max = False`.
  3. `cnt_mean`: Daily mean ridership volume.
     - `expect_column_values_to_not_be_null`
     - `expect_column_values_to_be_between`: `min_value = 77.186`, `max_value = 208.683` (calibrated directly to Phase I empirical Shewhart 3-sigma range), `strict_min = False`, `strict_max = False`.
- **Evaluation Load**: 6 expectations per batch $\times$ 366 Phase II batches = **2,196 expectation evaluations** per scenario run.
- **Alert Logic**: Single-batch memoryless alert whenever any expectation fails.
- **Composite Suite Alert**: Defined as logical disjunction:
  $$\text{Alert}_{\text{composite}, t} = \text{Alert}_{\text{row\_count}, t} \lor \text{Alert}_{\text{temp\_null\_rate}, t} \lor \text{Alert}_{\text{cnt\_mean}, t}$$

### 2.2 Shewhart Individuals Control Chart ($I\text{-}MR$)
- **Implementation**: [`src/spc/control_charts.py`](file:///home/jslxh/PROJETCS/spc/src/spc/control_charts.py) (lines 27–75, 200–330, 440–520).
- **Monitored Metric**: Daily mean ridership `cnt_mean` ($n=1$ individual observation per batch).
- **Phase I Calibration Baseline**: 365 daily batches (2011).
- **Center Line (CL)**: $\mu_0 = \bar{X} = 142.934581$.
- **Dispersion Estimator**: Average moving range of successive daily batches ($n=2$):
  $$\bar{MR} = \frac{1}{m-1} \sum_{i=2}^{m} |x_i - x_{i-1}| = 24.721413$$
- **Standard Deviation Estimate**:
  $$\hat{\sigma} = \frac{\bar{MR}}{d_2} = \frac{24.721413}{1.128} = 21.916146$$
  *(where $d_2 = 1.128$ is the standard Shewhart unbiasing factor for subgroup size $n=2$)*.
- **Control Limits (3-sigma)**:
  - $\text{LCL} = \mu_0 - 3\hat{\sigma} = 142.934581 - 3(21.916146) = 77.186143$ (unclamped).
  - $\text{UCL} = \mu_0 + 3\hat{\sigma} = 142.934581 + 3(21.916146) = 208.683020$.
- **Decision Rule**: Alert on day $t$ if $x_t < \text{LCL}$ or $x_t > \text{UCL}$. Memoryless (depends only on current batch).

### 2.3 Sequential Tabular CUSUM
- **Implementation**: [`src/spc/cusum.py`](file:///home/jslxh/PROJETCS/spc/src/spc/cusum.py) (lines 8–43, 56–115, 200–330, 370–490).
- **Monitored Metric**: Daily mean ridership `cnt_mean`.
- **Standardized Observation**:
  $$z_t = \frac{x_t - \mu_0}{\hat{\sigma}} = \frac{x_t - 142.934581}{21.916146}$$
- **Recursive Accumulators**:
  $$C^+_t = \max\left(0, C^+_{t-1} + z_t - k\right)$$
  $$C^-_t = \max\left(0, C^-_{t-1} - z_t - k\right)$$
- **Parameter Values**:
  - Slack / reference parameter: $k = 0.5$ (tuned to detect mean shifts of $\delta = 1.0\sigma$).
  - Decision threshold: $h = 5.0$ sigma units.
  - Mode: Two-sided sequential cumulative sum.
  - Initial condition: $C^+_0 = 0.0, C^-_0 = 0.0$ (no head-start).
  - Reset policy: `reset_policy="none"` (persistent cumulative state without alarm reset).
- **Decision Rule**: Alert on day $t$ if $C^+_t > h$ or $C^-_t > h$.
- **Methodological Exclusion on `temp_null_rate`**:
  - In Phase I, `temp_null_rate` is identically $0.0$ across all 365 batches ($\sigma_0 = 0.0$).
  - Standard Gaussian CUSUM divides by $\sigma_0$ ($z_t = (x_t - \mu_0)/\sigma_0$), creating a zero-division singularity.
  - Continuous CUSUM is uncalibrated and invalid on zero-variance baseline quality metrics.

### 2.4 Attribute Proportion Control Chart ($p$-Chart)
- **Implementation**: [`src/spc/control_charts.py`](file:///home/jslxh/PROJETCS/spc/src/spc/control_charts.py) (lines 76–118, 340–435, 530–610).
- **Monitored Metric**: `temp_null_rate`, with subgroup size $n_i = \text{row\_count}_i$.
- **Phase I Baseline Pooled Proportion**: $\bar{p} = 0.0$ (0 defects observed out of 8,645 hourly measurements).
- **Dispersion**: Standard binomial standard error collapses:
  $$\sigma_p = \sqrt{\frac{\bar{p}(1-\bar{p})}{n_i}} = 0.0$$
- **Control Limits**: $\text{CL} = 0.0$, $\text{LCL} = 0.0$, $\text{UCL} = 0.0$.
- **Zero-Defect Policy**: `zero_defect_policy = True`, flagging any batch with $p_t > 0.0$.
- **Contingent Equivalence with Great Expectations**:
  - Under daily batching ($N \approx 24$ hourly rows), a single missing observation yields $p_t = 1/24 \approx 4.167\%$.
  - Because $4.167\% > 1.0\%$ (the Great Expectations SLA limit), any non-zero defect batch breaches both the $p$-chart $\text{UCL} = 0.0$ and the GX SLA $[0.0, 0.01]$.
  - The observed 100% agreement between GX and $p$-chart is strictly contingent on small batch size ($N < 100$). For large batches ($N \ge 100$), a single defect ($0.1\% \le p \le 0.9\%$) would breach the $p$-chart but satisfy the 1% SLA.

---

## 3. Drift Scenarios, Seeds, and Experimental Scope

All event metadata below are preserved in [`results/tables/table_ground_truth_events.csv`](file:///home/jslxh/PROJETCS/spc/results/tables/table_ground_truth_events.csv).

### 3.1 Scenario 1: Abrupt Distribution Shift (`abrupt_shift_cnt`)
- **Target Column**: `cnt` (hourly ridership count).
- **Drift Type**: Additive constant shift of $+75.0$ bikes/hour.
- **Configuration & Ground Truth**: [`data/processed/drift/ground_truth_abrupt_shift_cnt.json`](file:///home/jslxh/PROJETCS/spc/data/processed/drift/ground_truth_abrupt_shift_cnt.json).
- **Generator Implementation**: [`src/spc/drift_injection.py`](file:///home/jslxh/PROJETCS/spc/src/spc/drift_injection.py) (lines 12–85).
- **Configured Onset Date**: `2012-07-01`.
- **First Realized Defect Date**: `2012-07-01` ($t_{\text{conf}} = t_{\text{defect}}$).
- **End Date**: `2012-12-31`.
- **Pre-Onset Clean Window**: `2012-01-01` to `2012-06-30` (182 batches, 4,358 rows).
- **Drift Window**: 184 daily batches, 4,376 rows affected.
- **Baseline Period Mean**: 166.924 bikes/hour (pre-onset Phase II mean).
- **Effective Shift Magnitude**: $+75.0$ bikes/hour ($\approx 3.42\hat{\sigma}$).
- **Random Seed**: `42`.
- **Repetitions**: 1 deterministic evaluation.

### 3.2 Scenario 2: Gradual Null-Rate Drift (`gradual_null_temp`)
- **Target Column**: `temp` (hourly ambient temperature reading).
- **Drift Type**: Linear ramp of Bernoulli missingness probability from $p = 0.0$ at `2012-06-01` to $p = 0.40$ at `2012-12-31`.
- **Configuration & Ground Truth**: [`data/processed/drift/ground_truth_gradual_null_temp.json`](file:///home/jslxh/PROJETCS/spc/data/processed/drift/ground_truth_gradual_null_temp.json).
- **Generator Implementation**: [`src/spc/drift_injection.py`](file:///home/jslxh/PROJETCS/spc/src/spc/drift_injection.py) (lines 86–160).
- **Configured Onset Date**: `2012-06-01`.
- **First Realized Defect Date**: `2012-06-10` (independent Bernoulli trials on June 1–9 produced 0 null cells).
- **End Date**: `2012-12-31`.
- **Configured Pre-Onset Window**: `2012-01-01` to `2012-05-31` (152 batches, 3,620 rows).
- **Realized Defect-Free Pre-Window**: `2012-01-01` to `2012-06-09` (161 batches, 3,836 rows).
- **Injected Batches with Realized Defects**: 205 batches.
- **Total Injected Null Cells**: 1,033 cells across Phase II.
- **Effective Mean Injected Null Rate**: 0.203 over active window.
- **Random Seed**: `42`.
- **Repetitions**: 1 deterministic evaluation.

### 3.3 Explicit Boundaries of Experimental Scope
To ensure scientific transparency, the following experiments were **NOT executed** in the committed repository:
1. **No Standalone Normal-Variation Phase II Test**: Phase II was evaluated strictly under the two synthetic injection runs; an isolated un-injected Phase II control benchmark was not generated as an independent result table.
2. **No Multi-Severity Sweeps**: Shift magnitudes other than $+75.0$ (e.g., $+25, +50, +100$) and null ramp slopes other than $0 \to 0.40$ were not evaluated.
3. **No Multi-Duration Sweeps**: Transient pulse drifts (e.g., 7-day or 14-day anomalies) were not evaluated.
4. **No Multi-Seed Replications**: All synthetic injections used exclusively seed `42`; no Monte Carlo repetitions or confidence intervals were generated.

---

## 4. Ground-Truth Matching, Episode Tracking, and Timing Dynamics

All alarm episode metrics below are preserved in [`results/tables/table_alarm_episodes.csv`](file:///home/jslxh/PROJETCS/spc/results/tables/table_alarm_episodes.csv).

### 4.1 Evaluation Framework and Ground-Truth Labeling
- **Evaluation Period**: Phase II ($N = 366$ days, `2012-01-01` to `2012-12-31`).
- **Binary Classification Ground Truth**:
  - Condition Positive ($P$): Days on or after onset ($t \ge t_{\text{onset}}$).
  - Condition Negative ($N$): Days prior to onset ($t < t_{\text{onset}}$).
- **Batch Conservation Identity**:
  $$\text{TP} + \text{FP} + \text{TN} + \text{FN} = 366 \quad (\forall \text{ scenario, method, onset reference})$$
  *(verified with zero discrepancy across all 12 evaluated combinations)*.

### 4.2 Timing Definitions: Nominal Alert Lag vs. Threshold Crossing Lag
The repository evaluation distinguishes between two distinct operational timing concepts:
1. **Nominal Detection Lag ($\Delta t_{\text{alert}}$)**:
   $$\Delta t_{\text{alert}} = t_{\text{first\_post\_onset\_alert}} - t_{\text{onset}}$$
   Measures whether the monitoring system was emitting an alert on or immediately after the onset date, irrespective of whether that alert was triggered by the injected event or by pre-existing out-of-control conditions.
2. **Fresh Threshold Crossing Lag ($\Delta t_{\text{cross}}$)**:
   $$\Delta t_{\text{cross}} = t_{\text{first\_post\_onset\_crossing}} - t_{\text{onset}}$$
   Measures the number of days until the system transitions from an *in-control* state to an *out-of-control* state (rising edge) on or after the onset date. If the system was already alarming on the eve of onset ($t_{\text{onset}} - 1$), the nominal alert lag is $0.0$ days, but the crossing lag reflects the first genuine rising-edge transition after clearing.

### 4.3 Alarm Episodes on Abrupt Ridership Shift (`abrupt_shift_cnt`)
- **Pre-Existing Out-of-Control State**:
  - On the eve of onset (`2012-06-30`), mean ridership was $236.9583$ (exceeding $\text{UCL} = 208.6830$).
  - **Shewhart Individuals**: On July 1, Shewhart was on day 19 of **Episode 15**, which began on `2012-06-13` and lasted **138 unbroken days** through `2012-10-28`.
  - **Tabular CUSUM**: On July 1, CUSUM was on day 116 of **Episode 7**, which began on `2012-03-07` ($C^+ = 5.2590$) and accumulated to $C^+ = 548.7230$ by June 30 under `reset_policy="none"`.
- **Timing Interpretation**:
  - Shewhart / GX: Nominal alert lag is $0.0$ days (`2012-07-01`), but this is a pre-existing state artifact (`detection_status = "not distinguishable from pre-existing alarms"`). Episode 15 cleared on `2012-10-28`. October 29–30 were in-control ($97.0000$ and $174.6364$). The first fresh post-onset rising-edge crossing occurred on **`2012-10-31`** ($306.9167 > \text{UCL}$), yielding a genuine crossing lag of **122.0 days**.
  - Tabular CUSUM: The accumulator never cleared below $h = 5.0$ between March 7 and December 31 (300 consecutive days above threshold). Zero fresh crossings occurred on or after July 1. Crossing lag is mathematically undefined (`None`). Its 100% recall is an artifact of pre-shift accumulator saturation.

### 4.4 Alarm Episodes on Gradual Telemetry Drift (`gradual_null_temp`)
- **Pre-Onset State**: Completely clean. Zero false alarms occurred prior to onset ($\text{alarming_on_eve} = \text{False}$, $\text{FAR} = 0.0\%$).
- **Configured Onset (`2012-06-01`) Reference**:
  - June 1–9 had zero defects. First alert occurred on `2012-06-10`.
  - Nominal alert lag = **9.0 days**; threshold crossing lag = **9.0 days**.
- **Realized Defect Onset (`2012-06-10`) Reference**:
  - First defect occurred on `2012-06-10` ($p_t = 1/24 \approx 4.17\%$).
  - Nominal alert lag = **0.0 days**; threshold crossing lag = **0.0 days**.
  - Attribute $p$-chart and Great Expectations both detected the defect on the exact calendar date of first realization.

---

## 5. Verified Contingency Matrices and Detection Performance Table

The table below reproduces the authoritative results preserved in [`results/tables/comparative_metrics.csv`](file:///home/jslxh/PROJETCS/spc/results/tables/comparative_metrics.csv) and [`results/tables/table_detection_performance.csv`](file:///home/jslxh/PROJETCS/spc/results/tables/table_detection_performance.csv).

| Scenario | Target Metric | Method | Signal Scope | Onset Reference | Onset Date | $P$ | $N$ | TP | FP | TN | FN | Recall (TPR) | FAR (FPR) | Precision | $F_1$ Score | Alert Lag (d) | Crossing Lag (d) | Detection Status |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `abrupt_shift_cnt` | `cnt_mean` | Great Expectations | Target Metric | Configured | `2012-07-01` | 184 | 182 | 169 | 105 | 77 | 15 | 0.918478 | 0.576923 | 0.616788 | 0.737991 | 0.0 | 122.0 | Not Distinguishable |
| `abrupt_shift_cnt` | `cnt_mean` | Shewhart Indiv. ($I$) | Target Metric | Configured | `2012-07-01` | 184 | 182 | 169 | 105 | 77 | 15 | 0.918478 | 0.576923 | 0.616788 | 0.737991 | 0.0 | 122.0 | Not Distinguishable |
| `abrupt_shift_cnt` | `cnt_mean` | Tabular CUSUM | Target Metric | Configured | `2012-07-01` | 184 | 182 | 184 | 141 | 41 | 0 | 1.000000 | 0.774725 | 0.566154 | 0.722986 | 0.0 | N/A | Not Distinguishable |
| `abrupt_shift_cnt` | `cnt_mean` | GX Composite Suite | Composite | Configured | `2012-07-01` | 184 | 182 | 171 | 105 | 77 | 13 | 0.929348 | 0.576923 | 0.619565 | 0.743478 | 0.0 | 145.0 | Not Distinguishable |
| `gradual_null_temp` | `temp_null_rate` | Great Expectations | Target Metric | Configured | `2012-06-01` | 214 | 152 | 192 | 0 | 152 | 22 | 0.897196 | 0.000000 | 1.000000 | 0.945813 | 9.0 | 9.0 | Detected |
| `gradual_null_temp` | `temp_null_rate` | Attribute $p$-Chart | Target Metric | Configured | `2012-06-01` | 214 | 152 | 192 | 0 | 152 | 22 | 0.897196 | 0.000000 | 1.000000 | 0.945813 | 9.0 | 9.0 | Detected |
| `gradual_null_temp` | `temp_null_rate` | Tabular CUSUM | Target Metric | Configured | `2012-06-01` | 214 | 152 | — | — | — | — | N/A | 0.000000 | N/A | N/A | N/A | N/A | Excluded ($\sigma_0=0$) |
| `gradual_null_temp` | `temp_null_rate` | GX Composite Suite | Composite | Configured | `2012-06-01` | 214 | 152 | 212 | 77 | 75 | 2 | 0.990654 | 0.506579 | 0.733564 | 0.842942 | 1.0 | 1.0 | Not Distinguishable |
| `gradual_null_temp` | `temp_null_rate` | Great Expectations | Target Metric | First Defect | `2012-06-10` | 205 | 161 | 192 | 0 | 161 | 13 | 0.936585 | 0.000000 | 1.000000 | 0.967254 | 0.0 | 0.0 | Detected |
| `gradual_null_temp` | `temp_null_rate` | Attribute $p$-Chart | Target Metric | First Defect | `2012-06-10` | 205 | 161 | 192 | 0 | 161 | 13 | 0.936585 | 0.000000 | 1.000000 | 0.967254 | 0.0 | 0.0 | Detected |
| `gradual_null_temp` | `temp_null_rate` | Tabular CUSUM | Target Metric | First Defect | `2012-06-10` | 205 | 161 | — | — | — | — | N/A | 0.000000 | N/A | N/A | N/A | N/A | Excluded ($\sigma_0=0$) |
| `gradual_null_temp` | `temp_null_rate` | GX Composite Suite | Composite | First Defect | `2012-06-10` | 205 | 161 | 204 | 85 | 76 | 1 | 0.995122 | 0.527950 | 0.705882 | 0.825911 | 0.0 | 3.0 | Not Distinguishable |

---

## 6. Reproducibility, Test Suite Status, and Verification Commands

### 6.1 Test Suite Status Across Runtime Environments
1. **Isolated Container Python 3.12 Runtime** (`/tmp/spc-gx-test/venv`):
   - Status: **82 passed, 0 failed, 0 skipped** (100% pass rate).
   - Execution command:
     ```bash
     /tmp/spc-gx-test/venv/bin/python -m unittest discover -s tests -p "test_*.py"
     ```
2. **Host Python 3.14 Runtime** (`.venv`):
   - Status: **74 passed, 8 skipped, 0 failed**.
   - Skips: 8 Great Expectations integration tests skipped gracefully via `unittest.skipIf(sys.version_info >= (3, 13), ...)` due to upstream Great Expectations dependency constraints (`great-expectations==1.24.0` supports Python $\le 3.12$).
   - Execution command:
     ```bash
     PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -p "test_*.py"
     ```

### 6.2 Safe Pipeline Reproduction Commands
- **Dry-Run Reproduction (Read-Only Verification)**:
  ```bash
  PYTHONPATH=. .venv/bin/python scripts/reproduce_pipeline.py --dry-run
  ```
- **Host Execution (Python 3.14 compatible, regenerates statistical outputs while preserving GX)**:
  ```bash
  PYTHONPATH=. .venv/bin/python scripts/reproduce_pipeline.py --skip-gx
  ```
- **Evidence Manifest Integrity Verification (44 registered artifacts)**:
  ```bash
  sha256sum -c docs/evidence_manifest.sha256
  ```

---

## 7. Code and Data Availability Status

- **Git Repository State**: Local Git repository initialized at commit `edd6295`.
- **Remote Configuration**: No remote origin configured (`git remote -v` outputs nothing).
- **Public URL / DOI**: Not yet established.
- **Open Data License**: Raw dataset distributed under Capital Bikeshare open data terms and UCI Machine Learning Repository public archive.
- **Mandatory Next Step for Manuscript Publication**:
  1. Push repository to an institutional or public GitHub/GitLab repository.
  2. Create a versioned release (e.g. `v1.0.0`) and archive to Zenodo to obtain an immutable DOI.
  3. Include GitHub URL and Zenodo DOI in the manuscript's Code Availability section.

