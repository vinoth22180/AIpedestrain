import pickle
import networkx as nx
import random
import unittest.mock

def test_routing():
    path = "data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl"
    with open(path, "rb") as f:
        G = pickle.load(f)
        
    from src.congestion.manager import congestion_manager
    congestion_manager.reset_congestion()
    
    # We patch get_nearest_node so we can pass node IDs directly
    import src.pada_r.router
    original_get_nearest = src.pada_r.router.get_nearest_node
    
    def mocked_get_nearest(graph, point):
        if isinstance(point, int) or isinstance(point, str):
            return point
        return original_get_nearest(graph, point)
        
    src.pada_r.router.get_nearest_node = mocked_get_nearest

    largest_cc = max(nx.weakly_connected_components(G), key=len) if G.is_directed() else max(nx.connected_components(G), key=len)
    nodes = list(largest_cc)
    
    random.seed(42)
    pairs = [(random.choice(nodes), random.choice(nodes)) for _ in range(5000)]
    
    discrepancies = []
    
    def calc_true_length(path, G):
        length = 0
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            if G.is_multigraph():
                min_l = min(d.get('length_m', 0) for k, d in G.get_edge_data(u, v).items())
                length += min_l
            else:
                length += G[u][v].get('length_m', 0)
        return length

    for u, v in pairs:
        if u == v: continue
        try:
            true_path = nx.shortest_path(G, u, v, weight='length_m')
            true_length = calc_true_length(true_path, G)
        except nx.NetworkXNoPath:
            continue
            
        try:
            res = src.pada_r.router.compute_pada_route(G, u, v, 'general')
            pada_path = res[0]
            if pada_path is None:
                discrepancies.append((u, v, true_length, "PADA RETURNED NONE"))
                continue
                
            pada_length = calc_true_length(pada_path, G)
            if round(pada_length, 2) > round(true_length, 2):
                discrepancies.append((u, v, true_length, pada_length, true_path, pada_path))
                if len(discrepancies) >= 10: break
        except Exception as e:
            pass
            
    print(f"Tested pairs. Found {len(discrepancies)} discrepancies.")
    if discrepancies:
        for d in discrepancies[:5]:
            print(f"Mismatch: u={d[0]}, v={d[1]}, true_len={d[2]}, pada_len={d[3]}")
            if len(d) > 4:
                print(f"True path edges: {len(d[4])}, PADA path edges: {len(d[5])}")
                print(f"True path: {d[4]}")
                print(f"PADA path: {d[5]}")

if __name__ == '__main__':
    test_routing()
