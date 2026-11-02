import networkx as nx
from typing import Dict, Any, List, Tuple, Optional

from src.routing import get_nearest_node
from src.darr.candidate_generator import route_generator
from src.darr.scorer import route_scorer
from src.darr.subgraph import subgraph_manager

def compute_darr_routes(
    G_base: nx.Graph,
    origin_point: Tuple[float, float],
    destination_point: Tuple[float, float],
    profile_name: str = "general"
) -> Dict[str, Any]:
    """
    Primary DARR entry point:
    Generates multiple candidate routes, evaluates resilience metrics (AOC, ARL, CAD, MAL),
    predicts accessibility-collapse risks, and selects the optimal route.
    """
    orig_node = get_nearest_node(G_base, origin_point)
    dest_node = get_nearest_node(G_base, destination_point)

    if orig_node is None or dest_node is None:
        return {
            "status": "NO_NODES_FOUND",
            "message": "Origin or destination could not be snapped to the pedestrian graph.",
            "selected_route": None,
            "candidate_routes": [],
            "network_resilience": None,
            "collapse_risk": None
        }

    # 1. Generate candidate routes
    candidates = route_generator.generate_candidate_routes(
        G_base, orig_node, dest_node, profile_name
    )

    if not candidates:
        return {
            "status": "NO_PATH_FOUND",
            "message": f"No accessible path found between selected locations for the {profile_name} profile.",
            "selected_route": None,
            "candidate_routes": [],
            "network_resilience": {
                "aoc": 0,
                "arl": 0.0
            },
            "collapse_risk": {
                "collapse_risk": "CRITICAL",
                "risk_score": 1.0
            }
        }

    # 2. Score and select best route
    selected, scored_candidates = route_scorer.select_best_route(candidates, profile_name)

    # 3. Overall network resilience & collapse forecasting (Removed)

    decision_summary = selected["reason"] if selected else "No route selected"

    return {
        "status": "SUCCESS",
        "algorithm": "DARR (Dynamic Accessibility Resilience Routing)",
        "profile": profile_name,
        "selected_route": selected,
        "candidate_routes": scored_candidates,
        "network_resilience": None,
        "collapse_risk": None,
        "decision_summary": decision_summary
    }
