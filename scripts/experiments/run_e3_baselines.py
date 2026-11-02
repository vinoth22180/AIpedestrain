"""
PCVC Phase 6 Experiment E3: Baseline Ranking Comparison
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Systematically compares PCVC against 5 standard verification prioritization baselines:
- B1: Random (uniform random ranking)
- B2: Uncertainty-Only (pure active learning heuristic: 1.0 * uncertainty)
- B3: CAD-Only (pure structural bottleneck heuristic: 1.0 * CAD)
- B4: Counterfactual Impact-Only (pure resilience impact: 1.0 * norm_delta_arl)
- B5: Uncertainty + CAD (structural active learning: 0.5 * norm_unc + 0.5 * CAD)
- B6: Full PCVC (0.25 * norm_unc + 0.55 * norm_delta_arl + 0.15 * CAD)

All baselines evaluate the EXACT SAME candidate population across 10 deterministic random seeds (42–51).

Outputs:
- results/pcvc/e3/raw/baseline_run_results.csv
- results/pcvc/e3/summary/baseline_comparison_summary.csv
- results/pcvc/e3/summary/baseline_statistical_tests.json
- results/pcvc/e3/summary/e3_summary.json
- results/pcvc/e3/figures/baseline_tic_comparison.png
- results/pcvc/e3/figures/baseline_ndcg_comparison.png
"""

import sys
import random
import argparse
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kendalltau, friedmanchisquare, wilcoxon
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
from src.pcvc.uncertainty import compute_edge_uncertainty, is_attribute_known
from src.pcvc.counterfactual import evaluate_counterfactual_impact
from src.darr.subgraph import subgraph_manager
from src.darr.resilience import resilience_engine

SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
CANDIDATE_POOL_SIZE = 40
PROFILE = "wheelchair"

BASELINE_NAMES = {
    "B1": "Random",
    "B2": "Uncertainty-Only",
    "B3": "CAD-Only",
    "B4": "Impact-Only",
    "B5": "Uncertainty + CAD",
    "B6": "Full PCVC"
}


def compute_dcg(relevances: List[float], k: int) -> float:
    dcg = 0.0
    for i in range(min(k, len(relevances))):
        dcg += relevances[i] / np.log2(i + 2)
    return dcg


def compute_ndcg(pred_relevances: List[float], oracle_relevances: List[float], k: int) -> float:
    dcg = compute_dcg(pred_relevances, k)
    ideal = sorted(oracle_relevances, reverse=True)
    idcg = compute_dcg(ideal, k)
    if idcg <= 0.0:
        return 1.0 if dcg <= 0.0 else 0.0
    return min(1.0, max(0.0, dcg / idcg))


def compute_tic(pred_relevances: List[float], oracle_relevances: List[float], k: int) -> float:
    pred_sum = sum(pred_relevances[:k])
    ideal_sum = sum(sorted(oracle_relevances, reverse=True)[:k])
    if ideal_sum <= 0.0:
        return 1.0 if pred_sum <= 0.0 else 0.0
    return min(1.0, max(0.0, pred_sum / ideal_sum))


