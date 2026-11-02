"""
PCVC Phase 6 Experiment E5: Safe-Return Probe Evaluation
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Systematically evaluates the Closed-Loop Safe-Return Rule for candidate verification edges:
Rule: Eligible = target edge feasible AND outbound path feasible AND return path feasible.
Route Topology: Anchor (nearest VIT landmark) -> outbound path -> target edge -> return path -> Anchor.

Measures:
- Total candidate edges evaluated across profiles
- Eligibility vs Rejection rates
- Primary rejection reasons
- Detour overhead ratio: (outbound_m + return_m) / target_edge_length_m
- Selected probe profiles and dispatch travel distances

Outputs:
- results/pcvc/e5/raw/safe_return_evaluations.csv
- results/pcvc/e5/summary/safe_return_summary.csv
- results/pcvc/e5/summary/safe_return_by_rejection.csv
- results/pcvc/e5/summary/e5_summary.json
- results/pcvc/e5/figures/rejection_reasons.png
- results/pcvc/e5/figures/detour_overhead_distribution.png
"""

import sys
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
    save_json,
    get_edge_id
)
from src.pcvc.uncertainty import get_uncertain_edges
from src.pcvc.probe_selector import (
    select_best_probe,
    is_safe_probe,
    find_nearest_landmark_anchor,
    _get_edge_length
)

TARGET_PROFILES = ["wheelchair", "elderly", "pregnant", "general"]
UNCERTAINTY_THRESHOLD = 0.40
CANDIDATE_LIMIT_PER_PROFILE = 100


