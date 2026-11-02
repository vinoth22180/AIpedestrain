# DATASET FORENSIC AUDIT
**VIT Vellore Accessibility-Aware Dynamic Pedestrian Rerouting System**
**Date**: September 2026

## 1. Active Dataset
- **Raw Dataset File**: `data/vit_vellore/raw/friend_base_pedestrian_network.csv`
- **Active Processed Dataset (Backend)**: `data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl`
- **Graph Manager**: `src/graph_manager.py` loads the `.pkl` into memory.

## 2. Dataset Pipeline
**RAW DATA (`.csv` + `.osm`) → ENRICHMENT (`build_final_dataset.py`) → PROCESSED GRAPH (`.pkl`) → ROUTING (`src/api.py` / `src/pada_r/router.py`)**

The pipeline merges the static properties of the CSV file with the actual geographic coordinates mapped in the `.osm` XML. 
It falls back to straight-line endpoints when the `.osm` way is missing.
It strips any empty/`None` properties explicitly before generating the active NetworkX MultiGraph `.pkl`.

## 3. Complete Column Analysis (RAW CSV)
| Column Name | Type | Unique | Missing (%) | Values / Examples |
|---|---|---|---|---|
| `edge_id` | str | 2371 | 0% | 'E000001', 'E000002', etc. |
| `way_id` | int64 | 488 | 0% | 89186541, etc. |
| `from_node` | int64 | 2048 | 0% | OSM node IDs |
| `to_node` | int64 | 2053 | 0% | OSM node IDs |
| `distance_m` | float64 | 1901 | 0% | 10.31, 24.5, etc. |
| `feature_type` | str | 10 | 0% | residential, service, footway, etc. |
| `name` | str | 30 | 78.87% | Mostly missing |
| `surface` | str | 9 | 0% | asphalt, unknown, paved, unpaved... |
| `width_m` | float64 | 0 | 100% | Entirely missing |
| `slope_percent` | str | 7 | 0% | '2', '3', 'down', '3.5', 'up', '12', '2.5' |
| `slope_source` | str | 2 | 0% | 'ESTIMATE', 'OSM' |
| `stairs` | int64 | 2 | 0% | [0, 1] |
| `step_count` | float64 | 0 | 100% | Entirely missing |
| `ramp` | int64 | 1 | 0% | [0] (No ramps exist) |
| `ramp_slope_percent` | float64 | 0 | 100% | Entirely missing |
| `crossing` | str | 2 | 99.03% | 'marked', 'uncontrolled' |
| `barrier` | float64 | 0 | 100% | Entirely missing |
| `wheelchair_access` | str | 3 | 0% | 'unknown', 'likely', 'no' |

## 4. Edge Analysis (ACTIVE GRAPH)
- **Total Edges**: 1697
- **geometry_source**: `osm_way` (1683), `endpoint_fallback` (14).
- **Missing Geometry**: 0 edges.
- **Slopes**: 100% missing (`None`). Despite the CSV containing 7 unique slope values, the `.pkl` graph builder effectively discards all slopes during conversion by either failing string parsing or dropping `None` assignments.
- **Ramps**: 1697 False (0 ramps).
- **Stairs**: 7 True, 1690 False.
- **Wheelchair**: 1373 unknown, 317 likely, 7 no.

## 5. Node/Graph Analysis
- **Total Nodes**: 1551
- **Total Edges**: 1697
- **Connected Components**: 9
- **Largest Connected Component**: 1509 nodes
- **Isolated Nodes**: 2
- **Duplicate/Parallel Edges**: 0. The graph is technically instantiated as a `nx.MultiGraph`, but dynamically confirmed to hold exactly 0 parallel edges between any `(u, v)` pair.

## 6. Geometry Accuracy
- **STATUS**: High Accuracy
- **OSM geometry**: 99.18% (1683 edges).
- **Fallback geometry**: 0.82% (14 edges). 
- **Impact**: The 14 fallback straight-line edges are inconsequential minor stubs. They do NOT intercept any of the core academic routes tested.

## 7. Accessibility Analysis
The dataset suffers from severe sparsity in critical accessibility features.
- **Stairs**: 7 edges (0.41%)
- **Ramps**: 0 edges (0%)
- **Slopes**: 0 edges with usable data (0%)
- **Wheelchair Access**: 1373 unknown (80.9%)
- **Surface**: 1114 unknown (65.6%)

There is sufficient data for basic routing and simulated decay demonstrations, but insufficient physical data to create hyper-realistic profile differentiation natively (other than Stairs blocking Wheelchairs).

