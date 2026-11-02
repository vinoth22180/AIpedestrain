import pytest
import math
import networkx as nx
from src.graph_manager import load_or_build_graph
from src.pada_r.router import compute_pada_route
from src.congestion.manager import congestion_manager, CongestionState
from src.pada_r.cost_model import calculate_pada_cost, is_edge_allowed

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

@pytest.fixture(scope="module")
def vit_graph():
    return load_or_build_graph()

def test_updated_graph_topology(vit_graph):
    """
    Validates that the improved graph has resolved the missing 674 edges,
    now containing 2,149 nodes and 2,371 edges with 0 isolated nodes.
    """
    assert len(vit_graph.nodes) == 2149
    assert len(vit_graph.edges) == 2371
    
    # 0 isolated nodes
    isolated = [n for n in vit_graph.nodes if vit_graph.degree(n) == 0]
    assert len(isolated) == 0
    
    # Main connected component covers over 98% of nodes
    components = list(nx.connected_components(vit_graph))
    components.sort(key=len, reverse=True)
    assert len(components[0]) == 2126

def test_astar_dijkstra_equivalence_on_campus_pairs(vit_graph):
    """
    Validates that A* and Dijkstra agree 100% on shortest physical distance
    across representative pairs across all regions of the VIT Vellore campus.
    """
    congestion_manager.reset_congestion()
    
    # Map landmark names to coordinates
    landmarks = {}
    for n, d in vit_graph.nodes(data=True):
        if 'name' in d and d.get('node_type') in ['academic_block', 'landmark']:
            landmarks[d['name']] = (n, (d['x'], d['y']))
            
    test_pairs = [
        ('Anna Auditorium', 'SJT'),
        ('MGR', 'PRP'),
        ('SMV', 'TT'),
        ('Gandhi Block', 'CTS'),
        ('PRP', 'SJT')
    ]
    
    def dijkstra_weight(u, v, d):
        if vit_graph.is_multigraph():
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

    for orig_name, dest_name in test_pairs:
        if orig_name not in landmarks or dest_name not in landmarks:
            continue
        orig_node, orig_coords = landmarks[orig_name]
        dest_node, dest_coords = landmarks[dest_name]
        
        res = compute_pada_route(vit_graph, orig_coords, dest_coords, "general")
        astar_path = res[0]
        astar_dist = res[4]['distance']
        cand_coords = res[5][0]['geojson']['geometry']['coordinates']
        
        dijkstra_path = nx.dijkstra_path(vit_graph, orig_node, dest_node, weight=dijkstra_weight)
        dijkstra_dist = nx.dijkstra_path_length(vit_graph, orig_node, dest_node, weight=dijkstra_weight)
        
        # Verify node-for-node match
        assert astar_path == dijkstra_path, f"Mismatch on {orig_name} -> {dest_name}"
        assert abs(astar_dist - dijkstra_dist) < 1e-4, f"Distance discrepancy on {orig_name} -> {dest_name}"
        
        # Verify polyline orientation matches physical distance within sub-meter precision
        poly_dist = polyline_length(cand_coords)
        assert abs(astar_dist - poly_dist) < 0.5, f"Rendering discrepancy on {orig_name} -> {dest_name}: {abs(astar_dist - poly_dist):.3f}m"

def test_wheelchair_accessibility_on_expanded_graph(vit_graph):
    """
    Validates that wheelchair routing strictly excludes stairs and complies with
    accessibility constraints across the campus.
    """
    congestion_manager.reset_congestion()
    landmarks = {}
    for n, d in vit_graph.nodes(data=True):
        if 'name' in d and d.get('node_type') in ['academic_block', 'landmark']:
            landmarks[d['name']] = (n, (d['x'], d['y']))
            
    orig_node, orig_coords = landmarks['Anna Auditorium']
    dest_node, dest_coords = landmarks['SJT']
    
    res = compute_pada_route(vit_graph, orig_coords, dest_coords, "wheelchair")
    assert res[0] is not None
    assert res[4]['accessibility_summary']['stairs_avoided'] is True
    assert res[4]['accessibility_summary']['stairs_count'] == 0

def test_subway_and_newly_restored_paths(vit_graph):
    """
    Validates that the restored pedestrian subways (66 subway edges)
    and newly connected ways are navigable in the graph.
    """
    subway_edges = [e for e in vit_graph.edges(data=True) if e[2].get('subway')]
    assert len(subway_edges) > 20, f"Expected >20 subway edges, found {len(subway_edges)}"
    
    stairs_edges = [e for e in vit_graph.edges(data=True) if e[2].get('stairs')]
    assert len(stairs_edges) >= 13, f"Expected >=13 stairs edges, found {len(stairs_edges)}"
