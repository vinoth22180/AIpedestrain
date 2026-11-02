import os
import json
import uuid
import pandas as pd
import geopandas as gpd
import osmnx as ox
import networkx as nx
from shapely.geometry import Point, LineString

# Config
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data", "vit_vellore")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

# STRICT ACADEMIC BLOCK OVERRIDES
# Only these are considered academic blocks.
OVERRIDES = {
    "Technology Tower": {"short_name": "TT"},
    "Silver Jubilee Tower": {"short_name": "SJT"},
    "Dr. M.G.R": {"short_name": "MB", "aliases": ["Main Block", "Dr. M.G.R. Block", "Main Building"]},
    "G.D. Naidu": {"short_name": "GDN", "aliases": ["G D Naidu", "G.D Naidu"]},
    "Sri M. Visvesvaraya": {"short_name": "SMV", "aliases": ["SMV Block", "Sri. M. Vishweshwaraiah", "Sir M Visvesvaraya"]},
    "Gandhi Block": {"short_name": "GB"},
    "CBMR": {"short_name": "CBMR", "aliases": ["Pre-Clinical Research Laboratory"]},
    "CTS": {"short_name": "CTS"},
    "PEARL": {"short_name": "PEARL", "aliases": ["PRP", "Perl Research Park"]},
    "CDMM": {"short_name": "CDMM"}
}

def match_academic_block(name):
    if not pd.notna(name):
        return None, None
    name_str = str(name).lower()
    for off_name, data in OVERRIDES.items():
        if off_name.lower() in name_str:
            return off_name, data
        for alias in data.get("aliases", []):
            if alias.lower() in name_str:
                return off_name, data
    return None, None

def fetch_boundary():
    print("Fetching VIT Vellore boundary...")
    gdf = ox.geocode_to_gdf('R15931944', by_osmid=True)
    poly = gdf.geometry.iloc[0]
    gdf.to_file(os.path.join(PROCESSED_DIR, "campus_boundary.geojson"), driver="GeoJSON")
    return poly

def process_academic_blocks(poly):
    print("Fetching academic blocks...")
    tags = {'building': True, 'amenity': 'university'} # amenity=university sometimes used for blocks
    features = ox.features_from_polygon(poly, tags=tags)
    
    academic_blocks = []
    
    for idx, row in features.iterrows():
        geom = row.geometry
        if geom.is_empty: continue
        
        name = row.get('name', None)
        if not pd.notna(name):
            continue
            
        canonical_name, override_data = match_academic_block(name)
        if canonical_name is None:
            continue # STRICT FILTER: Discard if not verified academic block
            
        block_obj = {
            "building_id": f"AB_{uuid.uuid4().hex[:8]}",
            "name": canonical_name,
            "short_name": override_data['short_name'],
            "type": "academic_block",
            "latitude": geom.centroid.y,
            "longitude": geom.centroid.x,
            "geometry": geom,
            "source": "OSM/Overrides",
            "confidence": "high"
        }
        academic_blocks.append(block_obj)
            
    return gpd.GeoDataFrame(academic_blocks, crs="EPSG:4326" if academic_blocks else None)