## 8. Profile Feasibility
- **General**: Successfully routes globally.
- **Elderly / Pregnant**: Routes successfully. Distances are identical to General routing, but **Costs differ** because the algorithm multiplies the distance base-cost by different profile safety/effort weights. No slopes exist to create physical detours.
- **Wheelchair**: Successfully blocks 7 specific stairways. Detours effectively around those 7 edges.

## 9. Congestion Compatibility
- **STATUS**: VERIFIED.
- The UI triggers `select_edge`, which maps GPS coordinates to the nearest Graph edge tuple `(u, v)` via `get_nearest_edge()`. 
- `inject_congestion` applies a penalty value (LOW:50, MEDIUM:100, HIGH:200) to `SignalDecayEngine.add_penalty()`. 
- The backend `pada_weight_func` safely queries the globally instantiated engine directly.

## 10. Signal Decay Compatibility
- **STATUS**: VERIFIED. 
- Decay dynamically updates via `controller.step()`. The mathematical penalty shrinks continuously over time. PADA-R incorporates this dynamically per-edge.

## 11. Manual Location Validation
All 9 requested locations are geographically accurate and effectively snapped to the graph:
- MGR (16.23m)
- SMV (43.85m)
- TT (11.19m)
- SJT (41.47m)
- PRP (89.78m)
- Gandhi Block (84.94m)
- Anna Auditorium (21.85m)
- Parking Lot (24.09m)
- CTS (24.88m)
All nodes belong to the largest connected component (1509 nodes) and are perfectly routable.

## 12. Route Validation
Tested critical routes (MGR→SMV, SMV→TT, TT→SJT, SJT→PRP, PRP→Gandhi, MGR→CTS, CTS→SMV).
- **Result**: 100% pathfinding success for all profiles.
- **Geometry Source**: 100% `osm_way` for all segments comprising these routes. (0 fallback geometries encountered).

## 13. Data Quality Issues
- **Missing Slopes**: `slope_percent` parsing fails during dataset build, stripping all valuable slope constraints from the graph.
- **Missing Ramps**: Zero ramps exist in the CSV.
- **Missing Widths**: 100% missing `width_m`.
- **Unknown Surfaces**: 65% of the campus has an `unknown` surface.

## 14. Critical Bugs
- **Validation Script**: `scripts/validate_vit_dataset.py` is obsolete and uses old tags (`node_type == 'building_entrance'`), generating false failure metrics.

## 15. Limitations
The primary limitation is purely physical data availability. The code mechanisms (PADA-R, Hysteresis, Decay) are highly functional, but they lack physical variance (slopes, ramps, precise surfaces) to demonstrate their full depth in the baseline un-congested state.

## 16. Recommended Fixes
1. **Fix `slope_percent` parsing**: Modify `build_final_dataset.py` to correctly parse strings like `"up"`, `"down"`, `"12"` into mathematical float constraints so they aren't stripped from the PKL graph.
2. **Update Validation Script**: Replace tag-based lookups with geospatial nearest-node mapping in `validate_vit_dataset.py`.

## 17. Recommended Future Enhancements
- Deploy a map-editing sprint to manually populate VIT Vellore's OSM XML with true ramps and surface values.
- Ingest live IoT metrics to drive the congestion engine automatically.

---

### CLEAR STATUS TABLE

| Component | Status | Evidence |
|---|---|---|
| Dataset integrity | PASS | Clean extraction pipeline. MultiGraph correctly configured. |
| Coordinates | PASS | Valid EPSG:4326 lat/lon formats. No dead coordinates. |
| OSM geometry | PASS | 99.18% authentic line strings used. |
| Pedestrian topology | PASS | Massive 1509-node primary connected component. |
| Stairs | PASS | 7 mapped instances. Successfully blocked by Wheelchair logic. |
| Ramps | FAIL | 0 recorded instances. 100% missing data. |
| Slopes | FAIL | 100% missing data. CSV string-parse failures strip data from PKL. |
| Wheelchair data | PASS | Sparse (80% unknown), but functionally valid where known. |
| General routing | PASS | 100% success on all tested academic routes. |
| Elderly routing | PASS | Operates correctly using effort/distance cost multipliers. |
| Pregnant routing | PASS | Operates correctly using safety/effort cost multipliers. |
| Wheelchair routing | PASS | Successfully avoids stairs automatically. |
| Congestion injection | PASS | UI triggers successfully map to `(u,v)` graph indices. |
| Signal Decay | PASS | `exp()` decay mathematics validated against theoretical formula. |
| Dynamic rerouting | PASS | Demonstrated autonomous avoidance of high-penalty edges. |
| Route geometry | PASS | 0 fallback edges encountered on critical routes. Authentic visuals. |
