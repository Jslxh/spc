# Final Results Audit and Manuscript Evidence Lock Report

**Audit Date**: October 24, 2026  
**Auditor**: Independent Read-Only Research Audit  
**Target Repository**: `/home/jslxh/PROJETCS/spc`  
**Current Baseline Commit**: `edd6295` (`feat: document reproducible monitoring workflow`)  
**Previous Baseline Commit**: `22de149` (`feat: establish reproducible SPC monitoring research baseline`)  
**Evidence Checksum Status**: **45/45 passed** (`docs/evidence_manifest.sha256`)  

---

## 1. Repository Commit and Cleanliness

1. **Commit Identification**:
   - Current HEAD is at commit `edd6295` on branch `master`.
   - Preceding baseline commit was `22de149`.
2. **Working Tree Cleanliness**:
   - Prior to creating this audit report, `git status --short` was completely clean (0 modified files, 0 untracked files).
   - All tests in the test suite pass:
     - **Host Python 3.14 Environment**: 82 tests ran — 74 passed, 8 skipped due to Great Expectations Python $\le 3.12$ environment boundaries.
     - **Isolated Container Python 3.12 Runtime**: 82 tests ran — 82 passed, 0 skipped, 100% passing.
3. **Evidence Integrity**:
   - No experiment outputs, raw datasets, processed metrics, ground-truth manifests, figures, or tables were modified or regenerated in the committed repository during this audit.

---

## 2. Checksum Verification

Verification against the authoritative SHA-256 evidence manifest (`docs/evidence_manifest.sha256`) was executed before and during the audit:

```bash
$ sha256sum -c docs/evidence_manifest.sha256
```

All 45 registered evidence files passed checksum verification successfully:
- `configs/gx_thresholds_daily_metrics.json`: OK
- `data/processed/drift/ground_truth_abrupt_shift_cnt.json`: OK
- `data/processed/drift/ground_truth_gradual_null_temp.json`: OK
- `data/processed/drift/hour_abrupt_shift_cnt.csv`: OK
- `data/processed/drift/hour_gradual_null_temp.csv`: OK
- `data/raw/Readme.txt`: OK
- `data/raw/day.csv`: OK
- `data/raw/hour.csv`: OK
- `docs/results_and_discussion_draft.md`: OK
- `results/figures/abrupt_shift_monitoring.png`: OK
- `results/figures/detection_timing.png`: OK
- `results/figures/false_alarm_comparison.png`: OK
- `results/figures/gradual_null_drift.png`: OK
- `results/processed/comparative_daily_alerts.csv`: OK
- `results/processed/comparative_evaluation_summary.json`: OK
- `results/processed/daily_metrics_abrupt_shift_cnt.csv`: OK
- `results/processed/daily_metrics_gradual_null_temp.csv`: OK
- `results/processed/daily_quality_metrics_raw_with_null_cols.csv`: OK
- `results/processed/monitoring_cusum_cnt_mean.csv`: OK
- `results/processed/monitoring_p_chart_temp_null_rate.csv`: OK
- `results/processed/monitoring_shewhart_cnt_mean.csv`: OK
- `results/raw/daily_quality_metrics.csv`: OK
- `results/raw/evaluation/audit_report.json`: OK
- `results/raw/evaluation/environment_snapshot.json`: OK
- `results/raw/evaluation/execution.log`: OK
- `results/raw/evaluation/final_publication_audit.json`: OK
- `results/raw/evaluation/method_parameters.json`: OK
- `results/raw/gx/abrupt_shift_cnt/config.json`: OK
- `results/raw/gx/abrupt_shift_cnt/daily_summary.csv`: OK
- `results/raw/gx/abrupt_shift_cnt/detailed_records.csv`: OK
- `results/raw/gx/abrupt_shift_cnt/execution.log`: OK
- `results/raw/gx/abrupt_shift_cnt/runtime_info.json`: OK
- `results/raw/gx/abrupt_shift_cnt/summary.json`: OK
- `results/raw/gx/evaluation_summary.json`: OK
- `results/raw/gx/gradual_null_temp/config.json`: OK
- `results/raw/gx/gradual_null_temp/daily_summary.csv`: OK
- `results/raw/gx/gradual_null_temp/detailed_records.csv`: OK
- `results/raw/gx/gradual_null_temp/execution.log`: OK
- `results/raw/gx/gradual_null_temp/runtime_info.json`: OK
- `results/raw/gx/gradual_null_temp/summary.json`: OK
- `results/tables/comparative_metrics.csv`: OK
- `results/tables/table_alarm_episodes.csv`: OK
- `results/tables/table_detection_performance.csv`: OK
- `results/tables/table_ground_truth_events.csv`: OK
- `results/tables/table_method_parameters.csv`: OK

