from src.graph_manager import load_or_build_graph
import math

G = load_or_build_graph()
target_lon, target_lat = 79.1632, 12.9717

def haversine(lon1, lat1, lon2, lat2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

nearby = []
for u, v, k, d in G.edges(keys=True, data=True):
    u_pt = (G.nodes[u]['x'], G.nodes[u]['y'])
    v_pt = (G.nodes[v]['x'], G.nodes[v]['y'])
    mid = ((u_pt[0] + v_pt[0])/2, (u_pt[1] + v_pt[1])/2)
    dist = haversine(target_lon, target_lat, mid[0], mid[1])
    if dist < 50:
        nearby.append((dist, d.get('edge_id'), k, u, v, d.get('name'), d.get('highway'), d.get('length_m'), d.get('way_id')))

nearby.sort()
print(f"Total edges within 50m: {len(nearby)}")
for n in nearby:
    print(f"{n[1]} (key={n[2]}): dist={n[0]:.1f}m, length={n[7]}m, way_id={n[8]}, name='{n[5]}', nodes=({n[3]} -> {n[4]})")
