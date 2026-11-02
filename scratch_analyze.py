import networkx as nx
import pickle

def analyze_more():
    path = "data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl"
    with open(path, "rb") as f:
        G = pickle.load(f)

    # Node coordinates
    xs = [d.get('x') for n, d in G.nodes(data=True) if 'x' in d]
    ys = [d.get('y') for n, d in G.nodes(data=True) if 'y' in d]
    if xs and ys:
        print(f"X range: {min(xs)} to {max(xs)}")
        print(f"Y range: {min(ys)} to {max(ys)}")

    # Edge metrics
    stairs_count = sum(1 for u, v, k, d in G.edges(keys=True, data=True) if d.get('stairs') == True)
    slope_unknown = sum(1 for u, v, k, d in G.edges(keys=True, data=True) if d.get('slope_percent') is None or d.get('slope_percent') == 'unknown' or d.get('slope_status') == 'unknown')
    slope_known = [d.get('slope_percent') for u, v, k, d in G.edges(keys=True, data=True) if isinstance(d.get('slope_percent'), (int, float))]
    
    wheelchair_vals = {}
    for u, v, k, d in G.edges(keys=True, data=True):
        wc = str(d.get('wheelchair'))
        wheelchair_vals[wc] = wheelchair_vals.get(wc, 0) + 1

    barriers_vals = {}
    for u, v, k, d in G.edges(keys=True, data=True):
        b = str(d.get('barrier'))
        barriers_vals[b] = barriers_vals.get(b, 0) + 1

    length_diffs = []
    for u, v, k, d in G.edges(keys=True, data=True):
        lm = d.get('length_m')
        gm = d.get('geometry_distance_m')
        if isinstance(lm, (int, float)) and isinstance(gm, (int, float)):
            length_diffs.append(abs(lm - gm))

    print(f"Stairs True: {stairs_count}, False: {G.number_of_edges() - stairs_count}")
    print(f"Wheelchair values: {wheelchair_vals}")
    print(f"Barrier values: {barriers_vals}")
    print(f"Slope percent known: {len(slope_known)}, unknown/missing: {G.number_of_edges() - len(slope_known)}")
    if slope_known:
        print(f"Slope min: {min(slope_known)}, max: {max(slope_known)}, avg: {sum(slope_known)/len(slope_known)}")
    
    if length_diffs:
        print(f"Max difference between length_m and geometry_distance_m: {max(length_diffs)}")

if __name__ == '__main__':
    analyze_more()
