# PCVC Phase 6 Research Experiment Harness
**Project:** Profile-Coupled Counterfactual Verification Controller (PCVC) for Accessibility-Aware Pedestrian Networks  
**Target Publication:** IEEE Access  
**Dataset:** VIT Vellore Academic Pedestrian Network (`data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl`)  
**Network Dimensions:** 1,551 nodes, 1,721 edges, undirected NetworkX `MultiGraph`, 9 connected components (largest = 1,509 nodes).

---

## 1. Overview and Architecture

The Phase 6 experimental harness provides an empirical evaluation framework for prioritizing uncertain pedestrian network accessibility attributes through counterfactual resilience degradation and closed-loop safe-return probe routing.

All experiments are completely reproducible, non-destructive (operating on in-memory deep copies without modifying the active dataset on disk), and deterministic across controlled random seeds.

### Experiment Inventory

| Experiment | Title | Description | Primary Metric |
| :--- | :--- | :--- | :--- |
| **E1** | Natural Uncertainty Distribution | Census of accessibility uncertainty across all 1,721 edges for all 4 profiles | Mean / Median Uncertainty, Candidate Count ($\ge 0.40$) |
| **E2** | Oracle Hold-Out / Masking | Main research experiment evaluating prioritization against ground-truth degradation impact | $\Delta\text{ARL}$, TIC@10, NDCG@10, Spearman $\rho$ |
| **E3** | Baseline Ranking Comparison | Comparative benchmark of PCVC against 5 standard active learning & structural heuristics | TIC@10, NDCG@10, Wilcoxon $p$-values |
| **E4** | Profile Sensitivity | Pairwise differentiation across General, Elderly, Pregnant, and Wheelchair | Top-10 Jaccard Similarity, Overlap % |
| **E5** | Safe-Return Probe Evaluation | Feasibility and detour overhead of closed-loop probe verification routes | Eligibility %, Detour Overhead Ratio |
| **E6** | Probe Correctness Verification | Trajectory constraint auditing (stairs, slope, width) for dispatched probes | Constraint Violation Rate (Ideal = 0.0%) |
| **E7** | Component Ablation Study | Contribution of uncertainty, counterfactual impact, and CAD components | TIC@10, Redundancy Diagnostic Correlation |
| **E8** | Execution Runtime Profiling | High-precision latency profiling across all 8 pipeline stages (10 repetitions) | Latency (s) per stage, End-to-end runtime |
| **E9** | Candidate Scalability Benchmarking | Computational scaling as candidate evaluation limit $N$ scales from 5 to 200 | Latency (s) vs $N$, ms per candidate |

---

## 2. How to Run

### Environment Requirements
- Python `3.14.2` (virtual environment at `.venv`)
- Key packages: `networkx`, `numpy`, `pandas`, `scipy`, `matplotlib`, `shapely`, `geopandas`
- Working directory: Repository root (`d:\dynamic_pedestrian_rerouting`)

### Running Individual Experiments
```bash
# E1: Natural Uncertainty Distribution
python scripts/experiments/run_e1_uncertainty.py

# E2: Oracle Hold-Out / Masking (10 seeds, K=20, 40, 80)
python scripts/experiments/run_e2_oracle_masking.py

# E3: Baseline Ranking Comparison
python scripts/experiments/run_e3_baselines.py

# E4: Profile Sensitivity
python scripts/experiments/run_e4_profile_sensitivity.py

# E5: Safe-Return Probe Evaluation
python scripts/experiments/run_e5_safe_return.py

# E6: Probe Correctness Verification
python scripts/experiments/run_e6_probe_correctness.py

# E7: Metric / Component Ablation
python scripts/experiments/run_e7_ablation.py

# E8: Execution Runtime Profiling
python scripts/experiments/run_e8_runtime.py

# E9: Candidate Scalability Benchmarking
python scripts/experiments/run_e9_scalability.py
```

