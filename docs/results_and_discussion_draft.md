# Results and Discussion: Comparative Evaluation of Great Expectations, Shewhart Control Charts, and Sequential CUSUM for Data Pipeline Monitoring

---

## 4. Results

This section presents empirical results from evaluating three monitoring paradigms—a Great Expectations (GX) declarative static threshold baseline [5], Shewhart individual and attribute control charts [2, 4], and tabular sequential CUSUM [3, 4]—across two distinct synthetic drift scenarios: an abrupt distribution shift in continuous ridership (`cnt_mean`) and gradual missing-data drift in pipeline telemetry (`temp_null_rate`), derived from the Capital Bikeshare benchmark dataset [1]. All reported metrics, episode counts, and timing characteristics are derived from frozen Phase II experimental outputs and verified against authoritative ground-truth specifications.

---

### 4.1 Calibration and Baseline Method Parameters

Phase I baseline calibration was conducted over the complete 365 daily batches of calendar year 2011 (January 1, 2011, through December 31, 2011) from the bike sharing dataset [1]. Table 1 summarizes the calibrated parameters, dispersion estimators, decision limits, and operational rationales for each method. Table 2 details the authoritative ground-truth specifications for both Phase II synthetic drift scenarios (calendar year 2012, $N = 366$ daily batches).

```
Table 1: Phase I Baseline Calibration and Monitoring Parameters (2011-01-01 to 2011-12-31, N = 365 Batches)
======================================================================================================================================
Method                               Monitored Metric  Center Line (CL)  Dispersion Estimator     Dispersion (σ0) Decision Limits / Thresholds      Memory Type
--------------------------------------------------------------------------------------------------------------------------------------
Great Expectations (Static)          cnt_mean          142.934581        Moving-Range (MR̄/1.128)  21.916146       [77.186, 208.683]                 Memoryless (Single-Batch)
Shewhart Individuals Chart (X/MR)    cnt_mean          142.934581        Moving-Range (MR̄/1.128)  21.916146       LCL = 77.186, UCL = 208.683       Memoryless (Single-Batch)
Tabular Sequential CUSUM             cnt_mean          142.934581        Moving-Range (MR̄/1.128)  21.916146       k = 0.5, h = 5.0 σ units (C+, C-) Sequential Accumulator (none)
Great Expectations (Static)          temp_null_rate    0.000000          Historical Zero SLA      0.000000        [0.0, 0.01] (1.0% SLA max)        Memoryless (Single-Batch)
Attribute p-Chart                    temp_null_rate    0.000000          Binomial Baseline        0.000000        UCL = 0.0 (Zero-Defect Limit)     Memoryless (Single-Batch)
Tabular Sequential CUSUM             temp_null_rate    0.000000          Degenerate (σ0 = 0.0)    0.000000        Uncalibrated / Invalid            N/A (Excluded)
======================================================================================================================================
```

```
Table 2: Ground-Truth Synthetic Drift Scenarios (Phase II: 2012-01-01 to 2012-12-31, N = 366 Batches)
======================================================================================================================================
Scenario Name               Target Metric Drift Type           Configured Onset First Observed Defect Injected Batches Total Rows / Defect Cells Effective Shift
--------------------------------------------------------------------------------------------------------------------------------------
Abrupt Distribution Shift   cnt_mean      Additive Shift       2012-07-01       2012-07-01            184              4,376 rows affected       +75.0 riders/hour
Gradual Null Rate Drift     temp_null_rate Linear Ramp (0→0.4) 2012-06-01       2012-06-10            214 (window)     1,033 missing cells       +0.203 null rate
======================================================================================================================================
```

For continuous ridership (`cnt_mean`), Phase I mean ridership was $\mu_0 = 142.934581$ with an average moving range between adjacent consecutive daily observations of $\bar{MR} = 24.721413$. Using the standard subgroup divisor $d_2 = 1.128$ for sample size $n = 2$ [4], the Phase I standard deviation was estimated as $\sigma_0 = \bar{MR}/d_2 = 21.916146$. This yields standard Shewhart 3-sigma limits [2, 4] of:
$$\text{LCL} = \mu_0 - 3\sigma_0 = 77.186143, \quad \text{UCL} = \mu_0 + 3\sigma_0 = 208.683020$$
Great Expectations bounds [5] were set to $[77.186, 208.683]$ to establish an identical single-batch threshold baseline.

Tabular sequential CUSUM [3, 4] was formulated as a two-sided Gaussian recursion monitoring standardized deviations $z_t = (x_t - \mu_0)/\sigma_0$:
$$C^+_t = \max(0, C^+_{t-1} + z_t - k)$$
$$C^-_t = \max(0, C^-_{t-1} - z_t - k)$$
with initial conditions $C^+_0 = 0$ and $C^-_0 = 0$. Parameters were set to standard reference values: reference allowance $k = 0.5$ (tuned to detect sustained shifts of magnitude $1.0\sigma_0$) and decision interval threshold $h = 5.0$. Accumulators retained continuous history without resetting upon alarm (`reset_policy="none"`).

