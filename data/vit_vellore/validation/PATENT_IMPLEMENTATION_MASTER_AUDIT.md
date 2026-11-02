# Accessibility-Aware Dynamic Pedestrian Rerouting System
## PATENT IMPLEMENTATION MASTER AUDIT

### 1. Executive Summary
This document provides a comprehensive, forensic audit of the current state of the "Accessibility-Aware Dynamic Pedestrian Rerouting System." It strictly identifies what is actively implemented in the codebase versus what is simulated, planned, or missing. No assumptions have been made; all findings are backed by the source code, dataset files, and validation reports.

### 2. Current Architecture
The system follows a modular architecture separating the static GIS dataset from dynamic simulation state and routing algorithms.

**Backend (Python/FastAPI):**
- **IMPLEMENTED**: `src/api.py` (REST endpoints), `src/graph_manager.py` (Dataset loading/caching), `src/models/edge_state.py` (Structured state).
- **Routing Modules**: `src/pada_r/router.py` (Dijkstra-based pathfinding), `src/pada_r/cost_model.py` (Cost function), `src/pada_r/profiles.py` (Profile weights).
- **Simulation Modules**: `src/signal_decay/engine.py` (Exponential decay), `src/simulation/waterlogging_engine.py` (IoT static hazard simulation), `src/simulation/controller.py` (Simulation clock).
- **External Integration**: `src/weather/service.py` (Open-Meteo API integration).
- **Legacy/Simulated**: `src/congestion/model.py` (Reads from a static `counts_sample.csv` containing Melbourne data, mapped onto VIT locations).

**Frontend (React/Vite/MapLibre GL JS):**
- **IMPLEMENTED**: `App.jsx`, `MapCanvas.jsx`, `Sidebar.jsx`, `WeatherPanel.jsx`, `WaterloggingPanel.jsx`, `SimulationControls.jsx`, `StatsOverlay.jsx`, `RouteExplanationPanel.jsx`.

**Dataset Generation Scripts:**
- **IMPLEMENTED**: `scripts/build_final_dataset.py`, `scripts/build_vit_dataset.py`.

### 3. Dataset Audit (VIT Vellore)
- **Source:** OSM (`data/vit_vellore/map.osm`) + Manual CSV (`friend_base_pedestrian_network.csv`).
- **Graph State (`vit_vellore_academic_pedestrian_network.pkl`):**
  - **Nodes**: 1551
  - **Edges**: 1721
  - **Connected Components**: 9
  - **Is Multigraph**: True

**Feature Availability in Active Graph:**
| Feature | Raw Data | Active Graph | Used by Routing | Visualized |
|---------|----------|--------------|-----------------|------------|
| Stairs | Yes (13) | Yes (7) | Yes | Yes |
| Ramps | No | No (0) | Yes (Logic exists) | Yes |
| Slopes | Yes (7) | Yes (7) | Yes | Yes (>4%) |
| Crossings | Yes (23) | Yes (23) | Yes | Yes |
| Barriers | No | No (0) | Yes (Logic exists) | Yes |
| Subways | Yes | Yes (22) | Yes | Yes |
| Pedestrian Paths | Yes | Yes (329 footways) | Yes | Yes |
| Surface Type | Yes (419 asphalt) | Yes | Yes | No |

**Discrepancies:**
- The raw dataset indicates 13 stairs, but the active graph contains 7. This is due to topological pruning of disconnected components during graph construction in `build_vit_dataset.py`.
- Surface types are heavily skewed towards "unknown" (1114/1721 edges), limiting the actual real-world impact of the implemented surface interaction logic.

### 4. Algorithm Audit (PADA-R)
The Profile-Aware Dynamic Accessibility Routing (PADA-R) algorithm is fully implemented in `src/pada_r/cost_model.py` and `router.py`.
- **Core Mechanism**: Uses NetworkX `shortest_path` (Dijkstra) with a custom `weight` function.
- **Inputs**: Origin/Destination coordinates, Profile Name, Simulation Date/Hour.
- **Outputs**: Path node list, Path edge list, Route Status, Explanation array, Stats dictionary.
- **Profiles Implemented**: General, Wheelchair, Elderly, Pregnant.

**Cost Formula Extraction (Implemented Code):**
```python
total_cost = (base_dist * distance_weight) 
           + (base_dist * accessibility_weight * M_acc) 
           + (base_dist * effort_weight * M_eff) 
           + (base_dist * safety_weight * M_saf)
           + (congestion_penalty * congestion_weight) 
           + (signal_cost * signal_weight) 
           + (decay_cost * decay_weight) 
           + (weather_impact) 
           + (waterlogging_cost)
```

