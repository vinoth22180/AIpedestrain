import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.graph_manager import load_or_build_graph
from src.simulation.waterlogging_engine import waterlogging_engine
from src.simulation.controller import sim_controller
from src.pada_r.router import compute_pada_route

def test_waterlogging():
    print("Loading Graph...")
    G = load_or_build_graph()
    
    origin = (144.9669, -37.8183) # Flinders Street Station (approx center in melbourne test)
    destination = (144.9646, -37.8098) # State Library
    
    # Or just use two known connected nodes from edges
    edges = list(G.edges(keys=False, data=True))
    if len(edges) > 0:
        edge = edges[0]
        u = edge[0]
        v = edge[1]
        
        # Inject waterlogging on the edge
        waterlogging_engine.inject_waterlogging(u, v, 4.0) # 4 cm
        print(f"Injected 4cm waterlogging on edge {u}->{v}")
        
        sim_state = sim_controller.get_state()
        print("Active waterlogging events:", len(sim_state['active_waterlogging_events']))
        
        path, path_edges, route_status, route_explanation, stats = compute_pada_route(
            G, (G.nodes[u]['x'], G.nodes[u]['y']), (G.nodes[v]['x'], G.nodes[v]['y']), 
            "wheelchair", 
            sim_date_str="2025-10-23", 
            sim_hour=8
        )
        
        print("\nWheelchair Route status (4cm):", route_status)
        print("Wheelchair Route explanation:", route_explanation)
        
        # General profile should still pass
        path, path_edges, route_status, route_explanation, stats = compute_pada_route(
            G, (G.nodes[u]['x'], G.nodes[u]['y']), (G.nodes[v]['x'], G.nodes[v]['y']), 
            "general", 
            sim_date_str="2025-10-23", 
            sim_hour=8
        )
        
        print("\nGeneral Route status (4cm):", route_status)
        print("General Route explanation:", route_explanation)
        
        waterlogging_engine.clear_waterlogging(u, v)
        print(f"\nCleared waterlogging on edge {u}->{v}")
        
        print("Tests completed.")

if __name__ == "__main__":
    test_waterlogging()
