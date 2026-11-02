import os
import json
import math
import uuid
import pickle
import pandas as pd
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point, LineString, Polygon
import osmnx as ox

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data", "vit_vellore")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")

CSV_PATH = os.path.join(RAW_DIR, "friend_base_pedestrian_network.csv")

OVERRIDES = {
    "Technology Tower": {"short_name": "TT"},
    "Silver Jubilee Tower": {"short_name": "SJT"},
    "Dr. M.G.R": {"short_name": "MB", "aliases": ["Main Block", "Dr. M.G.R. Block", "Main Building"]},
    "G.D. Naidu": {"short_name": "GDN", "aliases": ["G D Naidu", "G.D Naidu"]},
    "Sri M. Visvesvaraya": {"short_name": "SMV", "aliases": ["SMV Block", "Sri. M. Vishweshwaraiah", "Sir M Visvesvaraya Block"]},
    "Gandhi Block": {"short_name": "GB"},
    "CBMR": {"short_name": "CBMR", "aliases": ["Pre-Clinical Research Laboratory"]},
    "CTS": {"short_name": "CTS"},
    "PEARL": {"short_name": "PEARL", "aliases": ["PRP", "Perl Research Park"]},
    "CDMM": {"short_name": "CDMM"}
}

def setup_directories():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

def match_academic_block(name):
    if not name:
        return None
    name_str = str(name).lower()
    for k, v in OVERRIDES.items():
        if k.lower() in name_str:
            return v
        for alias in v.get("aliases", []):
            if alias.lower() in name_str:
                return v
    return None

