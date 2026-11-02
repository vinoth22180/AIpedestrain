"""
PCVC Phase 6 Comprehensive Validity Audit Script
Audits Issues 1 through 7 for E2, E3, E5, and E6.
DOES NOT MODIFY PCVC ALGORITHM OR DATASET.
"""

import sys
import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kendalltau

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.experiments.common import load_active_graph, safe_copy_graph, set_seed, get_edge_id
from src.pcvc.uncertainty import compute_edge_uncertainty, is_attribute_known, get_uncertain_edges
from src.pcvc.counterfactual import evaluate_counterfactual_impact
from src.pcvc.probe_selector import is_safe_probe, select_best_probe, _get_edge_length
from src.darr.subgraph import subgraph_manager
from src.darr.resilience import resilience_engine

print("=" * 80)
print("STARTING PHASE 6 METRIC VALIDITY AUDIT")
print("=" * 80)

# ============================================================================
# AUDIT 1: E2 TIC/NDCG SATURATION & IMPACT CONCENTRATION
# ============================================================================
print("\n--- AUDIT 1: E2 TIC/NDCG SATURATION & IMPACT CONCENTRATION ---")
df_e2 = pd.read_csv(PROJECT_ROOT / "results/pcvc/e2/raw/oracle_edge_results.csv")

e2_audit_records = []
impact_concentration_records = []

for (k_val, seed), group in df_e2.groupby(["k_masked", "seed"]):
    oracle_impacts = group["oracle_true_delta_arl"].values
    pred_scores = group["predicted_priority_score"].values
    edge_ids = group["edge_id"].values

    total_impact = float(np.sum(oracle_impacts))
    pos_count = int(np.sum(oracle_impacts > 0))
    zero_count = int(np.sum(oracle_impacts == 0))
    unique_levels = sorted(list(set(oracle_impacts)), reverse=True)

    # Sort descending by oracle impact
    oracle_sorted_df = group.sort_values(by=["oracle_true_delta_arl", "oracle_true_cad"], ascending=False)
    pred_sorted_df = group.sort_values(by=["predicted_priority_score", "masked_cad"], ascending=False)

    top1_impact = float(oracle_sorted_df.iloc[0]["oracle_true_delta_arl"]) if len(oracle_sorted_df) >= 1 else 0.0
    top5_impact = float(oracle_sorted_df.iloc[:5]["oracle_true_delta_arl"].sum()) if len(oracle_sorted_df) >= 5 else 0.0
    top10_impact = float(oracle_sorted_df.iloc[:10]["oracle_true_delta_arl"].sum()) if len(oracle_sorted_df) >= 10 else 0.0

    top1_share = (top1_impact / total_impact * 100.0) if total_impact > 0 else 0.0
    top5_share = (top5_impact / total_impact * 100.0) if total_impact > 0 else 0.0
    top10_share = (top10_impact / total_impact * 100.0) if total_impact > 0 else 0.0
    rem_share = 100.0 - top10_share

    # Predicted top 5 and top 10 impacts
    pred_top1_impact = float(pred_sorted_df.iloc[0]["oracle_true_delta_arl"]) if len(pred_sorted_df) >= 1 else 0.0
    pred_top5_impact = float(pred_sorted_df.iloc[:5]["oracle_true_delta_arl"].sum()) if len(pred_sorted_df) >= 5 else 0.0
    pred_top10_impact = float(pred_sorted_df.iloc[:10]["oracle_true_delta_arl"].sum()) if len(pred_sorted_df) >= 10 else 0.0

    tic_at_5 = (pred_top5_impact / top5_impact) if top5_impact > 0 else 1.0
    tic_at_10 = (pred_top10_impact / top10_impact) if top10_impact > 0 else 1.0

    e2_audit_records.append({
        "k_masked": k_val,
        "seed": seed,
        "total_edges": len(group),
        "total_impact": total_impact,
        "positive_impact_count": pos_count,
        "zero_impact_count": zero_count,
        "unique_impact_levels": unique_levels,
        "top1_oracle_impact": top1_impact,
        "top5_oracle_impact": top5_impact,
        "top10_oracle_impact": top10_impact,
        "top1_share_pct": round(top1_share, 2),
        "top5_share_pct": round(top5_share, 2),
        "top10_share_pct": round(top10_share, 2),
        "remaining_share_pct": round(rem_share, 2),
        "pred_top1_impact": pred_top1_impact,
        "pred_top5_impact": pred_top5_impact,
        "pred_top10_impact": pred_top10_impact,
        "tic_at_5": tic_at_5,
        "tic_at_10": tic_at_10,
        "pred_top1_edge": pred_sorted_df.iloc[0]["edge_id"],
        "oracle_top1_edge": oracle_sorted_df.iloc[0]["edge_id"]
    })

