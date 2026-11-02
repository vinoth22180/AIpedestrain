# Implementation Plan: Pedestrian Feature Mapping

## Goal Description
The goal is to map all verified pedestrian features (stairs, slopes, crossings, ramps, surfaces, highway types, barriers) from the existing dataset, render them as visual markers/lines on the frontend MapLibre component with a Legend, and ensure PADA-R incorporates them (which it already does structurally). No data will be fabricated.

## Proposed Changes

### Backend/Data Pipeline (`scripts/build_final_dataset.py`)
- Improve the `slope_percent` parsing to extract valid floats and correctly assign `"up"`/`"down"` to the `slope_status` attribute so this data isn't discarded.
- Extract `barrier`, `surface`, `highway` as exportable geojson collections in addition to the existing `stairs.geojson`, `ramps.geojson`, and `crossings.geojson`.
- Create `slopes.geojson`, `barriers.geojson`, and `highway_types.geojson` during the build process.
- Re-run `build_final_dataset.py` to update the active `vit_vellore_academic_pedestrian_network.pkl` and GeoJSON files.

### Frontend (`frontend/src/components/MapCanvas.jsx`)
- Create new MapLibre Source/Layer components for:
  - `slopes.geojson` (Render slope symbol + slope value/status)
  - `barriers.geojson` (Render barrier symbol)
  - `crossings.geojson` (Render crossing symbol)
  - Refine `stairs.geojson` and `ramps.geojson` to include symbols + text labels (e.g., "STAIRS", "RAMP").
- Color-code the pedestrian edges based on `surface` and `highway` types visually instead of treating them all as a single gray layer, or keep gray base and add specific styling for specific types.
- Ensure all marker placements use the geometry directly from the geojsons (no fake centroids).

### Frontend Legend (`frontend/src/components/MapLegend.jsx`)
- Create a new floating legend component `MapLegend.jsx` describing:
  - STAIRS, RAMP, SLOPE, CROSSING, BARRIER, PEDESTRIAN PATH, RESTRICTED PATH.
- Integrate it into the main layout so it's visible to the user.

### Validation Reports
- Generate the final script to execute routing tests and write the results to:
  - `data/vit_vellore/validation/FEATURE_MAPPING_REPORT.md`
  
## Verification Plan
1. Re-run dataset builder and confirm nodes/edges counts remain identical, but attributes like slopes are now fully preserved.
2. Run the PADA-R feasibility audit and write the outputs.
3. Open the UI and visually confirm the new symbols (Stairs, Slopes, Crossings) render geographically correctly without breaking routing paths.
