import pytest
import networkx as nx
from src.pada_r.profiles import (
    PADA_PROFILES,
    PROFILE_CONGESTION_MULTIPLIERS,
    PREGNANT_MAX_SLOPE,
    WHEELCHAIR_MAX_SLOPE,
    ELDERLY_SLOPE_THRESHOLD,
    is_edge_allowed,
    evaluate_feasibility
)
from src.pada_r.cost_model import calculate_pada_cost
from src.pada_r.router import compute_pada_route
from src.congestion.manager import congestion_manager
from src.congestion.config import CongestionConfig

@pytest.fixture
def multi_profile_graph():
    """
    Creates a graph with 3 distinct paths from Node 1 to Node 4:
    - Path A (Stairs shortcut): 1 -> 2 -> 4 (Distance: 60m, contains stairs)
    - Path B (Steep slope shortcut): 1 -> 3 -> 4 (Distance: 65m, slope: 12.0%, no stairs)
    - Path C (Accessible gentle path): 1 -> 5 -> 4 (Distance: 80m, slope: 2.0%, no stairs, flat)
    """
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=0.0001, y=0.0001)
    G.add_node(3, x=0.0001, y=-0.0001)
    G.add_node(5, x=0.0002, y=0.0)
    G.add_node(4, x=0.0004, y=0.0)

    # Path A: 1 -> 2 -> 4 (Stairs)
    G.add_edge(1, 2, length_m=30, stairs=False, slope_percent=2.0, surface='asphalt', accessible=True, wheelchair='likely')
    G.add_edge(2, 4, length_m=30, stairs=True, slope_percent=2.0, surface='concrete', accessible=False, wheelchair='no')

    # Path B: 1 -> 3 -> 4 (Steep slope 12.0%)
    G.add_edge(1, 3, length_m=32, stairs=False, slope_percent=12.0, surface='asphalt', accessible=True, wheelchair='unknown')
    G.add_edge(3, 4, length_m=33, stairs=False, slope_percent=12.0, surface='asphalt', accessible=True, wheelchair='unknown')

    # Path C: 1 -> 5 -> 4 (Gentle, fully accessible, flat)
    G.add_edge(1, 5, length_m=40, stairs=False, slope_percent=0.0, surface='asphalt', accessible=True, wheelchair='likely')
    G.add_edge(5, 4, length_m=40, stairs=False, slope_percent=0.0, surface='asphalt', accessible=True, wheelchair='likely')

    return G

