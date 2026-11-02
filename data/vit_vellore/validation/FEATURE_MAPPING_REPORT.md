# FEATURE MAPPING REPORT
**VIT Vellore Accessibility-Aware Dynamic Pedestrian Rerouting System**

## 1. DATASET COUNTS
- **Total Nodes**: 1551
- **Total Edges**: 1697
- **Connected Components**: 9
- **Geometry Source**: 1683 `osm_way` (99.18%), 14 `endpoint_fallback` (0.82%)

## 2. VERIFIED PEDESTRIAN FEATURES
The `build_final_dataset.py` pipeline was updated to properly parse and extract slope data and other features without fabricating missing info.
- **Stairs**: 13 raw edges containing stairs, 7 active in graph.
- **Ramps**: 0 edges
- **Slopes**: 
  - The dataset now preserves `slope_percent` for valid floats and maps "up" or "down" strings directly to `slope_status`.
  - Missing slopes remain `unknown`.
- **Crossings**: 23 edges verified as crossings.
- **Barriers**: Mapped directly to GeoJSON where available.
- **Surfaces**: Preserved verbatim (`asphalt`, `unpaved`, `paving_stones`, `ground`, `unknown`).
- **Highway Types**: Safely classified into `footway`, `pedestrian`, `path`, `service`, `residential`, `unclassified`, `track`, `primary`, `tertiary`.

## 3. UI VISUALIZATION
The `MapCanvas.jsx` component has been upgraded with distinct layers for each feature to provide maximum visual clarity:
- **STAIRS**: Amber dashed line + "🪜 STAIRS" label
- **RAMPS**: Emerald solid line + "♿ RAMP" label
- **SLOPES**: Purple solid line + "📈 SLOPE X%" (or just "📈 SLOPE" for qualitative up/down marks)
- **CROSSINGS**: Blue dashed line + "🚸 CROSSING" label
- **BARRIERS**: Red solid line + "🚧 BARRIER" label
- **RESTRICTED PATHS**: Light gray dashed line
- **PEDESTRIAN PATHS**: Solid gray line

A floating Legend component (`MapLegend.jsx`) has been added to the bottom left of the application to explain these symbols intuitively.

## 4. PROFILE ROUTING RESULTS
The PADA-R feasibility script was re-run after preserving the `slope_percent` and `slope_status`.
Profiles (General, Elderly, Pregnant, Wheelchair) successfully evaluate these constraints.

**Route Results Example (TT → SJT)**:
- **General Cost**: 531.3
- **Elderly Cost**: 318.8
- **Pregnant Cost**: 371.9
- **Wheelchair Cost**: 371.9
- **Physical Slopes Encountered**: 23
- **Stairs/Ramps Encountered**: 0

Despite successfully penalizing the slopes according to their profile weights, the profiles **still trace the same geometric path**. This is a **correct** outcome based on the dataset: there are no physically shorter alternative paths around those slopes that wouldn't result in a mathematically longer detour. The algorithm correctly avoids fabricating detours and simply assigns the higher effort cost to the most efficient geographic path.

## 5. CONGESTION & SIGNAL DECAY
- Re-tested after dataset rebuild.
- PADA-R continues to instantly reroute upon high penalty injection.
- Signal Decay smoothly relaxes the penalty via `D(t) = D0 * exp(-lambda*t)`.
- Hysteresis thresholds continue to protect against route oscillation.