### Running All Experiments Sequentially
```bash
# Full execution of E1 through E9, producing MASTER_RESULTS.json and MASTER_RESULTS.csv
python scripts/experiments/run_all_experiments.py

# Fast smoke-test mode with reduced parameters
python scripts/experiments/run_all_experiments.py --quick
```

---

## 3. Directory and Output Structure

All outputs are saved to `results/pcvc/`:

```
results/pcvc/
├── MASTER_RESULTS.json                 # Consolidated machine-readable JSON across all experiments
├── MASTER_RESULTS.csv                  # Tabular summary of all experimental configurations
├── PHASE6_EXECUTION_REPORT.md          # Comprehensive execution and findings report
├── e1/
│   ├── raw/edge_uncertainty_all_profiles.csv
│   ├── summary/profile_uncertainty_summary.csv
│   ├── summary/uncertainty_frequency_bins.csv
│   ├── summary/e1_summary.json
│   └── figures/
│       ├── uncertainty_hist_*.png
│       └── uncertainty_distribution_comparison.png
├── e2/
│   ├── raw/oracle_edge_results.csv
│   ├── summary/oracle_summary.csv
│   ├── summary/oracle_summary.json
│   └── figures/
│       ├── tic_ndcg_by_k.png
│       └── spearman_distribution.png
├── e3/
│   ├── raw/baseline_run_results.csv
│   ├── summary/baseline_comparison_summary.csv
│   ├── summary/baseline_statistical_tests.json
│   ├── summary/e3_summary.json
│   └── figures/
│       ├── baseline_tic_comparison.png
│       └── baseline_ndcg_comparison.png
├── e4/
│   ├── raw/profile_rankings_top10.csv
│   ├── summary/pairwise_profile_similarity.csv
│   ├── summary/e4_summary.json
│   └── figures/
│       ├── profile_similarity_heatmap.png
│       └── profile_score_distribution.png
├── e5/
│   ├── raw/safe_return_evaluations.csv
│   ├── summary/safe_return_summary.csv
│   ├── summary/safe_return_by_rejection.csv
│   ├── summary/e5_summary.json
│   └── figures/
│       ├── rejection_reasons.png
│       └── detour_overhead_distribution.png
├── e6/
│   ├── raw/probe_correctness_evaluations.csv
│   ├── summary/probe_correctness_summary.csv
│   ├── summary/e6_summary.json
│   └── figures/constraint_violation_breakdown.png
├── e7/
│   ├── raw/ablation_run_results.csv
│   ├── summary/ablation_summary.csv
│   ├── summary/redundancy_diagnostic.json
│   ├── summary/e7_summary.json
│   └── figures/
│       ├── ablation_tic_ndcg.png
│       └── metric_redundancy_correlation.png
├── e8/
│   ├── raw/runtime_profiling_runs.csv
│   ├── summary/runtime_profiling_summary.csv
│   ├── summary/e8_summary.json
│   └── figures/
│       ├── runtime_breakdown_stages.png
│       └── runtime_repetitions_distribution.png
└── e9/
    ├── raw/scalability_runs.csv
    ├── summary/scalability_summary.csv
    ├── summary/e9_summary.json
    └── figures/
        ├── runtime_vs_candidate_limit.png
        └── scalability_stage_proportions.png
```

---

## 4. Primary Metrics and Mathematical Definitions

### A. Total Impact Captured at K (TIC@K)
Measures the fraction of total potential network degradation impact captured by the top-$K$ selected edges compared to an optimal oracle selector:
$$\text{TIC@K} = \frac{\sum_{i=1}^K \text{Impact}(\text{Pred}_i)}{\sum_{i=1}^K \text{Impact}(\text{Oracle}_i)}$$
If the denominator is 0 (all held-out edges have zero degradation impact), $\text{TIC@K} = 1.0$.

### B. Normalized Discounted Cumulative Gain at K (NDCG@K)
Evaluates graded ranking quality, heavily penalizing placing high-impact bottlenecks low in the priority queue:
$$\text{DCG@K} = \sum_{i=1}^K \frac{\text{Impact}(\text{Pred}_i)}{\log_2(i + 1)}, \quad \text{NDCG@K} = \frac{\text{DCG@K}}{\text{IDCG@K}}$$

