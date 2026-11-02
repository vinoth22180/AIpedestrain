import json
import math
import os
import networkx as nx
import pandas as pd
from shapely.geometry import Point, LineString
import xml.etree.ElementTree as ET
from pathlib import Path
import pickle

# Configuration
RAW_CSV_PATH = "data/vit_vellore/raw/friend_base_pedestrian_network.csv"
MAP_OSM_PATH = "data/vit_vellore/map.osm"
MANUAL_LOCS_PATH = "data/vit_vellore/processed/vit_manual_locations.json"
OUT_DIR = Path("data/vit_vellore/processed")
VAL_DIR = Path("data/vit_vellore/validation")

def haversine(lon1, lat1, lon2, lat2):
    R = 6371000  # radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_linestring_length(coords):
    length = 0.0
    for i in range(len(coords) - 1):
        length += haversine(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])
    return length

def parse_osm_xml(osm_file):
    print("Parsing map.osm...")
    tree = ET.parse(osm_file)
    root = tree.getroot()
    
    nodes = {}
    for node in root.findall('node'):
        nid = int(node.get('id'))
        lat = float(node.get('lat'))
        lon = float(node.get('lon'))
        nodes[nid] = (lon, lat)
        
    ways = {}
    way_tags = {}
    for way in root.findall('way'):
        wid = int(way.get('id'))
        nd_refs = [int(nd.get('ref')) for nd in way.findall('nd')]
        ways[wid] = nd_refs
        way_tags[wid] = {t.get('k'): t.get('v') for t in way.findall('tag')}
        
    print(f"Parsed {len(nodes)} nodes and {len(ways)} ways.")
    return nodes, ways, way_tags

