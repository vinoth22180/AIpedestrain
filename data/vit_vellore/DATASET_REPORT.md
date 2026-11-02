# VIT Vellore Pedestrian Dataset Report

## 1. Data Sources
- **Source**: OpenStreetMap (OSM) via OSMnx API.
- **Boundary Relation**: `R15931944`

## 2. Graph Topology & Connectivity
- **Initial Nodes**: 271
- **Initial Edges**: 750
- **Connected Components**: 1
- **Largest Component Nodes**: 271 (kept)
- **Final Valid Nodes**: 271
- **Final Valid Edges**: 750

## 3. Path Types (Semantic Tags)
```json
{
  "service": 382,
  "footway": 220,
  "residential": 130,
  "['footway', 'steps']": 12,
  "unclassified": 4,
  "['residential', 'path']": 2
}
```

## 4. Accessibility Attributes
The dataset preserves `surface`, `smoothness`, `incline`, `wheelchair`, `tactile_paving`, and `steps` where provided by OSM.
Empty/null values indicate unverified properties.

## 5. Canonical Locations
Total Locations: 8
Successfully Mapped to Connected Network: 8

## 6. Known Limitations
- Accessibility tags (wheelchair, tactile paving, surface) may be missing in OSM.
- Non-mapped paths internal to buildings are not included to avoid false routing shortcuts.
