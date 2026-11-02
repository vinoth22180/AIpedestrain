# FULL VIT VELLORE PEDESTRIAN DATASET AUDIT & ROUTING BUG DIAGNOSIS

## Section A: Dataset inventory
**File Analyzed:** `data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl`
- **Graph Type:** `MultiGraph` (undirected, supports parallel edges)
- **Dimensions:** 1551 nodes, 1721 edges.
- **Connectivity:** The graph is disconnected. It contains 9 connected components and 2 completely isolated nodes.
- **Parallel Edges:** 48 edges have parallel variants.
- **Coordinates:** Nodes contain `x` (longitude) and `y` (latitude) in the EPSG:4326 CRS (Lon: 79.138 - 79.173, Lat: 12.957 - 12.994).
- **Edge Lengths:** The dataset contains `length_m` and `geometry_distance_m`. The maximum discrepancy between these values is only ~0.89m.

## Section B: Accessibility attribute inventory
The following attributes were verified in the actual graph data:
| Attribute | Present? | Actual data type | Value examples | Missing values | Reliability and routing use |
|---|---|---|---|---|---|
| `stairs` | Yes | Boolean (str/bool) | `True` (7 edges), `False` (1714 edges) | None | High. Directly used to enforce hard exclusions. |
| `slope_percent` | Yes | Float / String | `2.0` to `12.0` (avg 2.22%) | 7 ('unknown') | High. Used to restrict the pregnant and wheelchair profiles. The 7 unknown values correspond to the 7 stair segments. |
| `wheelchair` | Yes | String | `unknown` (1397), `likely` (317), `no` (7) | None | Moderate. The vast majority of the campus is marked 'unknown', which requires fallback accessibility logic. |
| `barrier` | Yes | String | `no` (1721) | None | Low. No actual barriers are marked in the graph. |
| `ramp` | Yes | Boolean | `True`, `False` | None | High. Used to override strict wheelchair unknown policies. |
| `signals` | No | N/A | N/A | All (1721) | Not present in the dataset. |

**Important Note:** The graph contains no marked barriers. The wheelchair data is overwhelmingly "unknown", though the system handles this safely via a "conservative" unknown data policy.

## Section C: Current routing architecture
1. **Graph Loading:** `src/graph_manager.py` loads the `.pkl` file. If an edge is missing a Shapely `LineString` geometry, it reconstructs a straight line from the `x,y` node coordinates. No weights are overwritten here.
2. **Cost Function:** `src/pada_r/cost_model.py` dynamically computes edge costs by applying multipliers for accessibility, effort, and safety to the base physical length. It also factors in `dynamic_congestion_penalty`, `signal_cost`, `decay_cost`, and live Open-Meteo `weather_cost`.
3. **Router:** `src/pada_r/router.py` uses `nx.astar_path` on the MultiGraph. 
4. **Heuristic:** The A* geographic heuristic correctly calculates the Haversine distance and scales it by the profile's `distance_weight`. Our heuristic admissibility audit confirmed that it never overestimates the actual cost (0 inadmissible edges out of 1721).

## Section D: Shortest-path bug diagnosis
When congestion is absent, the General profile is intended to optimize for pure shortest physical distance (`distance_weight=1.0`, all other weights `0.0`). 

A programmatic audit testing 5000 random origin-destination pairs on the actual graph confirmed that **the underlying A* algorithm strictly returns the true physical shortest path** (0 routing discrepancies).

The root cause of "the returned route appears longer than expected" is a combination of **two separate rendering and hysteresis bugs**, not a failure in A* minimization:

### Root Cause 1: Geometry Traversal Reversal (Visual Bug)
In `src/api.py` (lines ~70-80), the code extracts the Shapely `LineString` coordinates to send to the frontend:
```python
        coords = list(geom.coords)
        route_coords.extend(coords)
```
**The bug:** The underlying graph is an undirected `MultiGraph`. A `LineString` for an edge `(u, v)` has a fixed digitized direction (e.g., U to V). If the route traverses the edge backward (from V to U), `api.py` does not reverse the coordinate list. The frontend consequently draws a path that jumps forward and backward along the segment, producing severe visual zigzags. This makes the correct shortest path *appear* artificially longer and erratic.

### Root Cause 2: Route Stability Hysteresis (State Bug)
In `src/pada_r/router.py` (lines 212-216), a stability check prevents rapid route flickering when congestion fluctuates:
```python
        if current_feasible:
            improvement = current_cost - candidate_cost
            if improvement > 0 and improvement < stability_threshold:
                final_path = active_route_path
                route_status = "STABLE_RETAINED"
```
**The bug:** When heavy congestion occurs, the user is correctly routed onto a longer detour. When the congestion completely clears, the physical cost of the original shortest path drops back to normal. However, if the detour's physical length is only marginally longer than the true shortest path (e.g., 10m longer), the `improvement` (10m) is less than the General profile's `stability_threshold` (15m). 
**Result:** The router permanently traps the user on the detour. The UI shows zero congestion, but the system refuses to snap back to the shortest path.

## Section E: Congestion integration diagnosis
1. The `get_congestion_for_edge` method maps locations to coordinates and properly applies a Haversine radius check to identify affected edges.
2. The `/api/congestion/reset` endpoint calls `congestion_manager.reset_congestion()`, which effectively drops all active YOLO observations.
3. **Signal Decay Engine Bug:** `decay_engine` in `src/signal_decay/engine.py` is entirely decoupled from `congestion_manager`. If an event were injected via `decay_engine.add_penalty()`, a congestion reset would fail to clear it. *However*, a codebase search confirms that `add_penalty()` is currently dead code and is never invoked by the backend API.

## Section F: Ranked findings

| Severity | Issue | File / Function | Root Cause | Impact | Recommended Fix |
|---|---|---|---|---|---|
| **CRITICAL** | Geometry Traversal Reversal | `src/api.py` / `compute_route` | `route_coords.extend(list(geom.coords))` ignores the graph traversal direction (`path[i]` vs `path[i+1]`). | The correct shortest path visually renders as a chaotic zigzag, making it appear longer and incorrect to the user. | Manually check if the first coordinate of `geom.coords` is closest to the traversal origin node. If not, `.reverse()` the coords before extending. |
| **HIGH** | Stability Hysteresis Trap | `src/pada_r/router.py` / `compute_pada_route` | `stability_threshold` logic retains an `active_route_path` even if congestion has fully cleared, trapping users on detours. | Users remain on suboptimal detour paths after congestion drops to 0, directly causing the reported issue. | Add a condition: if both `active_route_path` and `candidate_path` have exactly `0` congestion penalty, bypass the stability threshold and strictly prefer the shortest distance. |

## Section G: Recommended implementation plan
Provide your approval, and I will execute the following safe fixes:
1. **Fix `src/api.py`:** Update the geometry coordinate extraction loop. We will explicitly check if the start node coordinates map to the start or end of the `geom.coords` LineString, and reverse the list if the edge is being traversed backward.
2. **Fix `src/pada_r/router.py`:** Update the stability check. If `dyn_cong == 0` across the entire new candidate path AND the active path, we will skip the `stability_threshold` and strictly return the true shortest candidate path.

## Section H: Validation plan
1. Run a custom path traversal script to ensure that 100% of route coordinate strings perfectly chain `coords[-1] == next_coords[0]`.
2. Simulate a route with high congestion forcing a detour.
3. Reset congestion and request the route again using the detour as the `active_route_path`.
4. Verify that the API immediately drops the detour and returns the shortest path.
