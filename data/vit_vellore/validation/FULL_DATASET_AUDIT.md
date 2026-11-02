# FULL DATASET AUDIT
**VIT Vellore Accessibility-Aware Dynamic Pedestrian Rerouting System**

## 1. DATASET IDENTIFICATION
- **Raw Data Source**: `data/vit_vellore/raw/friend_base_pedestrian_network.csv`
- **Active Processed Dataset**: `data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl`

## 2. NODE & GRAPH ANALYSIS
- **Total Nodes**: 1551
- **Total Edges**: 1697
- **Connected Components**: 9
- **Largest Component**: 1509 nodes
- **Isolated Nodes**: 2
- **Parallel Edges**: 0 (Graph behaves as standard graph without overlapping (u,v) pairs despite being instantiated as a MultiGraph).

## 3. EDGE ATTRIBUTE ANALYSIS
- **Highway/Path Type**: service (553), residential (391), footway (305), unclassified (186), primary (158), tertiary (51), track (34), path (12), steps (7).
- **Surface**: unknown (1114), asphalt (385), unpaved (129), paving_stones (38), ground (12), paved (10), dirt (6), compacted (3).
- **Stairs**: 7 edges
- **Ramps**: 0 edges
- **Slope_Percent**: 100% Missing (1697/1697).
- **Wheelchair**: unknown (1373), likely (317), no (7).
- **Crossing**: no (1674), True (23).

## 4. GEOMETRY AUDIT
- **Total Edges**: 1697
- **OSM Geometry (osm_way)**: 1683 (99.18%)
- **Fallback Geometry**: 14 (0.82%)
- **Missing Geometry**: 0

The 14 fallback geometry edges represent straight lines between endpoints. None of these 14 edges intersect or compromise the critical test paths.
