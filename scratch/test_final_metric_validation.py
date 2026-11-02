import sys
import pickle
import random
import hashlib
import json
import itertools
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kendalltau
import networkx as nx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.darr.subgraph import subgraph_manager
from src.darr.resilience import resilience_engine
from src.darr.config import get_profile_config, DARR_CONFIG
from src.pcvc.uncertainty import compute_edge_uncertainty, is_attribute_known
from src.pcvc.counterfactual import evaluate_counterfactual_impact
from scripts.experiments.common import load_active_graph, set_seed, get_edge_id, safe_copy_graph

print("=" * 80, flush=True)
print("PCVC FINAL METRIC VALIDATION & REFINED E2/E3 EXPERIMENTAL AUDIT", flush=True)
print("=" * 80, flush=True)

G = load_active_graph()
G_sub_wc = subgraph_manager.get_accessible_subgraph(G, "wheelchair")
bc_wc = resilience_engine._get_bridges(G_sub_wc)

eligible_pool = []
for u, v, k, data in G.edges(keys=True, data=True):
    val = data.get("wheelchair")
    if is_attribute_known("wheelchair", val):
        eligible_pool.append((u, v, k, data))

print(f"Total edges: {G.number_of_edges()}, Nodes: {G.number_of_nodes()}", flush=True)
print(f"Eligible wheelchair pool: {len(eligible_pool)}", flush=True)

SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
BASELINE_NAMES = {
    "B1": "Random",
    "B2": "Uncertainty-Only",
    "B3": "CAD-Only",
    "B4": "Impact-Only",
    "B5": "Uncertainty + CAD",
    "B6": "Full PCVC"
}

mrr_sensitivity_results = {b: [] for b in BASELINE_NAMES}
tie_robust_metrics = {b: [] for b in BASELINE_NAMES}

# We run ONE pass over the 10 seeds
for seed in SEEDS:
    set_seed(seed)
    random.seed(seed)
    sampled_idx = random.sample(range(len(eligible_pool)), 40)
    sampled_edges = [eligible_pool[idx] for idx in sampled_idx]
    
    # 1. Pre-evaluate oracle true impact
    oracle_items = []
    for u, v, k, _ in sampled_edges:
        eid = get_edge_id(u, v, k)
        imp = evaluate_counterfactual_impact(G, u, v, k, "wheelchair", bridge_cache=bc_wc)
        oracle_items.append({"edge_id": eid, "impact": imp.delta_arl, "cad": imp.cad})
    
    crit_set = set(item["edge_id"] for item in oracle_items if item["impact"] == 1.0)
    zero_set = set(item["edge_id"] for item in oracle_items if item["impact"] == 0.0)
    crit_size = len(crit_set)
    zero_size = len(zero_set)
    
    # 2. Masked graph
    G_masked = safe_copy_graph(G)
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
    
    # Critical set (edges with max impact = 1.0)
    max_impact = max(item["impact"] for item in oracle_items)
    tied_top_edges = [item["edge_id"] for item in oracle_items if item["impact"] == max_impact]
    
    for b_code, b_name in BASELINE_NAMES.items():
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

            scored.append({"edge_id": c["edge_id"], "score": score, "true_impact": c["true_impact"]})
            
        pred_sorted = sorted(scored, key=lambda x: x["score"], reverse=True)
        pred_ranks = {item["edge_id"]: r for r, item in enumerate(pred_sorted, start=1)}
        
        # 100 random tie breaks per seed * 10 seeds = 1000 total iterations
        mrrs_for_seed = []
        for _ in range(100):
            chosen_top1 = random.choice(tied_top_edges)
            rank_pos = pred_ranks.get(chosen_top1, 40)
            mrrs_for_seed.append(1.0 / rank_pos)
        mrr_sensitivity_results[b_code].extend(mrrs_for_seed)
        
        # Binary relevance & robust metrics
        pred_top1 = [x["edge_id"] for x in pred_sorted[:1]]
        pred_top5 = [x["edge_id"] for x in pred_sorted[:5]]
        pred_top10 = [x["edge_id"] for x in pred_sorted[:10]]
        
        p_at_1 = len(set(pred_top1) & crit_set) / 1.0
        p_at_5 = len(set(pred_top5) & crit_set) / 5.0
        p_at_10 = len(set(pred_top10) & crit_set) / 10.0
        
        r_at_10 = len(set(pred_top10) & crit_set) / float(crit_size) if crit_size > 0 else 0.0
        f1_at_10 = (2 * p_at_10 * r_at_10) / (p_at_10 + r_at_10) if (p_at_10 + r_at_10) > 0 else 0.0
        
        precisions = []
        hits = 0
        for i, item in enumerate(pred_sorted, start=1):
            if item["edge_id"] in crit_set:
                hits += 1
                precisions.append(hits / i)
        ap = float(np.mean(precisions)) if precisions else 0.0
        
        crit_ranks = [r for r, item in enumerate(pred_sorted, start=1) if item["edge_id"] in crit_set]
        mean_rank_crit = float(np.mean(crit_ranks)) if crit_ranks else 40.0
        median_rank_crit = float(np.median(crit_ranks)) if crit_ranks else 40.0
        
        s_rho, _ = spearmanr([c["score"] for c in scored], [c["true_impact"] for c in scored])
        k_tau, _ = kendalltau([c["score"] for c in scored], [c["true_impact"] for c in scored])

        tie_robust_metrics[b_code].append({
            "seed": seed,
            "crit_size": crit_size,
            "zero_size": zero_size,
            "p_at_1": p_at_1,
            "p_at_5": p_at_5,
            "p_at_10": p_at_10,
            "r_at_10": r_at_10,
            "f1_at_10": f1_at_10,
            "ap": ap,
            "mean_rank_crit": mean_rank_crit,
            "median_rank_crit": median_rank_crit,
            "spearman_rho": s_rho if not np.isnan(s_rho) else 0.0,
            "kendall_tau": k_tau if not np.isnan(k_tau) else 0.0
        })
    print(f"Completed Seed {seed} (Crit size: {crit_size}, Zero size: {zero_size})", flush=True)