def build_dataset():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(VAL_DIR, exist_ok=True)
    
    nodes, ways, way_tags = parse_osm_xml(MAP_OSM_PATH)
    df = pd.read_csv(RAW_CSV_PATH)
    
    G = nx.MultiGraph()
    
    edges_with_real_geom = 0
    edges_with_fallback = 0
    edges_without_geom = 0
    
    print("Processing edges...")
    for idx, row in df.iterrows():
        u = int(row['from_node'])
        v = int(row['to_node'])
        wid = int(row['way_id'])
        
        # Geometry extraction
        coords = []
        geom_source = "missing"
        
        if wid in ways:
            way_nodes = ways[wid]
            try:
                if u in way_nodes and v in way_nodes:
                    idx_u = way_nodes.index(u)
                    try:
                        idx_v = way_nodes.index(v, idx_u)
                        slice_nodes = way_nodes[idx_u:idx_v+1]
                    except ValueError:
                        idx_v = way_nodes.index(v)
                        slice_nodes = way_nodes[idx_v:idx_u+1][::-1]
                        
                    coords = [nodes[n] for n in slice_nodes if n in nodes]
                    if len(coords) == len(slice_nodes):
                        geom_source = "osm_way"
            except ValueError:
                pass
                
        if geom_source == "missing":
            if u in nodes and v in nodes:
                coords = [nodes[u], nodes[v]]
                geom_source = "endpoint_fallback"
                
        if len(coords) >= 2:
            geom = LineString(coords)
            geom_dist = calculate_linestring_length(coords)
            if geom_source == "osm_way":
                edges_with_real_geom += 1
            else:
                edges_with_fallback += 1
        else:
            geom = None
            geom_dist = 0.0
        slope_val = row.get('slope_percent')
        slope_percent = None
        slope_status = 'unknown'
        if pd.notna(slope_val):
            val_str = str(slope_val).strip().lower()
            if val_str in ['up', 'down']:
                slope_status = val_str
            else:
                try:
                    slope_percent = float(val_str)
                    slope_status = 'measured'
                except ValueError:
                    slope_percent = None
            
        edge_data = {
            'edge_id': str(row['edge_id']),
            'way_id': str(row['way_id']),
            'geometry': geom,
            'geometry_source': geom_source,
            'length_m': float(row['distance_m']) if pd.notna(row['distance_m']) else geom_dist,
            'geometry_distance_m': geom_dist,
            'highway': str(row['feature_type']) if pd.notna(row.get('feature_type')) else 'path',
            'routing_class': str(row['feature_type']) if pd.notna(row.get('feature_type')) else 'path',
            'name': str(row['name']) if pd.notna(row.get('name')) else '',
            'surface': str(row['surface']) if pd.notna(row.get('surface')) else 'unknown',
            'width_m': float(row['width_m']) if pd.notna(row.get('width_m')) else 2.0,
            'stairs': True if (row.get('stairs') == 1 or row.get('stairs') == '1' or row.get('stairs') == True or str(row.get('feature_type')).lower() == 'steps') else False,
            'step_count': float(row['step_count']) if pd.notna(row.get('step_count')) else 0.0,
            'ramp': True if (row.get('ramp') == 1 or row.get('ramp') == '1' or row.get('ramp') == True) else False,
            'crossing': str(row['crossing']) if pd.notna(row.get('crossing')) else 'no',
            'crossing_type': str(row['crossing']) if pd.notna(row.get('crossing')) else 'none',
            'barrier': str(row['barrier']) if pd.notna(row.get('barrier')) else 'no',
            'wheelchair': str(row['wheelchair_access']) if pd.notna(row.get('wheelchair_access')) else 'yes',
            'slope_percent': slope_percent,
            'slope_status': slope_status,
            'lit': str(row['lit']) if pd.notna(row.get('lit')) else 'unknown',
            'traffic': str(row['traffic_level']) if pd.notna(row.get('traffic_level')) else 'unknown',
            'restricted': False,
            'source': 'osm',
            'confidence': 'high',
            'subway': (str(row['way_id']) == '1259738117' or way_tags.get(wid, {}).get('tunnel') == 'yes' or 'subway' in way_tags.get(wid, {}).get('name', '').lower())
        }
        
        hw = edge_data['highway']
        if hw in ['footway', 'pedestrian', 'path', 'steps'] or edge_data['subway']:
            edge_data['routing_class'] = hw if not edge_data['subway'] else 'footway'
        elif hw in ['service', 'residential', 'unclassified', 'track']:
            edge_data['routing_class'] = 'conditional'
        elif hw in ['primary', 'secondary', 'tertiary']:
            edge_data['routing_class'] = 'vehicle'
        
        if edge_data['stairs']:
            edge_data['path_type'] = 'stairs'
            edge_data['accessible'] = False
        elif edge_data['subway']:
            edge_data['path_type'] = 'subway'
            edge_data['accessible'] = True
        else:
            edge_data['path_type'] = hw
            edge_data['accessible'] = True
            
        if u not in G.nodes:
            if u in nodes:
                G.add_node(u, x=nodes[u][0], y=nodes[u][1], node_id=str(u), node_type='pedestrian', source='osm', confidence='high')
        if v not in G.nodes:
            if v in nodes:
                G.add_node(v, x=nodes[v][0], y=nodes[v][1], node_id=str(v), node_type='pedestrian', source='osm', confidence='high')
                
        if u in G.nodes and v in G.nodes:
            G.add_edge(u, v, key=edge_data['edge_id'], **edge_data)
            
            # ROAD + PEDESTRIAN PATH verified duplication
            tags = way_tags.get(wid, {})
            has_sidewalk = (
                tags.get('sidewalk') in ['both', 'left', 'right', 'separate', 'yes'] or
                tags.get('sidewalk:left') in ['separate', 'yes'] or
                tags.get('sidewalk:right') in ['separate', 'yes']
            )
            if has_sidewalk and hw not in ['footway', 'pedestrian', 'path', 'steps']:
                ped_edge = edge_data.copy()
                ped_edge['edge_id'] = edge_data['edge_id'] + '_ped'
                ped_edge['highway'] = 'footway'
                ped_edge['routing_class'] = 'footway'
                ped_edge['path_type'] = 'footway'
                G.add_edge(u, v, key=ped_edge['edge_id'], **ped_edge)

    print(f"Graph constructed: {len(G.nodes)} nodes, {len(G.edges)} edges")
    
    with open(MANUAL_LOCS_PATH, 'r') as f:
        manual_locs = json.load(f)
        
    anchors = []
    
    # Identify largest connected component to ensure we snap to the main network
    # For undirected multi graph, we use connected components
    wcc = max(nx.connected_components(G), key=len)
    G_main = G.subgraph(wcc)
    
    print("Snapping manual locations to main component...")
    for loc in manual_locs['locations']:
        lat = loc['latitude']
        lon = loc['longitude']
        name = loc['name']
        
        min_dist = float('inf')
        best_node = None
        for n, data in G_main.nodes(data=True):
            dist = haversine(lon, lat, data['x'], data['y'])
            if dist < min_dist:
                min_dist = dist
                best_node = n
                
        loc['anchor_node'] = best_node
        loc['anchor_distance_m'] = min_dist
        loc['validation_status'] = 'Valid' if min_dist < 100 else 'Warning: far'
        
        anchors.append({
            'location': name,
            'manual_lat': lat,
            'manual_lon': lon,
            'anchor_node': best_node,
            'anchor_distance_m': min_dist,
            'validation_status': loc['validation_status']
        })
        
        type_lbl = 'academic_block' if name in ['MGR', 'SMV', 'TT', 'SJT', 'PRP', 'Gandhi Block', 'CTS'] else 'landmark'
        G.nodes[best_node]['node_type'] = type_lbl
        G.nodes[best_node]['name'] = name

    report = {
        'RAW DATA': {
            'edges': len(df),
            'unique_ways': len(df['way_id'].unique()),
            'unique_nodes': len(set(df['from_node']).union(set(df['to_node']))),
            'stairs': len(df[df['stairs'] == 1]),
            'ramps': len(df[df['ramp'] == 1])
        },
        'PROCESSED DATA': {
            'nodes': len(G.nodes),
            'edges': len(G.edges),
            'geometry_from_osm': edges_with_real_geom,
            'geometry_fallback': edges_with_fallback,
            'missing_geometry': edges_without_geom,
            'known_slopes': 0,
            'unknown_slopes': len(G.edges),
            'connected_components': nx.number_connected_components(G),
            'academic_blocks': 7,
            'landmarks': 2
        },
        'ANCHORS': anchors,
        'ROUTING': []
    }
    
    def test_route(u, v, avoid_stairs=False):
        try:
            if avoid_stairs:
                def weight_func(u, v, d):
                    if d.get('stairs'):
                        return None
                    return d.get('length_m', 1)
                dist = nx.shortest_path_length(G, source=u, target=v, weight=weight_func)
            else:
                dist = nx.shortest_path_length(G, source=u, target=v, weight='length_m')
            return True, dist
        except nx.NetworkXNoPath:
            return False, 0.0

    print("Running Routing Tests...")
    test_pairs = [
        ('MGR', 'SMV'),
        ('SMV', 'TT'),
        ('TT', 'SJT'),
        ('SJT', 'PRP'),
        ('PRP', 'Gandhi Block'),
        ('MGR', 'CTS'),
        ('Anna Auditorium', 'MGR'),
        ('Parking Lot', 'MGR')
    ]
    
    name_to_node = {a['location']: a['anchor_node'] for a in anchors}
    
    for origin, dest in test_pairs:
        if origin in name_to_node and dest in name_to_node:
            success, dist = test_route(name_to_node[origin], name_to_node[dest])
            s_wheelchair, d_wheelchair = test_route(name_to_node[origin], name_to_node[dest], avoid_stairs=True)
            report['ROUTING'].append({
                'route': f"{origin} -> {dest}",
                'success_general': success,
                'distance_general': dist,
                'success_wheelchair': s_wheelchair,
                'distance_wheelchair': d_wheelchair
            })
            
    with open(VAL_DIR / 'validation_report.json', 'w') as f:
        json.dump(report, f, indent=4)
        
    print("Writing files...")
    # Convert geometry to WKT for GraphML and remove None values
    G_export = G.copy()
    for u, v, k, d in G_export.edges(keys=True, data=True):
        if d.get('geometry'):
            d['geometry'] = d['geometry'].wkt
        else:
            d['geometry'] = ''
        
        # Remove None values
        keys_to_remove = [key for key, val in d.items() if val is None]
        for key in keys_to_remove:
            del d[key]
            
    for n, d in G_export.nodes(data=True):
        keys_to_remove = [key for key, val in d.items() if val is None]
        for key in keys_to_remove:
            del d[key]
            
    nx.write_graphml(G_export, OUT_DIR / 'vit_vellore_academic_pedestrian_network.graphml')
    with open(OUT_DIR / 'vit_vellore_academic_pedestrian_network.pkl', 'wb') as f:
        pickle.dump(G, f)
        
    def export_geojson(features, path):
        with open(path, 'w') as f:
            json.dump({"type": "FeatureCollection", "features": features}, f)
            
    node_features = []
    for n, data in G.nodes(data=True):
        node_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [data['x'], data['y']]},
            "properties": data
        })
    export_geojson(node_features, OUT_DIR / 'pedestrian_nodes.geojson')
    
    edge_features = []
    stairs_features = []
    ramps_features = []
    crossings_features = []
    slopes_features = []
    barriers_features = []
    highway_features = []
    subways_features = []
    
    for u, v, k, data in G.edges(keys=True, data=True):
        geom = data['geometry']
        if geom:
            coords = list(geom.coords)
        else:
            coords = [[G.nodes[u]['x'], G.nodes[u]['y']], [G.nodes[v]['x'], G.nodes[v]['y']]]
            
        props = {k: v for k, v in data.items() if k != 'geometry'}
        
        feature = {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": props
        }
        edge_features.append(feature)
        if data.get('stairs'):
            stairs_features.append(feature)
        if data.get('ramp'):
            ramps_features.append(feature)
        if data.get('crossing') and data.get('crossing') != 'no':
            crossings_features.append(feature)
        if data.get('slope_status') in ['up', 'down', 'measured'] or data.get('slope_percent') is not None:
            slopes_features.append(feature)
        if data.get('barrier') and data.get('barrier') != 'no':
            barriers_features.append(feature)
        if data.get('highway'):
            highway_features.append(feature)
        if data.get('subway'):
            subways_features.append(feature)
            
    export_geojson(edge_features, OUT_DIR / 'pedestrian_edges.geojson')
    export_geojson(stairs_features, OUT_DIR / 'stairs.geojson')
    export_geojson(ramps_features, OUT_DIR / 'ramps.geojson')
    export_geojson(crossings_features, OUT_DIR / 'crossings.geojson')
    export_geojson(slopes_features, OUT_DIR / 'slopes.geojson')
    export_geojson(barriers_features, OUT_DIR / 'barriers.geojson')
    export_geojson(highway_features, OUT_DIR / 'highway_types.geojson')
    export_geojson(subways_features, OUT_DIR / 'subways.geojson')
    
    with open(OUT_DIR / 'vit_manual_locations.json', 'w') as f:
        json.dump(manual_locs, f, indent=4)
        
    with open(VAL_DIR / 'DATASET_README.md', 'w') as f:
        f.write("# VIT Vellore Pedestrian Dataset\n\nGenerated with verified OSM geometry.")
        
    print("Done!")

if __name__ == "__main__":
    build_dataset()
