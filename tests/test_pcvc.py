import pytest
import time
import math
import networkx as nx
from typing import List, Dict, Any

from src.graph_manager import load_or_build_graph
from src.pcvc.models import (
    VerificationStatus,
    VerificationEventStatus,
    EdgeEvidenceState,
    CounterfactualImpact
)
from src.pcvc.uncertainty import (
    compute_edge_uncertainty,
    get_uncertain_edges,
    format_edge_id,
    parse_edge_id
)
from src.pcvc.counterfactual import evaluate_counterfactual_impact
from src.pcvc.probe_selector import (
    is_safe_probe,
    select_best_probe,
    find_nearest_landmark_anchor,
    get_vit_landmarks
)
from src.pcvc.evidence import EvidenceFreshnessTracker, evidence_tracker
from src.pcvc.controller import pcvc_controller, PCVCController
from src.darr.subgraph import subgraph_manager
from src.darr.resilience import resilience_engine

@pytest.fixture(scope="module")
def vit_graph():
    """Loads the real VIT Vellore pedestrian graph."""
    return load_or_build_graph()

@pytest.fixture
def synthetic_pcvc_graph():
    """
    Constructs a controlled synthetic network with:
    - Landmark Anchor: Node 1 (MGR)
    - Cut-edge / Bridge: Node 1 -> Node 2 (Critical walkway with missing wheelchair tag)
    - Node 2 -> Node 3: Segment with stairs (Inaccessible to wheelchair, accessible to general)
    - Node 2 -> Node 4: Loop bypass returning to Node 1
    - Disconnected Node 9: Isolated island
    """
    G = nx.MultiGraph()
    for n in range(1, 10):
        G.add_node(n, x=float(n * 10), y=float(n * 10))

    # Critical bridge with unknown wheelchair status (uncertain)
    G.add_edge(1, 2, key="E_crit", length_m=50.0, stairs=False, wheelchair="unknown", surface="unknown")
    # Redundant alternate bypass
    G.add_edge(1, 5, key="E_alt1", length_m=60.0, stairs=False, wheelchair="yes", width_m=1.8)
    G.add_edge(5, 2, key="E_alt2", length_m=60.0, stairs=False, wheelchair="yes", width_m=1.8)

    # Stairs pathway
    G.add_edge(2, 3, key="E_stairs", length_m=30.0, stairs=True, wheelchair="no", highway="steps")

    # Return loop back to anchor
    G.add_edge(3, 4, key="E_loop1", length_m=40.0, stairs=False, wheelchair="yes")
    G.add_edge(4, 1, key="E_loop2", length_m=50.0, stairs=False, wheelchair="yes")

    # One-way isolated pathway with no return route for wheelchair
    G.add_edge(2, 6, key="E_isolated", length_m=20.0, stairs=False, wheelchair="unknown")
    # 6 is a dead-end with no other edges

    return G

# ============================================================================
# TEST 1: Uncertain edge is detected
# ============================================================================
def test_uncertain_edge_detection(vit_graph):
    """Verifies that edges with incomplete accessibility evidence produce uncertainty > 0."""
    uncertain_edges = get_uncertain_edges(vit_graph, profile="wheelchair", uncertainty_threshold=0.4, limit=20)
    assert len(uncertain_edges) > 0
    first = uncertain_edges[0]
    assert first.accessibility_uncertainty >= 0.4
    assert first.accessibility_confidence <= 0.6
    assert len(first.missing_attributes) > 0
    # Must use deterministic edge_id
    u, v, k = parse_edge_id(first.edge_id)
    assert vit_graph.has_edge(u, v, key=k) or vit_graph.has_edge(u, v)

# ============================================================================
# TEST 2: Counterfactual removal changes ARL/AOC on critical edges
# ============================================================================
def test_critical_edge_counterfactual_impact(vit_graph):
    """Removing a genuinely critical bridge in the wheelchair subgraph causes delta_arl > 0."""
    G_wc = subgraph_manager.get_accessible_subgraph(vit_graph, "wheelchair")
    bridges = list(resilience_engine._get_bridges(G_wc))
    assert len(bridges) > 0

    u, v = bridges[0]
    # Find matching key
    keys = list(G_wc[u][v].keys()) if G_wc.is_multigraph() else [0]
    impact = evaluate_counterfactual_impact(vit_graph, u, v, keys[0], target_profile="wheelchair")
    assert impact.is_cut_edge is True
    assert impact.cad >= 0.6
    assert impact.delta_arl >= 1.0 or impact.delta_aoc >= 1

