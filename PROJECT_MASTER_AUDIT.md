# PROJECT MASTER AUDIT
**VIT Vellore Accessibility-Aware Dynamic Pedestrian Rerouting System**
**Date**: September 2026

## 1. Executive Summary
This document provides a comprehensive, code-level forensic audit of the Accessibility-Aware Dynamic Pedestrian Rerouting System for VIT Vellore. It verifies that the core proof-of-concept (POC) components—PADA-R and the Signal Decay mechanism—are successfully implemented. No external IoT sensor data is currently connected; the system relies entirely on simulated injections.

## 2. Complete System Architecture
- **Data Layer**: Geospatial extraction from OpenStreetMap (OSM) combined with raw CSV parameters, built into a NetworkX MultiGraph and persisted as a Python pickle file.
- **Routing Engine Layer**: PADA-R cost function integrating static physical costs and dynamic temporal costs (Signal Decay) scaled by user profiles.
- **Simulation Layer**: A software clock that tracks simulated time (300s ticks) and triggers decay updates for localized congestion events.
- **API/Server Layer**: FastAPI serving REST endpoints for route computation, simulation orchestration, and graph geometry serving.
- **Presentation Layer**: React-based SPA rendering MapLibre GL JS elements.

## 3. Technology Stack
- **Frontend**: React 18/19, Vite, MapLibre GL, react-map-gl
- **Backend**: Python 3.x, FastAPI, Uvicorn
- **Graph & Algorithms**: NetworkX (Dijkstra), math (exponential functions)
- **Geospatial Processing**: GeoPandas, Shapely, OSMnx (via build scripts)

## 4. Current Project Workflow
1. **Startup**: FastAPI loads the NetworkX graph `vit_vellore_academic_pedestrian_network.pkl`.
2. **Routing Request**: User selects origin/destination and profile. Frontend posts to `/api/route`.
3. **Cost Calculation**: Dijkstra dynamically calculates edge weights merging static attributes with current dynamic decay penalties.
4. **Hysteresis Gate**: Evaluates if the new path surpasses the stability threshold before replacing the active route.
5. **Congestion Injection**: Clicking an edge injects a penalty, which decays over time.

## 5. Dataset Source & Provenance
The pedestrian dataset (`vit_vellore_academic_pedestrian_network.pkl`) is constructed by `build_final_dataset.py`. It merges a raw `map.osm` XML file and a previously provided CSV (`friend_base_pedestrian_network.csv`).

## 6. Dataset Structure
- **STATUS**: VERIFIED
- **EVIDENCE**: Python script runtime inspection of `vit_vellore_academic_pedestrian_network.pkl`.
- **FILE**: `data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl`
- **Node Count**: 1551 nodes.
- **Edge Count**: 1697 edges.
- **Graph Format**: NetworkX `MultiGraph`.
- **Parallel Edges**: 0 instances of parallel edges. Although the graph is a MultiGraph object, every node pair has at most 1 edge connecting them.
- **Edge Attributes**: `length_m`, `highway` (path type), `surface`, `width_m`, `stairs` (boolean), `ramp` (boolean), `wheelchair` (yes/no/unknown).
- **Slope Data**: **All 1697 edges lack slope data**. 0% of the edges have a `slope_percent` attribute. The builder script intentionally strips `None` values rather than fabricating `0.0`. 
- **Endpoint Fallback Geometry**: 14 edges (0.82% of the graph) use synthetic straight-line geometries (`endpoint_fallback`). The remaining 1683 edges (99.18%) use highly accurate OSM geometries. No critical academic path relies on fallback geometry.

## 7. Geographic Accuracy Audit
- **STATUS**: VERIFIED
- **EVIDENCE**: Edge inspection reveals 99.18% of edges possess authentic Shapely `LineString` coordinate arrays extracted directly from OSM ways.
- **IMPACT**: The route drawn on the map adheres accurately to real-world pedestrian paths.
- **RECOMMENDED ACTION**: The 14 fallback edges can remain, as they are not on major routes.

## 8. Pedestrian Graph Audit
- **STATUS**: VERIFIED
- **EVIDENCE**: 1551 nodes, 1697 edges, 9 connected components, 2 isolated nodes.
- **IMPACT**: The graph is predominantly one massive connected component. 

