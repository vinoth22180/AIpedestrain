import os
import sys
import pickle
import pandas as pd
import numpy as np

project_root = os.path.abspath(os.path.dirname(__file__))

# 1. Active Dataset Identification
csv_path = os.path.join(project_root, "data", "vit_vellore", "raw", "friend_base_pedestrian_network.csv")
pkl_path = os.path.join(project_root, "data", "vit_vellore", "processed", "vit_vellore_academic_pedestrian_network.pkl")

print("=== RAW CSV ANALYSIS ===")
df = pd.read_csv(csv_path)
print(f"Total records: {len(df)}")
for col in df.columns:
    unique_vals = df[col].nunique()
    missing = df[col].isnull().sum()
    pct_missing = (missing / len(df)) * 100
    dtype = df[col].dtype
    print(f"Col: {col} | Type: {dtype} | Unique: {unique_vals} | Missing: {missing} ({pct_missing:.2f}%)")
    if unique_vals < 15:
        print(f"  Values: {df[col].dropna().unique().tolist()}")

print("\n=== PKL GRAPH ANALYSIS ===")
with open(pkl_path, 'rb') as f:
    G = pickle.load(f)

print(f"Total Nodes: {len(G.nodes)}")
print(f"Total Edges: {len(G.edges)}")
import networkx as nx
components = list(nx.connected_components(G))
print(f"Connected Components: {len(components)}")
print(f"Largest Component: {len(components[0])} nodes")
isolated = sum(1 for n in G.nodes if G.degree(n) == 0)
print(f"Isolated Nodes: {isolated}")

# Edge attributes stats
attr_stats = {
    'geometry_source': {},
    'highway': {},
    'surface': {},
    'stairs': {},
    'ramp': {},
    'wheelchair': {},
    'crossing': {},
    'barrier': {}
}

slopes_total = 0
slopes_missing = 0

for u, v, k, d in G.edges(data=True, keys=True):
    for attr in attr_stats.keys():
        val = d.get(attr)
        attr_stats[attr][val] = attr_stats[attr].get(val, 0) + 1
        
    if "slope_percent" not in d or d["slope_percent"] is None:
        slopes_missing += 1
    else:
        slopes_total += 1

for attr, stats in attr_stats.items():
    print(f"\nAttribute: {attr}")
    for k, v in stats.items():
        print(f"  {k}: {v}")

print(f"\nSlopes Missing/None: {slopes_missing}/{len(G.edges)}")
print(f"Slopes Present: {slopes_total}/{len(G.edges)}")