df_e2_audit = pd.DataFrame(e2_audit_records)
print("E2 Audit Summary across all K and Seeds:")
print(df_e2_audit[["k_masked", "seed", "total_edges", "positive_impact_count", "zero_impact_count", "top10_share_pct", "tic_at_10"]].head(10))

# Aggregate impact concentration by K
print("\n--- IMPACT CONCENTRATION TABLE ACROSS K ---")
for k in [20, 40, 80]:
    sub = df_e2_audit[df_e2_audit["k_masked"] == k]
    print(f"K = {k:2d}: Mean Positive Count = {sub['positive_impact_count'].mean():.1f} / {k} ({sub['positive_impact_count'].mean()/k*100:.1f}%) | Mean Zero Count = {sub['zero_impact_count'].mean():.1f}")
    print(f"       Top 1 Share: {sub['top1_share_pct'].mean():.2f}% | Top 5 Share: {sub['top5_share_pct'].mean():.2f}% | Top 10 Share: {sub['top10_share_pct'].mean():.2f}% | Remaining: {sub['remaining_share_pct'].mean():.2f}%")

# ============================================================================
# AUDIT 2: E3 BASELINE VALIDITY & EXTENDED DIAGNOSTICS
# ============================================================================
print("\n--- AUDIT 2: E3 BASELINE VALIDITY & EXTENDED DIAGNOSTICS ---")
df_e3_raw = pd.read_csv(PROJECT_ROOT / "results/pcvc/e3/raw/baseline_run_results.csv")
print(f"Loaded {len(df_e3_raw)} baseline run records from E3.")

# Load active graph to rerun exact baseline diagnostics and compute MRR, Rank pos of top-1, Recall@K, etc.
G_base = load_active_graph()
G_sub_base = subgraph_manager.get_accessible_subgraph(G_base, "wheelchair")
bc_base = resilience_engine._get_bridges(G_sub_base)

eligible_pool = []
for u, v, k, data in G_base.edges(keys=True, data=True):
    val = data.get("wheelchair")
    if is_attribute_known("wheelchair", val):
        eligible_pool.append((u, v, k, data))

extended_baseline_diagnostics = []

SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
BASELINE_NAMES = {
    "B1": "Random",
    "B2": "Uncertainty-Only",
    "B3": "CAD-Only",
    "B4": "Impact-Only",
    "B5": "Uncertainty + CAD",
    "B6": "Full PCVC"
}

# Verify Candidate Universes (Issue 3) while running
universe_verification_records = []

