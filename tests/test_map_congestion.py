import pytest
import networkx as nx
from src.congestion.manager import congestion_manager
from src.pada_r.router import compute_pada_route
import time

def setup_test_graph():
    G = nx.MultiDiGraph()
    # Node 1 to Node 2: edge A
    # Node 2 to Node 3: edge B
    G.add_node(1, x=10.0, y=10.0)
    G.add_node(2, x=20.0, y=10.0)
    G.add_node(3, x=30.0, y=10.0)
    G.add_node(4, x=15.0, y=15.0) # Unrelated path
    
    G.add_edge(1, 2, key="k1", length_m=10, accessible=True)
    G.add_edge(2, 3, key="k1", length_m=10, accessible=True)
    G.add_edge(1, 4, key="k1", length_m=10, accessible=True)
    return G

def test_exact_edge_congestion():
    G = setup_test_graph()
    congestion_manager.reset_congestion()
    
    # 1. Simulate exact edge congestion selection
    edge_id = "edge:1:2:k1"
    
    # Send congestion update
    job_id = congestion_manager.create_job(edge_id)
    congestion_manager.update_job(job_id, {
        "congestion_score": 150.0,
        "congestion_level": "SEVERE",
        "average_people": 25,
        "peak_people": 30,
        "timestamp": time.time()
    })
    
    # 2. Assert exact edge gets high congestion
    cong_1_2 = congestion_manager.get_congestion_for_edge(1, 2, G)
    assert cong_1_2 == 150.0, "Exact edge should receive congestion penalty"
    
    # 3. Assert unrelated edge does not get congestion
    cong_2_3 = congestion_manager.get_congestion_for_edge(2, 3, G)
    assert cong_2_3 == 0.0, "Unrelated edge should not receive congestion penalty"
    
    cong_1_4 = congestion_manager.get_congestion_for_edge(1, 4, G)
    assert cong_1_4 == 0.0, "Parallel or unrelated edge should not receive congestion penalty"
    
    # 4. Check routing respects the congestion
    # Route from 1 to 3: should go 1->2->3, but 1->2 is heavily congested. Let's add a detour.
    G.add_node(5, x=10.0, y=20.0)
    G.add_node(6, x=30.0, y=20.0)
    G.add_edge(1, 5, key="k1", length_m=12, accessible=True)
    G.add_edge(5, 6, key="k1", length_m=20, accessible=True)
    G.add_edge(6, 3, key="k1", length_m=12, accessible=True)
    
    path, path_edges, route_status, route_explanation, stats, cands = compute_pada_route(G, (10, 10), (30, 10), "general")
    
    # Without congestion, 1->2->3 is 20m. With 150 score, cost is huge.
    # Detour is 12+20+12 = 44m.
    # It should take the detour!
    assert path == [1, 5, 6, 3], "Routing should detour around exactly matched congested edge"

def test_api_pedestrian_network_generates_edge_ids():
    from src.api import get_pedestrian_network, G_base
    import src.api
    
    G = setup_test_graph()
    # Mock geometry for the graph to pass get_pedestrian_network geom check
    from shapely.geometry import LineString
    for u, v, k, d in G.edges(keys=True, data=True):
        d['geometry'] = LineString([(G.nodes[u]['x'], G.nodes[u]['y']), (G.nodes[v]['x'], G.nodes[v]['y'])])
        
    src.api.G_base = G
    
    res = get_pedestrian_network()
    features = res.get("features", [])
    
    edge_ids = [f["properties"]["edge_id"] for f in features]
    assert "edge:1:2:k1" in edge_ids
    assert "edge:2:3:k1" in edge_ids

def test_congestion_history_different_edges():
    congestion_manager.reset_congestion()
    j1 = congestion_manager.create_job("edge:1:2:0")
    congestion_manager.update_job(j1, {"congestion_score": 50})
    
    j2 = congestion_manager.create_job("edge:2:3:0")
    congestion_manager.update_job(j2, {"congestion_score": 80})
    
    s1 = congestion_manager.get_active_congestion().get("edge:1:2:0")
    s2 = congestion_manager.get_active_congestion().get("edge:2:3:0")
    
    assert s1.congestion_score == 50
    assert s2.congestion_score == 80
    
    # Update same edge
    j3 = congestion_manager.create_job("edge:1:2:0")
    congestion_manager.update_job(j3, {"congestion_score": 90})
    
    s1_new = congestion_manager.get_active_congestion().get("edge:1:2:0")
    assert s1_new.congestion_score == 90
    assert len(congestion_manager.get_history("edge:1:2:0")) == 2
