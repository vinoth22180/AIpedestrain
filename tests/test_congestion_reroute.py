import networkx as nx
from src.pada_r.router import compute_pada_route
from src.congestion.manager import congestion_manager, CongestionState

def test_congestion_reroute():
    # Create a simple deterministic graph
    G = nx.MultiDiGraph()
    
    # Nodes with coordinates (x, y)
    G.add_node("START", x=0.0, y=0.0)
    G.add_node("A", x=10.0, y=0.0)
    G.add_node("B", x=15.0, y=5.0)
    G.add_node("C", x=15.0, y=-5.0)
    G.add_node("D", x=20.0, y=0.0)
    G.add_node("DEST", x=30.0, y=0.0)
    
    # Edges with distances
    # Short path: START -> A -> D -> DEST (Length: 10 + 10 + 10 = 30)
    G.add_edge("START", "A", length=10)
    G.add_edge("A", "D", length=10)
    G.add_edge("D", "DEST", length=10)
    
    # Alternative path: START -> A -> B -> D -> DEST (Length: 10 + 7 + 7 + 10 = 34)
    # A bit longer.
    G.add_edge("A", "B", length=7)
    G.add_edge("B", "D", length=7)
    
    # Without congestion
    congestion_manager.reset_congestion()
    path_no_cong, _, _, _, stats_no_cong = compute_pada_route(G, (0.0, 0.0), (30.0, 0.0), "general")
    print("--- WITHOUT CONGESTION ---")
    print(f"Path: {path_no_cong}")
    print(f"Cost: {stats_no_cong['cost']}")
    
    assert path_no_cong == ["START", "A", "D", "DEST"], "Expected shortest path without congestion"
    
    # With HIGH congestion on the middle edge A->D
    # We will mock the get_congestion_for_edge since it uses haversine and specific nodes.
    original_get = congestion_manager.get_congestion_for_edge
    def mock_get_congestion(u, v, graph, now=None):
        # If it's the A->D edge
        if (u in ("A", "D") and v in ("A", "D")) or (u == (10.0, 0.0) and v == (20.0, 0.0)) or (u == (20.0, 0.0) and v == (10.0, 0.0)):
            return 0.8  # HIGH congestion score
        return 0.0
    
    congestion_manager.get_congestion_for_edge = mock_get_congestion
    
    path_cong, _, _, _, stats_cong = compute_pada_route(G, (0.0, 0.0), (30.0, 0.0), "general")
    print("\n--- WITH HIGH CONGESTION (on A->D) ---")
    print(f"Path: {path_cong}")
    print(f"Cost: {stats_cong['cost']}")
    
    # Restore original function
    congestion_manager.get_congestion_for_edge = original_get
    
    assert path_cong == ["START", "A", "B", "D", "DEST"], f"Expected alternative path A->B->D, got {path_cong}"
    print("\nTest passed! Rerouting successful.")

if __name__ == "__main__":
    test_congestion_reroute()
