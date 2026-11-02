import pytest
import networkx as nx
from src.pada_r.router import compute_pada_route
from src.pada_r.profiles import PADA_PROFILES

@pytest.fixture
def mock_graph():
    G = nx.Graph()
    # Simple diamond graph
    G.add_node(1, x=0, y=0)
    G.add_node(2, x=0, y=1)
    G.add_node(3, x=1, y=0)
    G.add_node(4, x=1, y=1)
    
    G.add_edge(1, 2, length=50, has_stairs=True, wheelchair_accessible=False)
    G.add_edge(2, 4, length=50, has_stairs=False, wheelchair_accessible=True)
    
    G.add_edge(1, 3, length=200, has_stairs=False, wheelchair_accessible=True)
    G.add_edge(3, 4, length=200, has_stairs=False, wheelchair_accessible=True)
    
    return G

def test_general_profile_routing(mock_graph):
    # General should pick the shorter path (1 -> 2 -> 4), taking the stair penalty
    route, edges, route_status, route_explanation, stats = compute_pada_route(
        mock_graph, 
        (0, 0), 
        (1, 1), 
        "general", 
        active_route_path=None
    )
    
    # 1 -> 2 -> 4 distance = 100, cost = (50 + 20) + 50 = 120
    # 1 -> 3 -> 4 distance = 400, cost = 200 + 200 = 400
    assert route == [1, 2, 4]

def test_wheelchair_profile_routing(mock_graph):
    # Wheelchair should completely avoid 1->2 due to stairs (INACCESSIBLE)
    route, edges, route_status, route_explanation, stats = compute_pada_route(
        mock_graph, 
        (0, 0), 
        (1, 1), 
        "wheelchair", 
        active_route_path=None
    )
    
    assert route == [1, 3, 4]

def test_route_stability(mock_graph):
    # 1->3->4 cost is 400.
    # 1->2->4 cost is 120.
    
    # If the user is currently on 1->3->4, and stability threshold is 20, 
    # but the other path is 280 cheaper, it should definitely switch.
    
    # Wait, let's make a closer scenario to test stability hysteresis
    G = nx.Graph()
    G.add_node(1, x=0, y=0)
    G.add_node(2, x=0, y=1)
    G.add_node(3, x=1, y=0)
    G.add_node(4, x=1, y=1)
    G.add_edge(1, 2, length=100)
    G.add_edge(2, 4, length=100)
    G.add_edge(1, 3, length=105) # Just 5 units more expensive
    G.add_edge(3, 4, length=100)
    
    # Normally, 1->2->4 is chosen
    route, _, _, _, _ = compute_pada_route(G, (0, 0), (1, 1), "general", active_route_path=None)
    assert route == [1, 2, 4]
    
    # If we are already on 1->3->4, and 1->2->4 is only 5 units better,
    # stability_threshold is 15.0 for General, so it should retain 1->3->4
    route, edges, route_status, explanation, stats = compute_pada_route(G, (0, 0), (1, 1), "general", active_route_path=[1, 3, 4])
    
    # Path should remain 1->3->4
    assert route == [1, 3, 4]
    assert route_status == "STABLE_RETAINED"

    # But if 1->3 becomes 30 units more expensive (e.g. length=130), it should switch to 1->2->4
    G[1][3]['length'] = 130
    route, edges, route_status, explanation, stats = compute_pada_route(G, (0, 0), (1, 1), "general", active_route_path=[1, 3, 4])
    
    assert route == [1, 2, 4]
    assert route_status != "STABLE_RETAINED"
