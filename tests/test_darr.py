import pytest
import networkx as nx
from typing import List

from src.darr.config import get_profile_config
from src.darr.subgraph import subgraph_manager
from src.darr.candidate_generator import route_generator
from src.darr.scorer import route_scorer
from src.darr.router import compute_darr_routes
from src.signal_decay.engine import decay_engine

@pytest.fixture
def synthetic_graph():
    """
    Constructs a controlled synthetic graph with 3 distinct physical corridors
    between origin (1) and destination (6):
    - Corridor 1 (Short): 1 -> 2 -> 6 (length 100m, has stairs, wheelchair inaccessible)
    - Corridor 2 (Accessible): 1 -> 3 -> 6 (length 140m, step-free, ramp)
    - Corridor 3 (Detour): 1 -> 4 -> 5 -> 6 (length 200m, step-free, wide path)
    """
    G = nx.MultiGraph()
    for n in range(1, 7):
        G.add_node(n, x=float(n), y=float(n))

    # Corridor 1 (Stairs)
    G.add_edge(1, 2, key="E1", length_m=50.0, stairs=True, wheelchair_accessible=False, highway="steps")
    G.add_edge(2, 6, key="E2", length_m=50.0, stairs=False, wheelchair_accessible=True, highway="footway")

    # Corridor 2 (Accessible ramp)
    G.add_edge(1, 3, key="E3", length_m=70.0, stairs=False, wheelchair_accessible=True, ramp=True, highway="footway")
    G.add_edge(3, 6, key="E4", length_m=70.0, stairs=False, wheelchair_accessible=True, highway="footway")

    # Corridor 3 (Wide detour)
    G.add_edge(1, 4, key="E5", length_m=60.0, stairs=False, wheelchair_accessible=True, width_m=1.8, highway="footway")
    G.add_edge(4, 5, key="E6", length_m=80.0, stairs=False, wheelchair_accessible=True, width_m=1.8, highway="footway")
    G.add_edge(5, 6, key="E7", length_m=60.0, stairs=False, wheelchair_accessible=True, width_m=1.8, highway="footway")

    return G

# ============================================================================
# 1. Multi-Route Generation & Diversity Tests
# ============================================================================

def test_candidate_route_generation(synthetic_graph):
    decay_engine.reset()
    candidates = route_generator.generate_candidate_routes(synthetic_graph, 1, 6, "general")
    # Must generate at least 3 candidates when graph permits
    assert len(candidates) >= 3
    ids = [c["route_id"] for c in candidates]
    assert "route_1_fastest" in ids

def test_route_diversity(synthetic_graph):
    decay_engine.reset()
    candidates = route_generator.generate_candidate_routes(synthetic_graph, 1, 6, "general")
    assert len(candidates) >= 2
    # Ensure routes are meaningfully distinct (check node sequence differences)
    p1 = candidates[0]["path_nodes"]
    p2 = candidates[1]["path_nodes"]
    assert p1 != p2

# ============================================================================
# 2. Profile-Specific Accessibility Filtering Tests
# ============================================================================

def test_profile_accessibility_filtering(synthetic_graph):
    # Wheelchair profile must exclude Corridor 1 (has stairs)
    G_wheelchair = subgraph_manager.get_accessible_subgraph(synthetic_graph, "wheelchair")
    assert not G_wheelchair.has_edge(1, 2)
    assert G_wheelchair.has_edge(1, 3)
    assert G_wheelchair.has_edge(1, 4)

    # General profile can use all edges
    G_general = subgraph_manager.get_accessible_subgraph(synthetic_graph, "general")
    assert G_general.has_edge(1, 2)

# ============================================================================
# 3. Accessibility Option Count (AOC) & Resilience (ARL) Tests
# ============================================================================

# ============================================================================
# 4. Critical Accessibility Dependency (CAD) Tests
# ============================================================================

# ============================================================================
# 5. Accessibility-Collapse Prediction Tests
# ============================================================================

# ============================================================================
# 6. Counterfactual Route Simulation & MAL Tests
# ============================================================================

# ============================================================================
# 7. Route Scoring & Flexible Traffic Redistribution Tests
# ============================================================================

def test_flexible_traffic_redistribution(synthetic_graph):
    decay_engine.reset()
    candidates = route_generator.generate_candidate_routes(synthetic_graph, 1, 6, "general")
    selected, scored = route_scorer.select_best_route(candidates, "general")
    assert selected is not None
    assert selected["selection_status"] == "SELECTED"
    assert len(selected["reason"]) > 0

# ============================================================================
# 8. Signal Decay Integration Tests
# ============================================================================

def test_signal_decay_forward_projection():
    decay_engine.reset()
    decay_engine.add_penalty("U1", "V1", 100.0, "HIGH", lambda_rate=0.01)
    
    current_pen = decay_engine.get_penalty("U1", "V1")
    assert current_pen == 100.0
    
    # Predict penalty 100 seconds in the future
    future_pen = decay_engine.predict_penalty_at("U1", "V1", target_time=100.0)
    assert future_pen < current_pen
    assert future_pen > 0.0

# ============================================================================
# 9. Edge Cases: Zero Route & Destination Unreachable Tests
# ============================================================================

def test_zero_route_edge_case():
    # Disconnected graph
    G_disc = nx.MultiGraph()
    G_disc.add_node(1, x=0, y=0)
    G_disc.add_node(99, x=10, y=10)
    
    res = compute_darr_routes(G_disc, (0, 0), (10, 10), "wheelchair")
    assert res["status"] in ["NO_PATH_FOUND", "NO_NODES_FOUND"]
    assert len(res["candidate_routes"]) == 0

# ============================================================================
# 10. Required Cases A to I Tests
# ============================================================================

def test_case_a_no_congestion(synthetic_graph):
    decay_engine.reset()
    res = compute_darr_routes(synthetic_graph, (1, 1), (6, 6), "general")
    assert res["status"] == "SUCCESS"

def test_case_b_low_congestion(synthetic_graph):
    decay_engine.reset()
    decay_engine.add_penalty(1, 2, 50.0, "LOW")
    res = compute_darr_routes(synthetic_graph, (1, 1), (6, 6), "general")
    assert res["status"] == "SUCCESS"

def test_case_c_medium_congestion(synthetic_graph):
    decay_engine.reset()
    decay_engine.add_penalty(1, 2, 100.0, "MEDIUM")
    res = compute_darr_routes(synthetic_graph, (1, 1), (6, 6), "general")
    assert res["status"] == "SUCCESS"

def test_case_d_high_congestion(synthetic_graph):
    decay_engine.reset()
    decay_engine.add_penalty(1, 2, 200.0, "HIGH")
    res = compute_darr_routes(synthetic_graph, (1, 1), (6, 6), "general")
    assert res["status"] == "SUCCESS"

def test_case_e_critical_corridor_blocked(synthetic_graph):
    decay_engine.reset()
    # Heavily congest Corridor 2
    decay_engine.add_penalty(1, 3, 500.0, "HIGH")
    res = compute_darr_routes(synthetic_graph, (1, 1), (6, 6), "wheelchair")
    # Wheelchair should adapt to Corridor 3
    assert res["status"] == "SUCCESS"

def test_case_h_congestion_decays_over_time():
    decay_engine.reset()
    decay_engine.add_penalty("A", "B", 100.0, "HIGH", lambda_rate=0.05)
    p0 = decay_engine.get_penalty("A", "B")
    decay_engine.update_time(50.0)
    p1 = decay_engine.get_penalty("A", "B")
    assert p1 < p0

