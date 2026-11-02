"""
PCVC Phase 6 Experiment E4: Profile Sensitivity Analysis
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Evaluates whether PCVC candidate selection and verification prioritization
diverge meaningfully across the 4 supported mobility profiles:
- general
- elderly
- pregnant
- wheelchair

Measures:
- Top 10 verification targets for each profile
- Multi-attribute score components (Uncertainty, delta_ARL, CAD)
- Pairwise Top-5 and Top-10 Jaccard similarity
- Pairwise overlap percentages
- Probe assignments for top targets

Outputs:
- results/pcvc/e4/raw/profile_rankings_top10.csv
- results/pcvc/e4/summary/pairwise_profile_similarity.csv
- results/pcvc/e4/summary/e4_summary.json
- results/pcvc/e4/figures/profile_similarity_heatmap.png
- results/pcvc/e4/figures/profile_score_distribution.png
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
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
from src.pcvc.controller import pcvc_controller

PROFILES = ["general", "elderly", "pregnant", "wheelchair"]


def run_e4() -> Dict[str, Any]:
    dirs = ensure_result_dirs("e4")
    raw_dir = dirs["raw"]
    summary_dir = dirs["summary"]
    figures_dir = dirs["figures"]

    print("=" * 75)
    print("PCVC Experiment E4: Profile Sensitivity Analysis")
    print("=" * 75)

    G = load_active_graph()
    g_stats = graph_statistics(G)
    env_info = get_environment_info()

    profile_plans = {}
    ranking_records: List[Dict[str, Any]] = []

    for profile in PROFILES:
        print(f"Computing PCVC verification plan for profile: '{profile}'...")
        plan = pcvc_controller.compute_verification_targets(
            G,
            target_profile=profile,
            top_k=10,
            uncertainty_threshold=0.40,
            candidate_limit=40
        )
        profile_plans[profile] = plan

        selected_probe_name = plan.probe_selection.selected_probe if plan.probe_selection else "None"
        anchor_node = plan.probe_selection.anchor_node if plan.probe_selection else None

        for rank_idx, cand in enumerate(plan.ranked_candidates, start=1):
            ranking_records.append({
                "profile": profile,
                "rank": rank_idx,
                "edge_id": cand.edge_id,
                "u": cand.u,
                "v": cand.v,
                "key": cand.key,
                "name": cand.name,
                "priority_score": cand.priority_score,
                "uncertainty": cand.uncertainty,
                "delta_arl": cand.impact.delta_arl,
                "delta_aoc": cand.impact.delta_aoc,
                "mal_impact": cand.impact.mal_impact,
                "cad": cand.impact.cad,
                "is_cut_edge": cand.impact.is_cut_edge,
                "reason": cand.reason,
                "selected_probe_for_top1": selected_probe_name if rank_idx == 1 else "",
                "anchor_node": anchor_node if rank_idx == 1 else None
            })

    df_rankings = pd.DataFrame(ranking_records)
    save_csv(df_rankings, raw_dir / "profile_rankings_top10.csv")

    # Pairwise comparison
    pairwise_records: List[Dict[str, Any]] = []
    matrix_jaccard_10 = np.zeros((len(PROFILES), len(PROFILES)))
    matrix_jaccard_5 = np.zeros((len(PROFILES), len(PROFILES)))

    for i, p_a in enumerate(PROFILES):
        cands_a = [c.edge_id for c in profile_plans[p_a].ranked_candidates]
        set_a_5 = set(cands_a[:5])
        set_a_10 = set(cands_a[:10])

        for j, p_b in enumerate(PROFILES):
            cands_b = [c.edge_id for c in profile_plans[p_b].ranked_candidates]
            set_b_5 = set(cands_b[:5])
            set_b_10 = set(cands_b[:10])

            # Jaccard similarities
            union_5 = set_a_5 | set_b_5
            jaccard_5 = len(set_a_5 & set_b_5) / len(union_5) if union_5 else 0.0

            union_10 = set_a_10 | set_b_10
            jaccard_10 = len(set_a_10 & set_b_10) / len(union_10) if union_10 else 0.0

            overlap_count_10 = len(set_a_10 & set_b_10)
            overlap_pct_10 = round(overlap_count_10 / 10.0 * 100.0, 1)

            matrix_jaccard_10[i, j] = jaccard_10
            matrix_jaccard_5[i, j] = jaccard_5

            if i < j:
                pairwise_records.append({
                    "profile_a": p_a,
                    "profile_b": p_b,
                    "comparison": f"{p_a} vs {p_b}",
                    "candidates_a": len(cands_a),
                    "candidates_b": len(cands_b),
                    "top10_overlap_count": overlap_count_10,
                    "top10_overlap_pct": overlap_pct_10,
                    "jaccard_at_5": round(float(jaccard_5), 4),
                    "jaccard_at_10": round(float(jaccard_10), 4)
                })

    df_pairwise = pd.DataFrame(pairwise_records)
    save_csv(df_pairwise, summary_dir / "pairwise_profile_similarity.csv")

    # Generate Figures
    # A) Heatmap of Jaccard@10
    fig, ax = plt.subplots(figsize=(6, 5), dpi=300)
    cax = ax.imshow(matrix_jaccard_10, cmap="YlGnBu", vmin=0, vmax=1.0)
    fig.colorbar(cax, ax=ax, fraction=0.046, pad=0.04, label="Jaccard Similarity @ 10")
    ax.set_xticks(range(len(PROFILES)))
    ax.set_yticks(range(len(PROFILES)))
    ax.set_xticklabels([p.capitalize() for p in PROFILES], fontsize=10)
    ax.set_yticklabels([p.capitalize() for p in PROFILES], fontsize=10)

    for r in range(len(PROFILES)):
        for c in range(len(PROFILES)):
            val = matrix_jaccard_10[r, c]
            text_color = "white" if val > 0.6 else "black"
            ax.text(c, r, f"{val:.2f}", ha="center", va="center", color=text_color, fontweight="bold")

    ax.set_title("PCVC E4: Top-10 Target Jaccard Similarity Matrix", fontsize=11, fontweight="bold")
    plt.tight_layout()
    plt.savefig(figures_dir / "profile_similarity_heatmap.png")
    plt.close(fig)

    # B) Profile Score Distribution Plot
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    for profile in PROFILES:
        scores = df_rankings[df_rankings["profile"] == profile]["priority_score"].values
        ranks = range(1, len(scores) + 1)
        ax.plot(ranks, scores, marker="o", label=profile.capitalize(), linewidth=1.8)

    ax.set_xlabel("Candidate Rank", fontsize=10)
    ax.set_ylabel("Priority Score", fontsize=10)
    ax.set_title("PCVC E4: Priority Score Decay across Top-10 Targets", fontsize=11, fontweight="bold")
    ax.set_xticks(range(1, 11))
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(figures_dir / "profile_score_distribution.png")
    plt.close(fig)

    # Summary JSON
    e4_json = {
        "experiment": "E4_Profile_Sensitivity",
        "description": "Evaluation of profile-specific prioritization differentiation",
        "profiles_evaluated": PROFILES,
        "pairwise_similarity": pairwise_records,
        "environment": env_info
    }
    save_json(e4_json, summary_dir / "e4_summary.json")

    print("\n--- E4 PAIRWISE SENSITIVITY SUMMARY ---")
    for row in pairwise_records:
        print(f"{row['comparison']:25s} | Top-10 Overlap: {row['top10_overlap_count']}/10 ({row['top10_overlap_pct']}%) | Jaccard@5: {row['jaccard_at_5']:.3f} | Jaccard@10: {row['jaccard_at_10']:.3f}")

    return e4_json


if __name__ == "__main__":
    run_e4()