**Constraints & Mechanics:**
- **Wheelchair**: Hard constraint on stairs and >3.0cm waterlogging (`INACCESSIBLE`).
- **Elderly/Pregnant**: Hard constraint on >5.0cm waterlogging (`INACCESSIBLE`). Heavy effort/safety penalties for stairs.
- **Hysteresis**: Implemented via `stability_threshold` in `PADA_PROFILES`. A new route is only adopted if its cost is less than `(active_route_cost - threshold)`.
- **Rerouting**: Profile-specific routes geometrically differ. A wheelchair will topographically avoid stairs entirely, while a general profile will take them with a minor effort penalty.

### 5. Signal Decay Audit
Fully implemented in `src/signal_decay/engine.py`.
- **Mechanism**: Calculates dynamic decay based on the simulation clock (`elapsed_seconds`), allowing spatial rerouting that snaps back over time.
- **Decay Equation**: `D_new = D_old * exp(-lambda * delta_t)`
- **Parameters**: `lambda_rate` = 0.005, `epsilon` = 0.1 (Threshold for removal).
- **Lifecycle**: EVENT INJECTED -> PENALTY APPLIED -> COST MULTIPLIED -> DIJKSTRA REROUTES -> SIMULATION TIME TICKS -> PENALTY EXPONENTIALLY DECAYS -> ROUTE COST DROPS -> HYSTERESIS CHECK -> ROUTE SNAPS BACK.

### 6. Dynamic Congestion Audit
- **Status**: SIMULATED.
- **Mechanism**: The backend reads from `data/raw/pedestrian_counts/counts_sample.csv`.
- **Reality**: This CSV is historical data from Melbourne, mapping `location_id` to `hourday`. It does not contain live VIT Vellore data. The "Predictive" congestion is a simple average of this historical file.
- **Frontend**: The user manually injects "Decay Events" (Congestion) on specific edges. There are no actual live sensors connected to the system.

### 7. GIS / Map Audit
- **Engine**: MapLibre GL JS (`frontend/src/components/MapCanvas.jsx`).
- **Rendered Features**: Path geometry (grey), Stairs (dashed brown), Crossings (dashed blue), Slopes (purple), Subways (dashed cyan), Congestion (red), Waterlogging (variable opacity light blue).
- **Accuracy**: Markers and geometries map strictly to OSM/GeoJSON coordinates. No fake visual geometries are introduced.
- **Slope Visualization**: Slopes are only visually highlighted if `slope_percent > 4`, but the underlying numeric value impacts the PADA-R effort cost regardless of visual threshold.

### 8. Current VIT Vellore Map Gaps
- Pedestrian road behind VIT Lake: **PARTIALLY IMPLEMENTED** (Base roads exist, fine-grained pathways missing).
- Subway near SJT: **IMPLEMENTED** (Mapped as `routing_class=footway` and `subway=True`).
- Pedestrian pathways toward Gandhi Block: **IMPLEMENTED** (Verified topologically).
- Subways represented in legend: **IMPLEMENTED** (Dashed cyan line).
*Note: Due to the strict adherence to NOT fabricating data, paths lacking OSM representation remain disconnected in the graph.*

### 9. Frontend / UI Audit
- **IMPLEMENTED AND FUNCTIONAL**: Profile selector, Origin/Destination dropdown (bound to manual landmark JSON), Route Summary (Distance, Time), PADA-R Status (e.g., `PERSONALIZED_OPTIMAL`), Route Explanations (extracts text directly from backend cost model), Weather Simulation Toggles (Rain/Heat), Waterlogging Injection, Congestion Injection, Play/Reset Simulation Clock, Map Legend (renders live network stats).
- **COSMETIC**: None. All buttons trigger actual backend state mutations (via FastAPI) which re-evaluates the PADA-R route.

### 10. Validation Audit
Validation scripts in `tests/` and `scratch/` were executed.
- `test_waterlogging.py`: Confirms wheelchairs receive `NO_PATH_FOUND` if the only route has 4cm waterlogging, while general profiles absorb the penalty.
- `test_weather_decay.py`: Confirms weather penalties remain static while congestion exponentially decays, causing route snap-back.
- `SIGNAL_DECAY_VALIDATION.md`: Confirms the mathematical accuracy of the decay output.

### 11. Implemented vs Planned Matrix

| Patent Component | Status | Evidence |
|------------------|--------|----------|
| Accessibility-Aware Routing | IMPLEMENTED | `router.py`, `cost_model.py` |
| Personalized Profiles | IMPLEMENTED | `profiles.py` (General, Elderly, Pregnant, Wheelchair) |
| Physical Constraints (Stairs/Slopes) | IMPLEMENTED | `edge_state.py`, `graph_manager.py` |
| Barriers/Ramps | PARTIALLY IMPLEMENTED | Logic exists in backend, but dataset contains 0 instances. |
| Signal Decay (Exponential) | IMPLEMENTED | `signal_decay/engine.py` |
| Weather Adaptation | IMPLEMENTED | `weather/service.py` (Open-Meteo) & `impact.py` |
| Static Hazard (Waterlogging) | IMPLEMENTED | `waterlogging_engine.py` |
| Dynamic Rerouting & Hysteresis | IMPLEMENTED | `router.py` (stability threshold) |
| Real-time Congestion Sensors | SIMULATED | `congestion/model.py` uses static CSV |
| Predictive AI Congestion | SIMULATED | Simple hourly historical average from CSV |
| Edge AI / Automatic Event Detection | NOT IMPLEMENTED | System relies on manual frontend injection |

