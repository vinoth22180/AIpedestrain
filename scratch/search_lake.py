from src.graph_manager import load_or_build_graph
G = load_or_build_graph()

print("Searching edges for lake:")
for u, v, k, d in G.edges(keys=True, data=True):
    name = str(d.get('name', ''))
    hw = str(d.get('highway', ''))
    if 'lake' in name.lower() or 'lake' in hw.lower():
        eid = d.get('edge_id')
        lm = d.get('length_m')
        print(f"Edge {eid}: {name}, ({u}->{v}), len={lm}")

print("Searching nodes for lake:")
for n, d in G.nodes(data=True):
    name = str(d.get('name', ''))
    block = str(d.get('academic_block_id', ''))
    if 'lake' in name.lower() or 'lake' in block.lower():
        print(f"Node {n}: {name}, ({d.get('x')}, {d.get('y')})")
