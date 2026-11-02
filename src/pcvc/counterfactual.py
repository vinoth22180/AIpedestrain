import networkx as nx
from typing import Dict, Any, Tuple, Optional, Set
from src.pcvc.models import CounterfactualImpact
from src.darr.subgraph import subgraph_manager
from src.darr.resilience import resilience_engine

def evaluate_counterfactual_impact(
    G_base: nx.Graph,
    u: Any,
    v: Any,
    key: Any,
    target_profile: str = "wheelchair",
    bridge_cache: Optional[Set[Tuple[Any, Any]]] = None
) -> CounterfactualImpact:
    """
    Evaluates the profile-specific accessibility impact if edge (u, v, key) were to fail.
    
    1. Extracts profile-accessible subgraph G_sub.
    2. Measures baseline AOC and ARL between u and v in G_sub.
    3. Evaluates Critical Accessibility Dependency (CAD).
    4. Creates a copy of G_sub, removes the edge, and re-evaluates AOC and ARL.
    5. Returns CounterfactualImpact with delta_aoc, delta_arl, mal_impact, and cad.
    """
    # 1. Build profile-specific accessible subgraph
    G_sub = subgraph_manager.get_accessible_subgraph(G_base, target_profile)

    # If edge is not even feasible for this profile, removing it has 0 impact on this profile
    has_edge = False
    if G_sub.is_multigraph():
        has_edge = G_sub.has_edge(u, v, key=key) or G_sub.has_edge(u, v)
    else:
        has_edge = G_sub.has_edge(u, v)

    if not has_edge or not G_sub.has_node(u) or not G_sub.has_node(v):
        return CounterfactualImpact(
            baseline_aoc=0,
            baseline_arl=0.0,
            counterfactual_aoc=0,
            counterfactual_arl=0.0,
            delta_aoc=0,
            delta_arl=0.0,
            mal_impact=0.0,
            cad=0.0,
            is_cut_edge=False
        )

    # 2. Baseline resilience metrics
    baseline_aoc = resilience_engine.calculate_aoc(G_sub, u, v)
    baseline_arl = resilience_engine.calculate_arl(G_sub, u, v)
    
    # Critical Accessibility Dependency (CAD)
    cad = resilience_engine.calculate_cad_for_edge(G_base, u, v, target_profile, bridge_cache=bridge_cache)
    
    # Check if it's a bridge/cut-edge
    bridges = bridge_cache if bridge_cache is not None else resilience_engine._get_bridges(G_sub)
    is_cut_edge = (u, v) in bridges or (v, u) in bridges

    # 3. Counterfactual Graph Copy and Edge Removal
    G_counterfactual = G_sub.copy()
    if G_counterfactual.is_multigraph():
        if G_counterfactual.has_edge(u, v, key=key):
            G_counterfactual.remove_edge(u, v, key=key)
        elif G_counterfactual.has_edge(u, v):
            # Fallback if key differs
            k_first = next(iter(G_counterfactual[u][v].keys()))
            G_counterfactual.remove_edge(u, v, key=k_first)
    else:
        if G_counterfactual.has_edge(u, v):
            G_counterfactual.remove_edge(u, v)

    # 4. Counterfactual resilience metrics
    if is_cut_edge:
        # Removal of a bridge by definition disconnects u and v in this component
        cf_aoc = 0
        cf_arl = 0.0
    else:
        cf_aoc = resilience_engine.calculate_aoc(G_counterfactual, u, v)
        cf_arl = resilience_engine.calculate_arl(G_counterfactual, u, v)

    delta_aoc = max(0, baseline_aoc - cf_aoc)
    delta_arl = max(0.0, round(baseline_arl - cf_arl, 2))
    
    # MAL (Marginal Accessibility Loss): degradation in continuous resilience level
    mal_impact = delta_arl

    return CounterfactualImpact(
        baseline_aoc=baseline_aoc,
        baseline_arl=baseline_arl,
        counterfactual_aoc=cf_aoc,
        counterfactual_arl=cf_arl,
        delta_aoc=delta_aoc,
        delta_arl=delta_arl,
        mal_impact=mal_impact,
        cad=round(cad, 3),
        is_cut_edge=is_cut_edge
    )