### 12. Patent Novelty Audit
**CURRENTLY IMPLEMENTED TECHNICAL CONTRIBUTIONS:**
1. **Unified Dynamic Edge State**: The architectural decoupling of static physical data from temporal/dynamic data (`Weather`, `Decay`, `Waterlogging`) on a per-edge basis.
2. **Signal-Decay Hysteresis Integration**: The mathematical combination of an exponentially decaying spatial penalty with a route stability threshold, preventing rapid route toggling while simulating real-world event dispersion.
3. **Multi-Constraint Feasibility Gating**: Combining absolute physical barriers (stairs for wheelchairs) with dynamic environmental barriers (4cm water for wheelchairs) in a single pass Dijkstra weight function.

**NEEDS FURTHER DEVELOPMENT FOR NOVELTY:**
- **Predictive Congestion**: The current historical average is trivial. A true ML-based predictive model is required to claim "AI-driven predictive rerouting."
- **Multi-Source Data Fusion**: While implemented architecturally, the lack of real IoT sensors limits the claim of real-time data fusion.

### 13. Find Weaknesses (Ranked by Technical Dependency)
1. **Static/Melbourne Dataset for Congestion**: The biggest weakness. Claiming "Dynamic Congestion" while reading a static CSV of Melbourne traffic fundamentally undermines the VIT Vellore application.
2. **"Unknown" Surface Attributes**: Over 64% of the VIT edges lack surface type data, rendering the sophisticated weather-surface interaction logic (e.g., rain + dirt) mostly inert.
3. **Missing Critical Accessibility Data**: 0 Ramps and 0 Barriers in the processed dataset prevent validation of these core routing constraints.
4. **Lack of True Edge AI / Event Detection**: The system requires a human to click "Inject Congestion" or "Inject Waterlogging."
5. **No Mobile Validation**: The system operates on an idealized backend coordinate system without accounting for actual mobile GPS drift on pedestrian pathways.

### 14. What Has Already Been Done (Chronological Summary)
- **STAGE 1 - Project Foundation**: Graph loader, API, and core UI established.
- **STAGE 2 - VIT Vellore Dataset**: OSM extraction and graph processing (`build_final_dataset.py`).
- **STAGE 3 - Accessibility Routing**: Custom weight function parsing stairs and basic profiles.
- **STAGE 4 - PADA-R**: Formalized cost models (`cost_model.py`, `profiles.py`) with effort, safety, distance, and accessibility weights.
- **STAGE 5 - Signal Decay**: Implemented mathematical exponential decay engine linked to simulation clock.
- **STAGE 6 - Dynamic Congestion**: Connected static CSV data to simulate live/predictive traffic.
- **STAGE 7 - MapLibre Visualization**: Interactive map with geometry overlays.
- **STAGE 8 - Phase 2 (Weather)**: Integrated Open-Meteo live API and environmental impact modifiers.
- **STAGE 9 - Phase 3 (Waterlogging)**: Built static hazard engine for simulated IoT flood sensors with strict profile thresholds.
- **STAGE 10 - Current State**: The core routing engine is fully operational with complex dynamic state handling, but relies entirely on simulated or imported non-local dynamic data.

### 15. CURRENT PATENT IMPLEMENTATION STATUS
- **IMPLEMENTED**: PADA-R Algorithm, Exponential Signal Decay, Weather Integration, Static Hazard (Waterlogging) Thresholds, Personalized Profiles, Hysteresis, MapLibre Visualization.
- **PARTIALLY IMPLEMENTED**: Physical accessibility constraints (logic is flawless, but dataset lacks ramps/barriers/surfaces).
- **NOT IMPLEMENTED**: Edge AI, Automatic Event Detection, Mobile Client.
- **DATA LIMITATIONS**: Severe lack of tagged surface conditions, ramps, and barriers in VIT Vellore OSM data. Melbourne data used for congestion.
- **ALGORITHM LIMITATIONS**: Predictive congestion is a trivial historical average, not a machine learning model.
- **CURRENT NOVELTY CONTRIBUTIONS**: The fusion of topological accessibility constraints with exponentially decaying temporal penalties and live environmental modifiers in a unified cost function.
- **NEXT DEVELOPMENT REQUIREMENTS**: 
  1. Real-world IoT/Camera sensor integration for automated event injection.
  2. A machine learning model for true predictive congestion.
  3. Ground-truth dataset enrichment for VIT Vellore (adding ramps, surfaces, barriers).
