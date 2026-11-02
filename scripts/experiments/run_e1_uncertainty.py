"""
PCVC Phase 6 Experiment E1: Natural Uncertainty Distribution
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Evaluates the natural distribution of accessibility uncertainty and confidence
across all 1,721 edges in the active VIT Vellore pedestrian graph under the 4 profiles:
- general
- elderly
- pregnant
- wheelchair

Outputs:
- results/pcvc/e1/raw/edge_uncertainty_all_profiles.csv
- results/pcvc/e1/summary/profile_uncertainty_summary.csv
- results/pcvc/e1/summary/uncertainty_frequency_bins.csv
- results/pcvc/e1/summary/e1_summary.json
- results/pcvc/e1/figures/uncertainty_hist_{profile}.png
- results/pcvc/e1/figures/uncertainty_distribution_comparison.png
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
from src.pcvc.uncertainty import compute_edge_uncertainty, PROFILE_UNCERTAINTY_WEIGHTS

PROFILES = ["general", "elderly", "pregnant", "wheelchair"]
UNCERTAINTY_THRESHOLD = 0.40


def run_e1(output_dir: Optional[Path] = None) -> Dict[str, Any]:
    dirs = ensure_result_dirs("e1")
    raw_dir = dirs["raw"]
    summary_dir = dirs["summary"]
    figures_dir = dirs["figures"]

    print("=" * 70)
    print("PCVC Experiment E1: Natural Uncertainty Distribution")
    print("=" * 70)

    # 1. Load clean active graph
    G = load_active_graph()
    g_stats = graph_statistics(G)
    env_info = get_environment_info()

    print(f"Graph loaded: {g_stats['num_nodes']} nodes, {g_stats['num_edges']} edges.")

    # 2. Iterate edges and compute uncertainty for each profile
    edge_records: List[Dict[str, Any]] = []

    # Consistent edge ordering
    edge_list = list(G.edges(keys=True, data=True))

    for u, v, k, data in edge_list:
        eid = get_edge_id(u, v, k)
        edge_name = data.get("name") or data.get("display_name") or f"Walkway_{u}_{v}"
        length_m = data.get("length_m", data.get("length", 0.0))

        for profile in PROFILES:
            conf, unc, missing_attrs, known_attrs = compute_edge_uncertainty(data, profile=profile)
            edge_records.append({
                "edge_id": eid,
                "u": u,
                "v": v,
                "key": k,
                "name": edge_name,
                "length_m": round(float(length_m), 2) if length_m else 0.0,
                "profile": profile,
                "confidence": conf,
                "uncertainty": unc,
                "num_missing": len(missing_attrs),
                "missing_attributes": ";".join(missing_attrs),
                "num_known": len(known_attrs),
                "known_attributes": ";".join(known_attrs.keys()),
                "is_candidate": unc >= UNCERTAINTY_THRESHOLD
            })

    df_edges = pd.DataFrame(edge_records)
    save_csv(df_edges, raw_dir / "edge_uncertainty_all_profiles.csv")
    print(f"Saved complete edge-level uncertainty data: {len(df_edges)} rows.")

    # 3. Compute profile-level statistical summaries
    summary_rows: List[Dict[str, Any]] = []
    freq_bins_list: List[Dict[str, Any]] = []

    bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
    bin_labels = ["[0.0, 0.2)", "[0.2, 0.4)", "[0.4, 0.6)", "[0.6, 0.8)", "[0.8, 1.0]"]

    profile_summaries = {}

    for profile in PROFILES:
        pdf = df_edges[df_edges["profile"] == profile]
        unc_vals = pdf["uncertainty"].values
        conf_vals = pdf["confidence"].values

        total_edges = len(pdf)
        num_candidates = int((unc_vals >= UNCERTAINTY_THRESHOLD).sum())
        pct_candidates = round(float(num_candidates / total_edges * 100.0), 2) if total_edges > 0 else 0.0

        mean_unc = round(float(np.mean(unc_vals)), 4)
        median_unc = round(float(np.median(unc_vals)), 4)
        std_unc = round(float(np.std(unc_vals)), 4)
        min_unc = round(float(np.min(unc_vals)), 4)
        max_unc = round(float(np.max(unc_vals)), 4)

        mean_conf = round(float(np.mean(conf_vals)), 4)
        median_conf = round(float(np.median(conf_vals)), 4)
        std_conf = round(float(np.std(conf_vals)), 4)

        prof_stat = {
            "profile": profile,
            "total_edges": total_edges,
            "mean_uncertainty": mean_unc,
            "median_uncertainty": median_unc,
            "std_uncertainty": std_unc,
            "min_uncertainty": min_unc,
            "max_uncertainty": max_unc,
            "candidate_count_above_threshold": num_candidates,
            "candidate_pct_above_threshold": pct_candidates,
            "mean_confidence": mean_conf,
            "median_confidence": median_conf,
            "std_confidence": std_conf,
            "active_weights": PROFILE_UNCERTAINTY_WEIGHTS.get(profile, {})
        }
        summary_rows.append(prof_stat)
        profile_summaries[profile] = prof_stat

        # Frequency bin counts
        binned = pd.cut(pdf["uncertainty"], bins=bins, labels=bin_labels, right=False)
        bin_counts = binned.value_counts().to_dict()
        for blabel in bin_labels:
            freq_bins_list.append({
                "profile": profile,
                "bin_range": blabel,
                "count": int(bin_counts.get(blabel, 0)),
                "pct_of_edges": round(float(bin_counts.get(blabel, 0) / total_edges * 100.0), 2)
            })

    df_summary = pd.DataFrame(summary_rows)
    save_csv(df_summary, summary_dir / "profile_uncertainty_summary.csv")

    df_freq = pd.DataFrame(freq_bins_list)
    save_csv(df_freq, summary_dir / "uncertainty_frequency_bins.csv")

    # 4. Generate Figures
    # A) Individual profile histograms
    colors = {
        "general": "#2b5c8f",
        "elderly": "#3b82f6",
        "pregnant": "#8b5cf6",
        "wheelchair": "#ef4444"
    }

    for profile in PROFILES:
        fig, ax = plt.subplots(figsize=(6, 4), dpi=300)
        pdf = df_edges[df_edges["profile"] == profile]
        ax.hist(pdf["uncertainty"], bins=20, range=(0, 1), color=colors[profile], edgecolor="black", alpha=0.8)
        ax.axvline(x=UNCERTAINTY_THRESHOLD, color="darkred", linestyle="--", linewidth=1.5, label=f"Threshold = {UNCERTAINTY_THRESHOLD}")
        ax.set_title(f"Uncertainty Distribution: {profile.capitalize()} Profile", fontsize=11, fontweight="bold")
        ax.set_xlabel("Uncertainty Score (1 - Confidence)", fontsize=10)
        ax.set_ylabel("Edge Count", fontsize=10)
        ax.set_xlim(0, 1)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="upper right")
        plt.tight_layout()
        fig_path = figures_dir / f"uncertainty_hist_{profile}.png"
        plt.savefig(fig_path)
        plt.close(fig)

    # B) Combined comparative distribution plot
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), dpi=300, sharex=True, sharey=True)
    for idx, profile in enumerate(PROFILES):
        r, c = idx // 2, idx % 2
        ax = axes[r, c]
        pdf = df_edges[df_edges["profile"] == profile]
        ax.hist(pdf["uncertainty"], bins=20, range=(0, 1), color=colors[profile], edgecolor="black", alpha=0.75)
        ax.axvline(x=UNCERTAINTY_THRESHOLD, color="red", linestyle="--", linewidth=1.2)
        ax.set_title(f"{profile.capitalize()} (Candidates: {profile_summaries[profile]['candidate_count_above_threshold']})", fontsize=10, fontweight="bold")
        ax.grid(True, linestyle=":", alpha=0.5)
        if c == 0:
            ax.set_ylabel("Edge Count")
        if r == 1:
            ax.set_xlabel("Uncertainty (1 - Confidence)")
    plt.suptitle("PCVC E1: Accessibility Uncertainty Distribution Across Profiles (VIT Vellore)", fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(figures_dir / "uncertainty_distribution_comparison.png")
    plt.close(fig)

    # 5. Combined summary JSON
    e1_json = {
        "experiment": "E1_Natural_Uncertainty_Distribution",
        "description": "Natural accessibility uncertainty distribution on active VIT Vellore network",
        "environment": env_info,
        "graph_statistics": g_stats,
        "uncertainty_threshold": UNCERTAINTY_THRESHOLD,
        "profile_summaries": profile_summaries,
        "key_observations": [
            f"{p}: mean uncertainty = {profile_summaries[p]['mean_uncertainty']:.3f}, {profile_summaries[p]['candidate_count_above_threshold']} candidates ({profile_summaries[p]['candidate_pct_above_threshold']}%)"
            for p in PROFILES
        ]
    }
    save_json(e1_json, summary_dir / "e1_summary.json")

    print("\n--- E1 SUMMARY ---")
    for p in PROFILES:
        s = profile_summaries[p]
        print(f"Profile: {p:10s} | Mean: {s['mean_uncertainty']:.3f} | Median: {s['median_uncertainty']:.3f} | Candidates (>=0.40): {s['candidate_count_above_threshold']} ({s['candidate_pct_above_threshold']}%)")
    print(f"Results saved to: {dirs['base']}")

    return e1_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PCVC E1 Natural Uncertainty Distribution experiment")
    args = parser.parse_args()
    run_e1()
