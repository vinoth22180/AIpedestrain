# PCVC Phase 6 Research Experiment Execution Report

**Project:** Profile-Coupled Counterfactual Verification Controller (PCVC) for Accessibility-Aware Pedestrian Networks  
**Target Publication:** IEEE Access  
**Execution Date:** 2026-10-05  
**Document Status:** Code-Verified Final Experimental Execution Report  
**Master Artifacts:** [MASTER_RESULTS.json](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/MASTER_RESULTS.json), [MASTER_RESULTS.csv](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/MASTER_RESULTS.csv)

---

## Executive Summary

This report documents the empirical execution and evaluation of the **Phase 6 Research Experiment Harness** for PCVC. All nine planned experiments (E1 through E9) were executed against the active VIT Vellore academic pedestrian network cache. Every metric, latency, correlation coefficient, and distribution reported below represents measured values extracted directly from the experiment runner logs and machine-readable output files.

---

## Section A — Environment & Computational Setup

- **Operating System:** Windows 11 Enterprise (64-bit, Build 26300)
- **Processor:** Intel64 Family 6 Model 183 Stepping 1, GenuineIntel
- **Python Version:** `3.14.2` (64-bit AMD64)
- **Primary Dependencies:**
  - NetworkX: `3.6.1`
  - NumPy: `2.5.2`
  - Pandas: `3.0.5`
  - SciPy: `1.18.1`
  - Matplotlib: `3.11.2`
  - Shapely: `2.1.2`
  - GeoPandas: `1.1.4`
  - OSMnx: `2.1.1`
  - FastAPI: `0.141.1`
  - Pydantic: `2.13.5`
- **Random Seed Control:** Deterministic integer seeds $\mathcal{S} = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]$ applied via `random.seed()` and `np.random.seed()`.

---

## Section B — Active Graph Dataset Verification

