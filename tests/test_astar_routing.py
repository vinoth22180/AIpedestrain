import pytest
import networkx as nx
from unittest.mock import patch
from src.pada_r.router import compute_pada_route
from src.congestion.manager import congestion_manager

@pytest.fixture
def simple_graph():
    G = nx.MultiDiGraph()
    # Add nodes with coordinates
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=0.0, y=0.0002)
    G.add_node(3, x=0.0, y=0.0004)
    G.add_node(4, x=0.001, y=0.0002)
    
    # Add edges with attributes
    # Path A: 1 -> 2 -> 3 (direct, distance 200)
    G.add_edge(1, 2, length_m=100, stairs=False, surface_type='paved', wheelchair_accessible=True)
    G.add_edge(2, 3, length_m=100, stairs=False, surface_type='paved', wheelchair_accessible=True)
    
    # Path B: 1 -> 4 -> 3 (detour, distance 240)
    G.add_edge(1, 4, length_m=120, stairs=False, surface_type='paved', wheelchair_accessible=True)
    G.add_edge(4, 3, length_m=120, stairs=False, surface_type='paved', wheelchair_accessible=True)
    return G

@pytest.fixture
def vit_graph():
    from src.graph_manager import load_or_build_graph
    return load_or_build_graph()

def test_astar_shortest_path_simple(simple_graph):
    # TEST 1 & 2: A* finds shortest path and uses supplied weight
    congestion_manager.reset_congestion()
    path, _, status, _, stats = compute_pada_route(simple_graph, [0.0, 0.0], [0.0, 0.0004], "general")
    assert path == [1, 2, 3]
    assert pytest.approx(stats['cost'], abs=1.0) == 200.0


@patch('src.congestion.manager.CongestionManager._get_location_coords')
def test_astar_congestion_rerouting(mock_get_coords, simple_graph):
    # TEST 3: Congestion changes the selected path
    congestion_manager.reset_congestion()
    # Mock SJT to be near node 2 (Path A)
    mock_get_coords.side_effect = lambda loc_id, G: (0.0, 0.0002) if loc_id == "SJT" else None
    
    job_id = congestion_manager.create_job("SJT")
    congestion_manager.update_job(job_id, {
        "location": "SJT", "average_people": 25.0, "peak_people": 35,
        "congestion_score": 1.0, "congestion_level": "HIGH"
    })
    
    path, _, status, _, stats = compute_pada_route(simple_graph, [0.0, 0.0], [0.0, 0.0004], "general")
    
    # Path A was 200 + massive penalty. Path B is 240. Should choose B.
    assert path == [1, 4, 3]
    assert stats['distance'] == 240.0

@patch('src.congestion.manager.CongestionManager._get_location_coords')
def test_astar_congestion_absorb(mock_get_coords, simple_graph):
    # TEST 4: Congestion does not change route when original route is still cheaper
    congestion_manager.reset_congestion()
    mock_get_coords.side_effect = lambda loc_id, G: (0.0, 0.0002) if loc_id == "SJT" else None
    
    job_id = congestion_manager.create_job("SJT")
    congestion_manager.update_job(job_id, {
        "location": "SJT", "average_people": 1.0, "peak_people": 1,
        "congestion_score": 0.001, "congestion_level": "LOW" # tiny penalty
    })
    
    path, _, status, _, stats = compute_pada_route(simple_graph, [0.0, 0.0], [0.0, 0.0004], "general")
    # Path A should still be chosen
    assert path == [1, 2, 3]

def test_accessibility_profiles(simple_graph):
    # TEST 5: Accessibility profiles affect routing
    # Add stairs to path A
    simple_graph[1][2][0]['stairs'] = True
    congestion_manager.reset_congestion()
    
    # Wheelchair should avoid stairs
    path, _, status, _, stats = compute_pada_route(simple_graph, [0.0, 0.0], [0.0, 0.0004], "wheelchair")
    assert path == [1, 4, 3] # Wheelchair avoids stairs
    assert status == "PERSONALIZED_OPTIMAL"
    
def test_real_vit_graph(vit_graph):
    # TEST 6: Real VIT graph works
    congestion_manager.reset_congestion()
    origin = [79.1595, 12.9708] # TT
    destination = [79.1679, 12.9722] # Gandhi Block
    
    path, _, status, _, stats = compute_pada_route(vit_graph, origin, destination, "general")
    assert path is not None
    assert len(path) > 5
    assert stats['cost'] > 0
    assert status == "PERSONALIZED_OPTIMAL"

def test_sjt_congestion_reflected_in_edge_costs(vit_graph):
    # TEST 7: SJT congestion affects edges on the real graph
    from src.pada_r.cost_model import calculate_pada_cost
    
    # Create fake edge near SJT
    # SJT is at 79.1639, 12.9709
    congestion_manager.reset_congestion()
    u_c = (79.1639, 12.9709)
    v_c = (79.1640, 12.9710)
    
    # No congestion
    penalty_none = congestion_manager.get_congestion_for_edge(u_c, v_c, vit_graph)
    assert penalty_none == 0.0
    
    # Add high congestion
    job_id = congestion_manager.create_job("SJT")
    congestion_manager.update_job(job_id, {
        "location": "SJT", "average_people": 25.0, "peak_people": 35,
        "congestion_score": 0.8, "congestion_level": "HIGH"
    })
    
    penalty_high = congestion_manager.get_congestion_for_edge(u_c, v_c, vit_graph)
    assert penalty_high > 0.0
    assert penalty_high == 0.8
    
    # Verify it influences cost_model
    status, cost, breakdown, _ = calculate_pada_cost(None, None, {'length_m': 100}, 'general', dynamic_congestion_penalty=penalty_high)
    assert breakdown['congestion'] > 0
    assert cost > 100 # Should be heavily penalized