---

## 3. Files Inspected

The following authoritative files form the empirical foundation of this audit:

1. **Source Raw Datasets**:
   - `data/raw/hour.csv` (17,379 hourly observations across 2011–2012)
   - `data/raw/day.csv` (731 daily records)
   - `data/raw/Readme.txt` (Dataset documentation, licensing, and attribution metadata)
2. **Drift-Injected Datasets and Ground-Truth Specifications**:
   - `data/processed/drift/hour_abrupt_shift_cnt.csv` & `ground_truth_abrupt_shift_cnt.json` (+75 additive shift, onset 2012-07-01, seed 42)
   - `data/processed/drift/hour_gradual_null_temp.csv` & `ground_truth_gradual_null_temp.json` (linear ramp 0.0 to 0.40, onset 2012-06-01, seed 42)
3. **Daily Quality Aggregations**:
   - `results/raw/daily_quality_metrics.csv`
   - `results/processed/daily_quality_metrics_raw_with_null_cols.csv`
   - `results/processed/daily_metrics_abrupt_shift_cnt.csv`
   - `results/processed/daily_metrics_gradual_null_temp.csv`
4. **Primary Monitoring Time Series**:
   - `results/processed/monitoring_shewhart_cnt_mean.csv`
   - `results/processed/monitoring_p_chart_temp_null_rate.csv`
   - `results/processed/monitoring_cusum_cnt_mean.csv`
   - `results/raw/gx/abrupt_shift_cnt/daily_summary.csv` & `detailed_records.csv`
   - `results/raw/gx/gradual_null_temp/daily_summary.csv` & `detailed_records.csv`
5. **Comparative Alerts and Master Tables**:
   - `results/processed/comparative_daily_alerts.csv`
   - `results/tables/comparative_metrics.csv`
   - `results/tables/table_detection_performance.csv`
   - `results/tables/table_alarm_episodes.csv`
   - `results/tables/table_method_parameters.csv`
   - `results/tables/table_ground_truth_events.csv`
6. **Publication Figures**:
   - `results/figures/abrupt_shift_monitoring.png`
   - `results/figures/gradual_null_drift.png`
   - `results/figures/false_alarm_comparison.png`
   - `results/figures/detection_timing.png`
7. **Manuscript Draft**:
   - `docs/results_and_discussion_draft.md`

---

## 4. Recomputed Metrics and Comparison with Saved Tables

All batch classification metrics were independently recomputed from the 366 daily rows of `results/processed/comparative_daily_alerts.csv` using the ground-truth onset dates.

### Mathematical Definitions and Denominators
For each scenario and method evaluated over Phase II ($N_{\text{total}} = 366$ days, calendar year 2012 leap year):
- **Condition Positives ($P$)**: Number of batches on or after the reference onset date ($t \ge t_{\text{onset}}$).
- **Condition Negatives ($N$)**: Number of batches prior to the reference onset date ($t < t_{\text{onset}}$).
- **True Positives ($\text{TP}$)**: $\sum [ \text{Alert}_t = \text{True} \land t \ge t_{\text{onset}} ]$
- **False Positives ($\text{FP}$)**: $\sum [ \text{Alert}_t = \text{True} \land t < t_{\text{onset}} ]$
- **True Negatives ($\text{TN}$)**: $\sum [ \text{Alert}_t = \text{False} \land t < t_{\text{onset}} ]$
- **False Negatives ($\text{FN}$)**: $\sum [ \text{Alert}_t = \text{False} \land t \ge t_{\text{onset}} ]$
- **Batch Identity**: $\text{TP} + \text{FP} + \text{TN} + \text{FN} = 366$ (verified strictly across all runs).
- **Batch Recall (TPR)**: $\frac{\text{TP}}{P} = \frac{\text{TP}}{\text{TP} + \text{FN}}$
- **Pre-Onset False Alarm Rate (FAR / FPR)**: $\frac{\text{FP}}{N} = \frac{\text{FP}}{\text{FP} + \text{TN}}$
- **Batch Precision**: $\frac{\text{TP}}{\text{TP} + \text{FP}}$
- **Batch $F_1$ Score**: $\frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$

