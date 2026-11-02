"""
PCVC Phase 6 Experiment E2: Oracle Hold-Out / Masking
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Main Research Experiment:
Tests whether PCVC prioritizes uncertain edges that possess genuinely high
accessibility-resilience impact under profile constraints.

Uses non-destructive in-memory masking of verified known edges.
Pool: Known wheelchair accessibility edges (N = 324).
Evaluation parameters:
- Masking sizes: K in [20, 40, 80]
- Random seeds: 42, 43, 44, 45, 46, 47, 48, 49, 50, 51 (10 deterministic seeds)
- Profile: wheelchair (primary accessibility profile)
- Metric: delta_ARL as single primary impact (delta_ARL == delta_AOC == MAL)

Outputs:
- results/pcvc/e2/raw/oracle_edge_results.csv
- results/pcvc/e2/oracle_edge_results.csv (root copy as requested)
- results/pcvc/e2/summary/oracle_summary.csv
- results/pcvc/e2/oracle_summary.csv (root copy as requested)
- results/pcvc/e2/summary/oracle_summary.json
- results/pcvc/e2/oracle_summary.json (root copy as requested)
- results/pcvc/e2/figures/tic_ndcg_by_k.png
- results/pcvc/e2/figures/spearman_distribution.png
"""

import sys
import copy
import random
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kendalltau
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Ensure project root is accessible
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.experiments.common import (
    load_active_graph,
    safe_copy_graph,
    graph_statistics,
    get_environment_info,
    ensure_result_dirs,
    save_csv,
    save_json,
    set_seed,
    get_edge_id
)
from src.pcvc.uncertainty import (
    compute_edge_uncertainty,
    is_attribute_known
)
from src.pcvc.counterfactual import evaluate_counterfactual_impact
from src.darr.subgraph import subgraph_manager
from src.darr.resilience import resilience_engine

SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
K_VALUES = [20, 40, 80]
PROFILE = "wheelchair"


def compute_dcg(relevances: List[float], k: int) -> float:
    """Computes Discounted Cumulative Gain at rank k."""
    dcg = 0.0
    for i in range(min(k, len(relevances))):
        rel = relevances[i]
        dcg += rel / np.log2(i + 2) # i+2 because i is 0-indexed (rank 1 -> log2(2) = 1)
    return dcg


def compute_ndcg(pred_relevances: List[float], oracle_relevances: List[float], k: int) -> float:
    """Computes Normalized Discounted Cumulative Gain at rank k."""
    dcg = compute_dcg(pred_relevances, k)
    ideal_relevances = sorted(oracle_relevances, reverse=True)
    idcg = compute_dcg(ideal_relevances, k)
    if idcg <= 0.0:
        return 1.0 if dcg <= 0.0 else 0.0
    return min(1.0, max(0.0, dcg / idcg))


def compute_tic(pred_relevances: List[float], oracle_relevances: List[float], k: int) -> float:
    """
    Computes Total Impact Captured at rank k:
    TIC@K = sum(true impact of predicted top-K) / sum(true impact of oracle top-K)
    Handles zero-denominator safely.
    """
    top_pred_sum = sum(pred_relevances[:k])
    ideal_sum = sum(sorted(oracle_relevances, reverse=True)[:k])
    if ideal_sum <= 0.0:
        return 1.0 if top_pred_sum <= 0.0 else 0.0
    return min(1.0, max(0.0, top_pred_sum / ideal_sum))


