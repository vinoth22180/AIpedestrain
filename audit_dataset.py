import os
import sys
import pickle

project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

graph_path = os.path.join(project_root, "data", "vit_vellore", "processed", "vit_vellore_academic_pedestrian_network.pkl")
with open(graph_path, 'rb') as f:
    G_base = pickle.load(f)

# Dataset Structure
num_nodes = len(G_base.nodes)
num_edges = len(G_base.edges)
print(f"Nodes: {num_nodes}")
print(f"Edges: {num_edges}")

# Edge attributes check
fallback_count = 0
osm_geom_count = 0
missing_geom = 0
zero_slopes = 0
total_slopes = 0

for u, v, k, d in G_base.edges(data=True, keys=True):
    if d.get("geometry_source") == "endpoint_fallback":
        fallback_count += 1
    elif d.get("geometry_source") == "osm_way":
        osm_geom_count += 1
    elif d.get("geometry_source") == "missing":
        missing_geom += 1
        
    if "slope_percent" in d:
        total_slopes += 1
        if d["slope_percent"] == 0.0:
            zero_slopes += 1

print(f"Fallback geometry edges: {fallback_count} ({(fallback_count/num_edges)*100:.2f}%)")
print(f"OSM geometry edges: {osm_geom_count} ({(osm_geom_count/num_edges)*100:.2f}%)")
print(f"Missing geometry edges: {missing_geom}")
print(f"Zero slopes: {zero_slopes} / {total_slopes}")

# Test the 9 manual locations
manual_locs = {
    "MGR": (79.15583638463455, 12.969035851408112),
    "SMV": (79.15766374408548, 12.969246074425618),
    "TT": (79.15953483469843, 12.97082312983498),
    "SJT": (79.16394473901578, 12.970917609834906),
    "PRP": (79.16640540870385, 12.971264636436771),
    "Gandhi Block": (79.16799249061337, 12.972225506107774),
    "Anna Auditorium": (79.1556603675251, 12.96984326294177),
    "Parking Lot": (79.1550150327412, 12.968647332768128),
    "CTS": (79.15623259923282, 12.970266027390673)
}

from src.routing import get_nearest_node
import math

def haversine(lon1, lat1, lon2, lat2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

for name, coords in manual_locs.items():
    node = get_nearest_node(G_base, coords)
    n_data = G_base.nodes[node]
    dist = haversine(coords[0], coords[1], n_data['x'], n_data['y'])
    print(f"Loc: {name} -> snapped to node {node} at dist {dist:.2f}m")
    
# Multigraph parallel edge check
print(f"Is MultiGraph: {G_base.is_multigraph()}")
parallel_edges = 0
for u, v in set(G_base.edges(keys=False)):
    if G_base.number_of_edges(u, v) > 1:
        parallel_edges += 1
print(f"Pairs of nodes with parallel edges: {parallel_edges}")

