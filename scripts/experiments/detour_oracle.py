"""
PCVC Physical Detour Impact Oracle Module
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Implements the continuous Physical Detour Impact oracle:
    Δd(u, v) = shortest_path_length(G - e, u, v, weight='length_m') - length_m(e)

Quantifies the additional walking distance imposed on mobility-impaired users
when edge e=(u, v, key) is unavailable.
"""

from typing import Dict, Any, Tuple, Optional, List
import networkx as nx
import numpy as np
from scipy.stats import spearmanr, kendalltau


PENALTY_CAP_DISCONNECTED = 2000.0  # Meters (strictly > max finite campus detour 1,652m)


def compute_physical_detour_impact(
    G_accessible: nx.Graph,
    u: Any,
    v: Any,
    key: Any = None,
    weight_attr: str = "length_m",
    penalty_cap: float = PENALTY_CAP_DISCONNECTED
) -> Dict[str, Any]:
    """
    Computes the exact physical detour distance required to bypass edge e=(u, v, key)
    on the profile-accessible subgraph G_accessible.

    Returns:
        Dict with:
            - orig_length_m: original direct edge length
            - bypass_length_m: length of shortest alternate route (or inf)
            - delta_d: additional meters (bypass - orig) or inf if disconnected
            - effective_detour: delta_d capped at penalty_cap for finite ranking/metrics
            - is_disconnected: boolean, True if removal disconnects u and v
    """
    # 1. Direct edge length
    orig_length = 1.0
    if G_accessible.is_multigraph():
        if G_accessible.has_edge(u, v, key=key):
            orig_length = G_accessible[u][v][key].get(weight_attr, G_accessible[u][v][key].get("length", 1.0))
        elif G_accessible.has_edge(u, v):
            k0 = next(iter(G_accessible[u][v]))
            orig_length = G_accessible[u][v][k0].get(weight_attr, G_accessible[u][v][k0].get("length", 1.0))
    else:
        if G_accessible.has_edge(u, v):
            orig_length = G_accessible[u][v].get(weight_attr, G_accessible[u][v].get("length", 1.0))

    # 2. Copy accessible graph and remove target edge
    G_cf = G_accessible.copy()
    if G_cf.is_multigraph():
        if G_cf.has_edge(u, v, key=key):
            G_cf.remove_edge(u, v, key=key)
        elif G_cf.has_edge(u, v):
            k0 = next(iter(G_cf[u][v]))
            G_cf.remove_edge(u, v, key=k0)
    else:
        if G_cf.has_edge(u, v):
            G_cf.remove_edge(u, v)

    # 3. Evaluate connectivity and shortest path bypass
    if G_cf.has_node(u) and G_cf.has_node(v) and nx.has_path(G_cf, u, v):
        bypass_length = float(nx.shortest_path_length(G_cf, u, v, weight=weight_attr))
        delta_d = max(0.0, round(bypass_length - orig_length, 2))
        is_disconnected = False
        effective_detour = delta_d
    else:
        bypass_length = float("inf")
        delta_d = float("inf")
        is_disconnected = True
        effective_detour = penalty_cap

    return {
        "orig_length_m": round(orig_length, 2),
        "bypass_length_m": bypass_length,
        "delta_d": delta_d,
        "effective_detour": effective_detour,
        "is_disconnected": is_disconnected
    }