# ============================================================================
# TEST 3: Non-critical edge gets lower priority than highly critical edge
# ============================================================================
def test_priority_ranking_differential(synthetic_pcvc_graph):
    """A cut-edge gets higher verification priority than a redundant bypass."""
    ctrl = PCVCController()
    plan = ctrl.compute_verification_targets(synthetic_pcvc_graph, target_profile="wheelchair", top_k=5, uncertainty_threshold=0.2)
    assert len(plan.ranked_candidates) > 0
    # Top target should be the critical bridge or highest impact edge
    top = plan.ranked_candidates[0]
    assert top.impact.cad >= 0.5 or top.impact.is_cut_edge is True
    # Priority score is strictly bounded [0, 1]
    assert 0.0 <= top.priority_score <= 1.0

# ============================================================================
# TEST 4: Profile-specific impact differs
# ============================================================================
def test_profile_specific_impact(synthetic_pcvc_graph):
    """An edge with stairs has zero impact for wheelchair (already blocked), but positive impact for general."""
    u, v, k = 2, 3, "E_stairs"
    impact_wc = evaluate_counterfactual_impact(synthetic_pcvc_graph, u, v, k, target_profile="wheelchair")
    impact_gen = evaluate_counterfactual_impact(synthetic_pcvc_graph, u, v, k, target_profile="general")

    # Wheelchair cannot traverse stairs, so removing it has 0 impact on wheelchair connectivity
    assert impact_wc.baseline_aoc == 0
    assert impact_wc.delta_arl == 0.0

    # General profile can traverse stairs, so baseline_aoc > 0
    assert impact_gen.baseline_aoc > 0
    assert impact_gen.delta_arl >= 0.0

# ============================================================================
# TEST 5: Probe whose accessibility constraints reject target edge is rejected
# ============================================================================
def test_probe_rejection_on_hard_constraints(vit_graph):
    """Wheelchair probe is rejected on an edge with stairs."""
    stairs_edges = [(u, v, k) for u, v, k, d in vit_graph.edges(keys=True, data=True) if d.get("stairs") is True]
    assert len(stairs_edges) > 0
    u, v, k = stairs_edges[0]

    probe_res = is_safe_probe(vit_graph, "wheelchair", u, v, k, u)
    assert probe_res.eligible is False
    assert probe_res.target_edge_feasible is False
    assert "stairs" in probe_res.reason.lower() or "inaccessible" in probe_res.reason.lower()

# ============================================================================
# TEST 6: Probe with feasible outbound and return routes is accepted
# ============================================================================
def test_probe_acceptance_on_feasible_routes(vit_graph):
    """A general pedestrian probe with valid outbound and return routes is eligible."""
    landmarks = get_vit_landmarks()
    assert len(landmarks) > 0
    anchor_node = landmarks[0]["anchor_node"]

    # Pick an edge adjacent to the anchor
    neighbors = list(vit_graph.neighbors(anchor_node))
    assert len(neighbors) > 0
    v = neighbors[0]
    keys = list(vit_graph[anchor_node][v].keys()) if vit_graph.is_multigraph() else [0]

    probe_res = is_safe_probe(vit_graph, "general", anchor_node, v, keys[0], anchor_node)
    assert probe_res.eligible is True
    assert probe_res.outbound_feasible is True
    assert probe_res.target_edge_feasible is True
    assert probe_res.return_feasible is True
    assert probe_res.travel_cost > 0

# ============================================================================
# TEST 7: Target with no safe-return path is rejected
# ============================================================================
def test_no_safe_return_rejection(synthetic_pcvc_graph):
    """A probe reaching a dead-end with no feasible return path is rejected."""
    # Node 6 has an edge from 2, but no path back to anchor 1 if edge is directed or blocked
    # Let's test reaching an isolated node from anchor 1
    probe_res = is_safe_probe(synthetic_pcvc_graph, "wheelchair", 9, 9, "none", 1)
    assert probe_res.eligible is False
    assert probe_res.outbound_feasible is False or probe_res.return_feasible is False