For missingness telemetry (`temp_null_rate`), all 365 Phase I daily batches contained exactly zero missing values ($p_0 = 0.0, \sigma_0 = 0.0$). In classical Shewhart attribute charting [2, 4], the 3-sigma upper control limit is given by:
$$\text{UCL} = p_0 + 3\sqrt{\frac{p_0(1 - p_0)}{n}}$$
Because the Phase I defect rate was zero, the asymptotic margin collapses to zero ($\text{UCL} = 0.0$). The implemented $p$-chart uses a zero-defect limit ($\text{UCL} = 0.0$) and flags any non-zero observed defect rate ($p > 0$). Great Expectations [5], by contrast, uses a 1% operational SLA ($[0.0, 0.01]$).

For daily batches of approximately 24 observations ($N \approx 24$), a single missing value produces $1/24 \approx 0.04167$ (about $4.17\%$), exceeding the 1% SLA threshold. Consequently, both methods produced identical alert classifications in this experiment (flagging any batch with $\ge 1$ defect). This equivalence is strictly an artifact of the small daily batch size ($N \approx 24$) and zero-defect baseline; for pipelines with large batches ($N \ge 100$), a single missing value would yield defect proportions below 1% (e.g., $1/100 = 1.0\%$, $1/500 = 0.2\%$), which would breach a zero-defect $p$-chart ($\text{UCL} = 0.0$) while passing the 1% Great Expectations SLA.

Continuous Gaussian CUSUM requires standardizing inputs via $z_t = (x_t - \mu_0)/\sigma_0$. Because $\sigma_0 = 0.0$, division by zero is mathematically undefined. Continuous CUSUM was therefore formally marked as uncalibrated and excluded from the zero-variance attribute drift scenario.

---

### 4.2 Abrupt Distribution Shift Monitoring (`cnt_mean`)

Figure 1 displays the Phase II monitoring time series for the abrupt shift scenario, contrasting the single-batch Shewhart/GX decisions against the cumulative tabular CUSUM statistics across all 366 daily batches of 2012.

![Figure 1: Abrupt Shift Monitoring](file:///home/jslxh/PROJETCS/spc/results/figures/abrupt_shift_monitoring.png)

**Figure 1. Shewhart individuals and tabular sequential CUSUM Phase II monitoring dynamics on continuous ridership (`cnt_mean`).**  
*Top panel*: Daily mean ridership observations ($x_t$, blue solid line) for all 366 batches of 2012, plotted against the Phase I Center Line ($\text{CL} = 142.93$, dashed gray line) and $3\sigma$ decision limits ($\text{LCL} = 77.19$ dotted red, $\text{UCL} = 208.68$ dashed red) derived via moving-range dispersion ($\sigma_0 = 21.92$). Great Expectations static bounds are identical by construction. Red scatter points denote daily alarm states (100% agreement between GX and Shewhart). The green vertical line and shaded band demarcate the injected $+75.0$ additive shift window starting on `2012-07-01`.  
*Bottom panel*: Standardized two-sided tabular CUSUM accumulators ($C^+$ blue solid line, $C^-$ orange dashed line) with decision interval threshold $h = 5.0$ (dashed red line) and allowance $k = 0.5$. Positive residuals from seasonal spring expansion triggered Episode 7 on `2012-03-07` ($C^+ = 5.2590$), driving $C^+$ to $548.7230$ by June 30 and keeping it continuously above $h = 5.0$ for 300 unbroken days through year-end. Consequently, zero new threshold crossings occurred on or after the July 1 shift injection. *(Source: `results/figures/abrupt_shift_monitoring.png`)*.

#### Performance Metric Definitions and Ground-Truth Denominators
To ensure rigorous and reproducible classification accounting, Phase II performance is evaluated daily over all $N_{\text{total}} = 366$ batches of calendar year 2012 (a leap year). Each daily batch $t \in \{1, \dots, 366\}$ is partitioned relative to the reference onset date ($t_{\text{onset}}$):
- **Condition Positives ($P$)**: Batches occurring on or after onset ($t \ge t_{\text{onset}}$).
- **Condition Negatives ($N$)**: Batches occurring strictly before onset ($t < t_{\text{onset}}$).

For the abrupt distribution shift (`cnt_mean`, configured onset `2012-07-01`), the year partitions into $P = 184$ post-onset batches and $N = 182$ pre-onset batches. For gradual missingness drift (`temp_null_rate`), the configured onset (`2012-06-01`) yields $P = 214$ and $N = 152$, whereas the first realized defect date (`2012-06-10`) yields $P = 205$ and $N = 161$.

Across all scenarios and monitoring methods, daily alert classifications satisfy the strict conservation identity:
$$\text{TP} + \text{FP} + \text{TN} + \text{FN} = N_{\text{total}} = 366$$
where $\text{TP} = \sum [\text{Alert}_t = \text{True} \land t \ge t_{\text{onset}}]$, $\text{FP} = \sum [\text{Alert}_t = \text{True} \land t < t_{\text{onset}}]$, $\text{TN} = \sum [\text{Alert}_t = \text{False} \land t < t_{\text{onset}}]$, and $\text{FN} = \sum [\text{Alert}_t = \text{False} \land t \ge t_{\text{onset}}]$. The derived evaluation metrics are computed as:
$$\text{Recall (TPR)} = \frac{\text{TP}}{P} = \frac{\text{TP}}{\text{TP} + \text{FN}}$$
$$\text{False Alarm Rate (FAR / FPR)} = \frac{\text{FP}}{N} = \frac{\text{FP}}{\text{FP} + \text{TN}}$$
$$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}$$
$$F_1 = \frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$$

