from src.graph_manager import load_or_build_graph
from src.routing import get_nearest_node
import networkx as nx

G = load_or_build_graph()
mgr_coords = (79.15583638463455, 12.969035851408112)
gandhi_coords = (79.16799249061337, 12.972225506107774)

u = get_nearest_node(G, mgr_coords)
v = get_nearest_node(G, gandhi_coords)

jc_edges = []
for u1, v1, k, d in G.edges(keys=True, data=True):
    if d.get('name') == 'Jimmy Carter Road':
        jc_edges.append((d.get('edge_id'), u1, v1, d.get('length_m')))

print(f"Total edges named Jimmy Carter Road: {len(jc_edges)}")
for eid, u1, v1, l in jc_edges:
    # check if removing this single edge disconnects u and v
    G_test = nx.Graph(G)
    G_test.remove_edge(u1, v1)
    connected = nx.has_path(G_test, u, v)
    if not connected:
        print(f"CRITICAL CUT EDGE: {eid} ({u1} <-> {v1}), len={l}m - removing it disconnects MGR from Gandhi!")
    else:
        # What is the new shortest path distance?
        alt_len = nx.shortest_path_length(G_test, u, v, weight='length_m')
        print(f"Edge {eid} ({u1} <-> {v1}, len={l}m): can reroute! New distance = {alt_len:.2f}m")