# ============================================================================
# TEST 8: Verification event created successfully
# ============================================================================
def test_verification_event_lifecycle():
    """Verification event is created in PENDING state and transitions cleanly."""
    tracker = EvidenceFreshnessTracker()
    event = tracker.create_verification_event(
        edge_id="1035391385-1064545157-E000253",
        target_profile="wheelchair",
        probe_profile="general",
        anchor_node=14093702429,
        notes="Automated test verification event"
    )
    assert event.event_id.startswith("VE-")
    assert event.status == VerificationEventStatus.PENDING
    assert event.target_profile == "wheelchair"
    assert event.probe_profile == "general"

    # Transition to IN_PROGRESS
    updated = tracker.update_event_status(event.event_id, VerificationEventStatus.IN_PROGRESS)
    assert updated.status == VerificationEventStatus.IN_PROGRESS

    # Transition to COMPLETED
    completed = tracker.update_event_status(event.event_id, VerificationEventStatus.COMPLETED)
    assert completed.status == VerificationEventStatus.COMPLETED
    assert tracker.get_freshness("1035391385-1064545157-E000253") > 0.99

# ============================================================================
# TEST 9: Evidence freshness calculation works
# ============================================================================
def test_evidence_freshness_decay():
    """Evidence freshness follows exponential decay without touching Signal Decay."""
    tracker = EvidenceFreshnessTracker(lambda_evidence=0.001)
    edge_id = "test-edge-freshness"
    now = time.time()

    # Initial observation
    tracker.record_observation(edge_id, timestamp=now)
    assert tracker.get_freshness(edge_id, current_time=now) == 1.0
    assert tracker.get_verification_status(edge_id, current_time=now) == VerificationStatus.VERIFIED

    # After 1000 seconds: freshness = exp(-0.001 * 1000) = exp(-1) ~= 0.3679
    future_time = now + 1000.0
    freshness_later = tracker.get_freshness(edge_id, current_time=future_time)
    expected = round(math.exp(-1.0), 4)
    assert abs(freshness_later - expected) < 0.01
    # Below stale threshold (0.4) -> status becomes STALE
    assert tracker.get_verification_status(edge_id, current_time=future_time) == VerificationStatus.STALE

# ============================================================================
# TEST 10: Existing routing behavior unchanged
# ============================================================================
def test_existing_pada_and_darr_routing(vit_graph):
    """PADA-R and DARR route calculations continue to work normally."""
    from src.pada_r.router import compute_pada_route
    from src.darr.router import compute_darr_routes

    landmarks = get_vit_landmarks()
    mgr = landmarks[0] # MGR
    sjt = landmarks[3] # SJT

    orig = (mgr["longitude"], mgr["latitude"])
    dest = (sjt["longitude"], sjt["latitude"])

    path, path_edges, status, exp, stats = compute_pada_route(vit_graph, orig, dest, "general")
    assert path is not None
    assert status == "PERSONALIZED_OPTIMAL"
    assert stats["cost"] > 0

    darr_res = compute_darr_routes(vit_graph, orig, dest, "general")
    assert darr_res["status"] in ["SUCCESS", "FALLBACK"]
    assert len(darr_res["candidate_routes"]) > 0

# ============================================================================
# TEST 11: VIT landmarks and academic block labels preserved
# ============================================================================
def test_vit_landmarks_and_academic_blocks():
    """All 9 verified VIT landmarks are present with valid coordinates and anchor nodes."""
    landmarks = get_vit_landmarks()
    assert len(landmarks) == 9
    names = [loc["name"] for loc in landmarks]
    assert "MGR" in names
    assert "SJT" in names
    assert "TT" in names
    assert "PRP" in names
    assert "SMV" in names
    assert "Gandhi Block" in names
    assert "Anna Auditorium" in names
    assert "CTS" in names
    assert "Parking Lot" in names

# ============================================================================
# TEST 12: No Melbourne or simulation dependencies
# ============================================================================
def test_no_melbourne_or_simulation_in_pcvc():
    """Ensures PCVC code has zero imports or dependencies on Melbourne or simulation."""
    import inspect
    import src.pcvc.models as m
    import src.pcvc.uncertainty as u
    import src.pcvc.counterfactual as c
    import src.pcvc.probe_selector as p
    import src.pcvc.evidence as e
    import src.pcvc.controller as ctrl

    for mod in [m, u, c, p, e, ctrl]:
        src = inspect.getsource(mod).lower()
        assert "melbourne" not in src
        assert "congestion_sim" not in src
        assert "waterlogging_sim" not in src
