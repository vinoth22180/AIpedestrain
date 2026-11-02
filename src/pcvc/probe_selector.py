import os
import json
import math
import networkx as nx
from typing import Dict, Any, List, Tuple, Optional
from src.pcvc.models import ProbeSafeReturnResult, ProbeSelectionResult
from src.darr.config import get_profile_config
from src.darr.subgraph import subgraph_manager
from src.pada_r.profiles import evaluate_feasibility

LANDMARKS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "vit_vellore", "processed", "vit_manual_locations.json"
)

_CACHED_LANDMARKS = None

def get_vit_landmarks() -> List[Dict[str, Any]]:
    """Loads and caches the 9 verified VIT landmarks with snapped anchor nodes."""
    global _CACHED_LANDMARKS
    if _CACHED_LANDMARKS is not None:
        return _CACHED_LANDMARKS
    if os.path.exists(LANDMARKS_PATH):
        try:
            with open(LANDMARKS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                _CACHED_LANDMARKS = data.get("locations", [])
                return _CACHED_LANDMARKS
        except Exception:
            pass
    return []

def find_nearest_landmark_anchor(G: nx.Graph, node: Any) -> Tuple[Optional[str], Optional[Any], Optional[List[float]]]:
    """
    Finds the nearest VIT landmark anchor node to the given graph node.
    Returns (landmark_name, anchor_node, [lon, lat]).
    """
    landmarks = get_vit_landmarks()
    if not landmarks or not G.has_node(node):
        return None, None, None

    node_data = G.nodes[node]
    node_x = node_data.get("x", 0.0)
    node_y = node_data.get("y", 0.0)

    best_landmark = None
    min_dist = float("inf")

    for loc in landmarks:
        anchor_node = loc.get("anchor_node")
        if anchor_node and G.has_node(anchor_node):
            lx = loc.get("longitude", 0.0)
            ly = loc.get("latitude", 0.0)
            dist = math.hypot(node_x - lx, node_y - ly)
            if dist < min_dist:
                min_dist = dist
                best_landmark = loc

    if best_landmark:
        return (
            best_landmark.get("name"),
            best_landmark.get("anchor_node"),
            [best_landmark.get("longitude"), best_landmark.get("latitude")]
        )
    return None, None, None

def _get_edge_length(edge_data: Dict[str, Any]) -> float:
    length = edge_data.get("length_m", edge_data.get("length", 10.0))
    if hasattr(length, "iloc"):
        length = length.iloc[0]
    return float(length) if length else 10.0

def is_safe_probe(
    G: nx.Graph,
    profile_name: str,
    u: Any,
    v: Any,
    key: Any,
    anchor_node: Any
) -> ProbeSafeReturnResult:
    """
    Validates the Closed-Loop Safe-Return Rule for a candidate probe profile:
    
    1. Target Edge Feasibility: Can the probe profile physically traverse (u, v)?
    2. Outbound Feasibility: Is there an accessible path from anchor_node to u?
    3. Safe Return Feasibility: Is there an accessible return path from v back to anchor_node?
    
    A probe is eligible ONLY if all three conditions are satisfied.
    """
    profile_cfg = get_profile_config(profile_name)

    # 1. Fetch edge data
    edge_data = {}
    if G.is_multigraph():
        if G.has_edge(u, v, key=key):
            edge_data = G.get_edge_data(u, v, key=key)
        elif G.has_edge(u, v):
            k_first = next(iter(G[u][v].keys()))
            edge_data = G.get_edge_data(u, v, key=k_first)
    else:
        if G.has_edge(u, v):
            edge_data = G.get_edge_data(u, v)

    edge_dist = _get_edge_length(edge_data)

    # 2. Check Target Edge Accessibility under profile's hard constraints
    is_accessible, fail_reason = subgraph_manager.is_edge_accessible(edge_data, profile_cfg, u, v)
    feas_status, _, feas_explanations = evaluate_feasibility(edge_data, profile_name)

    if not is_accessible or feas_status == "INACCESSIBLE":
        reason = fail_reason if not is_accessible else (feas_explanations[0] if feas_explanations else "Inaccessible")
        return ProbeSafeReturnResult(
            profile=profile_name,
            eligible=False,
            outbound_feasible=False,
            target_edge_feasible=False,
            return_feasible=False,
            reason=f"Target edge violates {profile_name} accessibility constraints: {reason}",
            outbound_distance_m=0.0,
            return_distance_m=0.0,
            travel_cost=float("inf")
        )

    # 3. Build profile-specific accessible subgraph for path checks
    G_sub = subgraph_manager.get_accessible_subgraph(G, profile_name)

    def weight_func(nu, nv, ndata):
        if isinstance(ndata, dict):
            # In simple graph or multigraph edge dict
            if any(isinstance(val, dict) for val in ndata.values()):
                # Multigraph inner dictionary
                return min(_get_edge_length(d) for d in ndata.values())
            return _get_edge_length(ndata)
        return 1.0

    # 4. Outbound Path Check: anchor -> u (or anchor -> v)
    outbound_feasible = False
    outbound_dist = 0.0

    if anchor_node == u:
        outbound_feasible = True
        outbound_dist = 0.0
    elif G_sub.has_node(anchor_node) and G_sub.has_node(u) and nx.has_path(G_sub, anchor_node, u):
        outbound_feasible = True
        try:
            outbound_dist = float(nx.shortest_path_length(G_sub, anchor_node, u, weight=weight_func))
        except Exception:
            outbound_dist = float(nx.shortest_path_length(G_sub, anchor_node, u))

    if not outbound_feasible:
        return ProbeSafeReturnResult(
            profile=profile_name,
            eligible=False,
            outbound_feasible=False,
            target_edge_feasible=True,
            return_feasible=False,
            reason=f"No accessible outbound path from anchor to target edge for {profile_name}",
            outbound_distance_m=0.0,
            return_distance_m=0.0,
            travel_cost=float("inf")
        )

    # 5. Return Path Check: v -> anchor
    return_feasible = False
    return_dist = 0.0

    if anchor_node == v:
        return_feasible = True
        return_dist = 0.0
    elif G_sub.has_node(v) and G_sub.has_node(anchor_node) and nx.has_path(G_sub, v, anchor_node):
        return_feasible = True
        try:
            return_dist = float(nx.shortest_path_length(G_sub, v, anchor_node, weight=weight_func))
        except Exception:
            return_dist = float(nx.shortest_path_length(G_sub, v, anchor_node))

    if not return_feasible:
        return ProbeSafeReturnResult(
            profile=profile_name,
            eligible=False,
            outbound_feasible=True,
            target_edge_feasible=True,
            return_feasible=False,
            reason=f"No accessible return path from target edge back to anchor for {profile_name}",
            outbound_distance_m=round(outbound_dist, 1),
            return_distance_m=0.0,
            travel_cost=float("inf")
        )

    # All three conditions passed
    total_travel_cost = round(outbound_dist + edge_dist + return_dist, 1)
    return ProbeSafeReturnResult(
        profile=profile_name,
        eligible=True,
        outbound_feasible=True,
        target_edge_feasible=True,
        return_feasible=True,
        reason=f"Feasible outbound ({outbound_dist:.0f}m), traversal ({edge_dist:.0f}m), and safe-return ({return_dist:.0f}m) confirmed.",
        outbound_distance_m=round(outbound_dist, 1),
        return_distance_m=round(return_dist, 1),
        travel_cost=total_travel_cost
    )

def select_best_probe(
    G: nx.Graph,
    u: Any,
    v: Any,
    key: Any,
    anchor_node: Optional[Any] = None,
    anchor_name: Optional[str] = None,
    candidate_profiles: Optional[List[str]] = None
) -> ProbeSelectionResult:
    """
    Evaluates all 4 probe profiles (general, elderly, pregnant, wheelchair)
    and selects the lowest-cost safe probe according to the closed-loop safe-return test.
    """
    if candidate_profiles is None:
        candidate_profiles = ["general", "elderly", "pregnant", "wheelchair"]

    anchor_coords = None
    if anchor_node is None or not G.has_node(anchor_node):
        anchor_name, anchor_node, anchor_coords = find_nearest_landmark_anchor(G, u)

    if anchor_node is None or not G.has_node(anchor_node):
        # Fallback to u as anchor if no landmark reachable
        anchor_node = u
        anchor_name = f"Node_{u}"

    eligible: List[ProbeSafeReturnResult] = []
    rejected: List[ProbeSafeReturnResult] = []

    for prof in candidate_profiles:
        res = is_safe_probe(G, prof, u, v, key, anchor_node)
        if res.eligible:
            eligible.append(res)
        else:
            rejected.append(res)

    if not eligible:
        return ProbeSelectionResult(
            selected_probe=None,
            selection_reason="No safe probe profile is currently available for this verification target.",
            anchor_name=anchor_name,
            anchor_node=anchor_node,
            anchor_coords=anchor_coords,
            eligible_probes=[],
            rejected_probes=rejected
        )

    # Deterministic selection rule: lowest safe verification travel cost
    eligible.sort(key=lambda x: x.travel_cost)
    best_probe = eligible[0]

    return ProbeSelectionResult(
        selected_probe=best_probe.profile,
        selection_reason=f"Lowest-cost eligible probe ({best_probe.travel_cost:.0f}m total) with feasible outbound and return paths.",
        anchor_name=anchor_name,
        anchor_node=anchor_node,
        anchor_coords=anchor_coords,
        eligible_probes=eligible,
        rejected_probes=rejected
    )