def evaluate_continuous_ranking_metrics(
    scored_candidates: List[Dict[str, Any]],
    oracle_candidates: List[Dict[str, Any]],
    k_list: List[int] = [5, 10],
    penalty_cap: float = PENALTY_CAP_DISCONNECTED
) -> Dict[str, Any]:
    """
    Computes rigorous continuous evaluation metrics comparing predicted score ranking
    against true continuous Physical Detour Impact Δd.

    Args:
        scored_candidates: List of dicts with 'edge_id', 'score'
        oracle_candidates: List of dicts with 'edge_id', 'delta_d', 'effective_detour', 'is_disconnected'
    """
    N = len(scored_candidates)
    oracle_map = {item["edge_id"]: item for item in oracle_candidates}

    # Sort predicted (descending score, tie breaker deterministic)
    pred_sorted = sorted(scored_candidates, key=lambda x: x["score"], reverse=True)
    # Sort oracle (descending effective detour: inf/disconnected first, then highest detour)
    oracle_sorted = sorted(
        oracle_candidates,
        key=lambda x: (x["effective_detour"], x.get("cad", 0.0)),
        reverse=True
    )

    pred_ranks = {item["edge_id"]: r for r, item in enumerate(pred_sorted, start=1)}
    oracle_ranks = {item["edge_id"]: r for r, item in enumerate(oracle_sorted, start=1)}

    # 1. Rank correlation (Spearman rho and Kendall tau)
    scores = [item["score"] for item in scored_candidates]
    true_detours = [oracle_map[item["edge_id"]]["effective_detour"] for item in scored_candidates]

    s_rho, _ = spearmanr(scores, true_detours)
    k_tau, _ = kendalltau(scores, true_detours)
    s_rho = float(s_rho) if not np.isnan(s_rho) else 0.0
    k_tau = float(k_tau) if not np.isnan(k_tau) else 0.0

    # 2. Mean Absolute Rank Error (MARE)
    rank_errors = [abs(pred_ranks[eid] - oracle_ranks[eid]) for eid in pred_ranks]
    mean_abs_rank_error = float(np.mean(rank_errors))

    # 3. Maximum-detour edge rank
    max_detour_val = oracle_sorted[0]["effective_detour"]
    max_detour_edges = [item["edge_id"] for item in oracle_sorted if item["effective_detour"] == max_detour_val]
    max_edge_ranks = [pred_ranks[eid] for eid in max_detour_edges]
    min_rank_max_edge = int(np.min(max_edge_ranks))
    mean_rank_max_edge = float(np.mean(max_edge_ranks))

    results = {
        "spearman_rho": round(s_rho, 4),
        "kendall_tau": round(k_tau, 4),
        "mean_abs_rank_error": round(mean_abs_rank_error, 2),
        "min_rank_max_detour_edge": min_rank_max_edge,
        "mean_rank_max_detour_edge": round(mean_rank_max_edge, 2),
        "max_detour_ties_count": len(max_detour_edges),
    }

    # 4. Top-K metrics (TIC@K, NDCG@K, Mean Detour Captured@K)
    for k in k_list:
        if k > N:
            continue
        pred_top_k = pred_sorted[:k]
        oracle_top_k = oracle_sorted[:k]

        pred_k_detours = [oracle_map[item["edge_id"]]["effective_detour"] for item in pred_top_k]
        oracle_k_detours = [item["effective_detour"] for item in oracle_top_k]

        pred_sum = sum(pred_k_detours)
        oracle_sum = sum(oracle_k_detours)

        # TIC@K: ratio of total detour captured
        tic_k = pred_sum / oracle_sum if oracle_sum > 0 else 1.0

        # NDCG@K: continuous discounted cumulative gain
        dcg = sum((2 ** (d / penalty_cap) - 1) / np.log2(i + 2) for i, d in enumerate(pred_k_detours))
        idcg = sum((2 ** (d / penalty_cap) - 1) / np.log2(j + 2) for j, d in enumerate(oracle_k_detours))
        ndcg_k = dcg / idcg if idcg > 0 else 1.0

        # Mean True Detour Captured
        mean_detour_k = float(np.mean(pred_k_detours))
        oracle_mean_detour_k = float(np.mean(oracle_k_detours))

        results[f"tic_at_{k}"] = round(float(tic_k), 4)
        results[f"ndcg_at_{k}"] = round(float(ndcg_k), 4)
        results[f"mean_detour_captured_at_{k}"] = round(mean_detour_k, 2)
        results[f"oracle_mean_detour_at_{k}"] = round(oracle_mean_detour_k, 2)

    return results