### Audit Comparison Table

| Scenario | Target Metric | Method | Onset Ref | Onset Date | $P$ | $N$ | TP | FP | TN | FN | Recall | FAR | Precision | $F_1$ Score | Status in Table 3 | Agreement |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: |
| `abrupt_shift_cnt` | `cnt_mean` | Great Expectations | Configured | `2012-07-01` | 184 | 182 | 169 | 105 | 77 | 15 | 0.918478 | 0.576923 | 0.616788 | 0.737991 | Indist. Pre | Exact Match |
| `abrupt_shift_cnt` | `cnt_mean` | Shewhart Indiv. | Configured | `2012-07-01` | 184 | 182 | 169 | 105 | 77 | 15 | 0.918478 | 0.576923 | 0.616788 | 0.737991 | Indist. Pre | Exact Match |
| `abrupt_shift_cnt` | `cnt_mean` | Tabular CUSUM | Configured | `2012-07-01` | 184 | 182 | 184 | 141 | 41 | 0 | 1.000000 | 0.774725 | 0.566154 | 0.722986 | Indist. Pre | Exact Match |
| `abrupt_shift_cnt` | `cnt_mean` | GX Composite | Configured | `2012-07-01` | 184 | 182 | 171 | 105 | 77 | 13 | 0.929348 | 0.576923 | 0.619565 | 0.743478 | Indist. Pre | Exact Match |
| `gradual_null_temp` | `temp_null_rate` | Great Expectations | Configured | `2012-06-01` | 214 | 152 | 192 | 0 | 152 | 22 | 0.897196 | 0.000000 | 1.000000 | 0.945813 | Detected | Exact Match |
| `gradual_null_temp` | `temp_null_rate` | Attribute $p$-Chart | Configured | `2012-06-01` | 214 | 152 | 192 | 0 | 152 | 22 | 0.897196 | 0.000000 | 1.000000 | 0.945813 | Detected | Exact Match |
| `gradual_null_temp` | `temp_null_rate` | Tabular CUSUM | Configured | `2012-06-01` | 214 | 152 | — | — | — | — | N/A | 0.000000 | N/A | N/A | Excluded | Exact Match |
| `gradual_null_temp` | `temp_null_rate` | GX Composite | Configured | `2012-06-01` | 214 | 152 | 212 | 77 | 75 | 2 | 0.990654 | 0.506579 | 0.733564 | 0.842942 | Indist. Pre | Exact Match |
| `gradual_null_temp` | `temp_null_rate` | Great Expectations | First Defect | `2012-06-10` | 205 | 161 | 192 | 0 | 161 | 13 | 0.936585 | 0.000000 | 1.000000 | 0.967254 | Detected | Exact Match |
| `gradual_null_temp` | `temp_null_rate` | Attribute $p$-Chart | First Defect | `2012-06-10` | 205 | 161 | 192 | 0 | 161 | 13 | 0.936585 | 0.000000 | 1.000000 | 0.967254 | Detected | Exact Match |
| `gradual_null_temp` | `temp_null_rate` | Tabular CUSUM | First Defect | `2012-06-10` | 205 | 161 | — | — | — | — | N/A | 0.000000 | N/A | N/A | Excluded | Exact Match |
| `gradual_null_temp` | `temp_null_rate` | GX Composite | First Defect | `2012-06-10` | 205 | 161 | 204 | 85 | 76 | 1 | 0.995122 | 0.527950 | 0.705882 | 0.825911 | Indist. Pre | Exact Match |

