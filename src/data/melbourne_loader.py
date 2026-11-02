import os
import requests
import geopandas as gpd
import osmnx as ox

MELB_PED_URL = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/pedestrian-network/exports/geojson"
# Since this file is in src/data/, the root is three levels up, wait, src/data is two levels down. 
# __file__ -> src/data/melbourne_loader.py. dirname(__file__) -> src/data. dirname(dirname) -> src. dirname(dirname(dirname)) -> project root
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
PED_NET_PATH = os.path.join(DATA_DIR, "pedestrian_network", "pedestrian_network.geojson")
OSM_DIR = os.path.join(DATA_DIR, "osm_accessibility")
OSM_EDGES_PATH = os.path.join(OSM_DIR, "osm_edges.geojson")
OSM_NODES_PATH = os.path.join(OSM_DIR, "osm_nodes.geojson")

# Melbourne CBD Bounding Box (approx)
BBOX = (-37.808, -37.820, 144.975, 144.955) # north, south, east, west

def download_melbourne_network():
    if not os.path.exists(PED_NET_PATH):
        print(f"Downloading Melbourne Pedestrian Network to {PED_NET_PATH}...")
        os.makedirs(os.path.dirname(PED_NET_PATH), exist_ok=True)
        response = requests.get(MELB_PED_URL, timeout=30)
        response.raise_for_status()
        with open(PED_NET_PATH, 'wb') as f:
            f.write(response.content)
        print("Download complete.")
    else:
        print("Melbourne Pedestrian Network already exists.")

    gdf = gpd.read_file(PED_NET_PATH)
    
    # Clip to bounding box for the prototype
    from shapely.geometry import Polygon
    bbox_polygon = Polygon([
        (BBOX[3], BBOX[1]), 
        (BBOX[2], BBOX[1]), 
        (BBOX[2], BBOX[0]), 
        (BBOX[3], BBOX[0]), 
        (BBOX[3], BBOX[1])
    ])
    gdf = gpd.clip(gdf, bbox_polygon)
    print(f"Clipped Melbourne Network to {len(gdf)} edges.")
    return gdf

def fetch_osm_accessibility_data():
    if not os.path.exists(OSM_EDGES_PATH) or not os.path.exists(OSM_NODES_PATH):
        print("Fetching OSM accessibility data for Melbourne CBD...")
        # Define useful tags for pedestrian routing
        useful_tags_path = ['highway', 'surface', 'smoothness', 'incline', 'wheelchair', 'tactile_paving', 'steps']
        ox.settings.useful_tags_way = ox.settings.useful_tags_way + useful_tags_path
        try:
            # Bypass blocked Overpass API by downloading directly from main OSM XML API
            # BBOX format for API is: left,bottom,right,top (west, south, east, north)
            osm_api_url = f"https://api.openstreetmap.org/api/0.6/map?bbox={BBOX[3]},{BBOX[1]},{BBOX[2]},{BBOX[0]}"
            print(f"Downloading raw OSM XML from {osm_api_url}...")
            
            headers = {'User-Agent': 'AccessibilityRoutingPrototype/1.0'}
            resp = requests.get(osm_api_url, headers=headers, timeout=60)
            resp.raise_for_status()
            
            os.makedirs(OSM_DIR, exist_ok=True)
            osm_xml_path = os.path.join(OSM_DIR, "map.osm")
            with open(osm_xml_path, 'wb') as f:
                f.write(resp.content)
            
            # Create graph from the downloaded XML
            G_osm = ox.graph_from_xml(osm_xml_path, simplify=False)
            nodes, edges = ox.graph_to_gdfs(G_osm)
            
            # Save for later runs
            edges.to_file(OSM_EDGES_PATH, driver="GeoJSON")
            nodes.to_file(OSM_NODES_PATH, driver="GeoJSON")
            print("OSM data fetched and saved.")
        except Exception as e:
            print(f"Error fetching OSM data (likely network timeout): {e}")
            # Return empty geodataframes with expected structure
            edges = gpd.GeoDataFrame(columns=['geometry', 'highway', 'surface', 'smoothness', 'incline', 'wheelchair', 'tactile_paving', 'steps'], crs="EPSG:4326")
            nodes = gpd.GeoDataFrame(columns=['geometry'], crs="EPSG:4326")
    else:
        print("OSM accessibility data already exists. Loading...")
        edges = gpd.read_file(OSM_EDGES_PATH)
        nodes = gpd.read_file(OSM_NODES_PATH)
        
    return nodes, edges

def load_melbourne_data():
    melb_gdf = download_melbourne_network()
    osm_nodes, osm_edges = fetch_osm_accessibility_data()
    return melb_gdf, osm_edges, osm_nodes
