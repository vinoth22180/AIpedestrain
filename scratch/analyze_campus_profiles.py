import math
from src.graph_manager import load_or_build_graph
from src.pada_r.router import compute_pada_route
from src.congestion.manager import congestion_manager

G = load_or_build_graph()

# Get landmarks
landmarks = []
for n, d in G.nodes(data=True):
    if d.get('short_name'):
        landmarks.append((d['short_name'], (d['x'], d['y']), n))

print(f"Testing {len(landmarks)} landmarks:")
for name, coords, node in landmarks:
    print(f"  - {name}: node {node}, coords {coords}")

# Test all pairs of adjacent / distinct landmarks
pairs = [
    ("MGR", "TT"),
    ("MGR", "SMV"),
    ("SMV", "SJT"),
    ("SJT", "PRP"),
    ("PRP", "CTS"),
    ("Gandhi Block", "Anna Auditorium"),
    ("Parking Lot", "TT")
]

print("\n" + "="*80)
print("COMPARING PROFILE ROUTES ACROSS CAMPUS PAIRS")
print("="*80)

for orig_name, dest_name in pairs:
    orig = next((c for n, c, _ in landmarks if n == orig_name), None)
    dest = next((c for n, c, _ in landmarks if n == dest_name), None)
    if not orig or not dest:
        continue
    
    print(f"\n--- PAIR: {orig_name} -> {dest_name} ---")
    results = {}
    for prof in ["general", "elderly", "pregnant", "wheelchair"]:
        path, edges, status, expl, stats, cands = compute_pada_route(G, orig, dest, prof)
        results[prof] = {
            "found": path is not None,
            "status": status,
            "nodes_count": len(path) if path else 0,
            "dist": stats['distance'] if stats else 0,
            "cost": stats['cost'] if stats else 0,
            "path": path,
            "expl": expl.get('reason', '') if isinstance(expl, dict) else str(expl),
            "max_slope": stats['accessibility_summary']['max_slope_percent'] if stats else None,
            "stairs": stats['accessibility_summary']['stairs_count'] if stats else None
        }
        print(f"  {prof:11s} | Found: {results[prof]['found']} | Nodes: {results[prof]['nodes_count']} | Dist: {results[prof]['dist']:.1f}m | Cost: {results[prof]['cost']:.1f} | Stairs: {results[prof]['stairs']} | MaxSlope: {results[prof]['max_slope']}")
        if not results[prof]['found']:
            print(f"     Reason: {results[prof]['expl']}")

    # Compare paths
    p_gen = results['general']['path']
    for p_name in ['elderly', 'pregnant', 'wheelchair']:
        p_other = results[p_name]['path']
        if p_gen and p_other:
            is_same = (p_gen == p_other)
            print(f"  -> {p_name} matches general exactly? {is_same}")