### C. Precision@K and Hit@K
- $\text{Hit@K} = 1$ if at least one oracle top-$K$ bottleneck is present in predicted top-$K$, else $0$.
- $\text{Precision@K} = \frac{|\text{Top}_K(\text{Pred}) \cap \text{Top}_K(\text{Oracle})|}{K}$.

### D. Safe-Return Detour Overhead Ratio
Quantifies the routing overhead required to dispatch a probe from the nearest campus landmark anchor to verify target edge $(u, v)$ and return to the anchor:
$$\text{Detour Overhead} = \frac{\text{dist}(\text{Anchor} \to u) + \text{dist}(v \to \text{Anchor})}{\text{length}(u, v)}$$

---

## 5. Research Integrity & Implementation Diagnostics

To uphold rigorous scientific standards for IEEE Access, the following verified implementation properties are explicitly documented rather than concealed:

1. **Metric Redundancy ($\Delta\text{AOC} \equiv \Delta\text{ARL} \equiv \text{MAL}$):**
   In the active codebase (`src/pcvc/counterfactual.py` and `src/darr/resilience.py`), `delta_arl == float(delta_aoc)` and `mal_impact == delta_arl`. As empirically proven in Experiment E7 (`Spearman = 1.0000`), these three metrics are mathematically identical. Therefore, $\Delta\text{ARL}$ is used as the single counterfactual impact metric in all research experiments.

2. **Unused Priority Weights ($w_{\text{cost}}, w_{\text{risk}}$):**
   In `src/pcvc/controller.py`, `w_cost = 0.03` and `w_risk = 0.02` are defined in `DEFAULT_PCVC_WEIGHTS` but omitted from the active priority score calculation. The active priority score is:
   $$\text{Score}_{\text{PCVC}} = 0.25 \cdot \tilde{U} + 0.55 \cdot \Delta\widetilde{\text{ARL}} + 0.15 \cdot \text{CAD}$$
   Active weights sum to $0.95$.

3. **Uniform Synthetic Pathway Widths:**
   The active dataset uses synthetic constant width defaults ($1.8\text{m}$) across edges, precluding meaningful width-filtering variation in current experiments.

4. **Zero Confirmed Campus Ramps:**
   `ramps.geojson` contains 0 features; ramp attributes cannot be evaluated as an active obstacle factor.

5. **100% Missing Smoothness & Tactile Paving:**
   All 1,721 edges currently lack `smoothness_value` and `tactile_paving` tags, acting as uniform penalties in uncertainty scoring.

---

## 6. How Oracle Masking Works (Experiment E2)

1. The clean graph $G_{\text{base}}$ contains $N = 324$ edges with confirmed wheelchair accessibility tags (`wheelchair="yes"` or `"no"`).
2. For each random seed, $K \in \{20, 40, 80\}$ edges are deterministically sampled.
3. An in-memory deep copy $G_{\text{masked}}$ is created; the sampled edges have their `wheelchair` tag set to `"unknown"`.
4. On $G_{\text{base}}$, ground-truth counterfactual degradation impact ($\Delta\text{ARL}$) is evaluated for each held-out edge, establishing the Oracle Ranking.
5. On $G_{\text{masked}}$, PCVC computes verification priority scores based solely on incomplete evidence.
6. The predicted ranking of the held-out edges is directly compared against the oracle ranking.

---

## 7. Controlling Random Seeds

Randomness is strictly controlled across experiments using Python's `random.seed(s)` and NumPy's `np.random.seed(s)`.
Standard deterministic seed suite:
$$\mathcal{S} = \{42, 43, 44, 45, 46, 47, 48, 49, 50, 51\}$$
All baseline methods (E3) and ablation configurations (E7) evaluate the exact same candidate edge sets per seed.
