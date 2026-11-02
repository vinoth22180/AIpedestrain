from src.graph_manager import load_or_build_graph
from src.routing import get_nearest_node
import networkx as nx

G = load_or_build_graph()
mgr_coords = (79.15583638463455, 12.969035851408112)
gandhi_coords = (79.16799249061337, 12.972225506107774)

u = get_nearest_node(G, mgr_coords)
v = get_nearest_node(G, gandhi_coords)

# Create a copy of G without any edges named 'Jimmy Carter Road'
G_no_jc = nx.Graph()
for node, d in G.nodes(data=True):
    G_no_jc.add_node(node, **d)

for u1, v1, k, d in G.edges(keys=True, data=True):
    if d.get('name') == 'Jimmy Carter Road':
        continue
    l = d.get('length_m', 1.0)
    eid = d.get('edge_id', str(k))
    if not G_no_jc.has_edge(u1, v1) or l < G_no_jc[u1][v1]['weight']:
        G_no_jc.add_edge(u1, v1, weight=l, edge_id=eid, name=d.get('name', ''))

print(f"Has path without Jimmy Carter Road: {nx.has_path(G_no_jc, u, v)}")
if nx.has_path(G_no_jc, u, v):
    p = nx.shortest_path(G_no_jc, u, v, weight='weight')
    dist = sum(G_no_jc[p[i]][p[i+1]]['weight'] for i in range(len(p)-1))
    eids = [G_no_jc[p[i]][p[i+1]]['edge_id'] for i in range(len(p)-1)]
    road_names = [G_no_jc[p[i]][p[i+1]]['name'] for i in range(len(p)-1) if G_no_jc[p[i]][p[i+1]]['name']]
    print(f"Alternative path distance: {dist:.2f}m, nodes: {len(p)}")
    print(f"Roads on alternative path: {set(road_names)}")
    print(f"Edge IDs on alternative path (first 10): {eids[:10]}")
