import sys
import os
import networkx as nx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.graph_manager import load_or_build_graph
from src.pada_r.router import compute_pada_route
from src.signal_decay.engine import decay_engine
from src.weather.service import weather_service
from src.models.edge_state import WeatherState
import time

def run_test():
    G = load_or_build_graph()
    origin = (79.15583638463455, 12.969035851408112) # MGR
    destination = (79.15766374408548, 12.969246074425618) # SMV
    
    import src.routing as r
    u_node = r.get_nearest_node(G, origin)
    v_node = r.get_nearest_node(G, destination)
    
    print(f"Nearest Origin: {u_node}")
    print(f"Nearest Dest: {v_node}")
    
    sim_date = "2023-10-10"
    sim_hour = 10
    
    # 1. Baseline: NO CONGESTION, NORMAL WEATHER
    weather_service.set_simulation_override(None)
    path, path_edges, status, explanation, stats = compute_pada_route(G, origin, destination, "general", sim_date, sim_hour)
    
    print("\n--- BASELINE (NO CONGESTION, NORMAL WEATHER) ---")
    print(f"Cost: {stats['cost']:.2f}")
    print(f"Weather Cost: {stats['cost_breakdown']['weather']:.2f}")
    print(f"Congestion/Decay Cost: {stats['cost_breakdown']['decay']:.2f}")
    
    # Let's find an edge on the path to inject congestion
    if not path or len(path) < 2:
        print("No path found!")
        return
        
    inject_u, inject_v = path[1], path[2]
    
    # 2. Add Congestion + Rain
    weather_service.set_simulation_override(WeatherState(
        precipitation=10.0,
        weather_condition="RAIN",
        temperature=25.0,
        apparent_temperature=25.0,
        freshness="LIVE"
    ))
    
    decay_engine.add_penalty(inject_u, inject_v, 200.0, "HIGH")
    
    print("\n--- HIGH CONGESTION + RAIN (t=0) ---")
    path, path_edges, status, explanation, stats = compute_pada_route(G, origin, destination, "general", sim_date, sim_hour)
    print(f"Cost: {stats['cost']:.2f}")
    print(f"Weather Cost: {stats['cost_breakdown']['weather']:.2f}")
    print(f"Congestion/Decay Cost: {stats['cost_breakdown']['decay']:.2f}")
    
    for t in [300, 600, 900, 1200]:
        decay_engine.update_time(decay_engine.last_update_time + 300)
        path, path_edges, status, explanation, stats = compute_pada_route(G, origin, destination, "general", sim_date, sim_hour)
        print(f"\n--- ADVANCE DECAY (t={t}) ---")
        print(f"Cost: {stats['cost']:.2f}")
        print(f"Weather Cost: {stats['cost_breakdown']['weather']:.2f}")
        print(f"Congestion/Decay Cost: {stats['cost_breakdown']['decay']:.2f}")

if __name__ == "__main__":
    run_test()
