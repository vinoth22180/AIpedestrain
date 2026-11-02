import networkx as nx
import math
import time
from src.graph_manager import load_or_build_graph
from src.pada_r.router import compute_pada_route
from src.congestion.manager import congestion_manager

def run_controlled_test():
    print("Loading Graph...")
    G = load_or_build_graph()
    
    print("\n--- CASE A: NO CONGESTION ---")
    congestion_manager.reset_congestion()
    
    # TT to PRP
    origin = [79.1595, 12.9708]
    destination = [79.1664, 12.9712]
    
    start_time = time.time()
    path_A, edges_A, status_A, _, stats_A = compute_pada_route(G, origin, destination, "general")
    time_A = time.time() - start_time
    
    print(f"Algorithm computed route in {time_A:.4f}s")
    print(f"Status: {status_A}")
    print(f"Nodes in path: {len(path_A)}")
    print(f"Total Cost: {stats_A['cost']:.2f}")
    print(f"Distance: {stats_A['distance']:.2f}m")
    
    print("\n--- CASE B: SJT CONGESTION ---")
    # Find midpoint of an edge in path_A to guarantee we block the path
    mid_u = path_A[len(path_A)//2]
    mid_v = path_A[len(path_A)//2 + 1]
    mid_lon = (G.nodes[mid_u]['x'] + G.nodes[mid_v]['x']) / 2
    mid_lat = (G.nodes[mid_u]['y'] + G.nodes[mid_v]['y']) / 2
    
    # Simulate congestion exactly there (mocking a location dynamically)
    job_id = congestion_manager.create_job("BLOCKER")
    congestion_manager.update_job(job_id, {
        "location": "BLOCKER",
        "average_people": 25.0,
        "peak_people": 35,
        "congestion_score": 1.0,
        "congestion_level": "HIGH"
    })
    # Temporarily force manager to recognize this location
    congestion_manager._get_location_coords = lambda loc_id, G_ref: (mid_lon, mid_lat) if loc_id == "BLOCKER" else None
    
    start_time = time.time()
    
    path_B, edges_B, status_B, _, stats_B = compute_pada_route(G, origin, destination, "general")
    time_B = time.time() - start_time
    
    print(f"Algorithm computed route in {time_B:.4f}s")
    print(f"Status: {status_B}")
    print(f"Nodes in path: {len(path_B)}")
    print(f"Total Cost: {stats_B['cost']:.2f}")
    print(f"Distance: {stats_B['distance']:.2f}m")
    
    if path_A != path_B:
        print("\nSUCCESS: Congestion caused the route to change!")
    else:
        print("\nNOTE: Route remained the same. (Either no better route exists or congestion was bypassed)")

if __name__ == "__main__":
    run_controlled_test()