def main():
    setup_directories()
    
    campus_gdf = ox.geocode_to_gdf('R15931944', by_osmid=True)
    campus_poly = campus_gdf.geometry.iloc[0]
    campus_gdf.to_file(os.path.join(PROCESSED_DIR, "campus_boundary.geojson"), driver="GeoJSON")
    node_coords = {}
    way_nodes = {}
    
    print("Loading nodes from local map.osm...")
    map_osm_path = os.path.join(DATA_DIR, "map.osm")
    if os.path.exists(map_osm_path):
        import xml.etree.ElementTree as ET
        tree = ET.parse(map_osm_path)
        root = tree.getroot()
        for node in root.findall('node'):
            node_coords[int(node.get('id'))] = {
                'lat': float(node.get('lat')),
                'lon': float(node.get('lon'))
            }
        for way in root.findall('way'):
            wn = [int(nd.get('ref')) for nd in way.findall('nd')]
            way_nodes[int(way.get('id'))] = wn
            
        print(f"Loaded {len(node_coords)} nodes and {len(way_nodes)} ways from map.osm.")

    print("Fetching live OSM nodes and ways for the campus via Overpass API to supplement missing ones...")
    import requests
    minx, miny, maxx, maxy = campus_poly.bounds
    
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:90][bbox:{miny},{minx},{maxy},{maxx}];
    (
      way["highway"];
      node(w);
    );
    out body;
    """
    try:
        response = requests.post(overpass_url, data={'data': query}, timeout=90)
        if response.status_code == 200:
            data = response.json()
            new_nodes = 0
            for element in data.get("elements", []):
                if element["type"] == "node":
                    nid = element["id"]
                    if nid not in node_coords:
                        node_coords[nid] = {"lat": element["lat"], "lon": element["lon"]}
                        new_nodes += 1
                elif element["type"] == "way":
                    wid = element["id"]
                    if wid not in way_nodes:
                        way_nodes[wid] = element.get("nodes", [])
            print(f"Supplemented with {new_nodes} new nodes from live OSM.")
        else:
            print("Failed to fetch live OSM data.")
    except Exception as e:
        print(f"Overpass request failed: {e}")
        
    print("Parsing Base CSV...")
    df = pd.read_csv(CSV_PATH)
    
    print("Fetching Academic Blocks...")
    tags = {'building': True, 'amenity': 'university'}
    buildings = ox.features_from_polygon(campus_poly, tags=tags)
    
    academic_blocks = []
    for idx, row in buildings.iterrows():
        name = row.get('name')
        override_data = match_academic_block(name)
        if override_data:
            geom = row.geometry
            if geom.geom_type == 'Polygon' or geom.geom_type == 'MultiPolygon':
                canonical_name = [k for k, v in OVERRIDES.items() if v == override_data][0]
                ab_obj = {
                    "building_id": f"AB_{uuid.uuid4().hex[:8]}",
                    "name": canonical_name,
                    "short_name": override_data["short_name"],
                    "type": "academic_block",
                    "latitude": geom.centroid.y,
                    "longitude": geom.centroid.x,
                    "geometry": geom,
                    "source": "OSM",
                    "confidence": "high"
                }
                academic_blocks.append(ab_obj)
                
    academic_blocks_gdf = gpd.GeoDataFrame(academic_blocks, geometry='geometry', crs="EPSG:4326")
    academic_blocks_gdf.to_file(os.path.join(PROCESSED_DIR, "academic_blocks.geojson"), driver="GeoJSON")
    print(f"Verified {len(academic_blocks_gdf)} Academic Blocks.")
    
    print("Building Core Pedestrian Routing Graph...")
    G = nx.MultiGraph()
    
    missing_nodes = 0
    missing_geometry = 0
    
    for _, row in df.iterrows():
        u = row['from_node']
        v = row['to_node']
        
        # 1. Resolve coordinates
        if u not in node_coords or v not in node_coords:
            missing_nodes += 1
            continue
            
        u_data = node_coords[u]
        v_data = node_coords[v]
        
        # Ensure nodes are added
        if u not in G:
            G.add_node(u, x=u_data['lon'], y=u_data['lat'], latitude=u_data['lat'], longitude=u_data['lon'], node_type="junction")
        if v not in G:
            G.add_node(v, x=v_data['lon'], y=v_data['lat'], latitude=v_data['lat'], longitude=v_data['lon'], node_type="junction")
            
        # 2. Filter Motor Roads
        highway = row['highway']
        if pd.isna(highway):
            highway = 'unknown'
            
        is_crossing = row['crossing'] == 'marked' or row['crossing'] == 'uncontrolled' or (pd.notna(row['crossing']) and str(row['crossing']).lower() not in ['false', '0', 'no', 'nan'])
        
        if highway in ['primary', 'tertiary']:
            if not is_crossing and str(row['foot_access']).lower() != 'yes':
                continue # Skip major roads if no foot access or crossing
                
        # 3. Geometry resolution
        way_id = row['way_id']
        geom = None
        if pd.notna(way_id) and way_id in way_nodes:
            wn = way_nodes[way_id]
            # Try to extract the segment between u and v
            if u in wn and v in wn:
                u_idx = wn.index(u)
                v_idx = wn.index(v)
                if u_idx != v_idx:
                    step = 1 if u_idx < v_idx else -1
                    segment = wn[u_idx:v_idx+step:step]
                    # Ensure all intermediate nodes are in node_coords
                    valid = all(n in node_coords for n in segment)
                    if valid:
                        coords_list = [(node_coords[n]['lon'], node_coords[n]['lat']) for n in segment]
                        geom = LineString(coords_list)
        
        if geom is None:
            missing_geometry += 1
            geom = LineString([(u_data['lon'], u_data['lat']), (v_data['lon'], v_data['lat'])])
            
        # Dist
        if pd.notna(row['distance_m']):
            dist = float(row['distance_m'])
        else:
            dist = math.hypot(v_data['lon'] - u_data['lon'], v_data['lat'] - u_data['lat']) * 111000 # rough approximation
            
        # Attributes
        stairs = (str(row['stairs']) == '1.0' or highway == 'steps')
        ramp = False # explicitly requested 0 or query OSM
        slope = row['slope'] if pd.notna(row['slope']) else None
        
        G.add_edge(u, v,
            edge_id=row['edge_id'],
            way_id=way_id,
            geometry=geom,
            length_m=dist,
            path_type=highway if not stairs else 'stairs',
            name=row['name'] if pd.notna(row['name']) else None,
            surface=row['surface'] if pd.notna(row['surface']) else 'unknown',
            width_m=row['width_m'] if pd.notna(row['width_m']) else None,
            stairs=stairs,
            ramp=ramp,
            crossing=row['crossing'] if pd.notna(row['crossing']) else None,
            barrier=row['barrier'] if pd.notna(row['barrier']) else None,
            access=row['access'] if pd.notna(row['access']) else 'unknown',
            foot_access=row['foot_access'] if pd.notna(row['foot_access']) else 'unknown',
            wheelchair=row['wheelchair'] if pd.notna(row['wheelchair']) else 'unknown',
            traffic=row['traffic'] if pd.notna(row['traffic']) else 'unknown',
            lit=row['lit'] if pd.notna(row['lit']) else 'unknown',
            slope_percent=None, # slope calculation later
            slope_status='unknown',
            source="CSV_Friend",
            confidence="high"
        )
        
    print(f"Built Graph with {len(G.nodes)} nodes and {len(G.edges)} edges.")
    print(f"Missing Nodes: {missing_nodes}, Edges falling back to straight geometry: {missing_geometry}")
    
    # Entrance Connection Logic
    print("Mapping Academic Block Entrances...")
    entrance_nodes = set()
    for idx, row in academic_blocks_gdf.iterrows():
        min_dist = float('inf')
        best_n = None
        lat, lon = row['latitude'], row['longitude']
        for n, data in G.nodes(data=True):
            dist = math.hypot(data['longitude'] - lon, data['latitude'] - lat)
            if dist < min_dist:
                min_dist = dist
                best_n = n
        if best_n is not None:
            entrance_nodes.add(best_n)
            G.nodes[best_n]['node_type'] = 'building_entrance'
            G.nodes[best_n]['academic_block_id'] = row['building_id']
            G.nodes[best_n]['name'] = f"Entrance to {row['short_name']}"

    # Connect components?
    # Prune only true irrelevant dead-ends
    print("Pruning disconnected components and minor dead-ends...")
    # Only remove degree-1 nodes if they aren't entrances, stairs, crossings, etc.
    while True:
        dead_ends = []
        for n, d in G.degree():
            if d == 1:
                # check if entrance
                if n in entrance_nodes:
                    continue
                # check if stairs or crossing connected
                keep = False
                for u, v, k, edata in G.edges(n, data=True, keys=True):
                    if edata.get('stairs') or pd.notna(edata.get('crossing')):
                        keep = True
                        break
                if not keep:
                    dead_ends.append(n)
                    
        if not dead_ends:
            break
        G.remove_nodes_from(dead_ends)
        
    if len(G.nodes) > 0:
        largest_cc = max(nx.connected_components(G), key=len)
        G = G.subgraph(largest_cc).copy()
        
    print(f"Final Graph size: {len(G.nodes)} nodes, {len(G.edges)} edges.")

    # Save Graph
    print("Saving datasets...")
    with open(os.path.join(PROCESSED_DIR, "vit_vellore_academic_pedestrian_network.pkl"), 'wb') as f:
        pickle.dump(G, f)
        
    ox.save_graphml(G, os.path.join(PROCESSED_DIR, "vit_vellore_academic_pedestrian_network.graphml"))

    # Dump GeoJSONs
    nodes_data = []
    for n, data in G.nodes(data=True):
        nodes_data.append({
            "node_id": n,
            "latitude": data['latitude'],
            "longitude": data['longitude'],
            "node_type": data.get('node_type', 'junction'),
            "name": data.get('name'),
            "academic_block_id": data.get('academic_block_id'),
            "geometry": Point(data['longitude'], data['latitude'])
        })
    n_gdf = gpd.GeoDataFrame(nodes_data, geometry='geometry', crs="EPSG:4326")
    n_gdf.to_file(os.path.join(PROCESSED_DIR, "pedestrian_nodes.geojson"), driver="GeoJSON")

    edges_data = []
    for u, v, k, data in G.edges(data=True, keys=True):
        e = data.copy()
        edges_data.append(e)
    e_gdf = gpd.GeoDataFrame(edges_data, geometry='geometry', crs="EPSG:4326")
    e_gdf.to_file(os.path.join(PROCESSED_DIR, "pedestrian_edges.geojson"), driver="GeoJSON")

    stairs_gdf = e_gdf[e_gdf['stairs'] == True]
    if len(stairs_gdf) > 0:
        stairs_gdf.to_file(os.path.join(PROCESSED_DIR, "stairs.geojson"), driver="GeoJSON")

    crossings_gdf = e_gdf[e_gdf['crossing'].notna()]
    if len(crossings_gdf) > 0:
        crossings_gdf.to_file(os.path.join(PROCESSED_DIR, "crossings.geojson"), driver="GeoJSON")

    ramps_gdf = e_gdf[e_gdf['ramp'] == True]
    if len(ramps_gdf) > 0:
        ramps_gdf.to_file(os.path.join(PROCESSED_DIR, "ramps.geojson"), driver="GeoJSON")

    print("Done!")

if __name__ == "__main__":
    main()
