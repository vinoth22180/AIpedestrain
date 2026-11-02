import os
import urllib.request
import json
import csv

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

RAW_DIR = "data/raw"
ensure_dir(f"{RAW_DIR}/pedestrian_counts")
ensure_dir(f"{RAW_DIR}/pedestrian_sensors")
ensure_dir(f"{RAW_DIR}/traffic_signals")

def fetch_json_to_csv(url, output_path, dataset_name):
    print(f"Fetching {dataset_name}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            results = data.get('results', [])
            if not results:
                print(f"No results found for {dataset_name}.")
                return
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
            print(f"Saved {len(results)} records to {output_path}")
    except Exception as e:
        print(f"Failed to fetch {dataset_name}: {e}")

def fetch_file(url, output_path, dataset_name):
    print(f"Downloading {dataset_name}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            with open(output_path, 'wb') as f:
                f.write(response.read())
        print(f"Saved {dataset_name} to {output_path}")
    except Exception as e:
        print(f"Failed to fetch {dataset_name}: {e}")

if __name__ == "__main__":
    # 1. Pedestrian Counts (CSV Export for recent counts)
    counts_url = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/pedestrian-counting-system-monthly-counts-per-hour/exports/csv?limit=50000&timezone=UTC&use_labels=false&epsg=4326"
    fetch_file(counts_url, f"{RAW_DIR}/pedestrian_counts/counts_sample.csv", "Pedestrian Counts")
    
    # 2. Sensor Locations
    sensors_url = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/pedestrian-counting-system-sensor-locations/records?limit=100"
    fetch_json_to_csv(sensors_url, f"{RAW_DIR}/pedestrian_sensors/sensor_locations.csv", "Sensor Locations")
    
    # 3. Traffic Signals (Statewide, but we'll filter later)
    signals_url = "https://opendata.transport.vic.gov.au/dataset/923af458-363d-469f-bc5e-84746a80b9a2/resource/1036a318-8867-4dc6-bd84-fc3bcd6cbdb9/download/victorian_traffic_signals.csv"
    fetch_file(signals_url, f"{RAW_DIR}/traffic_signals/victorian_traffic_signals.csv", "Victorian Traffic Signals")