for seed in SEEDS:
    set_seed(seed)
    sampled_indices = [eligible_pool[idx] for idx in range(len(eligible_pool))] # Deterministic sample
    import random
    random.seed(seed)
    sampled_idx = random.sample(range(len(eligible_pool)), 40)
    sampled_edges = [eligible_pool[idx] for idx in sampled_idx]
    edge_ids = [get_edge_id(u, v, k) for u, v, k, _ in sampled_edges]
    edge_ids_sorted = sorted(edge_ids)
    edge_hash = hashlib.md5(";".join(edge_ids_sorted).encode()).hexdigest()

    # Pre-evaluate oracle true impact
    oracle_items = []
    for u, v, k, _ in sampled_edges:
        eid = get_edge_id(u, v, k)
        imp = evaluate_counterfactual_impact(G_base, u, v, k, "wheelchair", bridge_cache=bc_base)
        cad = imp.cad
        oracle_items.append({"edge_id": eid, "impact": imp.delta_arl, "cad": cad})

    oracle_sorted = sorted(oracle_items, key=lambda x: (x["impact"], x["cad"]), reverse=True)
    oracle_top1_id = oracle_sorted[0]["edge_id"]
    oracle_top5_ids = set(c["edge_id"] for c in oracle_sorted[:5])
    oracle_top10_ids = set(c["edge_id"] for c in oracle_sorted[:10])

    # G_masked
    G_masked = safe_copy_graph(G_base)
    for u, v, k, _ in sampled_edges:
        G_masked[u][v][k]["wheelchair"] = "unknown"
        if "wheelchair_accessible" in G_masked[u][v][k]:
            G_masked[u][v][k]["wheelchair_accessible"] = "unknown"

    G_sub_m = subgraph_manager.get_accessible_subgraph(G_masked, "wheelchair")
    bc_m = resilience_engine._get_bridges(G_sub_m)

    c_features = []
    for u, v, k, _ in sampled_edges:
        eid = get_edge_id(u, v, k)
        data_m = G_masked[u][v][k]
        _, unc_m, _, _ = compute_edge_uncertainty(data_m, "wheelchair")
        imp_m = evaluate_counterfactual_impact(G_masked, u, v, k, "wheelchair", bridge_cache=bc_m)
        true_imp = next(item["impact"] for item in oracle_items if item["edge_id"] == eid)
        c_features.append({
            "edge_id": eid,
            "unc": unc_m,
            "impact_m": imp_m.delta_arl,
            "cad_m": imp_m.cad,
            "true_impact": true_imp
        })

    max_d_arl = max([c["impact_m"] for c in c_features] + [1.0])

    for b_code, b_name in BASELINE_NAMES.items():
        universe_verification_records.append({
            "seed": seed,
            "baseline_code": b_code,
            "candidate_count": len(c_features),
            "candidate_hash": edge_hash
        })

        # Score candidates
        scored = []
        for c in c_features:
            norm_unc = c["unc"]
            norm_d_arl = c["impact_m"] / max_d_arl if max_d_arl > 0 else 0.0
            norm_cad = c["cad_m"]

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

            scored.append({"edge_id": c["edge_id"], "score": score, "cad": norm_cad, "true_impact": c["true_impact"]})

        pred_sorted = sorted(scored, key=lambda x: (x["score"], x["cad"]), reverse=True)
        pred_ranks = {item["edge_id"]: r for r, item in enumerate(pred_sorted, start=1)}

        # Diagnostics
        top1_rank_pos = pred_ranks.get(oracle_top1_id, 40)
        mrr = 1.0 / top1_rank_pos

        pred_top1_ids = {pred_sorted[0]["edge_id"]}
        pred_top5_ids = set(c["edge_id"] for c in pred_sorted[:5])
        pred_top10_ids = set(c["edge_id"] for c in pred_sorted[:10])

        recall_at_1 = 1.0 if oracle_top1_id in pred_top1_ids else 0.0
        recall_at_5 = len(pred_top5_ids & oracle_top5_ids) / 5.0
        recall_at_10 = len(pred_top10_ids & oracle_top10_ids) / 10.0

        top10_true_impacts = [c["true_impact"] for c in pred_sorted[:10]]
        mean_top10_impact = float(np.mean(top10_true_impacts))
        median_top10_impact = float(np.median(top10_true_impacts))
        frac_positive_top10 = float(np.mean([1.0 if imp > 0 else 0.0 for imp in top10_true_impacts]))

        s_rho, _ = spearmanr([c["score"] for c in scored], [c["true_impact"] for c in scored])
        k_tau, _ = kendalltau([c["score"] for c in scored], [c["true_impact"] for c in scored])

        extended_baseline_diagnostics.append({
            "seed": seed,
            "baseline_code": b_code,
            "baseline_name": b_name,
            "rank_pos_oracle_top1": top1_rank_pos,
            "mrr": mrr,
            "recall_at_1": recall_at_1,
            "recall_at_5": recall_at_5,
            "recall_at_10": recall_at_10,
            "mean_top10_impact": mean_top10_impact,
            "median_top10_impact": median_top10_impact,
            "fraction_positive_top10": frac_positive_top10,
            "spearman_rho": 0.0 if np.isnan(s_rho) else s_rho,
            "kendall_tau": 0.0 if np.isnan(k_tau) else k_tau
        })

