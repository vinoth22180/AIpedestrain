import sys
sys.path.insert(0, '.')
import json
from src.graph_manager import load_or_build_graph
from src.pada_r.router import compute_pada_route

G = load_or_build_graph()
print(f"Graph loaded. Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")

# Test vit_manual_locations
man = json.load(open('data/vit_vellore/processed/vit_manual_locations.json'))['locations']
print("\nTesting vit_manual_locations routing:")
for i in range(len(man)-1):
    orig = (man[i]['longitude'], man[i]['latitude'])
    dest = (man[i+1]['longitude'], man[i+1]['latitude'])
    name1 = man[i]['name']
    name2 = man[i+1]['name']
    path, edges, status, exp, stats = compute_pada_route(G, orig, dest, 'general')
    cost = stats.get('cost') if stats else None
    print(f"  {name1} -> {name2}: {status}, cost={cost}")

# Test locations.json
locs = json.load(open('data/vit_vellore/locations.json'))
print("\nTesting locations.json routing:")
for i in range(len(locs)-1):
    orig = (locs[i]['longitude'], locs[i]['latitude'])
    dest = (locs[i+1]['longitude'], locs[i+1]['latitude'])
    name1 = locs[i]['display_name']
    name2 = locs[i+1]['display_name']
    path, edges, status, exp, stats = compute_pada_route(G, orig, dest, 'general')
    cost = stats.get('cost') if stats else None
    print(f"  {name1} -> {name2}: {status}, cost={cost}")