def run_e5(candidate_limit: int = CANDIDATE_LIMIT_PER_PROFILE) -> Dict[str, Any]:
    dirs = ensure_result_dirs("e5")
    raw_dir = dirs["raw"]
    summary_dir = dirs["summary"]
    figures_dir = dirs["figures"]

    print("=" * 75)
    print("PCVC Experiment E5: Safe-Return Probe Evaluation")
    print("=" * 75)

    G = load_active_graph()
    g_stats = graph_statistics(G)
    env_info = get_environment_info()

    all_evaluations: List[Dict[str, Any]] = []

    for target_prof in TARGET_PROFILES:
        print(f"Scanning candidate edges for target profile: '{target_prof}'...")
        uncertain_cands = get_uncertain_edges(
            G,
            profile=target_prof,
            uncertainty_threshold=UNCERTAINTY_THRESHOLD,
            limit=candidate_limit
        )
        print(f"  Found {len(uncertain_cands)} candidates above threshold {UNCERTAINTY_THRESHOLD}.")

        for cand in uncertain_cands:
            u, v, k = cand.u, cand.v, cand.key
            eid = cand.edge_id
            edge_data = G[u][v][k] if G.is_multigraph() else G[u][v]
            edge_len = _get_edge_length(edge_data)

            # Probe selection across 4 candidate profiles
            probe_result = select_best_probe(G, u, v, k)

            has_eligible = (probe_result.selected_probe is not None)
            selected_probe = probe_result.selected_probe or "None"
            anchor_name = probe_result.anchor_name
            anchor_node = probe_result.anchor_node

            best_eligible = probe_result.eligible_probes[0] if probe_result.eligible_probes else None

            outbound_dist = best_eligible.outbound_distance_m if best_eligible else 0.0
            return_dist = best_eligible.return_distance_m if best_eligible else 0.0
            total_travel = best_eligible.travel_cost if best_eligible else 0.0

            # Detour overhead ratio
            detour_overhead = (outbound_dist + return_dist) / edge_len if edge_len > 0 and has_eligible else None

            # Primary rejection reasons across candidate probe profiles
            rej_reasons = [r.reason for r in probe_result.rejected_probes]
            primary_rejection = rej_reasons[0] if (not has_eligible and rej_reasons) else "None"

            all_evaluations.append({
                "target_profile": target_prof,
                "edge_id": eid,
                "u": u, "v": v, "key": k,
                "target_edge_length_m": round(edge_len, 2),
                "is_eligible": has_eligible,
                "selected_probe_profile": selected_probe,
                "anchor_name": anchor_name,
                "anchor_node": anchor_node,
                "outbound_distance_m": round(outbound_dist, 2),
                "return_distance_m": round(return_dist, 2),
                "total_travel_distance_m": round(total_travel, 2),
                "detour_overhead_ratio": round(detour_overhead, 3) if detour_overhead is not None else None,
                "num_eligible_probes": len(probe_result.eligible_probes),
                "num_rejected_probes": len(probe_result.rejected_probes),
                "primary_rejection_reason": primary_rejection
            })

    df_eval = pd.DataFrame(all_evaluations)
    save_csv(df_eval, raw_dir / "safe_return_evaluations.csv")

    # Aggregate Statistics by Target Profile
    summary_rows: List[Dict[str, Any]] = []
    for tp in TARGET_PROFILES:
        sub = df_eval[df_eval["target_profile"] == tp]
        total_cands = len(sub)
        elig_count = int(sub["is_eligible"].sum())
        rej_count = total_cands - elig_count
        elig_rate = round(elig_count / total_cands * 100.0, 2) if total_cands > 0 else 0.0

        detour_vals = sub[sub["is_eligible"]]["detour_overhead_ratio"].dropna().values
        travel_vals = sub[sub["is_eligible"]]["total_travel_distance_m"].dropna().values

        summary_rows.append({
            "target_profile": tp,
            "total_candidates": total_cands,
            "eligible_count": elig_count,
            "rejected_count": rej_count,
            "eligibility_rate_pct": elig_rate,
            "detour_overhead_mean": round(float(np.mean(detour_vals)), 3) if len(detour_vals) > 0 else None,
            "detour_overhead_median": round(float(np.median(detour_vals)), 3) if len(detour_vals) > 0 else None,
            "detour_overhead_std": round(float(np.std(detour_vals)), 3) if len(detour_vals) > 0 else None,
            "detour_overhead_min": round(float(np.min(detour_vals)), 3) if len(detour_vals) > 0 else None,
            "detour_overhead_max": round(float(np.max(detour_vals)), 3) if len(detour_vals) > 0 else None,
            "travel_distance_m_mean": round(float(np.mean(travel_vals)), 2) if len(travel_vals) > 0 else None,
            "travel_distance_m_median": round(float(np.median(travel_vals)), 2) if len(travel_vals) > 0 else None
        })

    df_summary = pd.DataFrame(summary_rows)
    save_csv(df_summary, summary_dir / "safe_return_summary.csv")

    # Rejection Breakdown
    rejected_subset = df_eval[~df_eval["is_eligible"]]
    rejection_counts = rejected_subset["primary_rejection_reason"].value_counts().to_dict()
    rejection_rows = [{"rejection_reason": r, "count": c} for r, c in rejection_counts.items()]
    df_rej = pd.DataFrame(rejection_rows)
    save_csv(df_rej, summary_dir / "safe_return_by_rejection.csv")

    # Selected Probe Breakdown
    selected_probe_counts = df_eval[df_eval["is_eligible"]]["selected_probe_profile"].value_counts().to_dict()

    # Figures
    # A) Rejection Reasons Bar Chart
    fig, ax = plt.subplots(figsize=(7, 4), dpi=300)
    if rejection_counts:
        reasons_clean = [k[:45] + "..." if len(k) > 45 else k for k in rejection_counts.keys()]
        ax.barh(reasons_clean, list(rejection_counts.values()), color="#ef4444")
        ax.set_xlabel("Rejection Count", fontsize=10)
        ax.set_title("PCVC E5: Primary Safe-Return Rejection Reasons", fontsize=11, fontweight="bold")
    else:
        ax.text(0.5, 0.5, "Zero Safe-Return Rejections\nAll Candidate Routes Feasible",
                ha="center", va="center", fontsize=12, fontweight="bold", color="#059669")
        ax.set_title("PCVC E5: Safe-Return Eligibility", fontsize=11, fontweight="bold")
    plt.tight_layout()
    plt.savefig(figures_dir / "rejection_reasons.png")
    plt.close(fig)

    # B) Detour Overhead Ratio Distribution
    fig, ax = plt.subplots(figsize=(7, 4), dpi=300)
    all_detours = df_eval[df_eval["is_eligible"]]["detour_overhead_ratio"].dropna().values
    if len(all_detours) > 0:
        ax.hist(all_detours, bins=25, color="#3b82f6", edgecolor="black", alpha=0.8)
        ax.axvline(x=np.median(all_detours), color="red", linestyle="--", linewidth=1.5,
                   label=f"Median Detour: {np.median(all_detours):.1f}x")
        ax.set_xlabel("Detour Overhead Ratio ((Outbound + Return) / Target Length)", fontsize=10)
        ax.set_ylabel("Count of Eligible Routes", fontsize=10)
        ax.set_title("PCVC E5: Verification Probe Detour Overhead Ratio Distribution", fontsize=11, fontweight="bold")
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend()
    plt.tight_layout()
    plt.savefig(figures_dir / "detour_overhead_distribution.png")
    plt.close(fig)

    # Summary JSON
    e5_json = {
        "experiment": "E5_Safe_Return_Evaluation",
        "description": "Evaluation of closed-loop safe-return probe feasibility and detour overhead",
        "total_evaluations": len(df_eval),
        "target_profile_summaries": summary_rows,
        "selected_probe_distribution": selected_probe_counts,
        "rejection_counts": rejection_counts,
        "environment": env_info
    }
    save_json(e5_json, summary_dir / "e5_summary.json")

    print("\n--- E5 SAFE-RETURN SUMMARY ---")
    for s in summary_rows:
        print(f"Target: {s['target_profile']:11s} | Total: {s['total_candidates']} | Eligible: {s['eligible_count']} ({s['eligibility_rate_pct']}%) | Mean Detour: {s['detour_overhead_mean']}x | Median Travel: {s['travel_distance_m_median']}m")

    return e5_json


if __name__ == "__main__":
    run_e5()
