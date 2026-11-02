# POST-CLEANUP COMPLETE PROJECT AUDIT - PART 1 of 2
## VIT Vellore Campus Pedestrian Routing System
### Audit Date: 2026-09-23 | READ-ONLY - NO CODE MODIFIED

---

## SECTION 1: MELBOURNE CLEANUP STATUS

### Production Code - Melbourne References

ALL Melbourne references found in production code paths:
NONE FOUND.

Dead files (on disk, NOT imported by any production path):
- src/data/melbourne_loader.py (MELB_PED_URL, download_melbourne_network, load_melbourne_data)
- src/data/fetch_datasets.py (lines 47, 51: Melbourne Open Data API URLs)

Non-production Melbourne references:
- scripts/write_audit.py: ~20 refs in old audit doc generator (historical)
- scratch/test_waterlogging.py: Melbourne coords in test origin (obsolete scratch)
- scratch/test_weather_decay.py: set_simulation_override() calls (obsolete scratch)
- README.md: lines 7, 44 - describes Melbourne network (documentation not updated)
- docs/dataset_sources.md: City of Melbourne (documentation not updated)
- docs/dataset_description.md: Melbourne CBD (documentation not updated)
- outputs/all_code.txt: historical archive (not executed)
- data/vit_vellore/validation/PATENT_IMPLEMENTATION_MASTER_AUDIT.md: lines 15, 83, 136, 158 (historical audit doc)

VERDICT: No Melbourne reference in any active production code path.
graph_cache_melbourne.pkl: ABSENT (only graph_cache_vit_vellore.pkl exists).
Dead source files exist on disk but are unimported - cosmetic gap only.

---

## SECTION 2: SIMULATION REMOVAL STATUS

### Simulation UI Components - Confirmed ABSENT from frontend:
- SimulationControls: NOT FOUND in any JSX file
- CongestionSelectionPanel: NOT FOUND in any JSX file
- WaterloggingPanel: NOT FOUND
- DARRDemoPanel: NOT FOUND
- Play/Pause/Reset UI: NOT FOUND
- LOW/MEDIUM/HIGH injection UI: NOT FOUND

### Simulation API endpoints - Confirmed ABSENT from api.py:
- /api/simulation/step: NOT FOUND
- /api/simulation/reset: NOT FOUND
- /api/simulation/select_edge: NOT FOUND
- /api/simulation/inject_congestion: NOT FOUND
- /api/weather/simulate: NOT FOUND

### Empty shell directories:
- src/simulation/: contains __pycache__ only. ZERO Python files.
- src/congestion/: contains __pycache__ only. ZERO Python files.
- src/traffic/: empty. ZERO files.

### Obsolete scratch files that will crash if run:
- scratch/test_waterlogging.py: imports src.simulation.waterlogging_engine (does not exist)
- scratch/test_waterlogging.py: imports src.simulation.controller (does not exist)
- scratch/test_weather_decay.py: calls weather_service.set_simulation_override() (does not exist)

### Legitimate remaining uses of the word simulate:
1. counterfactual.py:simulate_assignment() - MAL calculation (math only, not UI)
2. collapse_predictor.py comment - describes forward prediction loop (not UI)
3. signal_decay/engine.py:last_update_time=0.0 # simulation clock - time axis only
4. /api/routing/simulate-assignment endpoint - calls counterfactual evaluator (no frontend caller)

VERDICT: Simulation UI system entirely removed. Only algorithmic uses remain.

---

## SECTION 3: VIT VELLORE DATASET

| Property | Value |
|---|---|
| Config file | src/config/datasets.yaml |
| Active key | vit_vellore |
| Graph file | data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl |
| Graph size | 767,489 bytes (~750KB) |
| Companion file | vit_vellore_pedestrian_network.pkl (147KB) |
| Graph type | MultiGraph (OSMnx-derived, undirected) |
| Coordinate system | EPSG:4326 |
| Retrieval date | 2026-09-07 |
| Center lon,lat | 79.161, 12.972 |
| Bounding box | lon: 79.1514-79.1690, lat: 12.9664-12.9775 |

Node/edge count: NOT VERIFIED (read-only audit, no server started).
Loading path: graph_manager.py checks ACTIVE_DATASET == vit_vellore then loads pkl.
No Melbourne graph loaded anywhere.

Edge attributes confirmed in production code:
length/length_m, geometry (Shapely LineString), highway, stairs (bool), ramp (bool),
slope_percent (float/None), slope_status (up/down/measured/unknown), surface, crossing,
barrier, subway (bool), wheelchair, wheelchair_accessible (bool), congestion_penalty (float, default 0.0),
water_depth (float, default 0.0), academic_block_id (node attr).

---

## SECTION 4: VIT LABELS

/api/landmarks (api.py line 135): ACTIVE
- Reads data/vit_vellore/processed/vit_manual_locations.json
- Returns [{name, coords:[lon,lat]}] for ALL locations

/api/academic_blocks (api.py line 152): ACTIVE
- Same source, filtered to type==academic_block
- Returns GeoJSON FeatureCollection of Point features

VIT Locations (9 total, all validation_status=Valid):

| ID | Name | Type |
|---|---|---|
| MGR | MGR | academic_block |
| SMV | SMV | academic_block |
| TT | TT | academic_block |
| SJT | SJT | academic_block |
| PRP | PRP | academic_block |
| Gandhi Block | Gandhi Block | academic_block |
| Anna Auditorium | Anna Auditorium | landmark |
| Parking Lot | Parking Lot | landmark |
| CTS | CTS | academic_block |

