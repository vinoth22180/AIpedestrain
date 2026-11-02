import sys
import os
import networkx as nx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.graph_manager import load_or_build_graph
from src.pada_r.router import compute_pada_route

def find_test_scenario():
    G = load_or_build_graph()
    
    # We found stairs at edge ((144.967148, -37.819761), (144.966243, -37.819939))
    # Let's route from somewhat far away to allow alternative paths
    
    origin = (144.968605, -37.819667)
    # Pick a destination further away that forces routing through this area
    # Like Flinders Street Station (144.9669, -37.8183) or similar
    
    destination = (144.965, -37.821)
            
    profiles = [
        "general", 
        "wheelchair", 
        "visually_impaired", 
        "mobility_impaired", 
        "elderly", 
        "pregnant"
    ]
    
    print(f"\nRouting from {origin} to {destination}\n")
    
    for p in profiles:
        path, edges, status, exp, stats = compute_pada_route(
            G, origin, destination, p, 
            sim_date_str="2023-10-01", sim_hour=12
        )
        
        if not path:
            print(f"{p.upper():20}: NO PATH FOUND")
            continue
            
        dist = stats['distance']
        cost = stats['cost']
        acc = stats['cost_breakdown']['accessibility']
        eff = stats['cost_breakdown']['effort']
        saf = stats['cost_breakdown']['safety']
        
        print(f"{p.upper():20}: RouteLength={dist:.1f}m | TotalCost={cost:.1f} | PathEnd={path[-1]}")

if __name__ == "__main__":
    find_test_scenario()
