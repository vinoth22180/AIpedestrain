"""
PCVC Phase 6 Experiment E8: Execution Runtime Profiling
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Empirically measures execution latency across all 8 modular stages of the PCVC pipeline:
1. Graph Loading & Geometry Check
2. Accessible Subgraph Construction (wheelchair constraints)
3. Uncertainty Scanning (1,721 edges evaluated)
4. Bridge / Cut-edge Topological Detection
5. Counterfactual Impact Evaluation (40 candidates)
6. Multi-Attribute Priority Ranking
7. Closed-Loop Safe-Return Probe Selection
8. End-to-End PCVC Pipeline Execution

Runs 10 independent repetitions using high-precision time.perf_counter().

Outputs:
- results/pcvc/e8/raw/runtime_profiling_runs.csv
- results/pcvc/e8/summary/runtime_profiling_summary.csv
- results/pcvc/e8/summary/e8_summary.json
- results/pcvc/e8/figures/runtime_breakdown_stages.png
- results/pcvc/e8/figures/runtime_repetitions_distribution.png
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

NUM_REPETITIONS = 10
TARGET_PROFILE = "wheelchair"
CANDIDATE_LIMIT = 40


def run_e8(repetitions: int = NUM_REPETITIONS) -> Dict[str, Any]:
    dirs = ensure_result_dirs("e8")
    raw_dir = dirs["raw"]
    summary_dir = dirs["summary"]
    figures_dir = dirs["figures"]

    print("=" * 75)
    print("PCVC Experiment E8: Execution Runtime Profiling")
    print("=" * 75)

    env_info = get_environment_info()

    stage_names = [
        "stage_1_graph_loading",
        "stage_2_subgraph_construction",
        "stage_3_uncertainty_scanning",
        "stage_4_bridge_detection",
        "stage_5_counterfactual_evaluation",
        "stage_6_candidate_ranking",
        "stage_7_probe_selection",
        "stage_8_complete_end_to_end"
    ]

    run_records: List[Dict[str, Any]] = []

    print(f"Executing {repetitions} timed repetitions across all 8 PCVC stages...")

    for rep in range(1, repetitions + 1):
        # 1. Graph Loading
        t0 = time.perf_counter()
        G = load_active_graph()
        t1 = time.perf_counter()
        dur_load = t1 - t0

        # 2. Accessible Subgraph Construction
        t0 = time.perf_counter()
        G_sub = subgraph_manager.get_accessible_subgraph(G, TARGET_PROFILE)
        t1 = time.perf_counter()
        dur_subgraph = t1 - t0

        # 3. Uncertainty Scanning
        t0 = time.perf_counter()
        uncertain_cands = get_uncertain_edges(G, profile=TARGET_PROFILE, uncertainty_threshold=0.40, limit=CANDIDATE_LIMIT)
        t1 = time.perf_counter()
        dur_uncertainty = t1 - t0

        # 4. Bridge Detection
        t0 = time.perf_counter()
        bridges = resilience_engine._get_bridges(G_sub)
        t1 = time.perf_counter()
        dur_bridge = t1 - t0

        # 5. Counterfactual Impact Evaluation (40 candidates)
        t0 = time.perf_counter()
        impacts = []
        for cand in uncertain_cands:
            imp = evaluate_counterfactual_impact(G, cand.u, cand.v, cand.key, TARGET_PROFILE, bridge_cache=bridges)
            impacts.append(imp)
        t1 = time.perf_counter()
        dur_counterfactual = t1 - t0

        # 6. Candidate Ranking
        t0 = time.perf_counter()
        max_d_arl = max([imp.delta_arl for imp in impacts] + [1.0])
        max_mal = max([imp.mal_impact for imp in impacts] + [1.0])
        scores = []
        for cand, imp in zip(uncertain_cands, impacts):
            norm_unc = cand.accessibility_uncertainty
            norm_d_arl = imp.delta_arl / max_d_arl
            norm_cad = imp.cad
            score = 0.25 * norm_unc + 0.55 * norm_d_arl + 0.15 * norm_cad
            scores.append((score, cand, imp))
        scores.sort(key=lambda x: (x[0], x[2].cad), reverse=True)
        top_cand = scores[0] if scores else None
        t1 = time.perf_counter()
        dur_ranking = t1 - t0

        # 7. Probe Selection
        t0 = time.perf_counter()
        if top_cand:
            probe_res = select_best_probe(G, top_cand[1].u, top_cand[1].v, top_cand[1].key)
        t1 = time.perf_counter()
        dur_probe = t1 - t0

        # 8. Complete End-to-End PCVC Pipeline Execution
        t0 = time.perf_counter()
        plan = pcvc_controller.compute_verification_targets(
            G,
            target_profile=TARGET_PROFILE,
            top_k=5,
            uncertainty_threshold=0.40,
            candidate_limit=CANDIDATE_LIMIT
        )
        t1 = time.perf_counter()
        dur_complete = t1 - t0

        run_records.append({
            "repetition": rep,
            "stage_1_graph_loading_s": round(dur_load, 4),
            "stage_2_subgraph_construction_s": round(dur_subgraph, 4),
            "stage_3_uncertainty_scanning_s": round(dur_uncertainty, 4),
            "stage_4_bridge_detection_s": round(dur_bridge, 4),
            "stage_5_counterfactual_evaluation_s": round(dur_counterfactual, 4),
            "stage_6_candidate_ranking_s": round(dur_ranking, 4),
            "stage_7_probe_selection_s": round(dur_probe, 4),
            "stage_8_complete_end_to_end_s": round(dur_complete, 4)
        })
        print(f"  Repetition {rep:2d}/{repetitions}: End-to-End PCVC = {dur_complete:.3f}s (Counterfactual = {dur_counterfactual:.3f}s)")

    df_runs = pd.DataFrame(run_records)
    save_csv(df_runs, raw_dir / "runtime_profiling_runs.csv")

    # Aggregate Statistics
    summary_rows: List[Dict[str, Any]] = []
    display_names = {
        "stage_1_graph_loading_s": "1. Graph Loading & Geometries",
        "stage_2_subgraph_construction_s": "2. Subgraph Construction",
        "stage_3_uncertainty_scanning_s": "3. Uncertainty Scanning (1721 edges)",
        "stage_4_bridge_detection_s": "4. Bridge Detection Cache",
        "stage_5_counterfactual_evaluation_s": "5. Counterfactual Impact (40 edges)",
        "stage_6_candidate_ranking_s": "6. Priority Ranking & Sorting",
        "stage_7_probe_selection_s": "7. Probe Safe-Return Selection",
        "stage_8_complete_end_to_end_s": "8. Complete End-to-End Pipeline"
    }

    for col, name in display_names.items():
        vals = df_runs[col].values
        summary_rows.append({
            "stage_key": col,
            "stage_name": name,
            "mean_seconds": round(float(np.mean(vals)), 4),
            "median_seconds": round(float(np.median(vals)), 4),
            "std_seconds": round(float(np.std(vals)), 4),
            "min_seconds": round(float(np.min(vals)), 4),
            "max_seconds": round(float(np.max(vals)), 4)
        })

    df_summary = pd.DataFrame(summary_rows)
    save_csv(df_summary, summary_dir / "runtime_profiling_summary.csv")

    # Figures
    # A) Runtime Breakdown Bar Chart (excluding end-to-end to avoid double counting)
    sub_stages = summary_rows[:-1] # 1 to 7
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    names = [s["stage_name"] for s in sub_stages]
    means = [s["mean_seconds"] for s in sub_stages]
    stds = [s["std_seconds"] for s in sub_stages]

    bars = ax.barh(names, means, xerr=stds, capsize=4, color="#3b82f6", edgecolor="black", alpha=0.85)
    ax.set_xlabel("Latency (Seconds)", fontsize=10)
    ax.set_title("PCVC E8: Latency Breakdown by Pipeline Stage", fontsize=11, fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.6, axis="x")
    for bar, val in zip(bars, means):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2, f"{val:.3f}s",
                va="center", fontsize=9, fontweight="bold")
    plt.tight_layout()
    plt.savefig(figures_dir / "runtime_breakdown_stages.png")
    plt.close(fig)

    # B) End-to-End Execution Distribution Boxplot
    fig, ax = plt.subplots(figsize=(6, 4), dpi=300)
    ax.boxplot(df_runs["stage_8_complete_end_to_end_s"], patch_artist=True,
               boxprops=dict(facecolor="#dbeafe", color="#1d4ed8"),
               medianprops=dict(color="#b91c1c", linewidth=2))
    ax.set_ylabel("End-to-End PCVC Latency (Seconds)", fontsize=10)
    ax.set_xticklabels(["Complete PCVC Execution"])
    ax.set_title(f"PCVC E8: Latency Distribution (N={repetitions} Repetitions)", fontsize=11, fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    plt.tight_layout()
    plt.savefig(figures_dir / "runtime_repetitions_distribution.png")
    plt.close(fig)

    e8_json = {
        "experiment": "E8_Runtime_Profiling",
        "description": "Empirical runtime profiling across 8 stages over 10 repetitions",
        "num_repetitions": repetitions,
        "candidate_limit": CANDIDATE_LIMIT,
        "stage_summaries": summary_rows,
        "environment": env_info
    }
    save_json(e8_json, summary_dir / "e8_summary.json")

    print("\n--- E8 RUNTIME SUMMARY ---")
    for s in summary_rows:
        print(f"{s['stage_name']:35s} | Mean: {s['mean_seconds']:.3f}s | Median: {s['median_seconds']:.3f}s | Std: {s['std_seconds']:.3f}s")

    return e8_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PCVC E8 Runtime Profiling")
    parser.add_argument("--reps", type=int, default=NUM_REPETITIONS, help="Number of repetitions")
    args = parser.parse_args()
    run_e8(repetitions=args.reps)