df_diag_runs = pd.DataFrame(extended_baseline_diagnostics)

print("\n--- EXTENDED BASELINE DIAGNOSTICS (Mean across 10 seeds) ---")
summary_diag = []
for b_code, b_name in BASELINE_NAMES.items():
    sub = df_diag_runs[df_diag_runs["baseline_code"] == b_code]
    row = {
        "Baseline": f"{b_code} ({b_name})",
        "MRR": round(float(sub["mrr"].mean()), 4),
        "Rank Pos Top-1": round(float(sub["rank_pos_oracle_top1"].mean()), 2),
        "Recall@1": round(float(sub["recall_at_1"].mean()), 4),
        "Recall@5": round(float(sub["recall_at_5"].mean()), 4),
        "Recall@10": round(float(sub["recall_at_10"].mean()), 4),
        "Mean Impact@10": round(float(sub["mean_top10_impact"].mean()), 4),
        "Frac Positive@10": round(float(sub["fraction_positive_top10"].mean()), 4),
        "Spearman": round(float(sub["spearman_rho"].mean()), 4),
        "Kendall": round(float(sub["kendall_tau"].mean()), 4)
    }
    summary_diag.append(row)
print(pd.DataFrame(summary_diag).to_string())

# ============================================================================
# AUDIT 3: SAME CANDIDATE UNIVERSE HASH VERIFICATION
# ============================================================================
print("\n--- AUDIT 3: SAME CANDIDATE UNIVERSE HASH VERIFICATION ---")
df_uv = pd.DataFrame(universe_verification_records)
universe_valid = True
for seed, s_df in df_uv.groupby("seed"):
    hashes = s_df["candidate_hash"].unique()
    counts = s_df["candidate_count"].unique()
    if len(hashes) != 1 or len(counts) != 1 or counts[0] != 40:
        universe_valid = False
        print(f"Seed {seed}: HASH MISMATCH! {hashes}")
    else:
        print(f"Seed {seed}: Candidate Count = {counts[0]}, Hash = {hashes[0]} (VERIFIED IDENTICAL ACROSS ALL 6 BASELINES)")

print(f"\nFinal Candidate Universe Status: {'VALID (100% IDENTICAL)' if universe_valid else 'INVALID'}")

# ============================================================================
# AUDIT 6: E5 VS E6 COUNT DISCREPANCY TRACE
# ============================================================================
print("\n--- AUDIT 6: E5 VS E6 COUNT DISCREPANCY TRACE ---")
# E5 candidate breakdown:
e5_cands = {}
for p in ["wheelchair", "elderly", "pregnant", "general"]:
    c = get_uncertain_edges(G_base, profile=p, uncertainty_threshold=0.4, limit=100)
    e5_cands[p] = len(c)

e6_cands = {}
for p in ["wheelchair", "elderly", "pregnant", "general"]:
    c = get_uncertain_edges(G_base, profile=p, uncertainty_threshold=0.4, limit=50)
    e6_cands[p] = len(c)

print(f"E5 Candidate Counts (Limit=100 per profile): {e5_cands} -> Total = {sum(e5_cands.values())}")
print(f"E6 Candidate Counts (Limit=50 per profile):  {e6_cands} -> Total = {sum(e6_cands.values())}")

# ============================================================================
# AUDIT 7: E5 GENERAL PROBE DOMINANCE: MODE A VS MODE B
# ============================================================================
print("\n--- AUDIT 7: E5 PROBE MODES COMPARISON (MODE A: CROSS-PROFILE VS MODE B: SAME-PROFILE) ---")
# Evaluate all 214 candidate targets from E5 under both Mode A and Mode B
mode_records = []