def run_e3(seeds: List[int] = SEEDS, pool_size: int = CANDIDATE_POOL_SIZE) -> Dict[str, Any]:
    dirs = ensure_result_dirs("e3")
    raw_dir = dirs["raw"]
    summary_dir = dirs["summary"]
    figures_dir = dirs["figures"]

    print("=" * 75)
    print("PCVC Experiment E3: Baseline Ranking Comparison")
    print("=" * 75)

    G_base = load_active_graph()
    g_stats = graph_statistics(G_base)
    env_info = get_environment_info()

    G_sub_base = subgraph_manager.get_accessible_subgraph(G_base, PROFILE)
    bc_base = resilience_engine._get_bridges(G_sub_base)

    # Eligible pool of known wheelchair edges
    eligible_pool = []
    for u, v, k, data in G_base.edges(keys=True, data=True):
        val = data.get("wheelchair")
        if is_attribute_known("wheelchair", val):
            eligible_pool.append((u, v, k, data))

    print(f"Candidate sampling pool size: {len(eligible_pool)} known edges. Testing pool size: {pool_size}.")

    all_run_records: List[Dict[str, Any]] = []

    for seed in seeds:
        set_seed(seed)
        sampled_indices = random.sample(range(len(eligible_pool)), pool_size)
        sampled_edges = [eligible_pool[idx] for idx in sampled_indices]

        # Duplicate in memory and mask
        G_masked = safe_copy_graph(G_base)
        masked_items = []
        for u, v, k, orig_data in sampled_edges:
            eid = get_edge_id(u, v, k)
            G_masked[u][v][k]["wheelchair"] = "unknown"
            if "wheelchair_accessible" in G_masked[u][v][k]:
                G_masked[u][v][k]["wheelchair_accessible"] = "unknown"
            masked_items.append((u, v, k, eid))

        # Ground truth oracle impact on clean G_base
        oracle_items = []
        for u, v, k, eid in masked_items:
            imp_base = evaluate_counterfactual_impact(G_base, u, v, k, PROFILE, bridge_cache=bc_base)
            oracle_items.append({
                "edge_id": eid,
                "u": u, "v": v, "key": k,
                "true_delta_arl": imp_base.delta_arl,
                "true_cad": imp_base.cad
            })

        oracle_sorted = sorted(oracle_items, key=lambda x: (x["true_delta_arl"], x["true_cad"]), reverse=True)
        oracle_top5_set = {c["edge_id"] for c in oracle_sorted[:5]}
        oracle_top10_set = {c["edge_id"] for c in oracle_sorted[:10]}
        oracle_relevances = [c["true_delta_arl"] for c in oracle_sorted]

        # Compute masked features for the candidates
        G_sub_masked = subgraph_manager.get_accessible_subgraph(G_masked, PROFILE)
        bc_masked = resilience_engine._get_bridges(G_sub_masked)

        candidate_data = []
        for u, v, k, eid in masked_items:
            data_m = G_masked[u][v][k]
            _, unc_m, _, _ = compute_edge_uncertainty(data_m, PROFILE)
            imp_m = evaluate_counterfactual_impact(G_masked, u, v, k, PROFILE, bridge_cache=bc_masked)
            # Find true delta_arl
            true_d_arl = next(item["true_delta_arl"] for item in oracle_items if item["edge_id"] == eid)

            candidate_data.append({
                "edge_id": eid,
                "u": u, "v": v, "key": k,
                "unc": unc_m,
                "impact": imp_m,
                "true_delta_arl": true_d_arl
            })

        max_d_arl = max([c["impact"].delta_arl for c in candidate_data] + [1.0])

        # Evaluate each baseline on this identical candidate pool
        for b_code, b_name in BASELINE_NAMES.items():
            scored_candidates = []
            for c in candidate_data:
                norm_unc = c["unc"]
                norm_d_arl = c["impact"].delta_arl / max_d_arl if max_d_arl > 0 else 0.0
                norm_cad = c["impact"].cad

                if b_code == "B1":
                    score = random.random()
                elif b_code == "B2":
                    score = norm_unc
                elif b_code == "B3":
                    score = norm_cad
                elif b_code == "B4":
                    score = norm_d_arl
                elif b_code == "B5":
                    score = 0.5 * norm_unc + 0.5 * norm_cad
                elif b_code == "B6":
                    score = 0.25 * norm_unc + 0.55 * norm_d_arl + 0.15 * norm_cad
                else:
                    score = 0.0

                scored_candidates.append({
                    "edge_id": c["edge_id"],
                    "score": score,
                    "true_delta_arl": c["true_delta_arl"],
                    "cad": norm_cad
                })

            # Sort descending by score, tie-break by CAD
            pred_sorted = sorted(scored_candidates, key=lambda x: (x["score"], x["cad"]), reverse=True)
            pred_scores = [c["score"] for c in scored_candidates]
            true_impacts = [c["true_delta_arl"] for c in scored_candidates]

            # Correlation metrics
            if len(set(true_impacts)) <= 1 or len(set(pred_scores)) <= 1:
                s_rho, k_tau = 0.0, 0.0
            else:
                s_rho, _ = spearmanr(pred_scores, true_impacts)
                k_tau, _ = kendalltau(pred_scores, true_impacts)
                if np.isnan(s_rho):
                    s_rho = 0.0
                if np.isnan(k_tau):
                    k_tau = 0.0

            pred_relevances = [c["true_delta_arl"] for c in pred_sorted]
            pred_top5_set = {c["edge_id"] for c in pred_sorted[:5]}
            pred_top10_set = {c["edge_id"] for c in pred_sorted[:10]}

            hit_5 = 1.0 if len(pred_top5_set & oracle_top5_set) > 0 else 0.0
            hit_10 = 1.0 if len(pred_top10_set & oracle_top10_set) > 0 else 0.0
            prec_5 = len(pred_top5_set & oracle_top5_set) / 5.0
            prec_10 = len(pred_top10_set & oracle_top10_set) / 10.0

            tic_5 = compute_tic(pred_relevances, oracle_relevances, 5)
            tic_10 = compute_tic(pred_relevances, oracle_relevances, 10)
            ndcg_5 = compute_ndcg(pred_relevances, oracle_relevances, 5)
            ndcg_10 = compute_ndcg(pred_relevances, oracle_relevances, 10)

            all_run_records.append({
                "seed": seed,
                "baseline_code": b_code,
                "baseline_name": b_name,
                "spearman_rho": round(float(s_rho), 4),
                "kendall_tau": round(float(k_tau), 4),
                "hit_at_5": hit_5,
                "hit_at_10": hit_10,
                "precision_at_5": round(prec_5, 4),
                "precision_at_10": round(prec_10, 4),
                "tic_at_5": round(tic_5, 4),
                "tic_at_10": round(tic_10, 4),
                "ndcg_at_5": round(ndcg_5, 4),
                "ndcg_at_10": round(ndcg_10, 4)
            })

    df_runs = pd.DataFrame(all_run_records)
    save_csv(df_runs, raw_dir / "baseline_run_results.csv")

    # Aggregate summaries per baseline
    summary_list = []
    for b_code, b_name in BASELINE_NAMES.items():
        b_df = df_runs[df_runs["baseline_code"] == b_code]
        summary_list.append({
            "baseline_code": b_code,
            "baseline_name": b_name,
            "spearman_rho_mean": round(float(b_df["spearman_rho"].mean()), 4),
            "spearman_rho_std": round(float(b_df["spearman_rho"].std()), 4),
            "kendall_tau_mean": round(float(b_df["kendall_tau"].mean()), 4),
            "kendall_tau_std": round(float(b_df["kendall_tau"].std()), 4),
            "hit_at_5_mean": round(float(b_df["hit_at_5"].mean()), 4),
            "hit_at_10_mean": round(float(b_df["hit_at_10"].mean()), 4),
            "precision_at_5_mean": round(float(b_df["precision_at_5"].mean()), 4),
            "precision_at_10_mean": round(float(b_df["precision_at_10"].mean()), 4),
            "tic_at_5_mean": round(float(b_df["tic_at_5"].mean()), 4),
            "tic_at_5_std": round(float(b_df["tic_at_5"].std()), 4),
            "tic_at_10_mean": round(float(b_df["tic_at_10"].mean()), 4),
            "tic_at_10_std": round(float(b_df["tic_at_10"].std()), 4),
            "ndcg_at_5_mean": round(float(b_df["ndcg_at_5"].mean()), 4),
            "ndcg_at_5_std": round(float(b_df["ndcg_at_5"].std()), 4),
            "ndcg_at_10_mean": round(float(b_df["ndcg_at_10"].mean()), 4),
            "ndcg_at_10_std": round(float(b_df["ndcg_at_10"].std()), 4)
        })

    df_summary = pd.DataFrame(summary_list)
    save_csv(df_summary, summary_dir / "baseline_comparison_summary.csv")

    # Statistical significance testing
    # 1. Friedman test across all 6 baselines for TIC@10 and NDCG@10
    friedman_results = {}
    for metric in ["tic_at_10", "ndcg_at_10", "spearman_rho"]:
        samples = [df_runs[df_runs["baseline_code"] == b][metric].values for b in BASELINE_NAMES.keys()]
        stat, pval = friedmanchisquare(*samples)
        friedman_results[metric] = {
            "statistic": round(float(stat), 4),
            "p_value": round(float(pval), 6)
        }

    # 2. Pairwise Wilcoxon signed-rank tests: B6 (PCVC) vs each baseline
    wilcoxon_results = {}
    b6_tic10 = df_runs[df_runs["baseline_code"] == "B6"]["tic_at_10"].values
    b6_ndcg10 = df_runs[df_runs["baseline_code"] == "B6"]["ndcg_at_10"].values

    for b_code in ["B1", "B2", "B3", "B4", "B5"]:
        b_name = BASELINE_NAMES[b_code]
        b_tic10 = df_runs[df_runs["baseline_code"] == b_code]["tic_at_10"].values
        b_ndcg10 = df_runs[df_runs["baseline_code"] == b_code]["ndcg_at_10"].values

        # TIC@10 Wilcoxon
        diff_tic = b6_tic10 - b_tic10
        if np.all(diff_tic == 0):
            w_stat_tic, w_pval_tic = 0.0, 1.0
        else:
            w_res = wilcoxon(b6_tic10, b_tic10)
            w_stat_tic, w_pval_tic = float(w_res.statistic), float(w_res.pvalue)

        # NDCG@10 Wilcoxon
        diff_ndcg = b6_ndcg10 - b_ndcg10
        if np.all(diff_ndcg == 0):
            w_stat_ndcg, w_pval_ndcg = 0.0, 1.0
        else:
            w_res_n = wilcoxon(b6_ndcg10, b_ndcg10)
            w_stat_ndcg, w_pval_ndcg = float(w_res_n.statistic), float(w_res_n.pvalue)

        wilcoxon_results[f"B6_vs_{b_code}"] = {
            "comparison": f"Full PCVC vs {b_name}",
            "tic_at_10": {"w_stat": round(w_stat_tic, 4), "p_value": round(w_pval_tic, 6)},
            "ndcg_at_10": {"w_stat": round(w_stat_ndcg, 4), "p_value": round(w_pval_ndcg, 6)}
        }

    stat_json = {
        "friedman_test_all_baselines": friedman_results,
        "pairwise_wilcoxon_vs_b6": wilcoxon_results
    }
    save_json(stat_json, summary_dir / "baseline_statistical_tests.json")

    e3_json = {
        "experiment": "E3_Baseline_Comparison",
        "candidate_pool_size": pool_size,
        "num_seeds": len(seeds),
        "seeds": seeds,
        "baseline_summaries": summary_list,
        "statistical_tests": stat_json,
        "environment": env_info
    }
    save_json(e3_json, summary_dir / "e3_summary.json")

    # Generate figures
    # A) TIC Comparison Bar Chart
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    x = np.arange(len(BASELINE_NAMES))
    width = 0.35
    tic5_vals = [s["tic_at_5_mean"] for s in summary_list]
    tic10_vals = [s["tic_at_10_mean"] for s in summary_list]
    tic5_err = [s["tic_at_5_std"] for s in summary_list]
    tic10_err = [s["tic_at_10_std"] for s in summary_list]

    ax.bar(x - width/2, tic5_vals, width, yerr=tic5_err, capsize=4, label="TIC@5", color="#3b82f6")
    ax.bar(x + width/2, tic10_vals, width, yerr=tic10_err, capsize=4, label="TIC@10", color="#1d4ed8")
    ax.set_ylabel("Total Impact Captured (TIC)", fontsize=10)
    ax.set_title("PCVC E3: Prioritization Performance vs Standard Baselines (10 Seeds)", fontsize=11, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{k}\n({v})" for k, v in BASELINE_NAMES.items()], fontsize=8)
    ax.set_ylim(0, 1.15)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(figures_dir / "baseline_tic_comparison.png")
    plt.close(fig)

    # B) NDCG Comparison Bar Chart
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    ndcg5_vals = [s["ndcg_at_5_mean"] for s in summary_list]
    ndcg10_vals = [s["ndcg_at_10_mean"] for s in summary_list]
    ndcg5_err = [s["ndcg_at_5_std"] for s in summary_list]
    ndcg10_err = [s["ndcg_at_10_std"] for s in summary_list]

    ax.bar(x - width/2, ndcg5_vals, width, yerr=ndcg5_err, capsize=4, label="NDCG@5", color="#10b981")
    ax.bar(x + width/2, ndcg10_vals, width, yerr=ndcg10_err, capsize=4, label="NDCG@10", color="#047857")
    ax.set_ylabel("NDCG Score", fontsize=10)
    ax.set_title("PCVC E3: Normalized Discounted Cumulative Gain vs Baselines", fontsize=11, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{k}\n({v})" for k, v in BASELINE_NAMES.items()], fontsize=8)
    ax.set_ylim(0, 1.15)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(figures_dir / "baseline_ndcg_comparison.png")
    plt.close(fig)

    print("\n--- E3 BASELINE COMPARISON SUMMARY (10 Seeds Mean) ---")
    for s in summary_list:
        print(f"{s['baseline_code']} ({s['baseline_name']:18s}) | Spearman: {s['spearman_rho_mean']:.3f} | TIC@5: {s['tic_at_5_mean']:.3f} | TIC@10: {s['tic_at_10_mean']:.3f} | NDCG@10: {s['ndcg_at_10_mean']:.3f} | Prec@10: {s['precision_at_10_mean']:.3f}")

    return e3_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PCVC E3 Baseline Comparison experiment")
    parser.add_argument("--seeds", nargs="+", type=int, default=SEEDS, help="Random seeds")
    args = parser.parse_args()
    run_e3(seeds=args.seeds)
