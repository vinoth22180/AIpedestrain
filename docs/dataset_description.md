# Dataset Description

## 1. City of Melbourne Pedestrian Network
- **Dataset Name:** Pedestrian Network
- **Official Source:** City of Melbourne Open Data Portal (https://discover.data.vic.gov.au/dataset/pedestrian-network)
- **File Used:** Dynamically fetched via Open Data API (GeoJSON export). Cached locally to `data/pedestrian_network/pedestrian_network.geojson`.
- **Relevant Fields:**
  - `geometry`: LineString geometries representing the path of pedestrian walkways.
- **Geographic Coverage:** Melbourne CBD (Clipped dynamically via Bounding Box for this prototype: North: -37.808, South: -37.820, East: 144.975, West: 144.955).
- **Preprocessing:** Clipped to bounding box to minimize memory footprint. Graph nodes are inferred from the start/end coordinates of the LineStrings. Distance/length of paths calculated metrically.

## 2. OpenStreetMap (OSM) Accessibility Data
- **Dataset Name:** OSM Pedestrian Walkways (`network_type='walk'`)
- **Official Source:** OpenStreetMap via `osmnx`
- **File Used:** Fetched dynamically via `osmnx` bounding box query. Cached to `data/osm_accessibility/osm_edges.geojson`.
- **Relevant Fields & Extraction:**
  - `highway`: Filtered for `steps` to derive `has_stairs` (boolean).
  - `wheelchair`: Mapped to `wheelchair_accessible` (`True` if yes/designated, `False` if no, otherwise `None`/unknown).
  - `surface`: Extracted as string (`surface_type`).
  - `smoothness`: Extracted as string (`smoothness_value`).
  - `incline`: Extracted as string/float (`incline_value`).
  - `tactile_paving`: Extracted as string (`tactile_paving`).
- **Geographic Coverage:** Same bounding box as the Melbourne network.
- **Preprocessing & Derived Features:** OSM tags are mapped to structured fields in `src/accessibility.py`. To merge these attributes onto the Melbourne network, a geospatial `sjoin_nearest` operation is performed using `geopandas` within a 15-meter tolerance (after projecting to EPSG:28355 for accurate metric distances).

## Limitations
- **Data Completeness:** OSM accessibility tags are notoriously sparse. Missing values are intentionally maintained as `None` or 'unknown' to reflect real-world ambiguity, avoiding fabricated data. User profiles handle these unknowns with specific penalties.
- **Spatial Alignment:** The City of Melbourne network and OSM network lines do not align perfectly. The buffer/nearest-neighbor join introduces a small margin of error where an attribute might be assigned to a parallel nearby path.