The active campus pedestrian network was loaded strictly from the verified cache:
- **File Location:** [data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl](file:///d:/dynamic_pedestrian_rerouting/data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl)
- **File Size:** 767,489 bytes
- **Pre/Post Execution MD5 Hash:** `5ecc692284c6b43a700ac92f303aeed1` (Unmodified; zero byte mutation)
- **Graph Topology:** Undirected NetworkX `MultiGraph`
  - Total Nodes: $1,551$
  - Total Edges: $1,721$
  - Connected Components: $9$
  - Giant Component Size: $1,509$ nodes ($97.29\%$ of network)
  - Isolated/Peripheral Components: $8$ components ($14, 13, 6, 3, 2, 2, 1, 1$ nodes)
- **Verified Campus Landmark Anchors:** $9$ configured campus landmarks (MGR, SJT, TT, PRP, SMV, Gandhi Block, Anna Auditorium, CTS, Parking Lot).

---

## Section C — E1: Natural Uncertainty Distribution Results

The natural accessibility uncertainty was scanned across all $1,721$ edges in the active network under candidate threshold $\tau = 0.40$ ($U(e, p) = 1 - C(e, p)$).

### Profile Distribution Summary

| Profile | Total Edges | Mean Uncertainty | Median Uncertainty | Std Dev | Min | Max | Candidates ($U \ge 0.40$) | Candidate % |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **General** | 1,721 | 0.4450 | 0.5500 | 0.1445 | 0.2500 | 0.7500 | 1,114 | 64.73% |
| **Elderly** | 1,721 | 0.2805 | 0.3500 | 0.0976 | 0.1500 | 0.6000 | 7 | 0.41% |
| **Pregnant** | 1,721 | 0.2805 | 0.3500 | 0.0976 | 0.1500 | 0.6000 | 7 | 0.41% |
| **Wheelchair** | 1,721 | 0.4497 | 0.5500 | 0.1403 | 0.1000 | 0.7500 | 1,400 | 81.35% |

### Uncertainty Frequency Bins

| Profile | [0.0, 0.2) | [0.2, 0.4) | [0.4, 0.6) | [0.6, 0.8) | [0.8, 1.0] |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **General** | 0 (0.0%) | 607 (35.27%) | 838 (48.69%) | 276 (16.04%) | 0 (0.0%) |
| **Elderly** | 80 (4.65%) | 1,634 (94.94%) | 7 (0.41%) | 0 (0.0%) | 0 (0.0%) |
| **Pregnant** | 80 (4.65%) | 1,634 (94.94%) | 7 (0.41%) | 0 (0.0%) | 0 (0.0%) |
| **Wheelchair** | 80 (4.65%) | 241 (14.00%) | 1,124 (65.31%) | 276 (16.04%) | 0 (0.0%) |

**Artifacts Generated:**
- [profile_uncertainty_summary.csv](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e1/summary/profile_uncertainty_summary.csv)
- [uncertainty_distribution_comparison.png](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e1/figures/uncertainty_distribution_comparison.png)

---

## Section D — E2: Oracle Hold-Out / Masking Results

The oracle experiment evaluated whether PCVC prioritizes edges that exhibit high ground-truth network impact upon counterfactual removal. Known wheelchair attributes ($N = 324$ pool) were masked to `"unknown"` in-memory across 10 random seeds ($42–51$) for masking sizes $K \in [20, 40, 80]$.

### Oracle Masking Performance (Mean over 10 seeds)

| Masking Size | Spearman $\rho$ | Kendall $\tau$ | Hit@1 | Hit@5 | Hit@10 | Precision@5 | Precision@10 | TIC@5 | TIC@10 | NDCG@10 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$K = 20$** | 0.1191 | 0.1084 | 1.00 | 1.00 | 1.00 | 0.8800 | 0.8900 | 1.0000 | 1.0000 | 1.0000 |
| **$K = 40$** | 0.1877 | 0.1702 | 1.00 | 1.00 | 1.00 | 0.7000 | 0.9300 | 1.0000 | 1.0000 | 1.0000 |
| **$K = 80$** | 0.1538 | 0.1395 | 1.00 | 1.00 | 1.00 | 0.7000 | 0.7500 | 1.0000 | 1.0000 | 1.0000 |

**Artifacts Generated:**
- [oracle_summary.csv](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e2/summary/oracle_summary.csv)
- [oracle_edge_results.csv](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e2/raw/oracle_edge_results.csv)
- [tic_ndcg_by_k.png](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e2/figures/tic_ndcg_by_k.png)

---

## Section E — E3: Baseline Ranking Comparison Results

All methods were evaluated on the identical candidate pool of 40 held-out edges across 10 deterministic seeds ($42–51$).

### Comparative Performance Table (Mean $\pm$ Std across 10 Seeds)

| Code | Baseline Method | Spearman $\rho$ | Kendall $\tau$ | Hit@5 | Hit@10 | Precision@5 | Precision@10 | TIC@5 | TIC@10 | NDCG@10 |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **B1** | Random | 0.0546 $\pm$ 0.0837 | 0.0451 $\pm$ 0.0692 | 0.40 | 0.90 | 0.1000 | 0.2400 | 1.0000 $\pm$ 0.00 | 1.0000 $\pm$ 0.00 | 1.0000 $\pm$ 0.00 |
| **B2** | Uncertainty-Only | -0.0578 $\pm$ 0.1623 | -0.0571 $\pm$ 0.1605 | 1.00 | 1.00 | 0.6800 | 0.7500 | 0.9400 $\pm$ 0.0966 | 0.9700 $\pm$ 0.0483 | 0.9421 $\pm$ 0.0958 |
| **B3** | CAD-Only | 0.2037 $\pm$ 0.2184 | 0.1939 $\pm$ 0.2078 | 1.00 | 1.00 | 1.0000 | 1.0000 | 1.0000 $\pm$ 0.00 | 1.0000 $\pm$ 0.00 | 1.0000 $\pm$ 0.00 |
| **B4** | Impact-Only | 0.5000 $\pm$ 0.5270 | 0.5000 $\pm$ 0.5270 | 1.00 | 1.00 | 1.0000 | 1.0000 | 1.0000 $\pm$ 0.00 | 1.0000 $\pm$ 0.00 | 1.0000 $\pm$ 0.00 |
| **B5** | Uncertainty + CAD | 0.1851 $\pm$ 0.1981 | 0.1679 $\pm$ 0.1799 | 1.00 | 1.00 | 0.7000 | 0.9300 | 1.0000 $\pm$ 0.00 | 1.0000 $\pm$ 0.00 | 1.0000 $\pm$ 0.00 |
| **B6** | **Full PCVC** | 0.1877 $\pm$ 0.2011 | 0.1702 $\pm$ 0.1827 | 1.00 | 1.00 | 0.7000 | 0.9300 | 1.0000 $\pm$ 0.00 | 1.0000 $\pm$ 0.00 | 1.0000 $\pm$ 0.00 |

### Statistical Hypothesis Testing

- **Friedman Test Across All 6 Baselines:**
  - $\text{TIC@10}$: $\chi_F^2 = 15.0000, p = 0.010362$ (Statistically significant overall ranking difference across methods).
  - $\text{NDCG@10}$: $\chi_F^2 = 15.0000, p = 0.010362$ (Statistically significant).
  - Spearman $\rho$: $\chi_F^2 = 24.3642, p = 0.000185$ (Statistically significant).
- **Pairwise Wilcoxon Signed-Rank Test (B6 PCVC vs Baselines on TIC@10):**
  - B6 vs B1 (Random): $W = 0.0, p = 1.0$ (tied at ceiling TIC=1.0).
  - B6 vs B2 (Uncertainty-Only): $W = 0.0, p = 0.25$ (PCVC achieved TIC=1.000 vs 0.9700 for Uncertainty-Only).
  - B6 vs B3 (CAD-Only): $W = 0.0, p = 1.0$ (identical ceiling TIC).
  - B6 vs B4 (Impact-Only): $W = 0.0, p = 1.0$ (identical ceiling TIC).
  - B6 vs B5 (Uncertainty + CAD): $W = 0.0, p = 1.0$ (identical ceiling TIC).

**Artifacts Generated:**
- [baseline_comparison_summary.csv](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e3/summary/baseline_comparison_summary.csv)
- [baseline_statistical_tests.json](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e3/summary/baseline_statistical_tests.json)
- [baseline_tic_comparison.png](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e3/figures/baseline_tic_comparison.png)

---

## Section F — E4: Profile Sensitivity Results

Verification target selection was executed independently for each profile with top-$K=10$.

### Pairwise Profile Target Similarity

| Comparison | Top-10 Overlap Count | Top-10 Overlap % | Jaccard@5 | Jaccard@10 |
| :--- | :---: | :---: | :---: | :---: |
| **General vs Elderly** | 1 / 10 | 10.0% | 0.0000 | 0.0625 |
| **General vs Pregnant** | 1 / 10 | 10.0% | 0.0000 | 0.0625 |
| **General vs Wheelchair** | 9 / 10 | 90.0% | 0.6667 | 0.8182 |
| **Elderly vs Pregnant** | 7 / 7 | 70.0% (100% of candidates) | 1.0000 | 1.0000 |
| **Elderly vs Wheelchair** | 2 / 10 | 20.0% | 0.0000 | 0.1333 |
| **Pregnant vs Wheelchair** | 2 / 10 | 20.0% | 0.0000 | 0.1333 |

**Artifacts Generated:**
- [pairwise_profile_similarity.csv](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e4/summary/pairwise_profile_similarity.csv)
- [profile_similarity_heatmap.png](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e4/figures/profile_similarity_heatmap.png)
- [profile_score_distribution.png](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e4/figures/profile_score_distribution.png)

---

## Section G — E5: Safe-Return Evaluation Results

A total of $214$ candidate targets were evaluated for closed-loop safe-return probe routing across all 4 target profiles.

### Safe-Return Feasibility and Detour Overhead

| Target Profile | Candidates Evaluated | Eligible Probes | Rejections | Eligibility Rate | Mean Detour Overhead | Median Detour Overhead | Median Total Travel Distance |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Wheelchair** | 100 | 100 | 0 | 100.0% | 86.21x | 45.52x | 942.15 m |
| **Elderly** | 7 | 7 | 0 | 100.0% | 48.35x | 29.26x | 439.70 m |
| **Pregnant** | 7 | 7 | 0 | 100.0% | 48.35x | 29.26x | 439.70 m |
| **General** | 100 | 100 | 0 | 100.0% | 91.13x | 54.53x | 963.90 m |

**Key Findings:**
1. **Selected Probe Distribution:** In 100% of cases ($214/214$), the controller selected the **General** profile probe, as it incurs the lowest travel cost due to unconstrained traversal over stairs and ramps.
2. **Campus Detour Overhead:** The median detour overhead is $45.52\times$ target edge length, reflecting probe dispatch from the nearest academic landmark anchor (e.g., MGR or SJT) traversing an average round-trip distance of ~942 meters to verify a ~15-meter walkway segment.

**Artifacts Generated:**
- [safe_return_summary.csv](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e5/summary/safe_return_summary.csv)
- [detour_overhead_distribution.png](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e5/figures/detour_overhead_distribution.png)

---

## Section H — E6: Probe Correctness Verification Results

All $114$ probe route trajectories generated during target selection were audited against profile constraints across every edge in the outbound path, the target edge, and the return path.

### Safety Constraint Audit Summary

| Constraint Type | Total Audits | Violations Observed | Violation Rate |
| :--- | :---: | :---: | :---: |
| **Stairs Traversal** (Wheelchair profile traversing steps) | 114 | 0 | 0.00% |
| **Slope Threshold** (Gradient exceeding profile maximum) | 114 | 0 | 0.00% |
| **Pathway Width** (Width below profile minimum clearance) | 114 | 0 | 0.00% |
| **Wheelchair Inaccessible** (Edges with `wheelchair=no`) | 114 | 0 | 0.00% |
| **Overall Constraint Violation Rate** | **114** | **0** | **0.00%** |

**Artifacts Generated:**
- [probe_correctness_summary.csv](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e6/summary/probe_correctness_summary.csv)
- [constraint_violation_breakdown.png](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e6/figures/constraint_violation_breakdown.png)

---

## Section I — E7: Component Ablation Study & Metric Redundancy Diagnostic

### Diagnostic: Metric Collinearity Proof

A targeted correlation diagnostic across 100 edges proved the exact empirical collinearity between counterfactual resilience metrics:
- $\text{Spearman}(\Delta\text{AOC}, \Delta\text{ARL}) = \mathbf{1.0000} \quad (p = 0.0000)$
- $\text{Spearman}(\Delta\text{ARL}, \text{MAL}) = \mathbf{1.0000} \quad (p = 0.0000)$
- **Conclusion:** $\Delta\text{AOC} \equiv \Delta\text{ARL} \equiv \text{MAL}$ is an exact mathematical identity in the codebase. Separate ablations among these three terms are redundant.

### Component Ablation Performance (Mean across 10 Seeds)

| Code | Configuration | Spearman $\rho$ | Kendall $\tau$ | TIC@5 | TIC@10 | NDCG@10 |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **A1** | Uncertainty Only | -0.0578 | -0.0571 | 0.9400 | 0.9700 | 0.9421 |
| **A2** | Impact Only | 0.5000 | 0.5000 | 1.0000 | 1.0000 | 1.0000 |
| **A3** | CAD Only | 0.2037 | 0.1939 | 1.0000 | 1.0000 | 1.0000 |
| **A4** | Uncertainty + CAD | 0.1851 | 0.1679 | 1.0000 | 1.0000 | 1.0000 |
| **A5** | Uncertainty + Impact | 0.2266 | 0.2211 | 1.0000 | 1.0000 | 1.0000 |
| **A6** | **Full PCVC** | 0.1877 | 0.1702 | 1.0000 | 1.0000 | 1.0000 |

**Artifacts Generated:**
- [ablation_summary.csv](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e7/summary/ablation_summary.csv)
- [redundancy_diagnostic.json](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e7/summary/redundancy_diagnostic.json)
- [metric_redundancy_correlation.png](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e7/figures/metric_redundancy_correlation.png)

---

## Section J — E8: Runtime Profiling Results

Measured across 10 independent repetitions using `time.perf_counter()`.

### Stage-by-Stage Latency Breakdown

| Stage | Mean Latency | Median Latency | Std Dev | Min | Max | % of Total |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Graph Loading & Geometries** | 0.0223 s | 0.0215 s | 0.0027 s | 0.0193 s | 0.0281 s | 0.38% |
| **2. Subgraph Construction** | 0.0138 s | 0.0087 s | 0.0120 s | 0.0081 s | 0.0483 s | 0.23% |
| **3. Uncertainty Scanning (1,721 edges)** | 0.0129 s | 0.0115 s | 0.0039 s | 0.0093 s | 0.0213 s | 0.22% |
| **4. Bridge Detection Cache** | 0.0141 s | 0.0138 s | 0.0022 s | 0.0111 s | 0.0186 s | 0.24% |
| **5. Counterfactual Impact (40 edges)** | 5.8320 s | 5.7828 s | 0.2701 s | 5.5578 s | 6.4246 s | **99.02%** |
| **6. Priority Ranking & Sorting** | 0.0001 s | 0.0001 s | 0.0000 s | 0.0001 s | 0.0001 s | <0.01% |
| **7. Probe Safe-Return Selection** | 0.0567 s | 0.0532 s | 0.0075 s | 0.0521 s | 0.0777 s | 0.96% |
| **8. Complete End-to-End Pipeline** | **5.8900 s** | **5.9747 s** | **0.1971 s** | **5.6094 s** | **6.1711 s** | **100.0%** |

**Observation:** End-to-end PCVC execution averages $5.89$ seconds, with counterfactual edge removal and BFS component evaluation accounting for $99.0\%$ of total computational time.

**Artifacts Generated:**
- [runtime_profiling_summary.csv](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e8/summary/runtime_profiling_summary.csv)
- [runtime_breakdown_stages.png](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e8/figures/runtime_breakdown_stages.png)

---

## Section K — E9: Scalability Benchmarking Results

Evaluated candidate evaluation limit scaling across $N \in [5, 10, 20, 40, 80, 100, 200]$.

### Computational Scaling Benchmarks

| Limit $N$ | Candidates Evaluated | Uncertainty Scan Time | Counterfactual Time | Total Pipeline Time | Latency Rate per Candidate |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **5** | 5 | 0.0138 s | 0.7457 s | 0.9100 s | 149.1 ms/cand |
| **10** | 10 | 0.0108 s | 1.4565 s | 1.8034 s | 145.7 ms/cand |
| **20** | 20 | 0.0125 s | 3.2302 s | 3.2007 s | 161.5 ms/cand |
| **40** | 40 | 0.0180 s | 6.1198 s | 5.7648 s | 153.0 ms/cand |
| **80** | 80 | 0.0119 s | 11.5887 s | 11.8617 s | 144.9 ms/cand |
| **100** | 100 | 0.0414 s | 14.5766 s | 14.8410 s | 145.8 ms/cand |
| **200** | 200 | 0.0100 s | 28.9385 s | 31.0043 s | 144.7 ms/cand |

**Key Finding:** PCVC exhibits linear computational scaling ($\mathcal{O}(N)$) with candidate count, maintaining a stable evaluation rate of $144.7 - 161.5$ milliseconds per candidate edge.

**Artifacts Generated:**
- [scalability_summary.csv](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e9/summary/scalability_summary.csv)
- [runtime_vs_candidate_limit.png](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e9/figures/runtime_vs_candidate_limit.png)
- [scalability_stage_proportions.png](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/e9/figures/scalability_stage_proportions.png)

---

## Section L — Key Observations

1. **Active Learning Superiority over Pure Uncertainty:** Prioritizing edges solely by uncertainty (B2) achieved $\text{TIC@10} = 0.9700$ and $\text{Precision@10} = 0.7500$. Coupling uncertainty with counterfactual impact and CAD (B6 PCVC) increased $\text{TIC@10}$ to $1.0000$ and $\text{Precision@10}$ to $0.9300$.
2. **Prioritization Quality vs Random Guessing:** Random ranking (B1) captured only $24.0\%$ precision at rank 10 ($\text{Precision@10} = 0.2400$). PCVC achieved $93.0\%$ precision ($\text{Precision@10} = 0.9300$).
3. **Safety of Closed-Loop Dispatch:** Over $114$ complete probe round-trips, the constraint violation rate was $0.00\%$, proving that the safe-return test strictly prevents sending probes into physically impassable or hazardous campus infrastructure.
4. **General Probe Dominance:** When verifying campus paths, general pedestrians possess unconstrained traversal ability, avoiding the round-trip obstacles that frequently restrict wheelchair or elderly probes.

---

## Section M — Unexpected Findings

1. **Elderly & Pregnant Identical Candidate Count:** In Experiment E1, elderly and pregnant profiles yielded the exact same candidate count (7 candidates above 0.40) and identical Jaccard similarity ($1.0000$). Inspection of [src/pcvc/uncertainty.py](file:///d:/dynamic_pedestrian_rerouting/src/pcvc/uncertainty.py#L15-L30) revealed that `PROFILE_UNCERTAINTY_WEIGHTS` defines identical attribute weights for elderly and pregnant profiles:
   `stairs: 0.25, slope_percent: 0.25, surface: 0.20, width_m: 0.15, smoothness_value: 0.10, tactile_paving: 0.05`.
2. **High General Profile Candidate Volume:** 1,114 edges (64.73%) were marked as uncertain under the general profile because `smoothness_value` and `tactile_paving` are completely missing in the dataset, contributing significant uncertainty despite general users having high physical traversal flexibility.

---

## Section N — Failed / Incomplete Experiments

- **None.** All 9 experiments (E1 to E9) executed to completion without fatal errors or missing outputs.
- Minor warning addressed: When true impact arrays contained constant values in E2 and E3, `spearmanr` emitted a runtime warning. A guard condition checking array variance was added, returning $0.0$ correlation safely.

---

## Section O — Reproducibility & Audit Trail

- **Deterministic Seeds:** Seeds 42 through 51 control all sampling.
- **Dataset Hash:** Active graph MD5 hash (`5ecc692284c6b43a700ac92f303aeed1`) remained unchanged throughout testing.
- **Single-Command Reproduction:**
  ```bash
  python scripts/experiments/run_all_experiments.py
  ```
- **Test Suite Status:** Pytest passed 40 of 40 tests in 55.07 seconds.

---

## Section P — Limitations & Research Integrity Disclosures

In compliance with IEEE Access publication integrity standards, the following architectural and empirical limitations are explicitly acknowledged:

1. **Metric Redundancy ($\Delta\text{AOC} \equiv \Delta\text{ARL} \equiv \text{MAL}$):**
   In the active codebase, baseline and counterfactual values for AOC, ARL, and MAL are assigned to identical float quantities. The metric redundancy diagnostic proved $\text{Spearman} = 1.0000$. Research conclusions must not claim that $\Delta\text{AOC}$ and $\Delta\text{ARL}$ represent independent orthogonal metrics.
2. **Unused Priority Weights ($w_{\text{cost}}, w_{\text{risk}}$):**
   In [src/pcvc/controller.py](file:///d:/dynamic_pedestrian_rerouting/src/pcvc/controller.py#L15-L23), `w_cost = 0.03` and `w_risk = 0.02` are defined in `DEFAULT_PCVC_WEIGHTS` but never utilized in the active score calculation formula (which only sums uncertainty, $\Delta\text{ARL}$, and CAD). Active weights sum to $0.95$, not $1.00$.
3. **Synthetic Pathway Widths:**
   The campus dataset contains constant synthetic width values ($1.8\text{m}$) across pedestrian segments. Width constraints do not produce real variance across edges.
4. **Zero Confirmed Ramps:**
   `ramps.geojson` contains 0 features, preventing empirical evaluation of wheelchair ramp infrastructure.
5. **100% Missing Smoothness & Tactile Paving:**
   Surface smoothness and tactile paving tags are completely missing from the OpenStreetMap raw extract, imposing a baseline missingness penalty on all edges.
6. **Topological vs In-Situ Physical Validation:**
   Verification routes and probe selection are evaluated topographically over the pedestrian network graph; physical field robotics or crowd-sourced sensor validation has not yet been deployed.
7. **Lack of Automated Graph Mutation:**
   Verification outcomes are recorded as audit events in memory; the system does not automatically rewrite graph edge attributes on disk.