#### Daily Alert Equivalence Between GX and Shewhart
As shown in Table 3, Great Expectations and Shewhart Individuals charts produced bitwise identical daily alerts across all 366 Phase II batches. Both methods triggered 274 total alarm days: 105 in the 182-day pre-onset window ($\text{FAR} = 57.69\%$) and 169 in the 184-day post-onset window ($\text{Recall} = 91.85\%$, $\text{Precision} = 61.68\%$, $F_1 = 0.7380$). 

This equivalence is not accidental: because Great Expectations evaluated daily means against static thresholds $[77.186, 208.683]$ and the Shewhart Individuals chart flagged observations outside the identical limits $[\text{LCL}, \text{UCL}]$, the two implementations executed isomorphic decision rules on single-batch metrics.

```
Table 3: Phase II Detection Performance Across Monitoring Methods (N = 366 Batches)
========================================================================================================================================================================
Scenario          Metric         Method             Onset Ref.    Onset Date First Alert Lag (d) Status*      P   N   TP  FP  TN  FN   FAR      Recall   Precision F1 Score
------------------------------------------------------------------------------------------------------------------------------------------------------------------------
abrupt_shift_cnt  cnt_mean       Great Expectations Configured    2012-07-01 2012-07-01  0.0     Indist. Pre 184 182 169 105  77  15  57.69%   91.85%   61.68%    0.7380
abrupt_shift_cnt  cnt_mean       Shewhart Indiv.    Configured    2012-07-01 2012-07-01  0.0     Indist. Pre 184 182 169 105  77  15  57.69%   91.85%   61.68%    0.7380
abrupt_shift_cnt  cnt_mean       Tabular CUSUM      Configured    2012-07-01 2012-07-01  0.0     Indist. Pre 184 182 184 141  41   0  77.47%  100.00%†  56.62%    0.7230
abrupt_shift_cnt  cnt_mean       GX Composite       Configured    2012-07-01 2012-07-01  0.0     Indist. Pre 184 182 171 105  77  13  57.69%   92.93%   61.96%    0.7435
gradual_null_temp temp_null_rate Great Expectations Configured    2012-06-01 2012-06-10  9.0     Detected    214 152 192   0 152  22   0.00%   89.72%‡ 100.00%    0.9458
gradual_null_temp temp_null_rate Attribute p-Chart  Configured    2012-06-01 2012-06-10  9.0     Detected    214 152 192   0 152  22   0.00%   89.72%‡ 100.00%    0.9458
gradual_null_temp temp_null_rate Tabular CUSUM      Configured    2012-06-01 None        N/A     Excluded    214 152   —   —   —   —   0.00%     N/A      N/A       N/A
gradual_null_temp temp_null_rate GX Composite       Configured    2012-06-01 2012-06-02  1.0     Indist. Pre 214 152 212  77  75   2  50.66%   99.07%   73.36%    0.8429
gradual_null_temp temp_null_rate Great Expectations First Defect 2012-06-10 2012-06-10  0.0     Detected    205 161 192   0 161  13   0.00%   93.66%‡ 100.00%    0.9673
gradual_null_temp temp_null_rate Attribute p-Chart  First Defect 2012-06-10 2012-06-10  0.0     Detected    205 161 192   0 161  13   0.00%   93.66%‡ 100.00%    0.9673
gradual_null_temp temp_null_rate Tabular CUSUM      First Defect 2012-06-10 None        N/A     Excluded    205 161   —   —   —   —   0.00%     N/A      N/A       N/A
gradual_null_temp temp_null_rate GX Composite       First Defect 2012-06-10 2012-06-10  0.0     Indist. Pre 205 161 204  85  76   1  52.80%   99.51%   70.59%    0.8259
========================================================================================================================================================================
*Status: "Indist. Pre" indicates alert state was active prior to onset and indistinguishable from pre-existing excursions; "Excluded" denotes uncalibrated baseline (σ0 = 0.0).
†CUSUM 100% recall is an artifact of continuous accumulator saturation (initiated 2012-03-07, C+ = 548.72 on June 30); zero fresh rising-edge crossings occurred on or after July 1.
‡GX (1% SLA) and p-chart (UCL = 0.0) produce identical alerts because daily batches are small (N ≈ 24 hourly rows), where any defect represents 1/24 ≈ 4.17% > 1.0%; for batches N ≥ 100, decisions would diverge.
```

