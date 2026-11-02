import sys
import os
import networkx as nx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.graph_manager import load_or_build_graph
from src.pada_r.router import compute_pada_route

def test_all_profiles():
    G = load_or_build_graph()
    origin = (144.9669, -37.8183) # Flinders
    destination = (144.9646, -37.8098) # State Library
    
    profiles = [
        "general", 
        "wheelchair", 
        "visually_impaired", 
        "hearing_impaired", 
        "mobility_impaired", 
        "elderly", 
        "pregnant"
    ]
    
    print(f"Routing from {origin} to {destination}\n")
    
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
        
        print(f"{p.upper():20}: RouteLength={dist:.1f}m | TotalCost={cost:.1f} | Acc={acc:.1f} | Eff={eff:.1f} | Saf={saf:.1f}")

if __name__ == "__main__":
    test_all_profiles()
