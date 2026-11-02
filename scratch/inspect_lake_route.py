from src.graph_manager import load_or_build_graph
from src.routing import get_nearest_node
import networkx as nx

G = load_or_build_graph()
mgr_coords = (79.15583638463455, 12.969035851408112)
gandhi_coords = (79.16799249061337, 12.972225506107774)

u = get_nearest_node(G, mgr_coords)
v = get_nearest_node(G, gandhi_coords)

# Remove the whole SJT corridor:
# Nodes around SJT: 4137696585, 4137696586, 14040595918, 1035547458
G_test = nx.Graph(G)
# remove edge E000084
G_test.remove_edge(4137696585, 4137696586)
# When E000084 is removed, the reroute was 1554.54m. What edges did that take?
p_1554 = nx.shortest_path(G_test, u, v, weight='length_m')
print("Edges on 1554m reroute around E000084:")
eids_1554 = []
for i in range(len(p_1554)-1):
    u1, v1 = p_1554[i], p_1554[i+1]
    d = G[u1][v1][list(G[u1][v1].keys())[0]]
    eids_1554.append(d.get('edge_id'))
print("1554m path edge IDs:", eids_1554[30:45])

# Now what if the entire Jimmy Carter Road section through SJT is blocked?
# Let's remove all of E000081 through E000092
G_lake = nx.Graph(G)
for u1, v1, k, d in G.edges(keys=True, data=True):
    eid = d.get('edge_id')
    if eid in ['E000081', 'E000082', 'E000083', 'E000084', 'E000085', 'E000086', 'E000087', 'E000088', 'E000089', 'E000090', 'E000091', 'E000092']:
        if G_lake.has_edge(u1, v1):
            G_lake.remove_edge(u1, v1)

if nx.has_path(G_lake, u, v):
    p_lake = nx.shortest_path(G_lake, u, v, weight='length_m')
    dist_lake = nx.shortest_path_length(G_lake, u, v, weight='length_m')
    print(f"Lake-side route exists! Dist: {dist_lake:.2f}m, nodes: {len(p_lake)}")
    eids_lake = [G[p_lake[i]][p_lake[i+1]][list(G[p_lake[i]][p_lake[i+1]].keys())[0]].get('edge_id') for i in range(len(p_lake)-1)]
    names_lake = [G[p_lake[i]][p_lake[i+1]][list(G[p_lake[i]][p_lake[i+1]].keys())[0]].get('name') for i in range(len(p_lake)-1)]
    print(f"Roads on lake route: {set(filter(None, names_lake))}")
    print(f"Lake path edge IDs: {eids_lake}")
else:
    print("No path when Jimmy Carter corridor is blocked!")