**Audit Finding**: Every single recomputed metric in the table above agrees with [`results/tables/comparative_metrics.csv`](file:///home/jslxh/PROJETCS/spc/results/tables/comparative_metrics.csv), [`results/tables/table_detection_performance.csv`](file:///home/jslxh/PROJETCS/spc/results/tables/table_detection_performance.csv), and Table 3 in [`docs/results_and_discussion_draft.md`](file:///home/jslxh/PROJETCS/spc/docs/results_and_discussion_draft.md) with **zero discrepancy**.

---

## 5. Detection-Timing Interpretation

A critical contribution of this audit is formalizing the distinction between six detection-timing concepts:

1. **Configured Event Onset ($t_{\text{conf}}$)**: The scheduled calendar date specified by the experiment protocol (e.g., `2012-07-01` for ridership shift; `2012-06-01` for gradual telemetry drift).
2. **First Realized Injected Defect ($t_{\text{defect}}$)**: The first date on which data values actually deviate from clean baseline expectations. For abrupt shift, $t_{\text{defect}} = \text{2012-07-01}$. For gradual drift, $t_{\text{defect}} = \text{2012-06-10}$ (independent Bernoulli draws yielded 0 null cells for the first 9 days of June).
3. **First Alert of Any Kind**: The earliest date in Phase II where $\text{Alert}_t = \text{True}$.
   - Continuous `cnt_mean`: Shewhart/GX first alerted on `2012-01-21` (winter weekend low excursion); CUSUM first alerted on `2012-01-03`.
   - Telemetry `temp_null_rate`: First alert occurred on `2012-06-10` (no pre-onset alerts).
4. **First Alert on or After Onset**: The first date $t \ge t_{\text{onset}}$ where $\text{Alert}_t = \text{True}$.
   - All methods on `cnt_mean` alerted on `2012-07-01`.
   - Attribute methods on `temp_null_rate` alerted on `2012-06-10`.
5. **Pre-Existing Alarm Episodes**:
   - On the eve of the abrupt shift (`2012-06-30`), daily ridership was $236.9583$ (exceeding $\text{UCL} = 208.6830$ by $28.2753$). Shewhart was already on day 18 of **Episode 15**, which began on `2012-06-13` and lasted **138 unbroken days** through `2012-10-28`.
   - On the eve of shift injection, tabular CUSUM was on day 116 of **Episode 7**, which began on `2012-03-07` ($C^+ = 5.2590$) and accumulated to $C^+ = 548.7230$ by June 30.
   - Therefore, the nominal $0.0$-day detection lag on July 1 is a **pre-existing state artifact**, not a newly triggered event detection. The evaluation framework correctly categorizes this status as `"not distinguishable from pre-existing alarms"`.
6. **Fresh Post-Onset Detection After Clearing**:
   - For Shewhart/GX on `cnt_mean`, Episode 15 cleared on `2012-10-28`. October 29 ($97.0000$) and October 30 ($174.6364$) returned in-control. The first fresh rising-edge threshold crossing post-onset occurred on **`2012-10-31`** ($306.9167 > \text{UCL}$), initiating Episode 16. The genuine crossing lag is **122 days**.
   - For tabular CUSUM on `cnt_mean`, the accumulator never cleared below $h = 5.0$ through `2012-12-31`. Zero fresh post-onset crossings occurred. Fresh crossing lag is mathematically undefined (`None`).
   - For attribute methods on `temp_null_rate`, the process was clean prior to onset (`alarming_on_eve = False`). The first alert coincided with the first crossing on **`2012-06-10`**, establishing an unambiguous real-time detection lag of **$0.0$ days**.

---

## 6. Statistical Validity Findings

1. **Macro-Seasonality Confounding**:
   - Natural summer expansion in ridership breaches static Phase I limits, causing 105 false alarms in Shewhart/GX ($\text{FAR} = 57.69\%$) and 141 in CUSUM ($\text{FAR} = 77.47\%$).
   - Classical SPC assumptions of in-control stationarity are severely violated by raw business volume metrics.
2. **CUSUM Parameterization and Saturation**:
   - Parameters $k = 0.5$ and $h = 5.0$ with `reset_policy="none"` mean that sustained positive deviations produce unbounded accumulator growth ($C^+ > 500$). The apparent 100% recall is an artifact of pre-shift accumulator saturation.
3. **Degeneracy of $p$-Chart on Zero-Defect Baseline**:
   - Because Phase I had 0 defects ($p_0 = 0.0$), the binomial standard error collapses to $\sigma_p = 0.0$, making theoretical 3-sigma limits collapse to $\text{UCL} = 0.0$. The $p$-chart acts as a strict zero-defect filter (flagging any $p > 0$).
4. **Batch Size Effect on Threshold vs. $p$-Chart Equivalence**:
   - Daily batches contain $N \approx 24$ hourly observations. A single defect yields $p = 1/24 \approx 4.17\%$.
   - Because $4.17\% > 1.0\%$ (the Great Expectations SLA), any non-zero defect batch breaches both the $p$-chart zero-defect limit and the 1% GX SLA.
   - This equivalence is an artifact of small batch size ($N < 100$). For large batches ($N \ge 100$), a single defect ($0.1\% - 0.9\%$) would trigger the $p$-chart but pass the 1% SLA.
5. **Absence of Statistical Hypothesis Testing**:
   - No p-values, t-tests, ANOVA, or confidence intervals were computed. All claims are empirical benchmarking comparisons on deterministic synthetic injections.
6. **Scenario Scope**:
   - Experiments evaluated two specific deterministic scenarios (additive $+75.0$ shift and linear ramp $0 \to 0.40$) on a single random seed (`42`). Conclusions reflect these operational regimes and must not be over-generalized to stochastic variance shifts or arbitrary distributions.

---

## 7. Figures and Captions Requiring Correction

Review of the four publication figures in `results/figures/` and their manuscript captions in `docs/results_and_discussion_draft.md`:

1. **Figure 1 (`abrupt_shift_monitoring.png`)**:
   - *Graphic*: Correctly plots `cnt_mean` observations against CL ($142.93$) and 3-sigma limits ($77.19, 208.68$), with CUSUM $C^+$ and $C^-$ below.
   - *Caption*: Accurate. Explicitly reports Episode 7 starting March 7 ($C^+ = 5.2590$), $C^+ = 548.7230$ on June 30, and zero new crossings post-onset.
2. **Figure 2 (`gradual_null_drift.png`)**:
   - *Graphic*: Correctly plots observed null rates against linear ramp schedule, highlighting configured onset (`2012-06-01`) and realized defect onset (`2012-06-10`).
   - *Caption*: Accurate. Explicitly mentions the 1% SLA dashed line at $y = 0.01$ and $p$-chart zero-defect limit at $y = 0.0$.
3. **Figure 3 (`false_alarm_comparison.png`)**:
   - *Graphic*: Grouped bar chart comparing pre-onset FAR across scenarios with sample size annotations ($N = 182$ and $N = 161$).
   - *Caption*: Accurate. Notes composite suite false alarm propagation ($52.80\%$).
4. **Figure 4 (`detection_timing.png`)**:
   - *Graphic*: Grouped bar chart comparing nominal alert lag vs. threshold crossing lag.
   - *Caption*: Accurate. Highlights the distinction between nominal 0-day alert lag and 122-day crossing lag for Shewhart.
5. **Caption/Draft Status**: No figure graphics or caption numbers require correction; all numerical references match the authoritative data.

---

## 8. Unsupported Claims to Remove or Qualify

1. **CUSUM 100% Recall on Continuous Ridership**:
   - *Current Status*: The manuscript already explicitly qualifies this in Section 4.2 and Section 5.1.
   - *Audit Requirement*: Ensure that anywhere Table 3 is cited or summarized, the 100% recall is explicitly labeled as a "pre-existing saturation artifact" rather than genuine detection sensitivity.
2. **Shewhart 0-Day Detection Lag on Abrupt Shift**:
   - *Current Status*: Correctly qualified in Section 4.2 as day 19 of pre-existing Episode 15.
   - *Audit Requirement*: Maintain this qualification consistently in abstract and executive summary.
3. **Equivalence of Great Expectations and $p$-Chart**:
   - *Current Status*: Documented in Section 4.1.
   - *Audit Requirement*: Reiterate that this holds only because $N \approx 24$ rows/day ($1/24 \approx 4.17\% > 1\%$), and does not generalize to pipelines with large batch sizes ($N \ge 100$).
4. **Automated Test Count in Manuscript Appendix**:
   - *Current Status*: Appendix line 269 states: *"The complete evaluation suite passed 78/78 automated tests"*.
   - *Correction Needed*: With commit `edd6295`, four new tests were added, bringing the total suite to **82 tests** (82 passed, 0 failed, 0 skipped in Python 3.12).

---

## 9. Reference and Dataset-Attribution Issues

1. **Mandatory Dataset Attribution**:
   - In [`data/raw/Readme.txt`](file:///home/jslxh/PROJETCS/spc/data/raw/Readme.txt) (lines 90–100), the dataset license mandates publication citation to:
     > Fanaee-T, Hadi, and Gama, Joao. "Event labeling combining ensemble detectors and background knowledge." *Progress in Artificial Intelligence*, 2(2-3):113–127, 2013. Springer Berlin Heidelberg. DOI: `10.1007/s13748-013-0040-3`.
   - **Audit Finding**: `docs/results_and_discussion_draft.md` currently **lacks a dedicated References section**. This citation must be formally added to the manuscript.
2. **Classical SPC Literature Citations**:
   - The manuscript cites Shewhart individuals ($d_2 = 1.128$), tabular CUSUM ($k = 0.5, h = 5.0$), and attribute $p$-charts. Formal bibliographic entries should be added for:
     - Page, E. S. (1954). "Continuous Inspection Schemes." *Biometrika*, 41(1/2), 100–115. DOI: `10.2307/2333009`.
     - Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*. 8th ed., John Wiley & Sons.
     - Shewhart, W. A. (1931). *Economic Control of Quality of Manufactured Product*. D. Van Nostrand Company.
3. **Data Pipeline Quality References**:
   - Great Expectations documentation and data quality monitoring frameworks should be cited:
     - Great Expectations (2024). Software documentation, Version 1.24.0, Superconductive / Great Expectations, Inc. https://greatexpectations.io/

---

## 10. Prioritized List of Exact Changes Needed for Final Report and Paper

### Priority 1: High (Mandatory for Scholarly Integrity)
1. **Add References Section to Manuscript Draft**:
   - Insert a formal `## References` section at the end of `docs/results_and_discussion_draft.md` containing the verified citations for Fanaee-T & Gama (2013), Page (1954), Montgomery (2019), Shewhart (1931), and Great Expectations.
2. **Update Test Count in Appendix**:
   - In `docs/results_and_discussion_draft.md` (line 269), update *"passed 78/78 automated tests"* to *"passed 82/82 automated tests"*.

### Priority 2: Medium (Clarity and Contextual Precision)
3. **Emphasize Batch-Size Dependency in Table 3 Footnote**:
   - Add a brief footnote in Table 3 stating that the 100% agreement between Great Expectations (1% SLA) and the attribute $p$-chart ($\text{UCL}=0.0$) is contingent on daily batch sizes ($N \approx 24$) where any defect represents $\ge 4.17\%$.
4. **Reiterate CUSUM Saturation Caveat in Executive Summary**:
   - In any final report summary, ensure CUSUM's 100% recall is explicitly coupled with its 77.47% pre-onset false alarm rate and 300-day saturation duration.

### Priority 3: Low (Future Work / Editorial Polish)
5. **Discuss Reset-on-Alarm Trade-Offs**:
   - Note in the Discussion that automated reset-on-alarm or FIR CUSUM policies represent a valuable direction for future research on volume metrics, but require seasonal de-trending to avoid cyclic false-alarm storms.

---

## Verification Summary

- **Repository Cleanliness**: Verified. Clean working tree prior to audit report creation.
- **Evidence Manifest**: 45/45 SHA-256 checksums passed. Zero outputs overwritten.
- **Audit Deliverable**: Saved as [`docs/final_results_audit.md`](file:///home/jslxh/PROJETCS/spc/docs/final_results_audit.md).

