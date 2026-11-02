# Missing Path Enrichment Audit

**Date:** 2026-09-16
**Objective:** Restore missing pedestrian connectivity for VIT Lake → SJT, SJT Subway, and Gandhi Block pathways using verified OSM geometry without fabrication.

## 1. Network Modifications

The dataset building pipeline (`scripts/build_final_dataset.py`) was upgraded to identify explicit `sidewalk` tags in the OSM dataset (`map.osm`) and accurately model them as dual `highway=footway` edges parallel to the service roads, preserving full coordinate integrity and preventing geometry fabrication.

### Graph Statistics
- **Original Edges:** 1697
- **Updated Edges:** 1721
- **Newly Added Edges:** 24 verified pedestrian footway dual-edges
- **Connected Components:** 9
- **Largest Component:** 1509 nodes (Connectivity preserved!)

## 2. Feature Extraction Results

- **SJT Subway Extraction:** `way_id: 1259738117` was successfully flagged as a pedestrian subway. 
  - Subways extracted: 20 edge segments.
- **Lake → SJT Connectivity:** The Jimmy Carter Road corridor (`way_id: 1543114451` and `89215253`) has `sidewalk:left=separate` and `sidewalk=both` tags. These were processed to spawn the 24 new contiguous `footway` segments bridging the gap between VIT Lake and SJT.
- **SJT → Gandhi Block Connectivity:** The same contiguous dual-edge processing provides a dedicated footway path continuing to the Gandhi Block perimeter.

## 3. Routing Validation (PADA-R Engine)

Tests conducted using the active `.pkl` file confirm:
- **Lake -> SJT:** `True` (Path found via continuous `footway` edges)
- **SJT -> Gandhi Block:** `True` (Path found via continuous `footway` edges)

## 4. UI / GeoJSON Export Modifications

- `subways.geojson` is now compiled and output natively.
- `/api/pedestrian_network/stats` dynamically fetches the subway count (`stats.subways = 20` segments).
- `MapCanvas.jsx` renders subways with a prominent `cyan-500` dashed line (`[1, 2]`) and labels them prominently as `⬇ SUBWAY`.
- `MapLegend.jsx` accurately reports `🚇 PEDESTRIAN SUBWAY`.
