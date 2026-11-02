"""
PCVC Refined Experiment E2: Counterfactual Masking with Continuous Physical Detour Oracle
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Evaluates PCVC verification ranking against the continuous Physical Detour Impact oracle:
    Δd(u, v) = shortest_path_length(G - e, u, v, weight='length_m') - length_m(e)

Evaluates held-out known wheelchair segments across K in {20, 40, 80} and seeds 42-51.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import random
import json
from pathlib import Path
from typing import Dict, Any, List


import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.experiments.common import (
    load_active_graph,
    set_seed,
    get_edge_id,
    safe_copy_graph,
    save_csv,
    save_json
)
from scripts.experiments.detour_oracle import (
    compute_physical_detour_impact,
    evaluate_continuous_ranking_metrics,
    PENALTY_CAP_DISCONNECTED
)
from src.darr.subgraph import subgraph_manager
from src.darr.resilience import resilience_engine
from src.pcvc.uncertainty import compute_edge_uncertainty, is_attribute_known
from src.pcvc.counterfactual import evaluate_counterfactual_impact

K_VALUES = [20, 40, 80]
SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
TARGET_PROFILE = "wheelchair"


def run_e2_detour(output_base_dir: Path = PROJECT_ROOT / "results/pcvc/e2_detour") -> Dict[str, Any]:
    output_base_dir.mkdir(parents=True, exist_ok=True)
    raw_csv_path = output_base_dir / "detour_oracle_results.csv"
    summary_csv_path = output_base_dir / "detour_oracle_summary.csv"
    summary_json_path = output_base_dir / "detour_oracle_summary.json"

    print("=" * 80)
    print("PCVC Experiment E2 (Refined): Continuous Physical Detour Impact Oracle")
    print(f"Target Profile: {TARGET_PROFILE} | K Masking Sizes: {K_VALUES} | Seeds: {SEEDS}")
    print("=" * 80)

    G_base = load_active_graph()
    G_sub_clean = subgraph_manager.get_accessible_subgraph(G_base, TARGET_PROFILE)
    bc_clean = resilience_engine._get_bridges(G_sub_clean)

    # 1. Identify pool of 324 known wheelchair edges
    eligible_pool = []
    for u, v, k, data in G_base.edges(keys=True, data=True):
        val = data.get(TARGET_PROFILE)
        if is_attribute_known(TARGET_PROFILE, val):
            eligible_pool.append((u, v, k, data))

    print(f"Total network edges: {G_base.number_of_edges()}, Nodes: {G_base.number_of_nodes()}")
    print(f"Eligible known wheelchair ground-truth pool: {len(eligible_pool)}")

    # Pre-evaluate Δd on the clean graph for the entire known pool for audit & distribution
    print("\nPre-computing clean-graph Physical Detour Impact Δd across all known edges...")
    pool_detours = []
    for u, v, k, data in eligible_pool:
        eid = get_edge_id(u, v, k)
        res = compute_physical_detour_impact(G_sub_clean, u, v, key=k, penalty_cap=PENALTY_CAP_DISCONNECTED)
        cad = resilience_engine.calculate_cad_for_edge(G_base, u, v, TARGET_PROFILE, bridge_cache=bc_clean)
        pool_detours.append({
            "edge_id": eid,
            "u": u, "v": v, "key": k,
            "orig_length_m": res["orig_length_m"],
            "bypass_length_m": res["bypass_length_m"],
            "delta_d": res["delta_d"],
            "effective_detour": res["effective_detour"],
            "is_disconnected": res["is_disconnected"],
            "cad": cad
        })
    df_pool = pd.DataFrame(pool_detours)
    print(f"Pool evaluation complete: {len(df_pool)} edges. Disconnected count: {df_pool['is_disconnected'].sum()} ({df_pool['is_disconnected'].mean()*100:.1f}%)")

    # Audit distribution statistics
    finite_mask = ~df_pool["is_disconnected"]
    df_finite = df_pool[finite_mask]
    dist_stats = {
        "total_known_edges": len(df_pool),
        "finite_bypass_count": int(finite_mask.sum()),
        "disconnected_count": int(df_pool["is_disconnected"].sum()),
        "disconnected_ratio": round(float(df_pool["is_disconnected"].mean()), 4),
        "unique_finite_values": int(df_finite["delta_d"].nunique()),
        "finite_min_m": round(float(df_finite["delta_d"].min()), 2),
        "finite_max_m": round(float(df_finite["delta_d"].max()), 2),
        "finite_mean_m": round(float(df_finite["delta_d"].mean()), 2),
        "finite_median_m": round(float(df_finite["delta_d"].median()), 2),
        "finite_std_m": round(float(df_finite["delta_d"].std()), 2),
        "p25_m": round(float(df_finite["delta_d"].quantile(0.25)), 2),
        "p50_m": round(float(df_finite["delta_d"].quantile(0.50)), 2),
        "p75_m": round(float(df_finite["delta_d"].quantile(0.75)), 2),
        "p90_m": round(float(df_finite["delta_d"].quantile(0.90)), 2),
        "p95_m": round(float(df_finite["delta_d"].quantile(0.95)), 2)
    }

    # Plot 1: detour_oracle_distribution.png
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    ax1.hist(df_finite["delta_d"], bins=30, color="#1f77b4", edgecolor="black", alpha=0.75)
    ax1.axvline(dist_stats["finite_median_m"], color="red", linestyle="--", label=f"Median ({dist_stats['finite_median_m']:.1f}m)")
    ax1.axvline(dist_stats["finite_mean_m"], color="green", linestyle=":", label=f"Mean ({dist_stats['finite_mean_m']:.1f}m)")
    ax1.set_title("Distribution of Finite Physical Detour (Δd)", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Bypass Detour Distance (meters)")
    ax1.set_ylabel("Edge Frequency")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    pie_labels = [f"Finite Bypass\n({dist_stats['finite_bypass_count']} edges, {dist_stats['finite_bypass_count']/len(df_pool)*100:.1f}%)",
                  f"Disconnected Cut-Edges\n({dist_stats['disconnected_count']} edges, {dist_stats['disconnected_ratio']*100:.1f}%)"]
    ax2.pie([dist_stats["finite_bypass_count"], dist_stats["disconnected_count"]], labels=pie_labels, colors=["#2ca02c", "#d62728"], autopct="%1.1f%%", startangle=140)
    ax2.set_title("Campus Network Topological Resilience Classification", fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_base_dir / "detour_oracle_distribution.png", dpi=300)
    plt.close()
    print("Saved distribution plot to detour_oracle_distribution.png")

    pool_map = {item["edge_id"]: item for item in pool_detours}

    # 2. Execute E2 Masking across K and Seeds
    detailed_run_records = []
    summary_by_k = []

    for k_val in K_VALUES:
        print(f"\n--- Running K = {k_val} (10 seeds) ---")
        k_metrics = []

        for seed in SEEDS:
            set_seed(seed)
            random.seed(seed)

            # Sample K held-out edges
            sampled_idx = random.sample(range(len(eligible_pool)), k_val)
            sampled_edges = [eligible_pool[idx] for idx in sampled_idx]
            sampled_edge_ids = [get_edge_id(u, v, k) for u, v, k, _ in sampled_edges]

            # True oracle items for held-out set
            oracle_items = [pool_map[eid] for eid in sampled_edge_ids]

            # In-memory deep copy and mask
            G_masked = safe_copy_graph(G_base)
            for u, v, k, _ in sampled_edges:
                G_masked[u][v][k]["wheelchair"] = "unknown"
                if "wheelchair_accessible" in G_masked[u][v][k]:
                    G_masked[u][v][k]["wheelchair_accessible"] = "unknown"

            G_sub_m = subgraph_manager.get_accessible_subgraph(G_masked, TARGET_PROFILE)
            bc_m = resilience_engine._get_bridges(G_sub_m)

            # Score candidates using production PCVC logic (operating without true Δd)
            scored_candidates = []
            for u, v, k, _ in sampled_edges:
                eid = get_edge_id(u, v, k)
                data_m = G_masked[u][v][k]
                _, unc_m, _, _ = compute_edge_uncertainty(data_m, TARGET_PROFILE)
                imp_m = evaluate_counterfactual_impact(G_masked, u, v, k, TARGET_PROFILE, bridge_cache=bc_m)
                
                # Standard PCVC multi-attribute normalized score
                # w_u=0.25, w_imp=0.55, w_cad=0.15
                score = (0.25 * unc_m) + (0.55 * min(1.0, imp_m.delta_arl)) + (0.15 * imp_m.cad)
                scored_candidates.append({
                    "edge_id": eid,
                    "score": score,
                    "unc": unc_m,
                    "delta_arl_masked": imp_m.delta_arl,
                    "cad": imp_m.cad
                })

            # Continuous ranking evaluation
            metrics = evaluate_continuous_ranking_metrics(
                scored_candidates=scored_candidates,
                oracle_candidates=oracle_items,
                k_list=[5, 10],
                penalty_cap=PENALTY_CAP_DISCONNECTED
            )

            rec = {
                "k_masked": k_val,
                "seed": seed,
                "candidate_count": k_val,
                "disconnected_in_sample": sum(1 for item in oracle_items if item["is_disconnected"]),
                **metrics
            }
            detailed_run_records.append(rec)
            k_metrics.append(rec)

        df_k = pd.DataFrame(k_metrics)
        summary_rec = {
            "k_masked": k_val,
            "spearman_rho_mean": round(float(df_k["spearman_rho"].mean()), 4),
            "spearman_rho_std": round(float(df_k["spearman_rho"].std()), 4),
            "kendall_tau_mean": round(float(df_k["kendall_tau"].mean()), 4),
            "kendall_tau_std": round(float(df_k["kendall_tau"].std()), 4),
            "mean_abs_rank_error_mean": round(float(df_k["mean_abs_rank_error"].mean()), 2),
            "tic_at_5_mean": round(float(df_k["tic_at_5"].mean()), 4),
            "tic_at_5_std": round(float(df_k["tic_at_5"].std()), 4),
            "tic_at_10_mean": round(float(df_k["tic_at_10"].mean()), 4),
            "tic_at_10_std": round(float(df_k["tic_at_10"].std()), 4),
            "ndcg_at_5_mean": round(float(df_k["ndcg_at_5"].mean()), 4),
            "ndcg_at_5_std": round(float(df_k["ndcg_at_5"].std()), 4),
            "ndcg_at_10_mean": round(float(df_k["ndcg_at_10"].mean()), 4),
            "ndcg_at_10_std": round(float(df_k["ndcg_at_10"].std()), 4),
            "mean_detour_at_5_mean": round(float(df_k["mean_detour_captured_at_5"].mean()), 1),
            "mean_detour_at_10_mean": round(float(df_k["mean_detour_captured_at_10"].mean()), 1),
            "oracle_mean_detour_at_10_mean": round(float(df_k["oracle_mean_detour_at_10"].mean()), 1),
            "min_rank_max_edge_mean": round(float(df_k["min_rank_max_detour_edge"].mean()), 2)
        }
        summary_by_k.append(summary_rec)
        print(f"K={k_val:2d} Summary: Rho={summary_rec['spearman_rho_mean']:.4f}±{summary_rec['spearman_rho_std']:.4f} | TIC@10={summary_rec['tic_at_10_mean']:.4f}±{summary_rec['tic_at_10_std']:.4f} | NDCG@10={summary_rec['ndcg_at_10_mean']:.4f}±{summary_rec['ndcg_at_10_std']:.4f} | Mean Detour@10={summary_rec['mean_detour_at_10_mean']:.1f}m / {summary_rec['oracle_mean_detour_at_10_mean']:.1f}m")

    # Save CSVs
    df_raw = pd.DataFrame(detailed_run_records)
    df_summary = pd.DataFrame(summary_by_k)
    save_csv(df_raw, raw_csv_path)
    save_csv(df_summary, summary_csv_path)

    # Plot 2: detour_tic_ndcg.png
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    x_pos = np.arange(len(K_VALUES))
    width = 0.35

    ax1.bar(x_pos - width/2, df_summary["tic_at_5_mean"], width, yerr=df_summary["tic_at_5_std"], capsize=5, label="TIC@5", color="#3498db")
    ax1.bar(x_pos + width/2, df_summary["tic_at_10_mean"], width, yerr=df_summary["tic_at_10_std"], capsize=5, label="TIC@10", color="#2ecc71")
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels([f"K={k}" for k in K_VALUES])
    ax1.set_ylim(0.0, 1.1)
    ax1.set_title("Total Detour Impact Captured (TIC@K)", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Impact Captured Ratio")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.bar(x_pos - width/2, df_summary["ndcg_at_5_mean"], width, yerr=df_summary["ndcg_at_5_std"], capsize=5, label="NDCG@5", color="#e67e22")
    ax2.bar(x_pos + width/2, df_summary["ndcg_at_10_mean"], width, yerr=df_summary["ndcg_at_10_std"], capsize=5, label="NDCG@10", color="#9b59b6")
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels([f"K={k}" for k in K_VALUES])
    ax2.set_ylim(0.0, 1.1)
    ax2.set_title("Normalized Discounted Cumulative Gain (NDCG@K)", fontsize=11, fontweight="bold")
    ax2.set_ylabel("NDCG Score")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_base_dir / "detour_tic_ndcg.png", dpi=300)
    plt.close()

    # Plot 3: detour_rank_correlation.png (Spearman rho & Kendall tau across K)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(K_VALUES, df_summary["spearman_rho_mean"], yerr=df_summary["spearman_rho_std"], marker="o", linewidth=2, capsize=5, label="Spearman Rank Correlation (ρ)", color="#1abc9c")
    ax.errorbar(K_VALUES, df_summary["kendall_tau_mean"], yerr=df_summary["kendall_tau_std"], marker="s", linewidth=2, capsize=5, label="Kendall Rank Correlation (τ)", color="#e74c3c")
    ax.set_title("PCVC Rank Correlation vs. Continuous Physical Detour Oracle", fontsize=12, fontweight="bold")
    ax.set_xlabel("Held-Out Masking Size (K)")
    ax.set_ylabel("Rank Correlation Coefficient")
    ax.set_xticks(K_VALUES)
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_base_dir / "detour_rank_correlation.png", dpi=300)
    plt.close()

    final_payload = {
        "experiment": "E2_Detour_Oracle",
        "description": "Counterfactual masking evaluation using continuous Physical Detour Impact oracle Δd",
        "oracle_distribution_audit": dist_stats,
        "summary_by_k": summary_by_k,
        "figures": [
            "detour_oracle_distribution.png",
            "detour_tic_ndcg.png",
            "detour_rank_correlation.png"
        ]
    }
    save_json(final_payload, summary_json_path)
    print(f"\nE2 Detour experiment successfully completed. Results written to {output_base_dir}")
    return final_payload


if __name__ == "__main__":
    run_e2_detour()