Labels NOT hard-coded in frontend. Loaded from real VIT data via API.
MapCanvas.jsx calls fetch(/api/academic_blocks) on mount. Layer is ACTIVE and data-driven.

---

## SECTION 5: FROM/TO LOCATION SELECTION

Data source: /api/landmarks -> vit_manual_locations.json -> 9 VIT locations

Sidebar.jsx mechanism:
1. useEffect fetches /api/landmarks on mount
2. Stores response in locations[] state
3. Renders two <select> dropdowns: From (originIdx) and To (destIdx)
4. Default: originIdx=0, destIdx=1
5. Submit: calls onCalculate(locations[originIdx].coords, locations[destIdx].coords, profile)

Route request: POST /api/route { origin:[lon,lat], destination:[lon,lat], profile:string }
Matches RouteRequest Pydantic model in api.py.

Backend coord handling:
- api.py:52: origin_tuple = (request.origin[0], request.origin[1]) = (lon, lat)
- routing.py:get_nearest_node(): reads data[x] (lon) and data[y] (lat)

VERDICT: From/To selection is FULLY WORKING.

---

## SECTION 6: FRONTEND ARCHITECTURE

Stack: React 19.2.8, Vite 8.2.2, MapLibre GL 6.6.0, react-map-gl 8.1.2, lucide-react 1.39.0
Entry point: frontend/src/main.jsx -> App.jsx

ACTIVE Components:
- App.jsx: State hub. routeData, selectedCandidate, isLoading, error, lastRequest ref. Orchestrates fetch + background recalculate.
- Sidebar.jsx: From/To dropdowns, profile selector, Find Route button, embeds WeatherPanel.
- MapCanvas.jsx (739 lines): MapLibre GL map. Pedestrian network, academic blocks, 3 candidate routes, selected route, origin/dest markers. Candidate click + block popup. CALLS /api/sensors and /api/signals - BOTH MISSING from backend. 404 errors on every page load. State variables sensors[] and signals[] remain empty.
- DARRDecisionPanel.jsx: ARL, AOC, collapse risk card, decision rationale. Embeds CandidateRoutesPanel.
- CandidateRoutesPanel.jsx: 3 route cards with MAL, collapse risk, CAD metrics. Click-to-select.
- WeatherPanel.jsx: Polls /api/weather every 60s. Shows temp, condition, precipitation, wind, freshness badge.
- MapLegend.jsx: Fetches /api/pedestrian_network/stats. Shows feature type counts in legend.

DEAD Components (files exist, never mounted):
- SignalDecayMonitor.jsx: Not imported or mounted anywhere.
- RouteExplanationPanel.jsx: Not imported or mounted anywhere.
- StatsOverlay.jsx: Not imported or mounted anywhere.

---

## SECTION 7: BACKEND ARCHITECTURE

Entry point: uvicorn src.api:app -> FastAPI
Startup: @app.on_event(startup) -> load_or_build_graph()
  - Reads datasets.yaml -> active: vit_vellore
  - Loads vit_vellore_academic_pedestrian_network.pkl
  - Runs _ensure_edge_geometry() -> rebuilds missing Shapely geometries
  - Sets global G_base

Module map:
src/api.py                 FastAPI app, 12 active endpoints
src/graph_manager.py       PKL loading, geometry repair
src/routing.py             get_nearest_node(), get_nearest_edge()
src/accessibility.py       OSM tag extractor (data pipeline only)
src/config/datasets.yaml   active: vit_vellore
src/config/darr_config.yaml 4 profile configs, resilience params
src/config/weights.yaml    dynamic weight scalars
src/models/edge_state.py   EdgeState, WeatherState dataclasses
src/pada_r/router.py       compute_pada_route()
src/pada_r/cost_model.py   calculate_pada_cost(), build_edge_state()
src/pada_r/profiles.py     PADA_PROFILES dict, evaluate_feasibility()
src/darr/router.py         compute_darr_routes() - DARR entry point
src/darr/candidate_generator.py  MultiRouteGenerator - 3 candidates
src/darr/scorer.py         DARRRouteScorer - MAL-aware selection
src/darr/resilience.py     AOC / ARL / CAD computation
src/darr/collapse_predictor.py  300s forward risk prediction
src/darr/counterfactual.py MAL simulation
src/darr/subgraph.py       per-profile accessible subgraph
src/darr/config.py         ProfileConfig, load_darr_config()
src/signal_decay/engine.py SignalDecayEngine, decay_engine singleton
src/weather/service.py     WeatherService singleton, Open-Meteo
src/weather/impact.py      calculate_weather_impact()
src/data/melbourne_loader.py  DEAD FILE - not imported
src/data/fetch_datasets.py    DEAD FILE - not imported
src/simulation/            EMPTY DIRECTORY
src/congestion/            EMPTY DIRECTORY
src/traffic/               EMPTY DIRECTORY

Request flow:
POST /api/route { origin, destination, profile }
-> api.py:get_route()
-> compute_pada_route(G_base, origin_tuple, dest_tuple, profile)
   [snap to nearest node -> Dijkstra 9-component cost -> path]
-> compute_darr_routes(G_base, origin_tuple, dest_tuple, profile)
   [accessible subgraph -> 3 candidates -> MAL, AOC, ARL, CAD -> collapse -> MAL-aware select]
-> JSON: {route, restricted_segments, stats, candidate_routes, selected_candidate, network_resilience, collapse_risk, decision_summary}
-> Frontend: MapCanvas renders, DARRDecisionPanel populates
