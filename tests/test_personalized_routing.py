import pytest
import networkx as nx
from src.pada_r.router import compute_pada_route
from src.pada_r.profiles import (
    PREGNANT_MAX_SLOPE, WHEELCHAIR_MAX_SLOPE, ELDERLY_SLOPE_THRESHOLD,
    is_edge_allowed
)
from src.pada_r.cost_model import calculate_pada_cost
import math

def create_synthetic_graph():
    G = nx.MultiDiGraph()
    # Adding a few nodes near 0,0 to use Euclidean fallback in astar_heuristic
    # A->B->C (general path)
    G.add_node("A", x=0.0001, y=0.0001)
    G.add_node("B", x=0.0002, y=0.0002)
    G.add_node("C", x=0.0003, y=0.0003)
    G.add_node("D", x=0.0002, y=0.0001)  # Alternative B
    return G

def test_general_can_use_stair():
    G = create_synthetic_graph()
    G.add_edge("A", "B", length_m=10, stairs=True)
    G.add_edge("B", "C", length_m=10)
    
    path, edges, status, exp, stats, cands = compute_pada_route(G, (0.0001, 0.0001), (0.0003, 0.0003), "general")
    assert path == ["A", "B", "C"]
    assert stats['cost'] < float('inf')

def test_wheelchair_excludes_stair():
    G = create_synthetic_graph()
    G.add_edge("A", "B", length_m=10, stairs=True)
    G.add_edge("B", "C", length_m=10)
    
    # Alternative path D without stairs
    G.add_edge("A", "D", length_m=15, stairs=False, wheelchair="yes", accessible=True)
    G.add_edge("D", "C", length_m=15, stairs=False, wheelchair="yes", accessible=True)
    
    path, edges, status, exp, stats, cands = compute_pada_route(G, (0.0001, 0.0001), (0.0003, 0.0003), "wheelchair")
    assert path == ["A", "D", "C"]
    
def test_wheelchair_excludes_barrier():
    G = create_synthetic_graph()
    G.add_edge("A", "B", length_m=10, barrier="gate", wheelchair="yes", accessible=True)
    G.add_edge("B", "C", length_m=10, wheelchair="yes", accessible=True)
    
    G.add_edge("A", "D", length_m=15, wheelchair="yes", accessible=True)
    G.add_edge("D", "C", length_m=15, wheelchair="yes", accessible=True)
    
    path, edges, status, exp, stats, cands = compute_pada_route(G, (0.0001, 0.0001), (0.0003, 0.0003), "wheelchair")
    assert path == ["A", "D", "C"]

def test_pregnant_avoids_stairs_when_configured():
    G = create_synthetic_graph()
    G.add_edge("A", "B", length_m=10, stairs=True)
    G.add_edge("B", "C", length_m=10)
    
    G.add_edge("A", "D", length_m=15)
    G.add_edge("D", "C", length_m=15)
    
    path, edges, status, exp, stats, cands = compute_pada_route(G, (0.0001, 0.0001), (0.0003, 0.0003), "pregnant")
    assert path == ["A", "D", "C"]

def test_pregnant_avoids_slope():
    G = create_synthetic_graph()
    G.add_edge("A", "B", length_m=10, slope_percent=6.0) # Exceeds 5.0
    G.add_edge("B", "C", length_m=10)
    
    G.add_edge("A", "D", length_m=15, slope_percent=2.0)
    G.add_edge("D", "C", length_m=15, slope_percent=2.0)
    
    path, edges, status, exp, stats, cands = compute_pada_route(G, (0.0001, 0.0001), (0.0003, 0.0003), "pregnant")
    assert path == ["A", "D", "C"]

def test_elderly_soft_penalty_slope():
    G = create_synthetic_graph()
    # A->B is slightly shorter but has slope
    G.add_edge("A", "B", length_m=10, slope_percent=4.0) 
    G.add_edge("B", "C", length_m=10)
    
    # A->D is slightly longer but flat
    G.add_edge("A", "D", length_m=11, slope_percent=0.0)
    G.add_edge("D", "C", length_m=11, slope_percent=0.0)
    
    path, edges, status, exp, stats, cands = compute_pada_route(G, (0.0001, 0.0001), (0.0003, 0.0003), "elderly")
    assert path == ["A", "D", "C"]
    
def test_wheelchair_unknown_policy():
    G = create_synthetic_graph()
    # Completely unknown, no positive indicators
    G.add_edge("A", "B", length_m=10, wheelchair="unknown", accessible=None)
    G.add_edge("B", "C", length_m=10, wheelchair="unknown", accessible=None)
    
    path, edges, status, exp, stats, cands = compute_pada_route(G, (0.0001, 0.0001), (0.0003, 0.0003), "wheelchair")
    # Should be inaccessible
    assert status == "NO_ACCESSIBLE_ROUTE_FOUND"
    
def test_congestion_behavior():
    G = create_synthetic_graph()
    # Shorter but congested
    G.add_edge("A", "B", length_m=10, congestion_penalty=10.0, wheelchair="yes", accessible=True) 
    G.add_edge("B", "C", length_m=10, wheelchair="yes", accessible=True)
    
    # Longer but uncongested
    G.add_edge("A", "D", length_m=20, wheelchair="yes", accessible=True)
    G.add_edge("D", "C", length_m=20, wheelchair="yes", accessible=True)
    
    # For general, it might tolerate it if weight is 1.0 (let's check)
    path_g, _, _, _, _, _ = compute_pada_route(G, (0.0001, 0.0001), (0.0003, 0.0003), "general")
    
    # For wheelchair, multiplier is higher, should detour
    G["A"]["B"][0]["congestion_penalty"] = 5.0 # 5.0 penalty per meter => +50 cost for A-B
    
    path_wc, _, _, _, _, _ = compute_pada_route(G, (0.0001, 0.0001), (0.0003, 0.0003), "wheelchair")
    
    assert path_wc is not None
    
def test_alternative_routes():
    G = create_synthetic_graph()
    G.add_edge("A", "B", length_m=10)
    G.add_edge("B", "C", length_m=10)
    
    G.add_edge("A", "D", length_m=25)
    G.add_edge("D", "C", length_m=25)
    
    path, edges, status, exp, stats, cands = compute_pada_route(G, (0.0001, 0.0001), (0.0003, 0.0003), "general")
    assert len(cands) >= 1
