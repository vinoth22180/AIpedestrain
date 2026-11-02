"""
PCVC Refined Experiment E3: Baseline Benchmarking under Continuous Physical Detour Oracle
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Ranks identical candidate edge sets (N=40, seeds 42-51) across 6 baselines:
    B1: Random
    B2: Uncertainty-Only
    B3: CAD-Only
    B4: Oracle Impact Upper Bound (Reference only, uses ground truth Δd)
    B5: Uncertainty + CAD
    B6: Full PCVC (Operating without ground truth Δd)

Evaluates continuous metrics:
    - Spearman rho, Kendall tau
    - NDCG@5, NDCG@10
    - TIC@5, TIC@10
    - Mean True Detour Captured@5, @10
    - Maximum-impact bottleneck rank
    - Friedman test and Pairwise Wilcoxon signed-rank tests with Holm-Bonferroni correction
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import random
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import friedmanchisquare, wilcoxon

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

CANDIDATE_COUNT = 40
SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
TARGET_PROFILE = "wheelchair"

BASELINES = [
    {"code": "B1", "name": "Random", "is_deployable": True, "is_oracle_bound": False},
    {"code": "B2", "name": "Uncertainty-Only", "is_deployable": True, "is_oracle_bound": False},
    {"code": "B3", "name": "CAD-Only", "is_deployable": True, "is_oracle_bound": False},
    {"code": "B4", "name": "Oracle Impact Upper Bound", "is_deployable": False, "is_oracle_bound": True},
    {"code": "B5", "name": "Uncertainty + CAD", "is_deployable": True, "is_oracle_bound": False},
    {"code": "B6", "name": "Full PCVC", "is_deployable": True, "is_oracle_bound": False}
]


def holm_bonferroni_correction(p_values: List[float]) -> List[float]:
    """Applies step-down Holm-Bonferroni correction to a list of p-values."""
    m = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [0.0] * m
    cum_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        adj_p = min(1.0, (m - rank) * p)
        cum_max = max(cum_max, adj_p)
        adjusted[orig_idx] = round(cum_max, 6)
    return adjusted


def run_e3_detour_baselines(output_base_dir: Path = PROJECT_ROOT / "results/pcvc/e3_detour") -> Dict[str, Any]:
    output_base_dir.mkdir(parents=True, exist_ok=True)
    raw_csv_path = output_base_dir / "detour_baseline_results.csv"
    summary_csv_path = output_base_dir / "detour_baseline_summary.csv"
    stats_json_path = output_base_dir / "statistical_tests.json"

    print("=" * 80)
    print("PCVC Experiment E3 (Refined): Baseline Benchmarking with Physical Detour Oracle")
    print(f"Target Profile: {TARGET_PROFILE} | Candidates per seed: {CANDIDATE_COUNT} | Seeds: {SEEDS}")
    print("=" * 80)

    G_base = load_active_graph()
    G_sub_clean = subgraph_manager.get_accessible_subgraph(G_base, TARGET_PROFILE)
    bc_clean = resilience_engine._get_bridges(G_sub_clean)

    eligible_pool = []
    for u, v, k, data in G_base.edges(keys=True, data=True):
        val = data.get(TARGET_PROFILE)
        if is_attribute_known(TARGET_PROFILE, val):
            eligible_pool.append((u, v, k, data))

    # Pre-evaluate true Δd across pool
    pool_oracle_map = {}
    for u, v, k, data in eligible_pool:
        eid = get_edge_id(u, v, k)
        res = compute_physical_detour_impact(G_sub_clean, u, v, key=k, penalty_cap=PENALTY_CAP_DISCONNECTED)
        cad = resilience_engine.calculate_cad_for_edge(G_base, u, v, TARGET_PROFILE, bridge_cache=bc_clean)
        pool_oracle_map[eid] = {
            "edge_id": eid,
            "u": u, "v": v, "key": k,
            "orig_length_m": res["orig_length_m"],
            "bypass_length_m": res["bypass_length_m"],
            "delta_d": res["delta_d"],
            "effective_detour": res["effective_detour"],
            "is_disconnected": res["is_disconnected"],
            "cad": cad
        }

    raw_run_records = []

    for seed in SEEDS:
        set_seed(seed)
        random.seed(seed)

        # 1. Sample candidate universe (MUST BE 100% IDENTICAL ACROSS ALL BASELINES)
        sampled_idx = random.sample(range(len(eligible_pool)), CANDIDATE_COUNT)
        sampled_edges = [eligible_pool[idx] for idx in sampled_idx]
        candidate_eids = [get_edge_id(u, v, k) for u, v, k, _ in sampled_edges]
        cand_hash = hashlib.md5(";".join(sorted(candidate_eids)).encode()).hexdigest()

        # Oracle items for candidate set
        oracle_items = [pool_oracle_map[eid] for eid in candidate_eids]

        # 2. Masked graph
        G_masked = safe_copy_graph(G_base)
        for u, v, k, _ in sampled_edges:
            G_masked[u][v][k]["wheelchair"] = "unknown"
            if "wheelchair_accessible" in G_masked[u][v][k]:
                G_masked[u][v][k]["wheelchair_accessible"] = "unknown"

        G_sub_m = subgraph_manager.get_accessible_subgraph(G_masked, TARGET_PROFILE)
        bc_m = resilience_engine._get_bridges(G_sub_m)

        # 3. Extract candidate features on masked graph
        cand_features = []
        for u, v, k, _ in sampled_edges:
            eid = get_edge_id(u, v, k)
            data_m = G_masked[u][v][k]
            _, unc_m, _, _ = compute_edge_uncertainty(data_m, TARGET_PROFILE)
            imp_m = evaluate_counterfactual_impact(G_masked, u, v, k, TARGET_PROFILE, bridge_cache=bc_m)
            true_detour = pool_oracle_map[eid]["effective_detour"]
            cand_features.append({
                "edge_id": eid,
                "unc": unc_m,
                "delta_arl_m": imp_m.delta_arl,
                "cad_m": imp_m.cad,
                "true_detour": true_detour
            })

        max_d_arl = max([c["delta_arl_m"] for c in cand_features] + [1.0])

        # 4. Score each baseline
        for b_info in BASELINES:
            b_code = b_info["code"]
            b_name = b_info["name"]

            scored = []
            for c in cand_features:
                norm_unc = c["unc"]
                norm_d_arl = c["delta_arl_m"] / max_d_arl if max_d_arl > 0 else 0.0
                norm_cad = c["cad_m"]
                true_detour = c["true_detour"]

                if b_code == "B1":
                    score = random.random()
                elif b_code == "B2":
                    score = norm_unc
                elif b_code == "B3":
                    score = norm_cad
                elif b_code == "B4":
                    score = true_detour # Ground truth oracle upper bound
                elif b_code == "B5":
                    score = 0.5 * norm_unc + 0.5 * norm_cad
                elif b_code == "B6":
                    score = 0.25 * norm_unc + 0.55 * norm_d_arl + 0.15 * norm_cad

                scored.append({"edge_id": c["edge_id"], "score": score})

            metrics = evaluate_continuous_ranking_metrics(
                scored_candidates=scored,
                oracle_candidates=oracle_items,
                k_list=[5, 10],
                penalty_cap=PENALTY_CAP_DISCONNECTED
            )

            raw_run_records.append({
                "seed": seed,
                "baseline_code": b_code,
                "baseline_name": b_name,
                "candidate_hash": cand_hash,
                "is_deployable": b_info["is_deployable"],
                "is_oracle_bound": b_info["is_oracle_bound"],
                **metrics
            })

    df_raw = pd.DataFrame(raw_run_records)
    save_csv(df_raw, raw_csv_path)

    # 5. Summarize baselines
    summary_rows = []
    for b_info in BASELINES:
        b_code = b_info["code"]
        b_name = b_info["name"]
        sub = df_raw[df_raw["baseline_code"] == b_code]

        summary_rows.append({
            "baseline_code": b_code,
            "baseline_name": b_name,
            "is_deployable": b_info["is_deployable"],
            "spearman_rho_mean": round(float(sub["spearman_rho"].mean()), 4),
            "spearman_rho_std": round(float(sub["spearman_rho"].std()), 4),
            "kendall_tau_mean": round(float(sub["kendall_tau"].mean()), 4),
            "kendall_tau_std": round(float(sub["kendall_tau"].std()), 4),
            "tic_at_5_mean": round(float(sub["tic_at_5"].mean()), 4),
            "tic_at_5_std": round(float(sub["tic_at_5"].std()), 4),
            "tic_at_10_mean": round(float(sub["tic_at_10"].mean()), 4),
            "tic_at_10_std": round(float(sub["tic_at_10"].std()), 4),
            "ndcg_at_5_mean": round(float(sub["ndcg_at_5"].mean()), 4),
            "ndcg_at_5_std": round(float(sub["ndcg_at_5"].std()), 4),
            "ndcg_at_10_mean": round(float(sub["ndcg_at_10"].mean()), 4),
            "ndcg_at_10_std": round(float(sub["ndcg_at_10"].std()), 4),
            "mean_detour_at_5_mean": round(float(sub["mean_detour_captured_at_5"].mean()), 1),
            "mean_detour_at_5_std": round(float(sub["mean_detour_captured_at_5"].std()), 1),
            "mean_detour_at_10_mean": round(float(sub["mean_detour_captured_at_10"].mean()), 1),
            "mean_detour_at_10_std": round(float(sub["mean_detour_captured_at_10"].std()), 1),
            "min_rank_max_edge_mean": round(float(sub["min_rank_max_detour_edge"].mean()), 2),
            "min_rank_max_edge_std": round(float(sub["min_rank_max_detour_edge"].std()), 2)
        })

    df_summary = pd.DataFrame(summary_rows)
    save_csv(df_summary, summary_csv_path)

    # 6. Relative Gain of Full PCVC (B6) over Deployable Baselines
    b6_sub = df_summary[df_summary["baseline_code"] == "B6"].iloc[0]
    relative_gains = {}
    for comp_code in ["B1", "B2", "B3", "B5"]:
        comp_row = df_summary[df_summary["baseline_code"] == comp_code].iloc[0]
        comp_name = comp_row["baseline_name"]

        tic10_gain = ((b6_sub["tic_at_10_mean"] - comp_row["tic_at_10_mean"]) / comp_row["tic_at_10_mean"]) * 100.0 if comp_row["tic_at_10_mean"] > 0 else 0.0
        ndcg10_gain = ((b6_sub["ndcg_at_10_mean"] - comp_row["ndcg_at_10_mean"]) / comp_row["ndcg_at_10_mean"]) * 100.0 if comp_row["ndcg_at_10_mean"] > 0 else 0.0
        detour10_gain = ((b6_sub["mean_detour_at_10_mean"] - comp_row["mean_detour_at_10_mean"]) / comp_row["mean_detour_at_10_mean"]) * 100.0 if comp_row["mean_detour_at_10_mean"] > 0 else 0.0

        relative_gains[f"PCVC_vs_{comp_name}"] = {
            "tic_at_10_gain_pct": round(tic10_gain, 2),
            "ndcg_at_10_gain_pct": round(ndcg10_gain, 2),
            "detour_captured_at_10_gain_pct": round(detour10_gain, 2),
            "rank_max_edge_improvement": round(comp_row["min_rank_max_edge_mean"] - b6_sub["min_rank_max_edge_mean"], 2)
        }

    # 7. Statistical Tests (Friedman Test across deployable baselines + Wilcoxon signed-rank paired tests)
    deployable_codes = ["B1", "B2", "B3", "B5", "B6"]
    
    # Pivot for paired tests across 10 seeds
    pivot_tic10 = df_raw[df_raw["baseline_code"].isin(deployable_codes)].pivot(index="seed", columns="baseline_code", values="tic_at_10")
    pivot_ndcg10 = df_raw[df_raw["baseline_code"].isin(deployable_codes)].pivot(index="seed", columns="baseline_code", values="ndcg_at_10")
    pivot_detour10 = df_raw[df_raw["baseline_code"].isin(deployable_codes)].pivot(index="seed", columns="baseline_code", values="mean_detour_captured_at_10")

    # Friedman test
    f_stat_tic, p_friedman_tic = friedmanchisquare(*[pivot_tic10[c] for c in deployable_codes])
    f_stat_ndcg, p_friedman_ndcg = friedmanchisquare(*[pivot_ndcg10[c] for c in deployable_codes])
    f_stat_detour, p_friedman_detour = friedmanchisquare(*[pivot_detour10[c] for c in deployable_codes])

    # Pairwise Wilcoxon: PCVC (B6) vs each deployable baseline
    wilcoxon_tests = []
    comparisons = [("B1", "Random"), ("B2", "Uncertainty-Only"), ("B3", "CAD-Only"), ("B5", "Uncertainty + CAD")]
    
    raw_p_tic = []
    raw_p_ndcg = []
    raw_p_detour = []

    for comp_code, comp_name in comparisons:
        # TIC@10
        diff_tic = pivot_tic10["B6"] - pivot_tic10[comp_code]
        if np.all(diff_tic == 0):
            w_stat_tic, p_tic = 0.0, 1.0
        else:
            w_res = wilcoxon(pivot_tic10["B6"], pivot_tic10[comp_code], alternative="two-sided")
            w_stat_tic, p_tic = float(w_res.statistic), float(w_res.pvalue)

        # NDCG@10
        diff_ndcg = pivot_ndcg10["B6"] - pivot_ndcg10[comp_code]
        if np.all(diff_ndcg == 0):
            w_stat_ndcg, p_ndcg = 0.0, 1.0
        else:
            w_res = wilcoxon(pivot_ndcg10["B6"], pivot_ndcg10[comp_code], alternative="two-sided")
            w_stat_ndcg, p_ndcg = float(w_res.statistic), float(w_res.pvalue)

        # Detour@10
        diff_detour = pivot_detour10["B6"] - pivot_detour10[comp_code]
        if np.all(diff_detour == 0):
            w_stat_det, p_det = 0.0, 1.0
        else:
            w_res = wilcoxon(pivot_detour10["B6"], pivot_detour10[comp_code], alternative="two-sided")
            w_stat_det, p_det = float(w_res.statistic), float(w_res.pvalue)

        raw_p_tic.append(p_tic)
        raw_p_ndcg.append(p_ndcg)
        raw_p_detour.append(p_det)

        wilcoxon_tests.append({
            "comparison": f"Full PCVC (B6) vs {comp_name} ({comp_code})",
            "comp_code": comp_code,
            "tic_at_10_wilcoxon_stat": w_stat_tic,
            "tic_at_10_p_raw": round(p_tic, 5),
            "ndcg_at_10_wilcoxon_stat": w_stat_ndcg,
            "ndcg_at_10_p_raw": round(p_ndcg, 5),
            "detour_10_wilcoxon_stat": w_stat_det,
            "detour_10_p_raw": round(p_det, 5)
        })

    # Apply Holm-Bonferroni correction
    adj_p_tic = holm_bonferroni_correction(raw_p_tic)
    adj_p_ndcg = holm_bonferroni_correction(raw_p_ndcg)
    adj_p_detour = holm_bonferroni_correction(raw_p_detour)

    for i, t in enumerate(wilcoxon_tests):
        t["tic_at_10_p_holm_bonferroni"] = adj_p_tic[i]
        t["ndcg_at_10_p_holm_bonferroni"] = adj_p_ndcg[i]
        t["detour_10_p_holm_bonferroni"] = adj_p_detour[i]
        t["is_significant_0_05"] = bool(adj_p_tic[i] < 0.05 and adj_p_ndcg[i] < 0.05)

    stats_payload = {
        "friedman_test": {
            "deployable_baselines": deployable_codes,
            "tic_at_10": {"f_stat": round(float(f_stat_tic), 4), "p_value": round(float(p_friedman_tic), 5)},
            "ndcg_at_10": {"f_stat": round(float(f_stat_ndcg), 4), "p_value": round(float(p_friedman_ndcg), 5)},
            "mean_detour_at_10": {"f_stat": round(float(f_stat_detour), 4), "p_value": round(float(p_friedman_detour), 5)}
        },
        "pairwise_wilcoxon_tests": wilcoxon_tests,
        "relative_gains": relative_gains
    }
    save_json(stats_payload, stats_json_path)

    # 8. Plot 4: baseline_detour_comparison.png
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    names = [b["name"] for b in BASELINES]
    colors = ["#95a5a6", "#3498db", "#f39c12", "#27ae60", "#9b59b6", "#e74c3c"]

    # Bar 1: TIC@10 and NDCG@10
    x = np.arange(len(BASELINES))
    w = 0.35
    ax1.bar(x - w/2, df_summary["tic_at_10_mean"], w, yerr=df_summary["tic_at_10_std"], capsize=4, label="TIC@10", color="#2980b9")
    ax1.bar(x + w/2, df_summary["ndcg_at_10_mean"], w, yerr=df_summary["ndcg_at_10_std"], capsize=4, label="NDCG@10", color="#e67e22")
    ax1.set_xticks(x)
    ax1.set_xticklabels(names, rotation=25, ha="right", fontsize=9)
    ax1.set_ylabel("Metric Score")
    ax1.set_ylim(0.0, 1.15)
    ax1.set_title("E3 Baselines: Continuous TIC@10 & NDCG@10", fontsize=11, fontweight="bold")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Bar 2: Mean Detour Captured@10 (meters)
    bars = ax2.bar(x, df_summary["mean_detour_at_10_mean"], yerr=df_summary["mean_detour_at_10_std"], capsize=4, color=colors, alpha=0.85, edgecolor="black")
    ax2.set_xticks(x)
    ax2.set_xticklabels(names, rotation=25, ha="right", fontsize=9)
    ax2.set_ylabel("Mean Detour Captured at Top-10 (meters)")
    ax2.set_title("E3 Baselines: Physical Walking Detour Captured (m)", fontsize=11, fontweight="bold")
    ax2.grid(True, alpha=0.3)

    for bar in bars:
        h = bar.get_height()
        ax2.annotate(f"{h:.0f}m", xy=(bar.get_x() + bar.get_width()/2, h), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")

    plt.tight_layout()
    plt.savefig(output_base_dir / "baseline_detour_comparison.png", dpi=300)
    plt.close()

    print("\n--- E3 REFINED BASELINE SUMMARY ---")
    for r in summary_rows:
        print(f"{r['baseline_code']:2s} ({r['baseline_name']:26s}): TIC@10={r['tic_at_10_mean']:.4f}±{r['tic_at_10_std']:.4f} | NDCG@10={r['ndcg_at_10_mean']:.4f}±{r['ndcg_at_10_std']:.4f} | Detour@10={r['mean_detour_at_10_mean']:.1f}m±{r['mean_detour_at_10_std']:.1f}m | RankMax={r['min_rank_max_edge_mean']:.2f} | Rho={r['spearman_rho_mean']:.4f}")

    print("\n--- RELATIVE GAINS OF FULL PCVC (B6) ---")
    for k, v in relative_gains.items():
        print(f"{k:30s}: TIC@10 Gain: {v['tic_at_10_gain_pct']:+.1f}% | NDCG@10 Gain: {v['ndcg_at_10_gain_pct']:+.1f}% | Detour Captured Gain: {v['detour_captured_at_10_gain_pct']:+.1f}% | Top Bottleneck Rank Imprv: {v['rank_max_edge_improvement']:+.2f}")

    print(f"\nFriedman Test across deployable baselines: Q={f_stat_tic:.3f}, p={p_friedman_tic:.5e}")
    for t in wilcoxon_tests:
        print(f"Wilcoxon: {t['comparison']:38s} -> TIC p_adj={t['tic_at_10_p_holm_bonferroni']:.5f} | NDCG p_adj={t['ndcg_at_10_p_holm_bonferroni']:.5f}")

    print(f"\nE3 Refined Baselines complete. Outputs written to {output_base_dir}")
    return {"summary": summary_rows, "stats": stats_payload}


if __name__ == "__main__":
    run_e3_detour_baselines()
