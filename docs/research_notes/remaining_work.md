# Remaining Work and Scholarly Limitations

**Repository**: `/home/jslxh/PROJETCS/spc`  
**Baseline Commit**: `edd6295` (`feat: document reproducible monitoring workflow`)  
**Evidence Checksum Status**: 44/44 passed (`docs/evidence_manifest.sha256`)  
**Date**: October 2026  
**Document Purpose**: Internal research reference enumerating the remaining tasks required to complete the research paper, the scholarly limitations of the existing implementation, and an explicit disclosure of experiment configurations that were not executed.

---

## 1. Scholarly Tasks for Manuscript Completion

While the empirical evaluation, audit report, and Results & Discussion draft ([`docs/results_and_discussion_draft.md`](file:///home/jslxh/PROJETCS/spc/docs/results_and_discussion_draft.md)) are fully locked to repository evidence, several academic and editorial tasks remain before journal submission:

### 1.1 External Library and Citation Verification
The preliminary bibliography in Section 6 of the manuscript draft requires external library confirmation:
1. **[1] Fanaee-T & Gama (2013)**:
   - Citation: Fanaee-T, H., & Gama, J. (2013). "Event labeling combining ensemble detectors and background knowledge." *Progress in Artificial Intelligence*, 2(2–3), 113–127. DOI: `10.1007/s13748-013-0040-3`.
   - Action: Confirm final publisher issue assignment and page numbers (online-first pagination was 1–15; print pagination is 113–127).
2. **[2] Shewhart (1931)**:
   - Citation: Shewhart, W. A. (1931). *Economic Control of Quality of Manufactured Product*. New York: D. Van Nostrand Company.
   - Action: Confirm specific chapter and section references for individuals and moving-range chart formulations.
3. **[3] Page (1954)**:
   - Citation: Page, E. S. (1954). "Continuous Inspection Schemes." *Biometrika*, 41(1/2), 100–115. DOI: `10.1093/biomet/41.1-2.100`.
   - Action: Verify volume, issue, and DOI resolution via publisher records.
4. **[4] Montgomery (2019)**:
   - Citation: Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*, 8th ed. Hoboken, NJ: John Wiley & Sons.
   - Action: Confirm specific edition pagination for Phase I moving-range estimation and tabular CUSUM design.

### 1.2 Code and Data Availability Infrastructure
To satisfy journal open science requirements:
1. **Remote Repository Setup**:
   - The current repository has no configured Git remote (`git remote -v` returns empty).
   - Create a clean public repository on GitHub or GitLab under an institutional or individual account.
   - Push commit `edd6295` (or subsequent clean tag) to `main`/`master`.
2. **Persistent Archival and DOI Minting**:
   - Tag a release (e.g., `v1.0.0`).
   - Connect repository to Zenodo (`https://zenodo.org`) to mint a persistent Digital Object Identifier (DOI).
   - Insert the resulting DOI and repository URL into the manuscript's Code Availability disclosure.

### 1.3 Manuscript Composition Beyond Results and Discussion
The existing manuscript draft covers Section 4 (Empirical Evaluation), Section 5 (Discussion), and the Appendix. The remaining sections must be drafted prior to submission:
1. **Title, Abstract, and Keywords**:
   - Draft an informative title highlighting the comparative benchmarking between declarative data assertions (Great Expectations) and classical statistical process control (Shewhart, CUSUM, $p$-chart).
   - Write a structured abstract summarizing the core findings: macro-seasonality confounding, CUSUM saturation dynamics, $p$-chart zero-defect equivalence, and practical pipeline design recommendations.
2. **Section 1: Introduction**:
   - Background on modern automated data pipelines, silent data corruption, and data downtime.
   - Contrast between declarative data contracts (static assertions) and time-series process monitoring.
   - Summary of paper contributions and empirical methodology.
3. **Section 2: Related Work**:
   - Literature review covering:
     - Data quality monitoring frameworks (Great Expectations, Soda SQL, Monte Carlo).
     - Classical SPC in manufacturing and telemetry (Shewhart, Page, Roberts).
     - Concept drift detection in machine learning streams (ADWIN, DDM, EDDM).
     - Seasonal decomposition and time-series anomaly detection.
4. **Section 3: System Architecture and Methodology**:
   - Formal mathematical formulation of Phase I calibration, moving-range estimation, tabular CUSUM recursion, and attribute $p$-charts.
   - Data pipeline architecture and daily batching mechanics.
   - Synthetic drift injection protocols (abrupt step shift, gradual Bernoulli ramp).
5. **Journal Formatting**:
   - Convert Markdown manuscript to target publication format (LaTeX IEEEtran, ACM Small, or Springer Nature template).
   - Format publication figures (`results/figures/*.png`) to high-resolution 300 DPI EPS/PDF formats.

---

## 2. Methodological Scope and Limitations of the Existing Implementation

The empirical findings documented in [`docs/research_notes/repository_evidence.md`](file:///home/jslxh/PROJETCS/spc/docs/research_notes/repository_evidence.md) must be interpreted within the explicit methodological boundaries of the implementation:

1. **Static Single-Baseline Calibration**:
   - Phase I baseline calibration is conducted exclusively on calendar year 2011 (365 daily batches).
   - The current codebase does not implement dynamic rolling calibration windows, recursive Kalman-type updates, or seasonal de-trending. As a result, long-term annual seasonality breaches static limits.
2. **Fixed CUSUM Parameterization and Unbounded Accumulation**:
   - Tabular CUSUM was evaluated strictly with parameters $k = 0.5$, $h = 5.0$, and `reset_policy="none"`.
   - Alternative policies documented in the literature—such as resetting accumulators to zero upon alarm, Fast Initial Response (FIR) head-starts ($h/2$), or bounded accumulator clamping—were not empirically implemented or evaluated in the current codebase.
3. **Absence of Discrete Attribute CUSUM**:
   - The evaluated CUSUM algorithm is strictly a continuous Gaussian formulation.
   - When applied to zero-defect quality metrics (`temp_null_rate`), baseline standard deviation collapses to zero ($\sigma_0 = 0.0$), causing division-by-zero failure.
   - Specialized discrete attribute CUSUM schemes (e.g., Bernoulli CUSUM or Poisson CUSUM) were outside the codebase scope.
4. **Batch Size Dependency of Great Expectations vs. $p$-Chart Equivalence**:
   - The observed identical performance of Great Expectations (1% SLA) and the attribute $p$-chart ($\text{UCL}=0.0$) is contingent on daily batch sizes ($N \approx 24$ hourly rows), where a single defect represents $\approx 4.17\% > 1\%$.
   - This equivalence does not hold in data pipelines with large batches ($N \ge 100$).
5. **No Statistical Hypothesis Testing**:
   - Because evaluations were conducted on fixed deterministic synthetic drift runs, no p-values, t-tests, ANOVA, or statistical significance intervals are reported. All conclusions represent empirical benchmark comparisons.
6. **Runtime Environment Version Boundaries**:
   - Great Expectations version `1.24.0` depends on libraries that restrict compatibility to Python versions $\le 3.12$.
   - Host execution on Python 3.14 requires running with `--skip-gx` or using the isolated Python 3.12 container environment (`/tmp/spc-gx-test/venv`).

---

## 3. Explicit Disclosure of Unexecuted Experiments

To preserve scientific rigor and prevent unwarranted generalizations, the following experimental configurations were **explicitly NOT executed** in this repository:

1. **Normal-Variation (Un-Injected) Phase II Control Benchmark**:
   - Phase II data (2012) was evaluated solely under the two drift scenarios (`abrupt_shift_cnt` and `gradual_null_temp`).
   - A dedicated standalone benchmark evaluating the clean, un-injected 2012 test set across all methods was not generated as an independent result table or figure.
2. **Multiple Drift Severity Levels**:
   - Ridership shift was evaluated at exactly one magnitude: $+75.0$ bikes/hour ($\approx 3.42\hat{\sigma}$). Smaller shifts (e.g., $+0.5\sigma, +1.0\sigma, +2.0\sigma$) and larger shifts were not evaluated.
   - Missingness drift was evaluated at exactly one slope: linear ramp from $p = 0.0$ to $p = 0.40$. Other terminal defect rates (e.g., $p = 0.05, 0.10, 0.20, 0.80$) were not evaluated.
3. **Multiple Drift Durations and Transient Pulses**:
   - Both drift scenarios evaluated persistent shifts that continued through the end of the year (`2012-12-31`).
   - Transient pulse anomalies (e.g., 1-day spikes, 7-day outages, 14-day sensor recalibrations) were not evaluated.
4. **Multiple Random Seeds and Stochastic Replications**:
   - All synthetic drift injections were executed using a single deterministic seed (`seed=42`).
   - No multi-seed repetitions, Monte Carlo distributions, or empirical confidence bounds were generated.