# ----------------------------------------------------------------------------
# SUMMARIZE PART 1: MRR TIE SENSITIVITY
# ----------------------------------------------------------------------------
print("\n" + "=" * 80, flush=True)
print("PART 1: MRR TIE SENSITIVITY TEST RESULTS (1,000 RANDOM TIE BREAKS)", flush=True)
print("=" * 80, flush=True)
mrr_summary_table = []
for b_code, b_name in BASELINE_NAMES.items():
    mrrs = np.array(mrr_sensitivity_results[b_code])
    rec = {
        "baseline_code": b_code,
        "baseline_name": b_name,
        "mean_mrr": round(float(np.mean(mrrs)), 4),
        "median_mrr": round(float(np.median(mrrs)), 4),
        "std_mrr": round(float(np.std(mrrs)), 4),
        "min_mrr": round(float(np.min(mrrs)), 4),
        "max_mrr": round(float(np.max(mrrs)), 4)
    }
    mrr_summary_table.append(rec)
    print(f"{b_code:2s} ({b_name:18s}): Mean={rec['mean_mrr']:.4f} | Median={rec['median_mrr']:.4f} | Std={rec['std_mrr']:.4f} | Min={rec['min_mrr']:.4f} | Max={rec['max_mrr']:.4f}", flush=True)

# ----------------------------------------------------------------------------
# SUMMARIZE PART 2, 3, 4: TIE-ROBUST METRICS
# ----------------------------------------------------------------------------
print("\n" + "=" * 80, flush=True)
print("PART 2, 3, 4: TIE-ROBUST BINARY RELEVANCE METRICS (10-SEED MEAN)", flush=True)
print("=" * 80, flush=True)
robust_summary = []
for b_code, b_name in BASELINE_NAMES.items():
    records = tie_robust_metrics[b_code]
    res = {
        "baseline_code": b_code,
        "baseline_name": b_name,
        "p_at_1": round(float(np.mean([r["p_at_1"] for r in records])), 4),
        "p_at_5": round(float(np.mean([r["p_at_5"] for r in records])), 4),
        "p_at_10": round(float(np.mean([r["p_at_10"] for r in records])), 4),
        "r_at_10": round(float(np.mean([r["r_at_10"] for r in records])), 4),
        "f1_at_10": round(float(np.mean([r["f1_at_10"] for r in records])), 4),
        "ap": round(float(np.mean([r["ap"] for r in records])), 4),
        "mean_rank_crit": round(float(np.mean([r["mean_rank_crit"] for r in records])), 2),
        "median_rank_crit": round(float(np.mean([r["median_rank_crit"] for r in records])), 2),
        "spearman_rho": round(float(np.mean([r["spearman_rho"] for r in records])), 4),
        "kendall_tau": round(float(np.mean([r["kendall_tau"] for r in records])), 4)
    }
    robust_summary.append(res)
    print(f"{b_code:2s} ({b_name:18s}): P@10={res['p_at_10']:.4f} | R@10={res['r_at_10']:.4f} | F1@10={res['f1_at_10']:.4f} | AP={res['ap']:.4f} | MeanRank={res['mean_rank_crit']:.2f} | Rho={res['spearman_rho']:.4f}", flush=True)

# ----------------------------------------------------------------------------
# PART 6 & 7: ALTERNATIVE ORACLE INVESTIGATION
# ----------------------------------------------------------------------------
print("\n" + "=" * 80, flush=True)
print("PART 6 & 7: ALTERNATIVE ORACLE IMPACT INVESTIGATION ON 50 EDGES", flush=True)
print("=" * 80, flush=True)

test_edges = eligible_pool[:50]
alt_records = []

