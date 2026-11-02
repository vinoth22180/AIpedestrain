import pytest
import math
import networkx as nx
from src.graph_manager import load_or_build_graph
from src.pada_r.router import compute_pada_route
from src.congestion.manager import congestion_manager
from src.pada_r.cost_model import calculate_pada_cost, is_edge_allowed
from src.pada_r.profiles import PADA_PROFILES

def haversine(lon1, lat1, lon2, lat2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def polyline_length(coords):
    total = 0.0
    for i in range(len(coords) - 1):
        total += haversine(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])
    return total

def test_rendered_polyline_geometry_orientation():
    """
    Validates that edge geometries are strictly oriented in the traversal direction,
    resolving the 178.8m (+16.9%) visual zigzag discrepancy between physical edge distance
    and rendered polyline distance.
    """
    G = load_or_build_graph()
    congestion_manager.reset_congestion()
    
    # Reproducible pair: Anna Auditorium -> SJT
    orig_node = 5487048366
    dest_node = 4137696570
    orig_coords = (G.nodes[orig_node]['x'], G.nodes[orig_node]['y'])
    dest_coords = (G.nodes[dest_node]['x'], G.nodes[dest_node]['y'])
    
    path, path_edges, route_status, explanation, stats, candidates = compute_pada_route(
        G, orig_coords, dest_coords, "general", active_route_path=None
    )
    
    assert path is not None
    assert len(path) == 48
    
    # Verify every edge geometry is oriented in traversal direction
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        edge = path_edges[i]
        geom = edge.get('geometry')
        if geom and hasattr(geom, 'coords'):
            coords = list(geom.coords)
            u_pt = (G.nodes[u]['x'], G.nodes[u]['y'])
            v_pt = (G.nodes[v]['x'], G.nodes[v]['y'])
            d_u = math.hypot(coords[0][0] - u_pt[0], coords[0][1] - u_pt[1])
            d_v = math.hypot(coords[0][0] - v_pt[0], coords[0][1] - v_pt[1])
            # The start of coords must be closer to u than to v
            assert d_u <= d_v, f"Edge ({u}, {v}) geometry is oriented backwards!"
            
    # Verify polyline distance matches physical edge distance within sub-meter precision
    phys_dist = stats['distance']
    cand_coords = candidates[0]['geojson']['geometry']['coordinates']
    poly_dist = polyline_length(cand_coords)
    discrepancy = abs(phys_dist - poly_dist)
    
    assert discrepancy < 0.5, f"Expected sub-meter discrepancy, got {discrepancy:.3f}m"

def test_no_congestion_baseline_matches_dijkstra():
    """
    Validates that A* routing with general profile in the no-congestion baseline
    strictly returns the identical node path and physical distance as Dijkstra.
    """
    G = load_or_build_graph()
    congestion_manager.reset_congestion()
    
    orig_node = 5487048366
    dest_node = 4137696570
    orig_coords = (G.nodes[orig_node]['x'], G.nodes[orig_node]['y'])
    dest_coords = (G.nodes[dest_node]['x'], G.nodes[dest_node]['y'])
    
    res = compute_pada_route(G, orig_coords, dest_coords, "general", active_route_path=None)
    path = res[0]
    astar_dist = res[4]['distance']
    
    def dijkstra_weight(u, v, d):
        if G.is_multigraph():
            min_l = float('inf')
            for k, attrs in d.items():
                allowed, _ = is_edge_allowed(attrs, 'general')
                if allowed:
                    l = attrs.get('length_m', attrs.get('length', 0))
                    if l < min_l: min_l = l
            return min_l if min_l < float('inf') else None
        else:
            allowed, _ = is_edge_allowed(d, 'general')
            if not allowed: return None
            return d.get('length_m', d.get('length', 0))
            
    dijkstra_path = nx.dijkstra_path(G, orig_node, dest_node, weight=dijkstra_weight)
    dijkstra_dist = nx.dijkstra_path_length(G, orig_node, dest_node, weight=dijkstra_weight)
    
    assert path == dijkstra_path, "A* path must match Dijkstra reference path 100%"
    assert abs(astar_dist - dijkstra_dist) < 1e-4, "Physical distance must match exactly"

def test_hysteresis_bypass_stability():
    """
    Validates that bypass_stability=True allows snapping back to the optimal path
    even when improvement < stability_threshold, while default preserves stability retention.
    """
    G = nx.Graph()
    G.add_node(1, x=0, y=0)
    G.add_node(2, x=0, y=1)
    G.add_node(3, x=1, y=0)
    G.add_node(4, x=1, y=1)
    G.add_edge(1, 2, length=100)
    G.add_edge(2, 4, length=100)
    G.add_edge(1, 3, length=105) # 5m longer than 1->2
    G.add_edge(3, 4, length=100)
    
    # Baseline with active_route_path=[1, 3, 4] and default stability:
    res_stable = compute_pada_route(G, (0, 0), (1, 1), "general", active_route_path=[1, 3, 4], bypass_stability=False)
    assert res_stable[0] == [1, 3, 4]
    assert res_stable[2] == "STABLE_RETAINED"
    
    # With bypass_stability=True (e.g. after congestion cleared):
    res_bypassed = compute_pada_route(G, (0, 0), (1, 1), "general", active_route_path=[1, 3, 4], bypass_stability=True)
    assert res_bypassed[0] == [1, 2, 4]
    assert res_bypassed[2] == "PERSONALIZED_OPTIMAL"
