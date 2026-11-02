import os
import sys
import pickle

project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

graph_path = os.path.join(project_root, "data", "vit_vellore", "processed", "vit_vellore_academic_pedestrian_network.pkl")
with open(graph_path, 'rb') as f:
    G_base = pickle.load(f)

for u, v, k, d in G_base.edges(data=True, keys=True):
    print(d)
    break