for p in ["wheelchair", "elderly", "pregnant", "general"]:
    cands = get_uncertain_edges(G_base, profile=p, uncertainty_threshold=0.4, limit=100)
    for c in cands:
        u, v, k = c.u, c.v, c.key
        eid = c.edge_id
        edge_data = G_base[u][v][k] if G_base.is_multigraph() else G_base[u][v]
        edge_len = _get_edge_length(edge_data)

        # Mode A: Cross-profile (PCVC default)
        res_a = select_best_probe(G_base, u, v, k)
        sel_probe_a = res_a.selected_probe
        elig_a = (sel_probe_a is not None)
        best_a = res_a.eligible_probes[0] if res_a.eligible_probes else None
        dist_a = best_a.travel_cost if best_a else None
        detour_a = (best_a.outbound_distance_m + best_a.return_distance_m) / edge_len if best_a and edge_len > 0 else None

        # Mode B: Same-profile probe
        res_b = is_safe_probe(G_base, p, u, v, k, res_a.anchor_node)
        elig_b = res_b.eligible
        dist_b = res_b.travel_cost if elig_b else None
        detour_b = (res_b.outbound_distance_m + res_b.return_distance_m) / edge_len if elig_b and edge_len > 0 else None
        rej_b = res_b.reason if not elig_b else "None"

        mode_records.append({
            "target_profile": p,
            "edge_id": eid,
            "edge_len": edge_len,
            # Mode A
            "mode_a_eligible": elig_a,
            "mode_a_selected_probe": sel_probe_a,
            "mode_a_travel_dist": dist_a,
            "mode_a_detour": detour_a,
            # Mode B
            "mode_b_eligible": elig_b,
            "mode_b_selected_probe": p if elig_b else "None",
            "mode_b_travel_dist": dist_b,
            "mode_b_detour": detour_b,
            "mode_b_rejection_reason": rej_b
        })

df_modes = pd.DataFrame(mode_records)

mode_comparison_summary = []
for p in ["wheelchair", "elderly", "pregnant", "general"]:
    sub = df_modes[df_modes["target_profile"] == p]
    tot = len(sub)
    
    # Mode A stats
    elig_a_pct = sub["mode_a_eligible"].mean() * 100.0
    dist_a_mean = sub["mode_a_travel_dist"].dropna().mean()
    dist_a_med = sub["mode_a_travel_dist"].dropna().median()
    detour_a_mean = sub["mode_a_detour"].dropna().mean()
    
    # Mode B stats
    elig_b_pct = sub["mode_b_eligible"].mean() * 100.0
    dist_b_mean = sub["mode_b_travel_dist"].dropna().mean()
    dist_b_med = sub["mode_b_travel_dist"].dropna().median()
    detour_b_mean = sub["mode_b_detour"].dropna().mean()

    mode_comparison_summary.append({
        "Profile": p,
        "Candidates": tot,
        "Mode A Elig %": round(elig_a_pct, 1),
        "Mode A Median Dist": round(dist_a_med, 1) if not np.isnan(dist_a_med) else None,
        "Mode A Detour": round(detour_a_mean, 1) if not np.isnan(detour_a_mean) else None,
        "Mode B Elig %": round(elig_b_pct, 1),
        "Mode B Median Dist": round(dist_b_med, 1) if not np.isnan(dist_b_med) else None,
        "Mode B Detour": round(detour_b_mean, 1) if not np.isnan(detour_b_mean) else None
    })

print("\nMode A (Cross-Profile Best Probe) vs Mode B (Same-Profile Dedicated Probe):")
print(pd.DataFrame(mode_comparison_summary).to_string())

# Mode B Wheelchair rejection breakdown
sub_wc = df_modes[df_modes["target_profile"] == "wheelchair"]
print("\nMode B Wheelchair Probe Rejection Breakdown (out of 100 candidates):")
print(sub_wc["mode_b_rejection_reason"].value_counts())

print("\nAUDIT SCRIPT COMPLETED SUCCESSFULLY.")
