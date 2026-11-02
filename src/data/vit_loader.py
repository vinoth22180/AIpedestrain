import os
import geopandas as gpd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
VIT_DIR = os.path.join(DATA_DIR, "vit_vellore")
OSM_EDGES_PATH = os.path.join(VIT_DIR, "pedestrian_paths.geojson")
OSM_NODES_PATH = os.path.join(VIT_DIR, "osm_nodes.geojson")

def load_vit_data():
    if not os.path.exists(OSM_EDGES_PATH) or not os.path.exists(OSM_NODES_PATH):
        raise FileNotFoundError(f"VIT dataset files not found. Please run 'python scripts/build_vit_graph.py' first.")
        
    print("Loading verified VIT Vellore pedestrian dataset...")
    edges = gpd.read_file(OSM_EDGES_PATH)
    nodes = gpd.read_file(OSM_NODES_PATH)
    
    # In NetworkX build graph, we iterate over rows.
    # The edges GeoDataFrame contains all paths.
    return edges, edges, nodes
