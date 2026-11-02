"""
PCVC Phase 6 Experiment E9: Scalability Benchmarking
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Empirically benchmarks PCVC computational scalability as candidate evaluation limit N scales:
Limits tested: [5, 10, 20, 40, 80, 100, 200]

Measures for each limit N:
- Total execution runtime
- Uncertainty scanning time
- Counterfactual impact evaluation time
- Probe safe-return selection time
- Actual candidates evaluated vs returned

Outputs:
- results/pcvc/e9/raw/scalability_runs.csv
- results/pcvc/e9/summary/scalability_summary.csv
- results/pcvc/e9/summary/e9_summary.json
- results/pcvc/e9/figures/runtime_vs_candidate_limit.png
- results/pcvc/e9/figures/scalability_stage_proportions.png
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Ensure project root is accessible
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.experiments.common import (
    load_active_graph,
    graph_statistics,
    get_environment_info,
    ensure_result_dirs,
    save_csv,
    save_json
)
from src.pcvc.uncertainty import get_uncertain_edges
from src.pcvc.counterfactual import evaluate_counterfactual_impact
from src.pcvc.probe_selector import select_best_probe
from src.pcvc.controller import pcvc_controller
from src.darr.subgraph import subgraph_manager
from src.darr.resilience import resilience_engine

TEST_LIMITS = [5, 10, 20, 40, 80, 100, 200]
PROFILE = "wheelchair"


def run_e9(limits: List[int] = TEST_LIMITS) -> Dict[str, Any]:
    dirs = ensure_result_dirs("e9")
    raw_dir = dirs["raw"]
    summary_dir = dirs["summary"]
    figures_dir = dirs["figures"]

    print("=" * 75)
    print("PCVC Experiment E9: Candidate Scalability Benchmarking")
    print("=" * 75)

    G = load_active_graph()
    g_stats = graph_statistics(G)
    env_info = get_environment_info()

    G_sub = subgraph_manager.get_accessible_subgraph(G, PROFILE)
    bc = resilience_engine._get_bridges(G_sub)

    records: List[Dict[str, Any]] = []

    for lim in limits:
        print(f"Benchmarking candidate evaluation limit N = {lim}...")

        # 1. Uncertainty Scanning Time
        t0 = time.perf_counter()
        uncertain_cands = get_uncertain_edges(G, profile=PROFILE, uncertainty_threshold=0.40, limit=lim)
        t1 = time.perf_counter()
        dur_scan = t1 - t0

        evaluated_count = len(uncertain_cands)

        # 2. Counterfactual Impact Time
        t0 = time.perf_counter()
        impacts = []
        for cand in uncertain_cands:
            imp = evaluate_counterfactual_impact(G, cand.u, cand.v, cand.key, PROFILE, bridge_cache=bc)
            impacts.append(imp)
        t1 = time.perf_counter()
        dur_cf = t1 - t0

        # 3. Probe Selection Time (top candidate)
        t0 = time.perf_counter()
        if uncertain_cands:
            top_cand = uncertain_cands[0]
            probe_res = select_best_probe(G, top_cand.u, top_cand.v, top_cand.key)
        t1 = time.perf_counter()
        dur_probe = t1 - t0

        # 4. End-to-End Pipeline Execution Time using controller
        t0 = time.perf_counter()
        plan = pcvc_controller.compute_verification_targets(
            G,
            target_profile=PROFILE,
            top_k=5,
            uncertainty_threshold=0.40,
            candidate_limit=lim
        )
        t1 = time.perf_counter()
        dur_total = t1 - t0

        returned_count = len(plan.ranked_candidates)

        records.append({
            "candidate_limit": lim,
            "candidates_evaluated": evaluated_count,
            "candidates_returned": returned_count,
            "uncertainty_scan_time_s": round(dur_scan, 4),
            "counterfactual_time_s": round(dur_cf, 4),
            "probe_selection_time_s": round(dur_probe, 4),
            "total_runtime_s": round(dur_total, 4),
            "ms_per_candidate": round((dur_cf / evaluated_count * 1000.0), 2) if evaluated_count > 0 else 0.0
        })

        print(f"  N = {lim:3d} | Total Runtime: {dur_total:.3f}s | Counterfactual: {dur_cf:.3f}s | Rate: {records[-1]['ms_per_candidate']:.1f} ms/cand")

    df_scalability = pd.DataFrame(records)
    save_csv(df_scalability, raw_dir / "scalability_runs.csv")
    save_csv(df_scalability, summary_dir / "scalability_summary.csv")

    # Figures
    # A) Runtime vs Candidate Limit
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=300)
    ax.plot(df_scalability["candidate_limit"], df_scalability["total_runtime_s"],
            marker="o", color="#2563eb", linewidth=2.0, label="Total PCVC Pipeline Runtime")
    ax.plot(df_scalability["candidate_limit"], df_scalability["counterfactual_time_s"],
            marker="s", color="#ef4444", linestyle="--", linewidth=1.8, label="Counterfactual Degradation Analysis")

    ax.axvline(x=40, color="green", linestyle=":", linewidth=1.5, label="Production Default (N=40)")
    ax.set_xlabel("Candidate Evaluation Limit (N)", fontsize=10)
    ax.set_ylabel("Execution Time (Seconds)", fontsize=10)
    ax.set_title("PCVC E9: Execution Time Scaling with Candidate Evaluation Limit", fontsize=11, fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(figures_dir / "runtime_vs_candidate_limit.png")
    plt.close(fig)

    # B) Stage Proportions Stacked Bar
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    x = np.arange(len(df_scalability))
    cf_times = df_scalability["counterfactual_time_s"].values
    other_times = (df_scalability["total_runtime_s"] - df_scalability["counterfactual_time_s"]).clip(lower=0).values

    ax.bar(x, cf_times, label="Counterfactual Impact Analysis", color="#ef4444", alpha=0.85)
    ax.bar(x, other_times, bottom=cf_times, label="Other Pipeline Stages (Scan, Subgraph, Probe)", color="#3b82f6", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([f"N={n}" for n in df_scalability["candidate_limit"]])
    ax.set_ylabel("Execution Time (Seconds)", fontsize=10)
    ax.set_title("PCVC E9: Computational Bottleneck Profile Across Scaling Limits", fontsize=11, fontweight="bold")
    ax.legend(loc="upper left")
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    plt.tight_layout()
    plt.savefig(figures_dir / "scalability_stage_proportions.png")
    plt.close(fig)

    e9_json = {
        "experiment": "E9_Scalability_Benchmarking",
        "description": "Evaluation of candidate limit scaling from N=5 to N=200",
        "tested_limits": limits,
        "results": records,
        "environment": env_info
    }
    save_json(e9_json, summary_dir / "e9_summary.json")

    print("\n--- E9 SCALABILITY SUMMARY ---")
    for r in records:
        print(f"Limit: {r['candidate_limit']:3d} | Evaluated: {r['candidates_evaluated']:3d} | Total Time: {r['total_runtime_s']:6.3f}s | CF Time: {r['counterfactual_time_s']:6.3f}s | Rate: {r['ms_per_candidate']:.1f}ms/cand")

    return e9_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PCVC E9 Scalability Benchmarking")
    parser.add_argument("--limits", nargs="+", type=int, default=TEST_LIMITS, help="Candidate limits to test")
    args = parser.parse_args()
    run_e9(limits=args.limits)
