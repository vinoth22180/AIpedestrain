from src.graph_manager import load_or_build_graph
G = load_or_build_graph()

print("Edges at node 4137696585:")
for neighbor in G.neighbors(4137696585):
    for k, d in G[4137696585][neighbor].items():
        print(f"  -> {neighbor} via {d.get('edge_id')}, name='{d.get('name')}', highway={d.get('highway')}, len={d.get('length_m')}m")

print("\nEdges at node 14040595916:")
for neighbor in G.neighbors(14040595916):
    for k, d in G[14040595916][neighbor].items():
        print(f"  -> {neighbor} via {d.get('edge_id')}, name='{d.get('name')}', highway={d.get('highway')}, len={d.get('length_m')}m")