for u, v, k, d in test_edges:
    eid = get_edge_id(u, v, k)
    imp_a = evaluate_counterfactual_impact(G, u, v, k, "wheelchair", bridge_cache=bc_wc)
    
    # In counterfactual graph
    G_cf = G_sub_wc.copy()
    if G_cf.has_edge(u, v, key=k):
        G_cf.remove_edge(u, v, key=k)
    elif G_cf.has_edge(u, v):
        G_cf.remove_edge(u, v)
        
    # Case B: ARL with candidate_paths (3 shortest simple paths via islice)
    try:
        paths_uv_base = list(itertools.islice(nx.shortest_simple_paths(G_sub_wc, u, v, weight="length_m"), 3))
    except Exception:
        paths_uv_base = []
        
    try:
        paths_uv_cf = list(itertools.islice(nx.shortest_simple_paths(G_cf, u, v, weight="length_m"), 3))
    except Exception:
        paths_uv_cf = []
        
    arl_base = resilience_engine.calculate_arl(G_sub_wc, u, v, candidate_paths=paths_uv_base)
    arl_cf = resilience_engine.calculate_arl(G_cf, u, v, candidate_paths=paths_uv_cf)
    delta_arl_case_b = max(0.0, round(arl_base - arl_cf, 3))
    
    # Alternative A: Shortest Path Detour Delta (m)
    len_direct = d.get("length_m", 1.0)
    try:
        alt_dist = nx.shortest_path_length(G_cf, u, v, weight="length_m")
        delta_detour = round(alt_dist - len_direct, 2)
    except nx.NetworkXNoPath:
        delta_detour = 999.0
    except Exception:
        delta_detour = 0.0
        
    # Alternative B: Component size reduction (nodes)
    orig_comp = len(nx.node_connected_component(G_sub_wc, u)) if G_sub_wc.has_node(u) else 0
    if G_cf.has_node(u) and G_cf.has_node(v):
        if nx.has_path(G_cf, u, v):
            delta_comp = 0
        else:
            comp_u = len(nx.node_connected_component(G_cf, u))
            comp_v = len(nx.node_connected_component(G_cf, v))
            delta_comp = orig_comp - max(comp_u, comp_v)
    else:
        delta_comp = 0
        
    alt_records.append({
        "edge_id": eid,
        "delta_arl_case_a": imp_a.delta_arl,
        "cad": imp_a.cad,
        "is_bridge": imp_a.is_cut_edge,
        "delta_arl_case_b": delta_arl_case_b,
        "delta_detour_m": delta_detour,
        "delta_comp_nodes": delta_comp
    })

df_alt = pd.DataFrame(alt_records)
print(f"Case A (Current Delta ARL): Unique={df_alt['delta_arl_case_a'].nunique()} | Values={dict(Counter(df_alt['delta_arl_case_a']))}", flush=True)
print(f"Case B (ARL with Paths):    Unique={df_alt['delta_arl_case_b'].nunique()} | Values={dict(Counter(df_alt['delta_arl_case_b']))}", flush=True)
print(f"Alternative A (Detour m):   Unique={df_alt['delta_detour_m'].nunique()} | Min={df_alt['delta_detour_m'].min():.1f} | Max={df_alt['delta_detour_m'].max():.1f} | Mean={df_alt['delta_detour_m'].mean():.1f} | Non-999 Mean={df_alt[df_alt['delta_detour_m'] < 900]['delta_detour_m'].mean():.1f}", flush=True)
print(f"Alternative B (Comp Size):  Unique={df_alt['delta_comp_nodes'].nunique()} | Values={dict(Counter(df_alt['delta_comp_nodes']))}", flush=True)

# Save JSON
out_payload = {
    "mrr_tie_sensitivity": mrr_summary_table,
    "robust_metrics_summary": robust_summary,
    "alternative_oracles_summary": {
        "case_a_unique": int(df_alt["delta_arl_case_a"].nunique()),
        "case_a_counts": {str(k): int(v) for k, v in Counter(df_alt["delta_arl_case_a"]).items()},
        "case_b_unique": int(df_alt["delta_arl_case_b"].nunique()),
        "case_b_counts": {str(k): int(v) for k, v in Counter(df_alt["delta_arl_case_b"]).items()},
        "detour_unique": int(df_alt["delta_detour_m"].nunique()),
        "detour_min": float(df_alt["delta_detour_m"].min()),
        "detour_max": float(df_alt["delta_detour_m"].max()),
        "detour_mean": float(df_alt["delta_detour_m"].mean()),
        "comp_size_unique": int(df_alt["delta_comp_nodes"].nunique()),
        "comp_size_counts": {str(k): int(v) for k, v in Counter(df_alt["delta_comp_nodes"]).items()}
    }
}

with open(PROJECT_ROOT / "scratch/test_final_metric_validation.json", "w") as f:
    json.dump(out_payload, f, indent=2)

print("\nAudit payload written to scratch/test_final_metric_validation.json.", flush=True)