def build_graph(poly, academic_blocks_gdf):
    print("Building pedestrian graph...")
    useful_tags_way = list(set(ox.settings.useful_tags_way + ['surface', 'smoothness', 'incline', 'wheelchair', 'tactile_paving', 'steps', 'highway']))
    ox.settings.useful_tags_way = useful_tags_way
    
    G = ox.graph_from_polygon(poly, network_type='walk', simplify=True)
    G = G.to_undirected()
    
    # Identify entrance nodes for academic blocks.
    entrance_nodes = set()
    import math
    for idx, row in academic_blocks_gdf.iterrows():
        min_dist = float('inf')
        best_n = None
        lat, lon = row['latitude'], row['longitude']
        for n, data in G.nodes(data=True):
            dist = math.hypot(data['x'] - lon, data['y'] - lat)
            if dist < min_dist:
                min_dist = dist
                best_n = n
        if best_n is not None:
            entrance_nodes.add(best_n)
            G.nodes[best_n]['node_type'] = 'building_entrance'
            G.nodes[best_n]['academic_block_id'] = row['building_id']
            G.nodes[best_n]['name'] = f"Entrance to {row['short_name']}"

    # Prune dead-ends that are NOT entrances to retain only the functional routing core between blocks
    while True:
        dead_ends = [n for n, d in G.degree() if d == 1 and n not in entrance_nodes]
        if not dead_ends:
            break
        G.remove_nodes_from(dead_ends)
        
    # Also, we can optionally keep only the largest connected component to ensure connectivity.
    if len(G.nodes) > 0:
        largest_cc = max(nx.connected_components(G), key=len)
        G = G.subgraph(largest_cc).copy()

    # Process edges
    edge_features = []
    stairs = []
    ramps = []
    crossings = []
    
    for u, v, k, data in G.edges(keys=True, data=True):
        hw = data.get('highway', '')
        if isinstance(hw, list): hw = hw[0]
        
        path_type = 'pedestrian_path'
        is_stairs = False
        is_ramp = False
        is_crossing = False
        
        if hw == 'steps' or data.get('steps') == 'yes':
            path_type = 'stairs'
            is_stairs = True
        elif 'crossing' in str(hw):
            path_type = 'crossing'
            is_crossing = True
        elif hw == 'footway':
            path_type = 'footway'
        elif hw == 'pedestrian':
            path_type = 'pedestrian_path'
        elif hw == 'service':
            path_type = 'internal_road'
        
        if data.get('wheelchair') == 'yes' and not is_stairs:
            if data.get('incline') in ['up', 'down'] or data.get('ramp') == 'yes':
                path_type = 'ramp'
                is_ramp = True

        name = data.get('name', None)
        if isinstance(name, list): name = name[0]
        
        edge_id = f"E_{u}_{v}"
        
        edge_obj = {
            "edge_id": edge_id,
            "u": u,
            "v": v,
            "path_type": path_type,
            "name": name if pd.notna(name) else f"Internal_Path_{edge_id[:8]}", # Internal naming
            "length_m": data.get('length', 0),
            "surface": data.get('surface', 'unknown'),
            "width_m": data.get('width', None),
            "lit": data.get('lit', 'unknown'),
            "accessible": False if is_stairs else (True if data.get('wheelchair') == 'yes' else 'unknown'),
            "slope_percent": None, # Never invent
            "slope_status": "unknown",
            "stairs": is_stairs,
            "ramp": is_ramp,
            "crossing": is_crossing,
            "restricted": False,
            "confidence": "high" if pd.notna(name) else "medium",
            "source": "OSM"
        }
        
        if 'geometry' in data:
            edge_obj['geometry'] = data['geometry']
        else:
            pt_u = Point(G.nodes[u]['x'], G.nodes[u]['y'])
            pt_v = Point(G.nodes[v]['x'], G.nodes[v]['y'])
            edge_obj['geometry'] = LineString([pt_u, pt_v])
            
        edge_features.append(edge_obj)
        
        if is_stairs: stairs.append(edge_obj)
        if is_ramp: ramps.append(edge_obj)
        if is_crossing: crossings.append(edge_obj)
        
        for key, val in edge_obj.items():
            if key != 'geometry':
                G[u][v][k][key] = val

    # Process nodes
    node_features = []
    for n, data in G.nodes(data=True):
        node_type = data.get('node_type', "junction")
        if data.get('highway') == 'crossing' and node_type != 'building_entrance':
            node_type = "crossing"
        
        node_obj = {
            "node_id": n,
            "latitude": data['y'],
            "longitude": data['x'],
            "node_type": node_type,
            "name": data.get('name', f"Node_{n}"),
            "academic_block_id": data.get('academic_block_id', None),
            "accessible": 'unknown',
            "source": "OSM",
            "confidence": "medium",
            "geometry": Point(data['x'], data['y'])
        }
        node_features.append(node_obj)
        for key, val in node_obj.items():
            if key != 'geometry':
                G.nodes[n][key] = val

    return G, gpd.GeoDataFrame(node_features, crs="EPSG:4326" if node_features else None), gpd.GeoDataFrame(edge_features, crs="EPSG:4326" if edge_features else None), gpd.GeoDataFrame(stairs, crs="EPSG:4326" if stairs else None), gpd.GeoDataFrame(ramps, crs="EPSG:4326" if ramps else None), gpd.GeoDataFrame(crossings, crs="EPSG:4326" if crossings else None)

def main():
    poly = fetch_boundary()
    ab_gdf = process_academic_blocks(poly)
    
    G, nodes_gdf, edges_gdf, stairs_gdf, ramps_gdf, crossings_gdf = build_graph(poly, ab_gdf)
    
    # Save files
    if not ab_gdf.empty: 
        ab_gdf.to_file(os.path.join(PROCESSED_DIR, "academic_blocks.geojson"), driver="GeoJSON")
        # Keep buildings.geojson identical to academic_blocks to prevent breaking the app, as requested.
        ab_gdf.to_file(os.path.join(PROCESSED_DIR, "buildings.geojson"), driver="GeoJSON")
        
    if not nodes_gdf.empty: nodes_gdf.to_file(os.path.join(PROCESSED_DIR, "pedestrian_nodes.geojson"), driver="GeoJSON")
    if not edges_gdf.empty: edges_gdf.to_file(os.path.join(PROCESSED_DIR, "pedestrian_edges.geojson"), driver="GeoJSON")
    
    if not stairs_gdf.empty: stairs_gdf.to_file(os.path.join(PROCESSED_DIR, "stairs.geojson"), driver="GeoJSON")
    if not ramps_gdf.empty: ramps_gdf.to_file(os.path.join(PROCESSED_DIR, "ramps.geojson"), driver="GeoJSON")
    if not crossings_gdf.empty: crossings_gdf.to_file(os.path.join(PROCESSED_DIR, "crossings.geojson"), driver="GeoJSON")
    
    # Remove geometry from Graph before saving to graphml
    G_save = G.copy()
    for u, v, k, d in G_save.edges(keys=True, data=True):
        if 'geometry' in d:
            del d['geometry']
        for key, val in list(d.items()):
            if val is None:
                d[key] = ""
            elif type(val) not in [int, float, str, bool]:
                d[key] = str(val)
                
    for n, d in G_save.nodes(data=True):
        if 'geometry' in d:
            del d['geometry']
        for key, val in list(d.items()):
            if val is None:
                d[key] = ""
            elif type(val) not in [int, float, str, bool]:
                d[key] = str(val)
            
    nx.write_graphml(G_save, os.path.join(PROCESSED_DIR, "vit_vellore_academic_pedestrian_network.graphml"))
    
    import pickle
    with open(os.path.join(PROCESSED_DIR, "vit_vellore_academic_pedestrian_network.pkl"), 'wb') as f:
        pickle.dump(G, f)
        
    print("Academic Dataset built successfully.")

if __name__ == "__main__":
    main()
