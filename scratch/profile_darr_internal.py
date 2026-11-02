import sys
sys.path.insert(0, '.')
import time
import json
import networkx as nx

from src.graph_manager import load_or_build_graph
from src.darr.subgraph import subgraph_manager
from src.darr.resilience import resilience_engine
from src.darr.config import get_profile_config
from src.signal_decay.engine import decay_engine

G = load_or_build_graph()
locs = json.load(open('data/vit_vellore/processed/vit_manual_locations.json'))['locations']
source = locs[0]['anchor_node']
destination = locs[3]['anchor_node']
profile = "wheelchair"
G_sub = subgraph_manager.get_accessible_subgraph(G, profile)

print("Starting granular DARR profiling...")

# 1. Route 1 (Fastest)
t0 = time.perf_counter()
def weight_fastest(u, v, data):
    if G_sub.is_multigraph():
        return min(d.get('length_m', d.get('length', 1.0)) for d in data.values())
    return data.get('length_m', data.get('length', 1.0))

p1 = nx.shortest_path(G_sub, source=source, target=destination, weight=weight_fastest)
t_p1 = (time.perf_counter() - t0) * 1000
print(f"p1 (fastest Dijkstra): {t_p1:.2f} ms, length={len(p1)}")

# 2. Route 2 (Congestion)
t0 = time.perf_counter()
def weight_low_congestion(u, v, data):
    decay_pen = decay_engine.get_penalty(u, v)
    w_base = min(d.get('length_m', d.get('length', 1.0)) for d in data.values()) if G_sub.is_multigraph() else data.get('length_m', 1.0)
    return w_base + (2.0 * decay_pen)

p2 = nx.shortest_path(G_sub, source=source, target=destination, weight=weight_low_congestion)
t_p2 = (time.perf_counter() - t0) * 1000
print(f"p2 (congestion Dijkstra): {t_p2:.2f} ms, length={len(p2)}")

# 3. Route 3 (Resilience) - UNCACHED CAD
t0 = time.perf_counter()
cad_call_count = [0]
def weight_resilience_uncached(u, v, data):
    cad_call_count[0] += 1
    cad = resilience_engine.calculate_cad_for_edge(G, u, v, "wheelchair")
    decay_pen = decay_engine.get_penalty(u, v)
    w_base = min(d.get('length_m', d.get('length', 1.0)) for d in data.values()) if G_sub.is_multigraph() else data.get('length_m', 1.0)
    return w_base + (cad * 60.0) + (1.5 * decay_pen)

p3 = nx.shortest_path(G_sub, source=source, target=destination, weight=weight_resilience_uncached)
t_p3_uncached = (time.perf_counter() - t0) * 1000
print(f"p3 UNCACHED CAD Dijkstra: {t_p3_uncached:.2f} ms (CAD calls={cad_call_count[0]})")

# 4. Route 3 (Resilience) - PRECOMPUTED/CACHED CAD
t0 = time.perf_counter()
bridges = resilience_engine._get_bridges(G_sub)
cad_cache = {}
for u, v in G_sub.edges():
    if (u, v) not in cad_cache:
        c = resilience_engine.calculate_cad_for_edge(G, u, v, "wheelchair", bridge_cache=bridges)
        cad_cache[(u, v)] = c
        cad_cache[(v, u)] = c
t_cad_precompute = (time.perf_counter() - t0) * 1000
print(f"CAD precompute all edges of G_sub: {t_cad_precompute:.2f} ms (total edges={len(cad_cache)})")

t0 = time.perf_counter()
def weight_resilience_cached(u, v, data):
    cad = cad_cache.get((u, v), 0.1)
    decay_pen = decay_engine.get_penalty(u, v)
    w_base = min(d.get('length_m', d.get('length', 1.0)) for d in data.values()) if G_sub.is_multigraph() else data.get('length_m', 1.0)
    return w_base + (cad * 60.0) + (1.5 * decay_pen)

p3_cached = nx.shortest_path(G_sub, source=source, target=destination, weight=weight_resilience_cached)
t_p3_cached = (time.perf_counter() - t0) * 1000
print(f"p3 CACHED CAD Dijkstra: {t_p3_cached:.2f} ms")
print(f"SPEEDUP FOR P3: {t_p3_uncached / t_p3_cached:.1f}x faster!")