def run_e2(k_values: List[int] = K_VALUES, seeds: List[int] = SEEDS) -> Dict[str, Any]:
    dirs = ensure_result_dirs("e2")
    raw_dir = dirs["raw"]
    summary_dir = dirs["summary"]
    figures_dir = dirs["figures"]

    print("=" * 75)
    print("PCVC Experiment E2: Oracle Hold-Out / Masking Evaluation")
    print("=" * 75)

    G_base = load_active_graph()
    g_stats = graph_statistics(G_base)
    env_info = get_environment_info()

    # Precompute base graph bridges for fast evaluation
    G_sub_base = subgraph_manager.get_accessible_subgraph(G_base, PROFILE)
    bc_base = resilience_engine._get_bridges(G_sub_base)

    # 1. Identify eligible ground-truth pool of known wheelchair edges
    eligible_pool = []
    for u, v, k, data in G_base.edges(keys=True, data=True):
        val = data.get("wheelchair")
        if is_attribute_known("wheelchair", val):
            eligible_pool.append((u, v, k, data))

    print(f"Eligible known wheelchair ground-truth pool: {len(eligible_pool)} edges.")
    assert len(eligible_pool) >= max(k_values), f"Pool size ({len(eligible_pool)}) smaller than max K ({max(k_values)})"

    all_edge_records: List[Dict[str, Any]] = []
    run_summary_records: List[Dict[str, Any]] = []

    for k_val in k_values:
        print(f"\nEvaluating Masking Size K = {k_val} across {len(seeds)} random seeds...")

        for seed in seeds:
            set_seed(seed)

            # A. Deterministically sample K eligible edges
            sampled_indices = random.sample(range(len(eligible_pool)), k_val)
            sampled_edges = [eligible_pool[idx] for idx in sampled_indices]

            # B. Non-destructive in-memory graph duplication
            G_masked = safe_copy_graph(G_base)

            # C. Save oracle truth and mask attributes to 'unknown' in G_masked
            masked_meta = []
            for u, v, k, orig_data in sampled_edges:
                eid = get_edge_id(u, v, k)
                orig_wc = orig_data.get("wheelchair")
                orig_wc_acc = orig_data.get("wheelchair_accessible")

                # Mask in G_masked
                G_masked[u][v][k]["wheelchair"] = "unknown"
                if "wheelchair_accessible" in G_masked[u][v][k]:
                    G_masked[u][v][k]["wheelchair_accessible"] = "unknown"

                masked_meta.append({
                    "u": u, "v": v, "key": k, "edge_id": eid,
                    "orig_wc": orig_wc, "orig_wc_acc": orig_wc_acc
                })

            # D. Evaluate true oracle counterfactual impact on clean G_base
            oracle_impacts = {}
            for item in masked_meta:
                u, v, k, eid = item["u"], item["v"], item["key"], item["edge_id"]
                imp = evaluate_counterfactual_impact(G_base, u, v, k, PROFILE, bridge_cache=bc_base)
                oracle_impacts[eid] = {
                    "true_delta_arl": imp.delta_arl,
                    "true_delta_aoc": imp.delta_aoc,
                    "true_mal": imp.mal_impact,
                    "true_cad": imp.cad,
                    "true_is_cut": imp.is_cut_edge
                }

            # E. Compute PCVC score on G_masked for the K held-out candidates
            G_sub_masked = subgraph_manager.get_accessible_subgraph(G_masked, PROFILE)
            bc_masked = resilience_engine._get_bridges(G_sub_masked)

            candidate_evals = []
            for item in masked_meta:
                u, v, k, eid = item["u"], item["v"], item["key"], item["edge_id"]
                data_m = G_masked[u][v][k]
                conf_m, unc_m, missing_m, known_m = compute_edge_uncertainty(data_m, PROFILE)
                imp_m = evaluate_counterfactual_impact(G_masked, u, v, k, PROFILE, bridge_cache=bc_masked)

                candidate_evals.append({
                    "edge_id": eid,
                    "u": u, "v": v, "key": k,
                    "orig_wc": item["orig_wc"],
                    "unc_masked": unc_m,
                    "conf_masked": conf_m,
                    "impact_masked": imp_m,
                    "true_delta_arl": oracle_impacts[eid]["true_delta_arl"],
                    "true_is_cut": oracle_impacts[eid]["true_is_cut"],
                    "true_cad": oracle_impacts[eid]["true_cad"]
                })

            # F. PCVC multi-attribute normalized score calculation
            max_d_arl = max([c["impact_masked"].delta_arl for c in candidate_evals] + [1.0])
            for c in candidate_evals:
                norm_unc = c["unc_masked"]
                norm_d_arl = c["impact_masked"].delta_arl / max_d_arl if max_d_arl > 0 else 0.0
                norm_cad = c["impact_masked"].cad
                # Standard PCVC verified priority weighting:
                # 0.25 * unc + 0.55 * d_arl + 0.15 * cad
                score = 0.25 * norm_unc + 0.55 * norm_d_arl + 0.15 * norm_cad
                c["pred_score"] = round(score, 4)

            # G. Rankings
            # Predicted ranking: sorted by pred_score descending, then cad, then unc
            pred_sorted = sorted(candidate_evals, key=lambda x: (x["pred_score"], x["impact_masked"].cad, x["unc_masked"]), reverse=True)
            for r_idx, c in enumerate(pred_sorted, start=1):
                c["pred_rank"] = r_idx

            # Oracle ranking: sorted by true_delta_arl descending, then true_cad
            oracle_sorted = sorted(candidate_evals, key=lambda x: (x["true_delta_arl"], x["true_cad"]), reverse=True)
            for r_idx, c in enumerate(oracle_sorted, start=1):
                c["oracle_rank"] = r_idx

            # Record edge-level results
            for c in pred_sorted:
                all_edge_records.append({
                    "k_masked": k_val,
                    "seed": seed,
                    "edge_id": c["edge_id"],
                    "u": c["u"], "v": c["v"], "key": c["key"],
                    "orig_wheelchair_val": c["orig_wc"],
                    "masked_uncertainty": c["unc_masked"],
                    "masked_delta_arl": c["impact_masked"].delta_arl,
                    "masked_cad": c["impact_masked"].cad,
                    "predicted_priority_score": c["pred_score"],
                    "predicted_rank": c["pred_rank"],
                    "oracle_true_delta_arl": c["true_delta_arl"],
                    "oracle_true_is_cut": c["true_is_cut"],
                    "oracle_true_cad": c["true_cad"],
                    "oracle_rank": c["oracle_rank"]
                })

            # H. Compute evaluation metrics
            pred_scores = [c["pred_score"] for c in candidate_evals]
            true_impacts = [c["true_delta_arl"] for c in candidate_evals]

            # Correlation metrics
            if len(set(true_impacts)) <= 1 or len(set(pred_scores)) <= 1:
                s_rho, s_pval = 0.0, 1.0
                k_tau, k_pval = 0.0, 1.0
            else:
                s_rho, s_pval = spearmanr(pred_scores, true_impacts)
                k_tau, k_pval = kendalltau(pred_scores, true_impacts)
                if np.isnan(s_rho):
                    s_rho = 0.0
                if np.isnan(k_tau):
                    k_tau = 0.0

            # Rank-ordered true impacts under predicted ranking
            relevances_pred = [c["true_delta_arl"] for c in pred_sorted]
            relevances_oracle = [c["true_delta_arl"] for c in oracle_sorted]

            # Sets of top-K for set overlap metrics
            pred_top1_set = {pred_sorted[0]["edge_id"]}
            oracle_top1_set = {c["edge_id"] for c in oracle_sorted if c["true_delta_arl"] == oracle_sorted[0]["true_delta_arl"]}

            pred_top5_set = {c["edge_id"] for c in pred_sorted[:5]}
            oracle_top5_set = {c["edge_id"] for c in oracle_sorted[:5]}

            pred_top10_set = {c["edge_id"] for c in pred_sorted[:10]}
            oracle_top10_set = {c["edge_id"] for c in oracle_sorted[:10]}

            hit_at_1 = 1.0 if len(pred_top1_set & oracle_top1_set) > 0 else 0.0
            hit_at_5 = 1.0 if len(pred_top5_set & oracle_top5_set) > 0 else 0.0
            hit_at_10 = 1.0 if len(pred_top10_set & oracle_top10_set) > 0 else 0.0

            prec_at_5 = len(pred_top5_set & oracle_top5_set) / 5.0
            prec_at_10 = len(pred_top10_set & oracle_top10_set) / 10.0

            tic_at_5 = compute_tic(relevances_pred, relevances_oracle, 5)
            tic_at_10 = compute_tic(relevances_pred, relevances_oracle, 10)

            ndcg_at_5 = compute_ndcg(relevances_pred, relevances_oracle, 5)
            ndcg_at_10 = compute_ndcg(relevances_pred, relevances_oracle, 10)

            run_summary_records.append({
                "k_masked": k_val,
                "seed": seed,
                "spearman_rho": round(float(s_rho), 4),
                "spearman_pvalue": round(float(s_pval), 6) if not np.isnan(s_pval) else None,
                "kendall_tau": round(float(k_tau), 4),
                "kendall_pvalue": round(float(k_pval), 6) if not np.isnan(k_pval) else None,
                "hit_at_1": hit_at_1,
                "hit_at_5": hit_at_5,
                "hit_at_10": hit_at_10,
                "precision_at_5": round(prec_at_5, 4),
                "precision_at_10": round(prec_at_10, 4),
                "tic_at_5": round(tic_at_5, 4),
                "tic_at_10": round(tic_at_10, 4),
                "ndcg_at_5": round(ndcg_at_5, 4),
                "ndcg_at_10": round(ndcg_at_10, 4)
            })

    # Save Edge-level detailed CSV
    df_edges = pd.DataFrame(all_edge_records)
    save_csv(df_edges, raw_dir / "oracle_edge_results.csv")
    save_csv(df_edges, dirs["base"] / "oracle_edge_results.csv")

    # Save Run-level summary CSV
    df_runs = pd.DataFrame(run_summary_records)
    save_csv(df_runs, summary_dir / "oracle_summary.csv")
    save_csv(df_runs, dirs["base"] / "oracle_summary.csv")

    # Aggregate by K
    k_aggregates = {}
    for k_val in k_values:
        k_df = df_runs[df_runs["k_masked"] == k_val]
        k_aggregates[f"K_{k_val}"] = {
            "k_masked": k_val,
            "num_seeds": len(k_df),
            "spearman_rho_mean": round(float(k_df["spearman_rho"].mean()), 4),
            "spearman_rho_std": round(float(k_df["spearman_rho"].std()), 4),
            "kendall_tau_mean": round(float(k_df["kendall_tau"].mean()), 4),
            "kendall_tau_std": round(float(k_df["kendall_tau"].std()), 4),
            "hit_at_1_mean": round(float(k_df["hit_at_1"].mean()), 4),
            "hit_at_5_mean": round(float(k_df["hit_at_5"].mean()), 4),
            "hit_at_10_mean": round(float(k_df["hit_at_10"].mean()), 4),
            "precision_at_5_mean": round(float(k_df["precision_at_5"].mean()), 4),
            "precision_at_10_mean": round(float(k_df["precision_at_10"].mean()), 4),
            "tic_at_5_mean": round(float(k_df["tic_at_5"].mean()), 4),
            "tic_at_10_mean": round(float(k_df["tic_at_10"].mean()), 4),
            "ndcg_at_5_mean": round(float(k_df["ndcg_at_5"].mean()), 4),
            "ndcg_at_10_mean": round(float(k_df["ndcg_at_10"].mean()), 4)
        }

    # Combined Summary JSON
    e2_json = {
        "experiment": "E2_Oracle_Holdout_Masking",
        "profile": PROFILE,
        "eligible_pool_size": len(eligible_pool),
        "k_values": k_values,
        "seeds": seeds,
        "k_aggregates": k_aggregates,
        "environment": env_info
    }
    save_json(e2_json, summary_dir / "oracle_summary.json")
    save_json(e2_json, dirs["base"] / "oracle_summary.json")

    # Figures
    # A) TIC and NDCG vs K
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=300)
    k_labels = [str(k) for k in k_values]
    tic5_means = [k_aggregates[f"K_{k}"]["tic_at_5_mean"] for k in k_values]
    tic10_means = [k_aggregates[f"K_{k}"]["tic_at_10_mean"] for k in k_values]
    ndcg5_means = [k_aggregates[f"K_{k}"]["ndcg_at_5_mean"] for k in k_values]
    ndcg10_means = [k_aggregates[f"K_{k}"]["ndcg_at_10_mean"] for k in k_values]

    x = np.arange(len(k_values))
    width = 0.18
    ax.bar(x - 1.5 * width, tic5_means, width, label="TIC@5", color="#2563eb")
    ax.bar(x - 0.5 * width, tic10_means, width, label="TIC@10", color="#60a5fa")
    ax.bar(x + 0.5 * width, ndcg5_means, width, label="NDCG@5", color="#059669")
    ax.bar(x + 1.5 * width, ndcg10_means, width, label="NDCG@10", color="#34d399")

    ax.set_ylabel("Metric Score", fontsize=10)
    ax.set_xlabel("Masking Pool Size K", fontsize=10)
    ax.set_title("PCVC E2: Oracle Prioritization Performance Across Masking Sizes", fontsize=11, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(k_labels)
    ax.set_ylim(0, 1.1)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(figures_dir / "tic_ndcg_by_k.png")
    plt.close(fig)

    # B) Spearman Rho boxplot across K
    fig, ax = plt.subplots(figsize=(6, 4), dpi=300)
    data_by_k = [df_runs[df_runs["k_masked"] == k]["spearman_rho"].values for k in k_values]
    ax.boxplot(data_by_k, tick_labels=[f"K={k}" for k in k_values], patch_artist=True,
               boxprops=dict(facecolor="#dbeafe", color="#1d4ed8"),
               medianprops=dict(color="#b91c1c", linewidth=2))
    ax.set_ylabel("Spearman Rank Correlation (ρ)", fontsize=10)
    ax.set_title("PCVC E2: Rank Correlation with Oracle Ground-Truth Impact", fontsize=11, fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    plt.tight_layout()
    plt.savefig(figures_dir / "spearman_distribution.png")
    plt.close(fig)

    print("\n--- E2 SUMMARY (Mean across 10 deterministic seeds) ---")
    for k_val in k_values:
        agg = k_aggregates[f"K_{k_val}"]
        print(f"K = {k_val:2d} | Spearman: {agg['spearman_rho_mean']:.3f} | TIC@5: {agg['tic_at_5_mean']:.3f} | TIC@10: {agg['tic_at_10_mean']:.3f} | NDCG@10: {agg['ndcg_at_10_mean']:.3f} | Prec@10: {agg['precision_at_10_mean']:.3f}")

    return e2_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PCVC E2 Oracle Hold-Out Masking experiment")
    parser.add_argument("--k", nargs="+", type=int, default=K_VALUES, help="K values to evaluate")
    parser.add_argument("--seeds", nargs="+", type=int, default=SEEDS, help="Random seeds")
    args = parser.parse_args()
    run_e2(k_values=args.k, seeds=args.seeds)
