# Dataset Sources and Provenance

## 1. City of Melbourne Pedestrian Network
- **Dataset Name:** Pedestrian Network
- **Publisher:** City of Melbourne
- **Official URL:** https://discover.data.vic.gov.au/dataset/pedestrian-network
- **File Used:** Dynamically fetched GeoJSON via API, cached at `data/pedestrian_network/pedestrian_network.geojson`
- **Relevant Columns:** `geometry`
- **Preprocessing:** Clipped to CBD bounding box. Metric distance calculated.

## 2. OpenStreetMap (OSM) Accessibility Data
- **Dataset Name:** OSM Pedestrian Walkways
- **Publisher:** OpenStreetMap
- **Official URL:** Extracted via `osmnx`
- **File Used:** Cached locally at `data/osm_accessibility/osm_edges.geojson`
- **Relevant Columns:** `highway`, `wheelchair`, `surface`, `smoothness`, `incline`, `tactile_paving`
- **Preprocessing:** Geospatial nearest-join to Melbourne network.

## 3. Pedestrian Counting System - Counts
- **Dataset Name:** Pedestrian Counting System - Monthly (counts per hour)
- **Publisher:** City of Melbourne
- **Official URL:** https://data.melbourne.vic.gov.au/explore/dataset/pedestrian-counting-system-monthly-counts-per-hour/
- **File Used:** `data/raw/pedestrian_counts/counts_sample.csv` (Sample of 50,000 records)
- **Relevant Columns:** `location_id`, `sensing_date`, `hourday`, `pedestriancount`, `sensor_name`
- **Preprocessing:** Aggregated by hour to compute current pedestrian density. Values normalized into congestion scores.
- **Derived Variables:** `congestion_score` (0 to 1).

## 4. Pedestrian Counting System - Sensor Locations
- **Dataset Name:** Pedestrian Counting System - Sensor Locations
- **Publisher:** City of Melbourne
- **Official URL:** https://data.melbourne.vic.gov.au/explore/dataset/pedestrian-counting-system-sensor-locations/
- **File Used:** `data/raw/pedestrian_sensors/sensor_locations.csv`
- **Relevant Columns:** `location_id`, `sensor_name`, `latitude`, `longitude`
- **Preprocessing:** Nearest-edge geospatial join to map sensors to specific network edges.

## 5. Victorian Traffic Signals
- **Dataset Name:** Victorian Traffic Signals
- **Publisher:** Department of Transport and Planning (Victoria)
- **Official URL:** https://opendata.transport.vic.gov.au/dataset/victorian-traffic-signals
- **File Used:** `data/raw/traffic_signals/victorian_traffic_signals.csv`
- **Relevant Columns:** `SITE_NO`, `LATITUDE`, `LONGITUDE`
- **Preprocessing:** Nearest-edge geospatial join to map signals to graph nodes.
- **Derived Variables:** `traffic_signal_penalty` representing potential delay at intersections.