## 9. Academic Location Audit
- **STATUS**: VERIFIED
- **EVIDENCE**: A programmatic test verified the exact lat/lon coordinates of all 9 mandatory locations: MGR, SMV, TT, SJT, PRP, Gandhi Block, CTS, Anna Auditorium, Parking Lot.
- **Nearest Snapped Nodes**:
  - MGR (16.23m away)
  - SMV (43.85m away)
  - TT (11.19m away)
  - SJT (41.47m away)
  - PRP (89.78m away)
  - Gandhi Block (84.94m away)
  - Anna Auditorium (21.85m away)
  - Parking Lot (24.09m away)
  - CTS (24.88m away)
- **IMPACT**: All locations map successfully to the graph. The dataset provides continuous pathing between all these points.

## 10. PADA-R Algorithm Audit
- **STATUS**: VERIFIED
- **FILE**: `src/pada_r/cost_model.py` and `router.py`
- **EVIDENCE**: The algorithm calculates per-edge costs correctly by extracting edge attributes (`surface`, `stairs`), evaluating the feasibility gate, and summing distance + effort + safety + congestion + decay. The MultiGraph loop is implemented in `pada_weight_func` and safely handles standard edges since no actual parallel edges exist.

## 11. Accessibility Profile Audit
- **STATUS**: VERIFIED
- **FILE**: `src/pada_r/profiles.py` & `frontend/src/components/Sidebar.jsx`
- **EVIDENCE**: Only 4 profiles exist universally across the stack: General, Elderly, Pregnant, Wheelchair. The `wheelchair` profile properly rejects stair edges (`INACCESSIBLE`). Pregnant and Elderly apply custom effort multipliers. No stale profiles exist in the UI.

## 12. Signal Decay Algorithm Audit
- **STATUS**: VERIFIED
- **FILE**: `src/signal_decay/engine.py`
- **EVIDENCE**: The implementation `math.exp(-event.lambda_rate * event_delta_t)` is mathematically identical to the target formula `D(t) = D0 * exp(-lambda * t)`. Lambda is hardcoded to 0.005.

## 13. Congestion Injection Audit
- **STATUS**: VERIFIED
- **FILE**: `src/api.py` (/api/simulation/inject_congestion)
- **EVIDENCE**: User clicks are correctly snapped via `get_nearest_edge`. Injecting LOW/MEDIUM/HIGH applies 50/100/200 penalty respectively. The penalty is applied bidirectionally to `(u, v)` and `(v, u)` handling the undirected graph traversal.

## 14. Dynamic Rerouting Audit
- **STATUS**: VERIFIED
- **EVIDENCE**: Full end-to-end Python test (`test_congestion.py`) on TT -> SJT.
  - Baseline route: 531.3 cost.
  - After HIGH injection: The route recalculates and finds an alternate path (cost 543.6), completely avoiding the congested edge.
  - After 900s: The penalty decays from 200.0 to 2.22. 
  - Hysteresis: The system evaluates the active alternate route (543.6) vs the now-recovered baseline (531.3 + 2.22 = 533.52). The difference (10.08) is less than the `stability_threshold` (15.0). The system correctly holds the alternate route to prevent oscillation.

## 15. Frontend/UI Audit
- **STATUS**: VERIFIED
- **FILE**: `frontend/src/components/StatsOverlay.jsx` & `RouteExplanationPanel.jsx`
- **EVIDENCE**: The old Cost Breakdown section is completely removed from the UI. `RouteExplanationPanel.jsx` is effectively dead code (unimported).
- **IMPACT**: The UI is clean and strictly matches requirements.

## 16. Backend/API Audit
- **STATUS**: VERIFIED
- **FILE**: `src/api.py`
- **EVIDENCE**: 9 endpoints serve the UI effectively using REST. Simulation endpoints safely manipulate the global `SignalDecayEngine` state. 

## 17. Route Visualization Audit
- **STATUS**: VERIFIED
- **FILE**: `frontend/src/components/MapCanvas.jsx`
- **EVIDENCE**: START and DESTINATION markers appear correctly. The blue route line renders precisely along the OSM line strings. Directional arrows exist. "Blue node-dot artifacts" have been successfully hidden via layer filtering. Map auto-fits to route bounds.

## 18. Current Working Features
- Complete coordinate-based pedestrian routing.
- Real-time PADA-R cost evaluation with dynamic multi-profile weights.
- Exponential time-decay simulation engine with UI injection.
- Hysteresis anti-oscillation gate.
- Clean MapLibre GL UI with decay visualizations.