@pytest.fixture
def stairs_only_graph():
    """Graph where the ONLY path from 1 to 2 is stairs."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=0.0002, y=0.0002)
    G.add_edge(1, 2, length_m=20, stairs=True, accessible=False, wheelchair='no')
    return G

# TEST 1: General allows stairs
def test_01_general_allows_stairs():
    allowed, reason = is_edge_allowed({'stairs': True}, 'general')
    assert allowed is True
    assert reason is None
    status, _, _ = evaluate_feasibility({'stairs': True}, 'general')
    assert status == 'FEASIBLE'

# TEST 2: Wheelchair rejects stairs
def test_02_wheelchair_rejects_stairs():
    allowed, reason = is_edge_allowed({'stairs': True}, 'wheelchair')
    assert allowed is False
    assert "stairs" in reason.lower()
    status, _, explanation = evaluate_feasibility({'stairs': True}, 'wheelchair')
    assert status == 'INACCESSIBLE'
    assert any("stairs" in e.lower() for e in explanation)

# TEST 3: Elderly can use stairs but receives appropriate penalty
def test_03_elderly_allows_stairs_with_penalty():
    allowed, _ = is_edge_allowed({'stairs': True}, 'elderly')
    assert allowed is True
    
    # Calculate cost on flat edge vs stairs edge
    flat_edge = {'length_m': 50, 'stairs': False, 'slope_percent': 0.0}
    stairs_edge = {'length_m': 50, 'stairs': True, 'slope_percent': 0.0}
    
    _, cost_flat, _, _ = calculate_pada_cost(1, 2, flat_edge, 'elderly')
    _, cost_stairs, _, _ = calculate_pada_cost(1, 2, stairs_edge, 'elderly')
    
    assert cost_stairs > cost_flat * 2.0  # High effort and accessibility penalty

# TEST 4: Pregnant avoids slope above configured threshold
def test_04_pregnant_avoids_slope_above_threshold():
    steep_edge = {'slope_percent': 12.0}
    mild_edge = {'slope_percent': 3.0}
    
    allowed_steep, reason = is_edge_allowed(steep_edge, 'pregnant')
    assert allowed_steep is False
    assert "slope" in reason.lower()
    
    allowed_mild, _ = is_edge_allowed(mild_edge, 'pregnant')
    assert allowed_mild is True

# TEST 5: General allows slope
def test_05_general_allows_slope():
    steep_edge = {'slope_percent': 12.0}
    allowed, reason = is_edge_allowed(steep_edge, 'general')
    assert allowed is True
    assert reason is None

# TEST 6: Wheelchair route does not contain stairs
def test_06_wheelchair_route_does_not_contain_stairs(multi_profile_graph):
    congestion_manager.reset_congestion()
    path, edges, status, _, stats = compute_pada_route(multi_profile_graph, (0.0, 0.0), (0.0004, 0.0), 'wheelchair')
    
    assert path is not None
    assert status == "PERSONALIZED_OPTIMAL"
    # Must NOT have taken Path A (which goes through node 2 with stairs)
    assert 2 not in path
    for edge in edges:
        assert edge.get('stairs') is not True
    assert stats['accessibility']['stairs_avoided'] is True

# TEST 7: Pregnant route does not contain prohibited steep slopes
def test_07_pregnant_route_does_not_contain_prohibited_steep_slopes(multi_profile_graph):
    congestion_manager.reset_congestion()
    path, edges, status, _, stats = compute_pada_route(multi_profile_graph, (0.0, 0.0), (0.0004, 0.0), 'pregnant')
    
    assert path is not None
    # Must NOT have taken Path B (which goes through node 3 with 12% slope)
    assert 3 not in path
    for edge in edges:
        slope = edge.get('slope_percent')
        if slope is not None:
            assert slope <= PREGNANT_MAX_SLOPE
    assert stats['accessibility']['steep_slopes_avoided'] is True

# TEST 8: Different profiles can produce different routes when appropriate
def test_08_different_profiles_produce_different_routes(multi_profile_graph):
    congestion_manager.reset_congestion()
    # General should prefer Path A (1 -> 2 -> 4) because it's shortest (60m)
    path_gen, _, _, _, _ = compute_pada_route(multi_profile_graph, (0.0, 0.0), (0.0004, 0.0), 'general')
    assert path_gen == [1, 2, 4]
    
    # Wheelchair cannot use Path A (stairs) nor Path B (12% slope > 8%)
    # So Wheelchair must choose Path C (1 -> 5 -> 4)
    path_wc, _, _, _, _ = compute_pada_route(multi_profile_graph, (0.0, 0.0), (0.0004, 0.0), 'wheelchair')
    assert path_wc == [1, 5, 4]
    
    assert path_gen != path_wc

# TEST 9: Congestion affects each profile according to its multiplier
def test_09_congestion_affects_profiles_by_multiplier():
    edge_data = {'length_m': 100, 'stairs': False, 'slope_percent': 0.0, 'accessible': True}

    penalty = 0.5
    
    _, _, breakdown_gen, _ = calculate_pada_cost(1, 2, edge_data, 'general', dynamic_congestion_penalty=penalty)
    _, _, breakdown_eld, _ = calculate_pada_cost(1, 2, edge_data, 'elderly', dynamic_congestion_penalty=penalty)
    _, _, breakdown_preg, _ = calculate_pada_cost(1, 2, edge_data, 'pregnant', dynamic_congestion_penalty=penalty)
    _, _, breakdown_wc, _ = calculate_pada_cost(1, 2, edge_data, 'wheelchair', dynamic_congestion_penalty=penalty)
    
    c_gen = breakdown_gen['congestion']
    c_eld = breakdown_eld['congestion']
    c_preg = breakdown_preg['congestion']
    c_wc = breakdown_wc['congestion']
    
    # Verify strict multiplier ordering: Wheelchair (1.7) > Pregnant (1.6) > Elderly (1.5) > General (1.0)
    assert c_wc > c_preg > c_eld > c_gen
    assert pytest.approx(c_eld / c_gen, 0.01) == PROFILE_CONGESTION_MULTIPLIERS['elderly']
    assert pytest.approx(c_wc / c_gen, 0.01) == PROFILE_CONGESTION_MULTIPLIERS['wheelchair']

# TEST 10: No accessible wheelchair route returns a clear error
def test_10_no_accessible_wheelchair_route_returns_clear_error(stairs_only_graph):
    congestion_manager.reset_congestion()
    path, edges, status, explanation, stats = compute_pada_route(stairs_only_graph, (0.0, 0.0), (0.0002, 0.0002), 'wheelchair')
    
    assert path is None
    assert edges is None
    assert status == "NO_ACCESSIBLE_ROUTE_FOUND"
    assert "no wheelchair-accessible path" in explanation['reason'].lower()

# TEST 11: Route explanation matches profile
def test_11_route_explanation_matches_profile(multi_profile_graph):
    congestion_manager.reset_congestion()
    _, _, _, exp_wc, _ = compute_pada_route(multi_profile_graph, (0.0, 0.0), (0.0004, 0.0), 'wheelchair')
    _, _, _, exp_preg, _ = compute_pada_route(multi_profile_graph, (0.0, 0.0), (0.0004, 0.0), 'pregnant')
    _, _, _, exp_eld, _ = compute_pada_route(multi_profile_graph, (0.0, 0.0), (0.0004, 0.0), 'elderly')
    _, _, _, exp_gen, _ = compute_pada_route(multi_profile_graph, (0.0, 0.0), (0.0004, 0.0), 'general')
    
    assert "wheelchair" in exp_wc['reason'].lower()
    assert "stair" in exp_wc['reason'].lower()
    assert "slope" in exp_preg['reason'].lower()
    assert "gentle" in exp_eld['reason'].lower()
    assert "general" in exp_gen['reason'].lower()

# TEST 12: Alternative routes respect profile constraints
def test_12_alternative_routes_respect_profile_constraints(multi_profile_graph):
    congestion_manager.reset_congestion()
    res = compute_pada_route(multi_profile_graph, (0.0, 0.0), (0.0004, 0.0), 'wheelchair')
    candidates = res[5]
    
    assert len(candidates) > 0
    for cand in candidates:
        # No alternative candidate route for wheelchair should ever include stairs
        assert cand['accessibility']['stairs_count'] == 0
        assert cand['accessibility']['stairs_avoided'] is True

# TEST 13: Changing profile triggers new route calculation
def test_13_changing_profile_triggers_new_route_calculation(multi_profile_graph):
    congestion_manager.reset_congestion()
    res_gen = compute_pada_route(multi_profile_graph, (0.0, 0.0), (0.0004, 0.0), 'general')
    res_wc = compute_pada_route(multi_profile_graph, (0.0, 0.0), (0.0004, 0.0), 'wheelchair')
    
    # Path differs because of profile-specific constraints
    assert res_gen[0] != res_wc[0]
    assert res_gen[0] == [1, 2, 4]
    assert res_wc[0] == [1, 5, 4]

# TEST 14: A* heuristic remains unchanged and admissible
def test_14_astar_heuristic_admissible(multi_profile_graph):
    from src.pada_r.router import compute_pada_route
    # Verify routing with admissible heuristic terminates and finds optimal path
    path, _, status, _, stats = compute_pada_route(multi_profile_graph, (0.0, 0.0), (0.0004, 0.0), 'general')
    assert status == "PERSONALIZED_OPTIMAL"
    assert path == [1, 2, 4]
    assert stats['cost'] > 0

# TEST 15: Existing YOLO congestion system still works
def test_15_existing_yolo_congestion_works():
    assert CongestionConfig.get_level(0.0) == "LOW"
    assert CongestionConfig.get_level(0.3) == "MEDIUM"
    assert CongestionConfig.get_level(0.6) == "HIGH"
    assert CongestionConfig.get_level(0.9) == "HIGH"
    assert CongestionConfig.normalize_level("SEVERE") == "HIGH"
    assert CongestionConfig.normalize_level("MODERATE") == "MEDIUM"
