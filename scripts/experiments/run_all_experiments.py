"""
PCVC Phase 6 Master Experiment Runner
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Orchestrates execution of the entire PCVC Phase 6 experimental harness (E1 through E9):
- E1: Natural Uncertainty Distribution
- E2: Oracle Hold-Out / Masking
- E3: Baseline Ranking Comparison
- E4: Profile Sensitivity
- E5: Safe-Return Probe Evaluation
- E6: Probe Correctness Verification
- E7: Component Ablation & Redundancy Diagnostic
- E8: Execution Runtime Profiling
- E9: Candidate Scalability Benchmarking

Generates consolidated master results:
- results/pcvc/MASTER_RESULTS.json
- results/pcvc/MASTER_RESULTS.csv
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd

# Ensure project root is accessible
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.experiments.common import (
    load_active_graph,
    graph_statistics,
    get_environment_info,
    RESULTS_BASE_DIR,
    save_json,
    save_csv
)

from scripts.experiments.run_e1_uncertainty import run_e1
from scripts.experiments.run_e2_oracle_masking import run_e2
from scripts.experiments.run_e3_baselines import run_e3
from scripts.experiments.run_e4_profile_sensitivity import run_e4
from scripts.experiments.run_e5_safe_return import run_e5
from scripts.experiments.run_e6_probe_correctness import run_e6
from scripts.experiments.run_e7_ablation import run_e7
from scripts.experiments.run_e8_runtime import run_e8
from scripts.experiments.run_e9_scalability import run_e9


KNOWN_LIMITATIONS_AND_WARNINGS = [
    {
        "issue": "Metric Redundancy / Collinearity",
        "description": "delta_AOC, delta_ARL, and MAL are mathematically identical (Spearman rho = 1.0000) in the active codebase. delta_ARL is utilized as the unified counterfactual impact metric.",
        "status": "EXPLICITLY_DOCUMENTED"
    },
    {
        "issue": "Unused Priority Score Weights",
        "description": "w_cost (0.03) and w_risk (0.02) are defined in DEFAULT_PCVC_WEIGHTS in src/pcvc/controller.py but omitted from the active priority score formula. Active weights sum to 0.95.",
        "status": "EXPLICITLY_DOCUMENTED"
    },
    {
        "issue": "Synthetic Pathway Widths",
        "description": "Pathway width values (width_m = 1.8) are uniform synthetic defaults across pedestrian edges, precluding empirical width-filtering discrimination.",
        "status": "EXPLICITLY_DOCUMENTED"
    },
    {
        "issue": "Zero Confirmed Ramps in Campus Extent",
        "description": "The active dataset contains 0 confirmed ramp tags (ramps.geojson has 0 features), limiting ramp-specific counterfactual evaluation.",
        "status": "EXPLICITLY_DOCUMENTED"
    },
    {
        "issue": "100% Missing Smoothness & Tactile Paving",
        "description": "All 1,721 edges lack smoothness_value and tactile_paving tags. These contribute constant missingness penalty in profile uncertainty weights.",
        "status": "EXPLICITLY_DOCUMENTED"
    },
    {
        "issue": "Physical IoT Probe In-Situ Validation",
        "description": "Probe feasibility is evaluated using topological shortest-path and obstacle verification over the graph; real-world physical robot/sensor deployment remains future work.",
        "status": "EXPLICITLY_DOCUMENTED"
    },
    {
        "issue": "Closed-Loop Automated Graph Mutation",
        "description": "The current PCVC implementation records verification events in memory; automatic mutation of graph edge attributes on disk is not enabled.",
        "status": "EXPLICITLY_DOCUMENTED"
    }
]


def run_all(selected_experiments: List[str] = None, full_runs: bool = True) -> Dict[str, Any]:
    print("=" * 80)
    print("PCVC PHASE 6 MASTER EXPERIMENT RUNNER")
    print("Target Publication: IEEE Access")
    print("Dataset: VIT Vellore Academic Pedestrian Network (1551 nodes, 1721 edges)")
    print("=" * 80)

    t_start = time.perf_counter()

    G = load_active_graph()
    g_stats = graph_statistics(G)
    env_info = get_environment_info()

    if selected_experiments is None:
        selected_experiments = ["e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8", "e9"]

    selected_experiments = [e.lower() for e in selected_experiments]

    master_results = {
        "title": "PCVC Phase 6 Master Experimental Results",
        "project": "Profile-Coupled Counterfactual Verification Controller (PCVC)",
        "target_publication": "IEEE Access",
        "graph_statistics": g_stats,
        "runtime_environment": env_info,
        "experiment_parameters": {
            "selected_experiments": selected_experiments,
            "deterministic_seeds": [42, 43, 44, 45, 46, 47, 48, 49, 50, 51],
            "profiles": ["general", "elderly", "pregnant", "wheelchair"],
            "uncertainty_threshold": 0.40,
            "default_candidate_limit": 40
        },
        "experiments": {},
        "limitations_and_warnings": KNOWN_LIMITATIONS_AND_WARNINGS
    }

    # E1
    if "e1" in selected_experiments:
        print("\n>>> RUNNING E1: Natural Uncertainty Distribution...")
        master_results["experiments"]["e1"] = run_e1()

    # E2
    if "e2" in selected_experiments:
        print("\n>>> RUNNING E2: Oracle Hold-Out / Masking...")
        k_vals = [20, 40, 80] if full_runs else [20, 40]
        seeds = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
        master_results["experiments"]["e2"] = run_e2(k_values=k_vals, seeds=seeds)

    # E3
    if "e3" in selected_experiments:
        print("\n>>> RUNNING E3: Baseline Ranking Comparison...")
        seeds = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
        master_results["experiments"]["e3"] = run_e3(seeds=seeds, pool_size=40)

    # E4
    if "e4" in selected_experiments:
        print("\n>>> RUNNING E4: Profile Sensitivity...")
        master_results["experiments"]["e4"] = run_e4()

    # E5
    if "e5" in selected_experiments:
        print("\n>>> RUNNING E5: Safe-Return Probe Evaluation...")
        master_results["experiments"]["e5"] = run_e5(candidate_limit=100)

    # E6
    if "e6" in selected_experiments:
        print("\n>>> RUNNING E6: Probe Correctness Verification...")
        master_results["experiments"]["e6"] = run_e6(candidate_limit=50)

    # E7
    if "e7" in selected_experiments:
        print("\n>>> RUNNING E7: Component Ablation & Redundancy Diagnostic...")
        seeds = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
        master_results["experiments"]["e7"] = run_e7(seeds=seeds, pool_size=40)

    # E8
    if "e8" in selected_experiments:
        print("\n>>> RUNNING E8: Execution Runtime Profiling...")
        master_results["experiments"]["e8"] = run_e8(repetitions=10)

    # E9
    if "e9" in selected_experiments:
        print("\n>>> RUNNING E9: Candidate Scalability Benchmarking...")
        limits = [5, 10, 20, 40, 80, 100, 200]
        master_results["experiments"]["e9"] = run_e9(limits=limits)

    t_total = time.perf_counter() - t_start
    master_results["total_execution_time_seconds"] = round(t_total, 2)

    # Save MASTER_RESULTS.json
    json_path = RESULTS_BASE_DIR / "MASTER_RESULTS.json"
    save_json(master_results, json_path)
    print(f"\nSaved master JSON results: {json_path}")

    # Build MASTER_RESULTS.csv with summary rows
    csv_rows: List[Dict[str, Any]] = []

    # E1 summary row
    if "e1" in master_results["experiments"]:
        e1_data = master_results["experiments"]["e1"]
        for prof, stat in e1_data.get("profile_summaries", {}).items():
            csv_rows.append({
                "experiment": "E1_Natural_Uncertainty",
                "sub_experiment": prof,
                "metric_1_name": "mean_uncertainty",
                "metric_1_val": stat.get("mean_uncertainty"),
                "metric_2_name": "candidates_above_0.4",
                "metric_2_val": stat.get("candidate_count_above_threshold"),
                "metric_3_name": "candidate_pct",
                "metric_3_val": stat.get("candidate_pct_above_threshold"),
                "notes": f"Edges evaluated: {stat.get('total_edges')}"
            })

    # E2 summary rows
    if "e2" in master_results["experiments"]:
        e2_data = master_results["experiments"]["e2"]
        for k_key, k_stat in e2_data.get("k_aggregates", {}).items():
            csv_rows.append({
                "experiment": "E2_Oracle_Masking",
                "sub_experiment": f"K={k_stat.get('k_masked')}",
                "metric_1_name": "tic_at_10_mean",
                "metric_1_val": k_stat.get("tic_at_10_mean"),
                "metric_2_name": "ndcg_at_10_mean",
                "metric_2_val": k_stat.get("ndcg_at_10_mean"),
                "metric_3_name": "spearman_rho_mean",
                "metric_3_val": k_stat.get("spearman_rho_mean"),
                "notes": f"Precision@10: {k_stat.get('precision_at_10_mean')}, 10 seeds"
            })

    # E3 summary rows
    if "e3" in master_results["experiments"]:
        e3_data = master_results["experiments"]["e3"]
        for b_stat in e3_data.get("baseline_summaries", []):
            csv_rows.append({
                "experiment": "E3_Baseline_Comparison",
                "sub_experiment": f"{b_stat.get('baseline_code')} ({b_stat.get('baseline_name')})",
                "metric_1_name": "tic_at_10_mean",
                "metric_1_val": b_stat.get("tic_at_10_mean"),
                "metric_2_name": "ndcg_at_10_mean",
                "metric_2_val": b_stat.get("ndcg_at_10_mean"),
                "metric_3_name": "spearman_rho_mean",
                "metric_3_val": b_stat.get("spearman_rho_mean"),
                "notes": f"Precision@10: {b_stat.get('precision_at_10_mean')}"
            })

    # E4 summary rows
    if "e4" in master_results["experiments"]:
        e4_data = master_results["experiments"]["e4"]
        for pw in e4_data.get("pairwise_similarity", []):
            csv_rows.append({
                "experiment": "E4_Profile_Sensitivity",
                "sub_experiment": pw.get("comparison"),
                "metric_1_name": "top10_overlap_pct",
                "metric_1_val": pw.get("top10_overlap_pct"),
                "metric_2_name": "jaccard_at_5",
                "metric_2_val": pw.get("jaccard_at_5"),
                "metric_3_name": "jaccard_at_10",
                "metric_3_val": pw.get("jaccard_at_10"),
                "notes": f"Overlap count: {pw.get('top10_overlap_count')}/10"
            })

    # E5 summary rows
    if "e5" in master_results["experiments"]:
        e5_data = master_results["experiments"]["e5"]
        for s in e5_data.get("target_profile_summaries", []):
            csv_rows.append({
                "experiment": "E5_Safe_Return",
                "sub_experiment": s.get("target_profile"),
                "metric_1_name": "eligibility_rate_pct",
                "metric_1_val": s.get("eligibility_rate_pct"),
                "metric_2_name": "detour_overhead_mean",
                "metric_2_val": s.get("detour_overhead_mean"),
                "metric_3_name": "travel_distance_m_median",
                "metric_3_val": s.get("travel_distance_m_median"),
                "notes": f"Candidates evaluated: {s.get('total_candidates')}"
            })

    # E6 summary row
    if "e6" in master_results["experiments"]:
        e6_data = master_results["experiments"]["e6"]
        csv_rows.append({
            "experiment": "E6_Probe_Correctness",
            "sub_experiment": "all_profiles",
            "metric_1_name": "constraint_violation_rate_pct",
            "metric_1_val": e6_data.get("constraint_violation_rate_pct"),
            "metric_2_name": "valid_assignments",
            "metric_2_val": e6_data.get("valid_assignments"),
            "metric_3_name": "invalid_assignments",
            "metric_3_val": e6_data.get("invalid_assignments"),
            "notes": f"Violations: Stairs={e6_data.get('violation_counts_by_constraint', {}).get('stairs', 0)}"
        })

    # E7 summary rows
    if "e7" in master_results["experiments"]:
        e7_data = master_results["experiments"]["e7"]
        for s in e7_data.get("ablation_summaries", []):
            csv_rows.append({
                "experiment": "E7_Ablation",
                "sub_experiment": f"{s.get('ablation_code')} ({s.get('ablation_name')})",
                "metric_1_name": "tic_at_10_mean",
                "metric_1_val": s.get("tic_at_10_mean"),
                "metric_2_name": "ndcg_at_10_mean",
                "metric_2_val": s.get("ndcg_at_10_mean"),
                "metric_3_name": "spearman_rho_mean",
                "metric_3_val": s.get("spearman_rho_mean"),
                "notes": "Redundancy: delta_AOC == delta_ARL == MAL (Spearman=1.0)"
            })

    # E8 summary row
    if "e8" in master_results["experiments"]:
        e8_data = master_results["experiments"]["e8"]
        e2e_stat = next((s for s in e8_data.get("stage_summaries", []) if "end_to_end" in s.get("stage_key", "")), {})
        cf_stat = next((s for s in e8_data.get("stage_summaries", []) if "counterfactual" in s.get("stage_key", "")), {})
        csv_rows.append({
            "experiment": "E8_Runtime_Profiling",
            "sub_experiment": "pipeline_breakdown",
            "metric_1_name": "end_to_end_latency_s",
            "metric_1_val": e2e_stat.get("mean_seconds"),
            "metric_2_name": "counterfactual_latency_s",
            "metric_2_val": cf_stat.get("mean_seconds"),
            "metric_3_name": "latency_std_s",
            "metric_3_val": e2e_stat.get("std_seconds"),
            "notes": f"N={e8_data.get('num_repetitions')} repetitions, Candidate limit: {e8_data.get('candidate_limit')}"
        })

    # E9 summary rows
    if "e9" in master_results["experiments"]:
        e9_data = master_results["experiments"]["e9"]
        for r in e9_data.get("results", []):
            csv_rows.append({
                "experiment": "E9_Scalability",
                "sub_experiment": f"Limit_N={r.get('candidate_limit')}",
                "metric_1_name": "total_runtime_s",
                "metric_1_val": r.get("total_runtime_s"),
                "metric_2_name": "counterfactual_time_s",
                "metric_2_val": r.get("counterfactual_time_s"),
                "metric_3_name": "ms_per_candidate",
                "metric_3_val": r.get("ms_per_candidate"),
                "notes": f"Evaluated: {r.get('candidates_evaluated')}"
            })

    csv_path = RESULTS_BASE_DIR / "MASTER_RESULTS.csv"
    save_csv(csv_rows, csv_path)
    print(f"Saved master CSV results: {csv_path} ({len(csv_rows)} configuration rows)")

    print("\n" + "=" * 80)
    print(f"PHASE 6 EXECUTION COMPLETE IN {t_total:.1f} SECONDS")
    print(f"All experiment artifacts successfully generated in {RESULTS_BASE_DIR}")
    print("=" * 80)

    return master_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PCVC Phase 6 Master Experiment Runner")
    parser.add_argument("--experiments", nargs="+", choices=["e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8", "e9", "all"],
                        default=["all"], help="Specific experiments to run")
    parser.add_argument("--quick", action="store_true", help="Run with reduced parameters for fast smoke test")
    args = parser.parse_args()

    selected = None if "all" in args.experiments else args.experiments
    run_all(selected_experiments=selected, full_runs=(not args.quick))
