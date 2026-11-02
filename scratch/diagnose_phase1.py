import json
from src.graph_manager import load_or_build_graph
from src.pada_r.router import compute_pada_route
from src.congestion.manager import congestion_manager
from src.congestion.config import CongestionConfig

G = load_or_build_graph()
print(f"Total nodes: {len(G.nodes)}, Total edges: {len(G.edges)}")

names = {d.get('short_name'): (n, d) for n, d in G.nodes(data=True) if d.get('short_name')}
print("Locations with short_name:", list(names.keys()))

orig_node, orig_data = names.get('MGR', list(names.values())[0])
dest_node, dest_data = names.get('TT', list(names.values())[1])
orig_coords = (orig_data['x'], orig_data['y'])
dest_coords = (dest_data['x'], dest_data['y'])

print(f"\n--- TEST 1-4: NO CONGESTION ROUTING ---")
print(f"Route: {orig_data.get('short_name', orig_node)} -> {dest_data.get('short_name', dest_node)}")

routes = {}
for prof in ['general', 'elderly', 'pregnant', 'wheelchair']:
    path, edges, status, expl, stats, cands = compute_pada_route(G, orig_coords, dest_coords, prof)
    routes[prof] = (path, edges, status, stats)
    dist = stats.get('distance', 0) if stats else 0
    cost = stats.get('cost', 0) if stats else 0
    print(f"Profile {prof:11s} -> Found: {path is not None} | Status: {status} | Nodes: {len(path) if path else 0} | Dist: {dist:.1f}m | Cost: {cost:.1f}")
    if path:
        print(f"   First 5 nodes: {path[:5]}")
    else:
        print(f"   Explanation: {expl}")

# Check if paths are identical
gen_p = routes['general'][0]
for prof in ['elderly', 'pregnant', 'wheelchair']:
    p = routes[prof][0]
    if p is not None and gen_p is not None:
        print(f"Is {prof} path == general path? {p == gen_p}")

print("\n--- TEST 5: HIGH CONGESTION ON ORIGINAL ROUTE EDGE ---")
if gen_p and len(gen_p) >= 2:
    # Pick first edge
    u, v = gen_p[0], gen_p[1]
    # Edge identifier
    edge_data = G.get_edge_data(u, v)
    edge_key = list(edge_data.keys())[0] if isinstance(edge_data, dict) else 0
    edge_attrs = edge_data[edge_key] if isinstance(edge_data, dict) else edge_data
    edge_id = edge_attrs.get('edge_id', f"edge:{u}:{v}:{edge_key}")
    print(f"Injecting HIGH congestion (0.85) on edge: ({u}, {v}) -> {edge_id}")
    
    t0 = 1000.0
    job_id = congestion_manager.create_job(edge_id)
    congestion_manager.update_job(job_id, {"congestion_score": 0.85, "timestamp": t0})
    
    for prof in ['general', 'elderly', 'pregnant', 'wheelchair']:
        path, edges, status, expl, stats, cands = compute_pada_route(G, orig_coords, dest_coords, prof, now=t0)
        dist = stats.get('distance', 0) if stats else 0
        diff_from_orig = (path != gen_p) if path else "N/A"
        print(f"Profile {prof:11s} -> Diff from orig? {diff_from_orig} | Found: {path is not None} | Dist: {dist:.1f}m | Status: {status}")
        if path and (u, v) in zip(path[:-1], path[1:]):
            print(f"   WARNING: Profile {prof} STILL uses congested edge ({u}, {v})!")
        elif path:
            print(f"   SUCCESS: Avoided congested edge! First 5 nodes: {path[:5]}")

print("\n--- TEST 6: CONGESTION DECAYS HIGH -> MEDIUM -> LOW ---")
if gen_p and len(gen_p) >= 2:
    t_med = t0 + 1.5 * CongestionConfig.DECAY_HALF_LIFE_SECONDS
    print(f"At t_med (1.5 half lives), effective score on {edge_id}:")
    eff_med = congestion_manager.get_effective_congestion(edge_id, now=t_med)
    print(f"   Effective score: {eff_med.effective_score:.3f}, level: {eff_med.effective_level}")
    for prof in ['general', 'elderly']:
        path, edges, status, expl, stats, cands = compute_pada_route(G, orig_coords, dest_coords, prof, now=t_med)
        uses_edge = (u, v) in zip(path[:-1], path[1:]) if path else False
        print(f"   {prof} at MEDIUM -> Uses congested edge? {uses_edge} | Path len: {len(path) if path else 0}")

    t_low = t0 + 3.0 * CongestionConfig.DECAY_HALF_LIFE_SECONDS
    eff_low = congestion_manager.get_effective_congestion(edge_id, now=t_low)
    print(f"At t_low (3.0 half lives), effective score: {eff_low.effective_score:.3f}, level: {eff_low.effective_level}")
    for prof in ['general', 'elderly']:
        path, edges, status, expl, stats, cands = compute_pada_route(G, orig_coords, dest_coords, prof, now=t_low)
        uses_edge = (u, v) in zip(path[:-1], path[1:]) if path else False
        print(f"   {prof} at LOW -> Uses congested edge? {uses_edge} | Path len: {len(path) if path else 0}")
