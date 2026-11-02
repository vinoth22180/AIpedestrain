import pickle
import networkx as nx
import math

def test_geom_reversal():
    path = "data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl"
    with open(path, "rb") as f:
        G = pickle.load(f)

    # Find a path
    largest_cc = max(nx.weakly_connected_components(G), key=len) if G.is_directed() else max(nx.connected_components(G), key=len)
    nodes = list(largest_cc)
    
    u, v = nodes[0], nodes[-1]
    try:
        path = nx.shortest_path(G, u, v, weight='length_m')
    except nx.NetworkXNoPath:
        print("No path")
        return
        
    needs_reversal = 0
    for i in range(len(path)-1):
        n1, n2 = path[i], path[i+1]
        
        # Check geometry
        d = G.get_edge_data(n1, n2)
        if G.is_multigraph():
            d = d[list(d.keys())[0]]
            
        geom = d.get('geometry')
        if not geom: continue
        
        coords = list(geom.coords)
        n1_lon, n1_lat = G.nodes[n1]['x'], G.nodes[n1]['y']
        
        # Distance from n1 to coords[0]
        dist_to_first = math.hypot(coords[0][0] - n1_lon, coords[0][1] - n1_lat)
        dist_to_last = math.hypot(coords[-1][0] - n1_lon, coords[-1][1] - n1_lat)
        
        if dist_to_last < dist_to_first:
            needs_reversal += 1
            
    print(f"Path has {len(path)-1} edges. {needs_reversal} edges have reversed geometry.")

if __name__ == '__main__':
    test_geom_reversal()