#### Episode Deconstruction and the Timing Discrepancy
While the first post-onset alert occurred on the configured onset date (`2012-07-01`) for all methods—yielding a nominal detection lag of $0.0$ days—deconstructing daily flags into contiguous alarm episodes reveals an acute timing discrepancy. Table 4 presents the episode-level analysis.

```
Table 4: Alarm Episode Structure and Threshold Crossing Dynamics (Phase II: N = 366 Batches)
=======================================================================================================================================================
Scenario          Target Metric  Method*           Reference Onset  Onset Date Total Batches Total Episodes Pre-Onset Post-Onset First Crossing First Post Crossing Lag (days) Eve Alarming?
-------------------------------------------------------------------------------------------------------------------------------------------------------
abrupt_shift_cnt  cnt_mean       GX / Shewhart     Configured       2012-07-01 274           18             15        3          2012-01-21     2012-10-31          122        True (Ep 15, d18)
abrupt_shift_cnt  cnt_mean       Tabular CUSUM     Configured       2012-07-01 325           7              7         0          2012-01-03     None                N/A        True (Ep 7, d116)
abrupt_shift_cnt  cnt_mean       GX Composite      Configured       2012-07-01 276           17             15        2          2012-01-21     2012-11-23          145        True
gradual_null_temp temp_null_rate GX / p-Chart      Configured       2012-06-01 192           10             0         10         2012-06-10     2012-06-10          9          False
gradual_null_temp temp_null_rate Tabular CUSUM     Configured       2012-06-01 0             0              0         0          None           None                N/A        False
gradual_null_temp temp_null_rate GX Composite      Configured       2012-06-01 289           15             13        2          2012-01-21     2012-06-02          1          True
gradual_null_temp temp_null_rate GX / p-Chart      First Defect     2012-06-10 192           10             0         10         2012-06-10     2012-06-10          0          False
gradual_null_temp temp_null_rate Tabular CUSUM     First Defect     2012-06-10 0             0              0         0          None           None                N/A        False
gradual_null_temp temp_null_rate GX Composite      First Defect     2012-06-10 289           15             14        1          2012-01-21     2012-06-13          3          True
=======================================================================================================================================================
*Notes: GX and Shewhart / p-chart are presented together because their daily alert vectors and episode boundaries are bitwise identical (100% agreement).
```

On the eve of shift injection (`2012-06-30`), daily ridership was $236.9583$ (exceeding UCL by $28.2753$), and Shewhart was already in an active alarm state. This alarm was part of **Episode 15**, which began on **`2012-06-13`** ($\text{cnt\_mean} = 309.2083$) and continued unbroken for **138 consecutive days** through `2012-10-28`. Thus, on July 1, Shewhart was on day 19 of an active excursion that began 18 days prior to the injection. 

Following a brief return to in-control limits on October 29–30 ($97.0000$ and $174.6364$), the process breached UCL again on **`2012-10-31`** ($306.9167$). Consequently, the first genuine post-onset threshold crossing occurred 122 days after the injected shift.

#### CUSUM Accumulator Saturation Under Natural Seasonality
The distortion was more pronounced for tabular CUSUM. As shown in the bottom panel of Figure 1, positive residuals accumulated rapidly as spring ridership expanded. The upper accumulator ($C^+$) crossed the decision threshold $h = 5.0$ on **`2012-03-07`** (reaching $5.2590$), initiating **Episode 7**. 

Under `reset_policy="none"`, accumulators retained historical deviations without clearing to zero. Because warm-season ridership remained systematically elevated above the Phase I annual mean ($\mu_0 = 142.934581$), $C^+$ accumulated monotonically to $548.7230$ on June 30 and continued climbing through year-end, reaching an unbroken duration of **300 consecutive days**. Meanwhile, the lower accumulator ($C^-$) remained at zero throughout the excursion.

Because CUSUM never dropped below $h = 5.0$ between March 7 and December 31, it experienced **zero new threshold crossings on or after July 1, 2012**. The reported $100\%$ batch recall ($\text{TPR} = 1.0$, $184/184$ post-onset batches flagged) and nominal $0$-day detection lag do not represent detection of the $+75.0$ shift; they are mathematical artifacts of macro-seasonal saturation that began 116 days prior to the experiment.

---

