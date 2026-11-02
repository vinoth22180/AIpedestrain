from src.graph_manager import load_or_build_graph
from src.routing import get_nearest_node
import networkx as nx
import itertools

G = load_or_build_graph()
mgr_coords = (79.15583638463455, 12.969035851408112)
gandhi_coords = (79.16799249061337, 12.972225506107774)

u = get_nearest_node(G, mgr_coords)
v = get_nearest_node(G, gandhi_coords)
print(f"MGR: {u}, Gandhi: {v}")

# Create simple DiGraph/Graph with minimum length per (u, v)
G_simple = nx.Graph()
for node, d in G.nodes(data=True):
    G_simple.add_node(node, **d)

for u1, v1, k, d in G.edges(keys=True, data=True):
    l = d.get('length_m', d.get('length', 1.0))
    eid = d.get('edge_id', str(k))
    if G_simple.has_edge(u1, v1):
        if l < G_simple[u1][v1]['weight']:
            G_simple[u1][v1]['weight'] = l
            G_simple[u1][v1]['edge_id'] = eid
    else:
        G_simple.add_edge(u1, v1, weight=l, edge_id=eid)

print(f"G_simple: {G_simple.number_of_nodes()} nodes, {G_simple.number_of_edges()} edges")

# Find first 15 shortest paths
paths = []
for p in itertools.islice(nx.shortest_simple_paths(G_simple, u, v, weight='weight'), 15):
    dist = sum(G_simple[p[i]][p[i+1]]['weight'] for i in range(len(p)-1))
    eids = [G_simple[p[i]][p[i+1]]['edge_id'] for i in range(len(p)-1)]
    has_1926 = ('E001926' in eids)
    # Check if passes through SJT vs Lake
    # Let's check coordinates of the path
    mid_lats = [G.nodes[n]['y'] for n in p]
    avg_lat = sum(mid_lats) / len(mid_lats)
    paths.append((dist, len(p), has_1926, avg_lat, eids))

for i, (dist, n_nodes, has_1926, avg_lat, eids) in enumerate(paths):
    print(f"Path {i+1}: dist={dist:.2f}m, nodes={n_nodes}, has_E001926={has_1926}, avg_lat={avg_lat:.5f}")
