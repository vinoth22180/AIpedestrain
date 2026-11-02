from src.graph_manager import load_or_build_graph
from src.pada_r.router import compute_pada_route
from src.congestion.manager import congestion_manager
from src.congestion.config import CongestionConfig

G = load_or_build_graph()

landmarks = {d.get('short_name'): (n, (d['x'], d['y'])) for n, d in G.nodes(data=True) if d.get('short_name')}

pairs = [
    ("MGR", "TT"),
    ("MGR", "SMV"),
    ("SMV", "SJT"),
    ("Gandhi Block", "Anna Auditorium")
]

print("="*80)
print("TESTING CONGESTION REROUTING ON REAL CAMPUS GRAPH")
print("="*80)

for orig_name, dest_name in pairs:
    orig_node, orig_coords = landmarks[orig_name]
    dest_node, dest_coords = landmarks[dest_name]
    print(f"\n>>> PAIR: {orig_name} -> {dest_name} <<<")
    
    # 1. Base route
    congestion_manager.reset_congestion()
    t0 = 1000.0
    p_base, edges_base, status_base, expl_base, stats_base, cands_base = compute_pada_route(G, orig_coords, dest_coords, "general", now=t0)
    print(f"Base route (general): {len(p_base)} nodes, {stats_base['distance']:.1f}m")
    
    # Pick a critical edge along the route (e.g. edge 2 or 3)
    if len(p_base) > 3:
        target_idx = 2
        u, v = p_base[target_idx], p_base[target_idx+1]
        edge_data = G.get_edge_data(u, v)
        edge_key = list(edge_data.keys())[0] if isinstance(edge_data, dict) else 0
        attrs = edge_data[edge_key] if isinstance(edge_data, dict) else edge_data
        edge_id = attrs.get('edge_id', f"edge:{u}:{v}:{edge_key}")
        
        print(f"Applying HIGH congestion (0.85) to route edge {target_idx}: ({u}, {v}) [id: {edge_id}]")
        job = congestion_manager.create_job(edge_id)
        congestion_manager.update_job(job, {"congestion_score": 0.85, "timestamp": t0})
        
        # Test General
        p_gen, e_gen, s_gen, x_gen, st_gen, c_gen = compute_pada_route(G, orig_coords, dest_coords, "general", now=t0)
        edge_in_gen = (u, v) in zip(p_gen[:-1], p_gen[1:]) if p_gen else False
        print(f"General: avoids edge? {not edge_in_gen} | Nodes: {len(p_gen)} | Dist: {st_gen['distance']:.1f}m (vs {stats_base['distance']:.1f}m) | Status: {s_gen}")
        print(f"   Reason: {x_gen.get('reason')}")
        print(f"   Candidates count: {len(c_gen)}")
        for c in c_gen:
            print(f"     - Candidate: {c['route_id']} ({c['category']}): {c['distance']:.1f}m, cong: {c['congestion_level']}")
        
        # Now test with location name instead of edge_id
        congestion_manager.reset_congestion()
        print(f"\nApplying HIGH congestion (0.85) to Landmark '{orig_name}'...")
        job2 = congestion_manager.create_job(orig_name)
        congestion_manager.update_job(job2, {"congestion_score": 0.85, "timestamp": t0})
        p_land, e_land, s_land, x_land, st_land, c_land = compute_pada_route(G, orig_coords, dest_coords, "general", now=t0)
        print(f"General with Landmark congestion: Nodes: {len(p_land)} | Dist: {st_land['distance']:.1f}m | Status: {s_land}")
        print(f"   Reason: {x_land.get('reason')}")
        print(f"   Candidates count: {len(c_land)}")
        for c in c_land:
            print(f"     - Candidate: {c['route_id']} ({c['category']}): {c['distance']:.1f}m, cong: {c['congestion_level']}")