### 4.3 Gradual Data Quality Drift Monitoring (`temp_null_rate`)

Figure 2 illustrates Phase II monitoring for gradual telemetry missingness, contrasting the intended defect schedule against realized daily null rates and alert events.

![Figure 2: Gradual Null Drift Monitoring](file:///home/jslxh/PROJETCS/spc/results/figures/gradual_null_drift.png)

**Figure 2. Daily telemetry defect rates and attribute monitoring dynamics under gradual missing-data drift (`temp_null_rate`).**  
Daily observed null rate values ($p_t$, blue solid line) for all 366 batches of 2012, compared against the scheduled linear defect ramp ($0.0$ to $0.40$, gray dotted line). Red scatter points mark out-of-control batches exceeding control limits (the Great Expectations 1% operational SLA limit at $0.01$, dashed red line, and the p-chart zero-defect limit at $0.0$). Vertical lines demarcate the configured drift start (`2012-06-01`, dashed purple) and the first realized Bernoulli defect (`2012-06-10`, solid green), demonstrating that zero defects occurred during June 1–9 and establishing exact real-time detection on the day the first defect materialized (lag = 0 days). *(Source: `results/figures/gradual_null_drift.png`)*.

#### Realized Defects vs. Configured Schedule
The synthetic drift protocol specified a linear ramp in defect probability from $0.0$ on `2012-06-01` to $0.40$ on `2012-12-31`. However, because daily missing cells are generated via independent Bernoulli draws on hourly records ($N \approx 24$ rows/day), the realized defect rate in early June differed from the continuous expected schedule:
- On June 1, the scheduled defect probability was $p = 0.001869$, yielding $0$ missing cells in a 24-row batch ($\text{temp\_null\_rate} = 0.0$).
- Across the first 9 days of the window (June 1–9), every batch realized $0$ missing cells.
- The first non-zero defect occurred on **`2012-06-10`**, when 1 of 24 rows was missing ($\text{temp\_null\_rate} = 0.041667$, exceeding the $0.01$ SLA threshold).

#### Detection Performance and Sensitivity to Reference Onset
Both Great Expectations and the attribute $p$-chart exhibited zero false alarms across the pre-drift period ($\text{FAR} = 0.0\%$). Evaluating detection lag against the configured schedule start (`2012-06-01`) yields an apparent lag of $9.0$ days ($\text{Recall} = 89.72\%$, $F_1 = 0.9458$). 

However, evaluating performance against the first realized defect date (`2012-06-10`, $N_{\text{pre}} = 161$, $N_{\text{post}} = 205$) reveals exact real-time detection: both methods flagged the first defective batch on the day it occurred, achieving a true detection lag of **$0.0$ days**, $\text{Recall} = 93.66\%$, $\text{Precision} = 100.00\%$, and $F_1 = 0.9673$ (Table 3). 

As shown in Table 4, the attribute monitors produced 192 total alarm batches divided across 10 clean post-onset episodes, with zero pre-onset alarms. On the eve of onset, the alarm state was `False`. Thus, the first alarm state (`2012-06-10`) coincided exactly with the first threshold crossing, establishing unambiguous event detection.

#### Exclusion of Continuous Gaussian CUSUM
Because all 365 daily observations of `temp_null_rate` in Phase I were identically zero, the sample variance was $\sigma_0^2 = 0.0$. Continuous Gaussian CUSUM requires standardizing inputs via $z_t = (x_t - \mu_0)/\sigma_0$. Division by zero is undefined. 

Imposing an arbitrary non-zero variance or applying continuous Gaussian equations to zero-inflated bounded proportions violates statistical assumptions and fabricates invalid control signals. Continuous CUSUM was therefore formally marked as uncalibrated and excluded from the attribute evaluation.

---

### 4.4 Comparative Synthesis: False Alarms, Detection Lags, and Composite Suites

Figure 3 compares pre-onset false alarm rates across scenarios, and Figure 4 contrasts detection timing dynamics across methods and reference onsets.

![Figure 3: False Alarm Comparison](file:///home/jslxh/PROJETCS/spc/results/figures/false_alarm_comparison.png)

**Figure 3. Pre-onset false alarm rate (FAR) comparison across monitoring methods and drift scenarios.**  
Grouped bar chart displaying the proportion of false alarms triggered in the defect-free pre-onset window. Pre-window sample sizes are explicitly annotated ($N = 182$ days for ridership `cnt_mean`; $N = 161$ days for telemetry `temp_null_rate` relative to first defect). On continuous ridership, unmodeled seasonal volume causes extreme false alarm rates ($57.69\%$ for Shewhart and Great Expectations; $77.47\%$ for tabular CUSUM). On telemetry missingness, both Great Expectations and the attribute $p$-chart achieve zero false alarms ($\text{FAR} = 0.0\%$), whereas the GX composite suite inherits a $52.80\%$ false alarm rate via logical disjunction with `cnt_mean`. *(Source: `results/figures/false_alarm_comparison.png`)*.

![Figure 4: Detection Timing](file:///home/jslxh/PROJETCS/spc/results/figures/detection_timing.png)

**Figure 4. Event detection timing and threshold crossing lag comparison across monitoring paradigms.**  
Comparison of detection lags (in days) from drift onset across scenarios and reference types. In the gradual null rate scenario, Great Expectations and the attribute $p$-chart exhibit an apparent 9-day lag from the configured schedule start (`2012-06-01`), but an exact 0-day lag relative to the first realized defect (`2012-06-10`). In the abrupt shift scenario, Shewhart and Great Expectations show a nominal 0-day alert state lag on July 1, but require 122 days for the first new post-onset threshold crossing (`2012-10-31`). For tabular CUSUM, no new post-onset threshold crossing occurs due to pre-existing seasonal accumulator saturation. *(Source: `results/figures/detection_timing.png`)*.

#### Composite Suite Performance and Logical Disjunction
In production pipelines, validation tools like Great Expectations [5] typically run composite suites evaluating multiple assertions simultaneously. In our experiments, the composite suite evaluated `row_count`, `temp_null_rate`, and `cnt_mean`.

Mathematically, the composite suite alert evaluated on daily batches represents a conservative logical disjunction (union of failures):
$$\text{Alert}_{\text{composite}, t} = \text{Alert}_{\text{row\_count}, t} \lor \text{Alert}_{\text{temp\_null\_rate}, t} \lor \text{Alert}_{\text{cnt\_mean}, t}$$
Under the gradual null scenario (`gradual_null_temp`), monitoring the target metric alone yielded $\text{FAR} = 0.0\%$. However, the composite suite exhibited $\text{FAR} = 50.66\%$ ($77/152$ pre-onset days flagged relative to configured onset; $52.80\%$, $85/161$ days relative to first defect). 

Every single pre-onset false alarm in the composite suite was triggered by `cnt_mean` exceeding its summer limits in unshifted data. Consequently, on the gradual drift scenario, the composite suite was already in an active alarm state prior to onset (`alarming_on_eve = True`), masking the telemetry signal behind unrelated seasonal noise.

As detailed in Table 4, deconstructing the 15 total episodes of the composite suite under the two reference onsets reveals:
- *Configured Onset Reference (`2012-06-01`)*: Episode 13 ended on `2012-05-31`. June 1 was in-control (`False`). The first post-onset crossing occurred on **`2012-06-02`** (lag = 1 day), dividing the run into **13 pre-onset** and **2 post-onset** episodes.
- *First Observed Defect Reference (`2012-06-10`)*: Episode 14 began on `2012-06-02` and ran through `2012-06-11`. Because the suite was already alarming on June 10, the first new crossing on or after onset occurred on **`2012-06-13`** (lag = 3 days, following an in-control day on June 12), dividing the run into **14 pre-onset** and **1 post-onset** episode.

---

## 5. Discussion

The empirical findings highlight several methodological principles and operational trade-offs for automated data quality monitoring.

---

### 5.1 Alert Semantics in Process Monitoring: State vs. Crossing vs. Event Detection

A central conclusion of this study is that evaluations of pipeline monitors must distinguish between three distinct definitions of an alarm [4]:
1. **Daily Alarm State ($\text{Alert}_t$)**: A point-in-time condition indicating that the current batch statistic violates a control boundary ($x_t \notin [\text{LCL}, \text{UCL}]$ or $C_t > h$).
2. **Threshold Crossing ($\Delta \text{Alert}_t$)**: An edge-triggered transition where the process shifts from an in-control state to an out-of-control state ($\text{Alert}_t = \text{True}$ and $\text{Alert}_{t-1} = \text{False}$).
3. **Event-Level Detection**: The attribution of a threshold crossing to a specific exogenous perturbation or data corruption event.

When monitoring systems operate on non-stationary baselines, daily classification metrics ($\text{TPR}$, $\text{FPR}$, $\text{Precision}$, $F_1$) become decoupled from event detection. In our abrupt-shift experiment, tabular CUSUM recorded a nominal recall of $100\%$ and a detection lag of $0.0$ days. 

However, because the accumulator was already locked in an unbroken alarm run from March 7, the system was blind to the July 1 shift: it experienced zero new threshold crossings. Treating continuous alert states as event detections produces deceptive performance estimates in benchmark studies.

---

### 5.2 Seasonality and Non-Stationarity as Confounders in Sequential SPC

Sequential process control methods such as tabular CUSUM [3, 4] derive their mathematical optimality from the assumption that in-control observations are independent and identically distributed ($\text{i.i.d.}$) around a constant baseline mean $\mu_0$.

When applied to business volume metrics (such as ridership, click volume, or transaction counts), this assumption fails. Natural annual seasonality introduces persistent, autocorrelated positive deviations during peak periods. Under `reset_policy="none"`, these positive deviations accumulate monotonically in the upper accumulator:
$$C^+_t = \max(0, C^+_{t-1} + z_t - k)$$
Once $C^+_t$ climbs into hundreds of standard deviations (reaching $548.7230$ on June 30), the accumulator cannot clear without months of large negative deviations.

Shewhart charts [2, 4] are less vulnerable to cumulative lock-in because they are memoryless ($x_t$ depends only on the current batch), but they still experienced an unbroken 138-day alarm excursion (Episode 15) and a $57.69\%$ pre-onset false alarm rate.

These results demonstrate that classical SPC algorithms and static validation rules cannot be deployed directly on raw volume metrics without seasonal pre-adjustment (e.g., STL decomposition, seasonal differencing, or dynamic harmonic baselines).

---

### 5.3 Static Pipeline Validation (Great Expectations) vs. Statistical Process Control

Our comparative results provide a clear perspective on the relative strengths and operational boundaries of static data testing tools [5] versus statistical process control [2, 3, 4]:

#### Great Expectations
- **Strengths**: Excels at enforcing explicit operational service level agreements (SLAs), structural schemas, and business invariants [5]. On `temp_null_rate`, defining an SLA threshold of $1.0\%$ missingness produced clean detection ($F_1 = 0.967$, $\text{FAR} = 0.0\%$) with zero calibration overhead.
- **Limitations**: Static scalar boundaries cannot adapt to non-stationary distributions. Setting static 3-sigma thresholds derived from Phase I resulted in extreme false alarm rates ($57.69\%$) during seasonal expansion. Furthermore, memoryless evaluation cannot detect subtle, persistent drift below the 3-sigma limit.

#### Shewhart Control Charts
- **Strengths**: Provides mathematically rigorous, empirically grounded control limits derived from moving-range dispersion estimators ($\bar{MR}/d_2$) that are robust to isolated step shifts [2, 4].
- **Limitations**: Like Great Expectations, Shewhart charts are memoryless; when configured with matching thresholds, their operational alerts are identical. They lack sequential memory to accumulate small sub-sigma shifts.

#### Sequential CUSUM
- **Strengths**: Theoretically optimal for rapid detection of small to moderate sustained shifts ($0.5\sigma$ to $1.5\sigma$) that remain invisible to Shewhart limits [3, 4].
- **Limitations**: Highly fragile in the presence of unmodeled trends or seasonality. Accumulator saturation causes severe false alarm cascades under persistent positive residuals. Furthermore, standard continuous Gaussian CUSUM cannot be calibrated on zero-variance baselines ($\sigma_0 = 0.0$).

#### Batch-Size Sensitivity in Attribute Equivalence
Crucially, the empirical 100% agreement between Great Expectations (1% SLA) and the attribute $p$-chart ($\text{UCL} = 0.0$) observed in this study is contingent on small daily batch sizes ($N \approx 24$ hourly rows), where a single defect represents $1/24 \approx 4.17\% > 1\%$. In data pipelines operating on larger batches ($N \ge 100$), this operational equivalence breaks down: a batch containing a single defect ($p = 0.005$ for $N = 200$) will trigger the zero-defect $p$-chart but remain within the 1% Great Expectations SLA threshold. Organizations adopting declarative SLA tools must recognize this sensitivity to batch granularity.

---

### 5.4 Limitations of the Empirical Evaluation

To maintain scientific integrity, several explicit limitations of this study must be noted:
1. **Single Baseline Calibration**: Phase I calibration was evaluated on a single 365-day period (2011) without dynamic recursive updating or rolling calibration windows.
2. **Fixed CUSUM Parameterization and Reset Policy**: CUSUM was evaluated with fixed parameters ($k = 0.5, h = 5.0$) and `reset_policy="none"`. Alternative reset strategies (such as head-start/FIR CUSUM, cyclical accumulator clamping, or resetting to zero upon alarm) were not evaluated in this experiment.
3. **Absence of Attribute CUSUM**: The CUSUM implementation evaluated was restricted to continuous Gaussian formulations. Specialized discrete attribute CUSUM charts (e.g., Bernoulli or Poisson CUSUM) were outside the implementation scope and were not tested on the null-rate scenario.
4. **Synthetic Drift Scope**: Evaluations were conducted on two deterministic synthetic drift injection scenarios (one abrupt continuous shift, one gradual linear quality ramp) under a fixed seed (`42`). Complex multi-attribute drift interactions or stochastic variance shifts were not evaluated.
5. **No Statistical Significance Claims**: Consistent with empirical benchmarking standards on fixed deterministic scenarios, no statistical significance tests, p-values, or confidence intervals are claimed.

---

### 5.5 Practical Recommendations for Production Data Quality Systems

Based on our empirical findings, we recommend the following design principles for production data monitoring architectures:
1. **Match Monitoring Paradigms to Metric Types**:
   - For **data quality and schema invariants** (null rates, type mismatches, range breaches) where in-control expectations are near zero, use declarative static threshold suites (such as Great Expectations [5]) or attribute $p$-charts [2, 4]. They provide near-optimal detection timing with minimal false alarm overhead.
   - For **continuous volume metrics** subject to operational fluctuations, avoid static thresholds unless combined with seasonal decomposition.
2. **Implement Edge-Triggered Alerting in Orchestration**:
   - Upstream workflow orchestrators (e.g., Apache Airflow) should distinguish between *continuous alarm states* and *new threshold crossings*. Persistent daily failures should be grouped into contiguous incidents rather than triggering redundant daily alerts.
3. **Decouple Quality Tests from Volume Monitoring in Composite Suites**:
   - Composite test suites should not combine volume metrics with data quality assertions unless failure policies are tiered. In our experiments, seasonal noise on ridership completely obscured clean telemetry signals when evaluated as a unified suite.
4. **Operational Design of Accumulator Resets**:
   - In classical quality engineering, an out-of-control signal typically leads operators to halt physical operations, investigate an assignable cause, and reset accumulators to zero or a Fast Initial Response (FIR) head-start ($h/2$) [4]. In automated data pipelines running unattended overnight, automated reset-on-alarm represents a plausible operational design choice that would prevent accumulators from climbing to hundreds of standard deviations. *(Note: Reset-on-alarm, cyclical accumulator clamping, and Fast Initial Response (FIR) head-starts are literature-based architectural alternatives; our empirical experiments evaluated exclusively `reset_policy="none"` as documented in Table 1).* However, reset-on-alarm should not be viewed as an automatic cure: without underlying seasonal adjustment, resetting accumulators upon alert would simply convert one long saturation run into dozens of repetitive, high-frequency alarm crossings as positive deviations reaccumulate. The quantitative trade-offs of reset policies require focused empirical study.

---

## Appendix: Verified Audit and Data Parity Disclosure

Every value, table entry, and figure plotted in this manuscript was audited against raw Phase II experiment files and ground-truth metadata. The audit artifact is preserved at [`results/raw/evaluation/final_publication_audit.json`](file:///home/jslxh/PROJETCS/spc/results/raw/evaluation/final_publication_audit.json).

- **Numerical Parity**: Recomputed contingency matrices across all 366 Phase II batches matched [`results/tables/table_detection_performance.csv`](file:///home/jslxh/PROJETCS/spc/results/tables/table_detection_performance.csv) and [`results/tables/table_alarm_episodes.csv`](file:///home/jslxh/PROJETCS/spc/results/tables/table_alarm_episodes.csv) with zero discrepancies.
- **Timing Audit Correction**: An informal narrative note in preliminary internal review documentation ([`results/raw/evaluation/audit_report.json`](file:///home/jslxh/PROJETCS/spc/results/raw/evaluation/audit_report.json) line 23) stated that Shewhart Episode 15 began on `2012-06-28`. Independent audit of the daily alert series verified that Episode 15 began on **`2012-06-13`** ($\text{cnt\_mean} = 309.2083$) and was on day 19 of its excursion on July 1. All generated CSV tables and this manuscript report the verified ground fact.
- **Automated Test Suite**: The complete evaluation suite passed 82/82 automated tests in the isolated Python 3.12 container runtime environment (with 74 passed and 8 environment-skipped in host Python 3.14).

---

## References

[1] H. Fanaee-T and J. Gama, "Event labeling combining ensemble detectors and background knowledge," *Progress in Artificial Intelligence*, pp. 1–15, 2013. DOI: 10.1007/s13748-013-0040-3. [Authoritative citation specified in repository dataset license `data/raw/Readme.txt`; volume and issue pagination (vol. 2, no. 2–3, pp. 113–127) noted for external library verification].

[2] W. A. Shewhart, *Economic Control of Quality of Manufactured Product*. New York: D. Van Nostrand Company, 1931. [Foundational textbook; external library verification required for specific edition pagination].

[3] E. S. Page, "Continuous Inspection Schemes," *Biometrika*, vol. 41, no. 1/2, pp. 100–115, 1954. DOI: 10.1093/biomet/41.1-2.100. [External library verification required for volume/issue confirmation].

[4] D. C. Montgomery, *Introduction to Statistical Quality Control*, 8th ed. Hoboken, NJ: John Wiley & Sons, 2019. [Foundational textbook; external library verification required for specific chapter/section pagination].

[5] Great Expectations, *Great Expectations Software Documentation*, Version 1.24.0, Superconductive / Great Expectations, Inc., 2024. [Online]. Available: https://greatexpectations.io/ [Software version 1.24.0 verified against repository environment configuration `requirements-gx.txt`].