## 19. Confirmed Bugs
- **BUG 1: Broken Dataset Validation Script**
  - **STATUS**: FAILED
  - **FILE**: `scripts/validate_vit_dataset.py`
  - **FUNCTION**: `find_entrance(block_id)`
  - **ROOT CAUSE**: The script looks for `node_type == 'building_entrance'` and `academic_block_id`, which no longer exist in the final pipeline.
  - **IMPACT**: Prints false-negative routing failures for valid routes like SMV to CBMR.
  - **RECOMMENDED ACTION**: Update the script to use proximity-based nearest node lookups exactly like the production backend.

## 20. Potential Bugs
- **Stability Threshold Confusion**: The `STABLE_RETAINED` hysteresis is mathematically correct but might appear as a "bug" to users if a route doesn't bounce back perfectly to the absolute shortest path after a decay event expires.

## 21. Dataset Limitations
- **Slopes**: 100% of slopes are missing (None).
- **Ramps**: 0% of edges are marked as ramps.
- **Wheelchair Tags**: Heavily reliant on default `unknown` fallbacks due to sparse OSM data.

## 22. Algorithm Limitations
- **Dijkstra Scaling**: Runs optimally for VIT's size, but could bottleneck if the graph expands to 50,000+ edges without heuristic A* implementation.

## 23. Patent/Novelty Analysis
The combination of:
1. Extracting localized static OSM pedestrian geometries.
2. Embedding a continuous exponential mathematical decay formula (`D0 * exp(-lambda * t)`) directly into a Dijkstra edge-weight traversal.
3. Coupling it with a hysteresis "stability gate" tuned distinctly for separate physical accessibility profiles (wheelchair vs general).
...represents a specific and novel implementation of adaptive pedestrian routing without relying on central traffic infrastructure.

## 24. Implemented vs Future Features
- **Implemented**: Software simulation of congestion, PADA-R, mapping.
- **Future/Not Implemented**: ESP32 IoT hardware sensors, live crowd tracking, WebSockets, Bluetooth RSSI ingestion.

## 25. Recommended Next Improvements
1. **IoT Dummy Endpoint**: Build a `/api/sensors/ingest` endpoint to receive hardware signals.
2. **WebSocket Integration**: Push decay updates to the frontend instead of polling.
3. **Manual Dataset Tagging**: Manually tag slopes and ramps for key VIT Vellore walkways directly in the dataset pipeline.

## 26. Complete End-to-End Test Results
```text
=== END-TO-END CONGESTION INJECTION TRACE ===
1. Baseline Route (TT -> SJT)
Cost=531.3, Dist=531.3m, Nodes=24

2. Injecting HIGH congestion on edge (14058849426, 5487048333)
[DECAY] Event created: D0: 200.0 | Lambda: 0.005 | Time: 0.0

3. Recalculating Route (0s decay)
Cost=543.6, Dist=543.6m, Nodes=21, Status=PERSONALIZED_OPTIMAL
Route changed? True (Congested edge successfully avoided)

4. Simulating Decay (900s elapsed)
[DECAY] Event updated: Elapsed: 900.0s | Current penalty: 2.22

5. Recalculating Route (900s decay)
Recovered: Cost=543.6, Dist=543.6m, Nodes=21, Status=STABLE_RETAINED
(Path held due to stability hysteresis preventing micro-oscillations)
```

## 27. Final Project Status

**A. ALREADY IMPLEMENTED**
- Graph generation from OSM + CSV.
- PADA-R Dynamic Routing Engine.
- Signal Decay mathematical engine.
- React frontend & FastAPI backend.

**B. VERIFIED WORKING**
- Hysteresis routing gate.
- 4 strict accessibility profiles.
- 9 critical VIT anchors properly snapping.
- Complete exponential decay cycle.

**C. BUGS REQUIRING FIX**
- `scripts/validate_vit_dataset.py` uses obsolete tags.

**D. DATASET LIMITATIONS**
- 0 recorded ramps.
- Missing slope data globally (stripped to `None`).

**E. FUTURE IMPLEMENTATION**
- ESP32 live congestion ingestion.
- WebSockets for seamless UI ticking.

**F. POTENTIAL PATENT/NOVELTY FEATURES**
- Profile-adaptive hysteresis gating combined with temporal exponential decay in a static mesh graph.
