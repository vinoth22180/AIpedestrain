# POST-CLEANUP COMPLETE PROJECT AUDIT - PART 2 of 2
## VIT Vellore Campus Pedestrian Routing System
### Audit Date: 2026-09-23 | READ-ONLY - NO CODE MODIFIED

---

## SECTION 8: API ENDPOINT INVENTORY

ACTIVE ENDPOINTS:
| Endpoint | Method | Status |
|---|---|---|
| /api/config | GET | ACTIVE - returns dataset config (center, zoom) |
| /api/route | POST | ACTIVE - PRIMARY. PADA-R + DARR route computation |
| /api/routes/candidates | POST | ACTIVE - DARR candidates only |
| /api/weather | GET | ACTIVE - live Open-Meteo at VIT coords |
| /api/landmarks | GET | ACTIVE - all 9 VIT locations |
| /api/academic_blocks | GET | ACTIVE - VIT academic blocks GeoJSON |
| /api/pedestrian_network | GET | ACTIVE - full graph edges GeoJSON |
| /api/pedestrian_network/stats | GET | ACTIVE - edge type counts |
| /api/accessibility/resilience | GET | ACTIVE - AOC + ARL for OD pair |
| /api/accessibility/collapse-risk | GET | ACTIVE - collapse risk all profiles |
| /api/accessibility/critical-edges | GET | ACTIVE - CAD-ranked edges GeoJSON |
| /api/routing/simulate-assignment | POST | ACTIVE - MAL counterfactual (no frontend caller) |

MISSING ENDPOINTS (called by frontend, return 404):
| /api/sensors | MISSING - MapCanvas.jsx calls this, gets 404 |
| /api/signals | MISSING - MapCanvas.jsx calls this, gets 404 |

No /api/simulation/* endpoints exist.
No /api/weather/simulate endpoint exists.
No /api/congestion/* endpoints exist.

---

## SECTION 9: PADA-R IMPLEMENTATION

Algorithm: Dijkstra (nx.shortest_path with custom pada_weight_func)

Cost function:
Total Cost = w_dist x dist
           + w_acc  x dist x M_acc
           + w_eff  x dist x M_eff
           + w_saf  x dist x M_saf
           + w_cong x congestion_penalty
           + w_sig  x gamma x (1 if signals else 0)
           + w_decay x delta x DecayEngine.get_penalty(u,v)
           + weather_impact(weather, edge, profile)
           + waterlogging_cost(water_depth, profile)

User Profiles:
| Profile | Speed m/s | Stairs | Max Slope | Min Width |
|---|---|---|---|---|
| general | 1.4 | ALLOWED | none | 0.0m |
| elderly | 0.9 | PENALIZED (+5.0) | 8% | 0.6m |
| pregnant | 1.0 | PENALIZED (+3.5) | 8% | 0.6m |
| wheelchair | 0.8 | FORBIDDEN (inf) | 6% | 0.9m |

Accessibility gates:
- wheelchair + stairs=True -> INACCESSIBLE (cost=inf)
- wheelchair + wheelchair_accessible=False -> INACCESSIBLE
- wheelchair + water_depth >= 3.0cm -> INACCESSIBLE
- elderly/pregnant + water_depth >= 5.0cm -> INACCESSIBLE
- any + water_depth >= 8.0cm -> INACCESSIBLE

Active cost factors (wired):
+ Distance (base)
+ Accessibility multiplier (stairs, surface, slope)
+ Effort multiplier (incline, smoothness)
+ Safety multiplier (signals, tactile paving)
+ Signal Decay: decay_engine.get_penalty(u, v) [wired, currently always 0]
+ Live weather: weather_service.get_current_weather() [LIVE from Open-Meteo]
+ Waterlogging depth: edge_data.get(water_depth, 0.0) [wired, currently always 0]
+ Congestion penalty: edge_data.get(congestion_penalty, 0.0) [wired, currently always 0]
+ Route stability: retains current route if improvement < threshold

Currently zero-contribution (no input source):
- congestion_penalty: always 0.0
- water_depth: always 0.0
- signals: OSM VIT data has no signal tags - always empty list

---

## SECTION 10: DARR IMPLEMENTATION

Candidate generation (candidate_generator.py):
3 distinct routes via 3 Dijkstra objectives on profile-accessible subgraph:

| Route | ID | Weight Function |
|---|---|---|
| Route 1 | route_1_fastest | length_m |
| Route 2 | route_2_congestion | length_m + 2.0 x decay_penalty |
| Route 3 | route_3_resilience | length_m + cad x 60 + 1.5 x decay |

Diversity enforcement: if routes are identical, creates penalty-copy graph (2.5x or 3.0x weights on prior path edges) to force different paths.
Fallback: nx.shortest_simple_paths() (Yens algorithm) if still fewer than 3.

Per-candidate metrics computed:
- total_distance (m)
- estimated_travel_time (distance / speed_mps)
- accessibility_compatibility (per-profile bool dict)
- current_dynamic_cost (length + decay)
- predicted_dynamic_cost (length + predicted decay at arrival time)
- critical_edge_count (edges with CAD >= 0.4)
- marginal_accessibility_loss (MAL) via counterfactual
- accessibility_resilience_score (ARL)
- accessibility_collapse_risk (NORMAL/ELEVATED/WARNING/CRITICAL)

DARR Scorer:
RouteScore = w_dist x distance + w_time x time + w_dyn x predicted_cost
           + w_crit x critical_edges x 25 + w_coll x risk_penalty + w_mal x MAL x 80
Lower = better. Flexible reallocation: general profile selects alternative if fastest has MAL > 0.4 and alternative within 180s extra travel time.

Is DARR called on every /api/route request? YES.
api.py:100-112 calls compute_darr_routes() synchronously.
Output included in JSON: candidate_routes, selected_candidate, network_resilience, collapse_risk, decision_summary.

Resilience Engine (resilience.py):
- AOC (Accessibility Option Count): max-flow with unit capacities -> integer count edge-disjoint paths
- ARL (Accessibility Resilience Level): AOC adjusted for Jaccard overlap + shared bottleneck penalty
- CAD (Critical Accessibility Dependency): per-edge score - 1.0 if bridge, 0.5 if min-degree<=2, 0.3 if degree=3, 0.1 otherwise

Collapse Predictor (collapse_predictor.py):
- Projects Signal Decay events 300s forward
- Removes edges with predicted_decay >= 150 from constrained-profile subgraph
- Recomputes AOC/ARL on projected graph
- Returns NORMAL/ELEVATED/WARNING/CRITICAL + risk_score + time_to_critical

MAL (Marginal Accessibility Loss) - counterfactual.py:
- Simulates 25 pedestrians assigned to candidate path
- Applies congestion_per_pedestrian x (1 + cad) x load per edge
- Removes edges from wheelchair subgraph if penalty >= 50 and CAD >= 0.6
- MAL = max(0, ARL_before - ARL_after)

Accessible Subgraph (subgraph.py):
- Filters edges by: stairs, wheelchair tag, slope_percent, width_m, water_depth
- Returns nx.MultiGraph/Graph with only feasible edges for profile

---

## SECTION 11: SIGNAL DECAY IMPLEMENTATION

File: src/signal_decay/engine.py (152 lines)

Classes:
- DecayEvent (dataclass): event_id, edge(u,v), initial_penalty, current_penalty, lambda_rate, created_time, last_update_time, event_type, is_active
- SignalDecayEngine: manages events dict, decay computation
- decay_engine: module-level singleton

Mathematical formula:
D_e(t) = D0 x exp(-lambda x delta_t)
where:
  D0 = initial_penalty
  lambda = lambda_rate (default: 0.005 per second)
  delta_t = time elapsed since last update
  Expiry threshold epsilon = 0.1 (from weights.yaml)

Half-life at default lambda: ln(2)/0.005 = 138.6 time units

Methods:
- add_penalty(u, v, penalty, event_type, lambda_rate): creates forward+reverse DecayEvents
- update_time(current_time): decays all active events incrementally
- get_penalty(u, v): sums all active event penalties for edge (u,v)
- predict_penalty_at(u, v, target_time): non-mutating forward prediction
- get_active_events(): exports state for frontend visualization
- reset(): clears all events

Multi-event: YES. Multiple events accumulate on same edge. get_penalty() sums all.

Current callers in production:
- pada_r/cost_model.py:86: decay_engine.get_penalty(u, v) - EVERY edge during routing
- darr/candidate_generator.py:61,72,213,218: get_penalty() and predict_penalty_at()
- darr/collapse_predictor.py:53-56: iterates decay_engine.events, calls predict_penalty_at()

CRITICAL FINDING:
After the simulation cleanup, there is NO mechanism to create a Signal Decay event.
- src/simulation/ directory is empty - old SimulationController that called add_penalty() is gone
- No API endpoints in api.py call decay_engine.add_penalty()
- No background task creates decay events
- /api/routing/simulate-assignment does NOT call add_penalty()

The decay_engine starts with zero events and remains zero for the entire server lifetime.
Signal Decay is fully wired into routing but receives no input. It is ready infrastructure with no event source.

---

## SECTION 12: LIVE WEATHER

Service: src/weather/service.py - weather_service singleton
Coordinates: lat=12.9692, lon=79.1559 (VIT Vellore - hardcoded, confirmed correct)

Open-Meteo URL:
https://api.open-meteo.com/v1/forecast?latitude=12.9692&longitude=79.1559
  &current=temperature_2m,apparent_temperature,precipitation,rain,
           weather_code,wind_speed_10m,relative_humidity_2m

Fields: temperature_2m, apparent_temperature, precipitation, rain, weather_code (mapped to Clear/Cloudy/Fog/Drizzle/Rain/Thunderstorm), wind_speed_10m, relative_humidity_2m

Cache: TTL=300s (5min), stale threshold=3600s (1hr), freshness: LIVE/STALE/UNAVAILABLE

Weather-to-routing (weather/impact.py):
- Rain: precipitation x 0.5 x rain_sensitivity x surface_modifier x (distance/100)
- Heat: (apparent_temp-35) x 0.2 x heat_sensitivity x (distance/100) if temp > 35C
- Profile-specific sensitivity multipliers (wheelchair unpaved rain: 3.0x)

Weather simulation override: REMOVED. set_simulation_override() does not exist in current WeatherService.

VERDICT: Live weather IMPLEMENTED and ACTIVE. Simulation override REMOVED.

---

## SECTION 13: ACCESSIBILITY DATA

Data files (data/vit_vellore/processed/):
| File | Size | Status |
|---|---|---|
| barriers.geojson | 45 bytes | EFFECTIVELY EMPTY |
| ramps.geojson | 45 bytes | EFFECTIVELY EMPTY |
| stairs.geojson | 5,075 bytes | Some data |
| crossings.geojson | 16,936 bytes | Data present |
| subways.geojson | 16,059 bytes | Data present |
| slopes.geojson | 1,263,587 bytes | Extensive data |
| pedestrian_edges.geojson | 1,263,587 bytes | Extensive data |

Edge attribute status:
+ stairs: PRESENT in graph, used in routing
+ slope_percent: PRESENT, used in routing
+ slope_status: PRESENT, used in routing
+ surface: PRESENT, used in routing
+ crossing: PRESENT, used in routing
+ barrier: PRESENT but barriers.geojson is 45 bytes (empty) - effectively no barriers in VIT OSM
+ subway: PRESENT
+ ramp: PRESENT but ramps.geojson is 45 bytes (empty) - effectively no ramps in VIT OSM
+ highway: PRESENT
+ wheelchair/wheelchair_accessible: Partially present - OSM VIT data sparse
~ width_m: Code reads it, very sparse in OSM data
~ smoothness_value: Code reads it, very sparse in OSM
~ tactile_paving: Code reads it, almost certainly absent in VIT OSM
+ congestion_penalty: Present (default 0.0 - no live source)
+ water_depth: Present (default 0.0 - no live source)
X Lighting: NOT IMPLEMENTED
X Curb cuts: NOT IMPLEMENTED
X Time-of-day restrictions: NOT IMPLEMENTED

Critical: ramps.geojson and barriers.geojson are 45 bytes = JSON shell with no features.
Wheelchair routing operates by absence of stairs/slopes, not by confirmed presence of ramps.

---

## SECTION 14: MULTI-ROUTE BEHAVIOR

Number of candidates: Up to 3 (route_1_fastest, route_2_congestion, route_3_resilience)
Colors: Blue, Amber, Emerald

Generation: 3 Dijkstra variants on accessible subgraph, penalty-copy diversity enforcement, Yens fallback.
Route diversity: NOT GUARANTEED on sparse graph. Node-list equality check only. No geographic diversity enforcement.
Scoring: Multi-factor weighted. Lower = better. Profile-specific weights.
Selection: DARR scorer. General profile uses MAL-aware reallocation rule.

Route click behavior (MapCanvas.jsx):
Click on candidate-routes-line -> get route_id -> setSelectedCandidate(matched) -> visual highlight updates.
Clicking does NOT trigger route recalculation. PADA-R serves original primary route unchanged.

Dynamic candidate regeneration: NOT IMPLEMENTED. One computation per click of Find Route button.

---

## SECTION 15: DYNAMIC REROUTING STATUS

What triggers rerouting NOW:
| Trigger | Reroutes? |
|---|---|
| User clicks Find Accessible Route | YES - primary trigger |
| WeatherPanel 60s poll | NO - display only |
| Signal Decay events | NO - no events exist; no listener calls handleRecalculate() |
| Candidate route click | NO - visual highlight only |
| Graph state changes | NO - graph is static after startup |
| External data push | NO - no push mechanism |

App.jsx has handleRecalculate() which reuses lastRequest.current to issue background recalculation (isBackground=true, suppresses loading state). BUT handleRecalculate() is defined and NEVER CALLED by any component, timer, or event listener.

VERDICT: Rerouting is ENTIRELY MANUAL. User must click Find Accessible Route to get updated route.

---

## SECTION 16: HARDWARE STATUS

Search for: ESP32, MPU650, MPU6500, MPU6050, accelerometer, gyroscope, IMU, BLE, firmware, wearable, UART, serial, GPS
Searched files: *.py, *.js, *.jsx, *.ts, *.md, *.yaml, *.json

RESULT: ZERO MATCHES FOUND.

NO HARDWARE INTEGRATION EXISTS.
No ESP32 code, no sensor ingestion, no IMU processing, no BLE/WiFi reader, no GPS, no firmware, no wearable integration.

---

## SECTION 17: HARDWARE READINESS (INSERTION POINTS ONLY)

Based on current architecture, the cleanest IoT insertion points:

Option A - Signal Decay injection:
  New endpoint: POST /api/events/sensor { edge_u, edge_v, penalty, event_type }
  -> decay_engine.add_penalty(u, v, penalty_value, event_type)
  -> Immediately affects all future routing calls via get_penalty()
  -> Signal Decay autonomous decay begins from that moment
  Zero changes needed to PADA-R, DARR, or routing logic.

Option B - Edge state write:
  G_base[u][v][k][water_depth] = measured_value (cm)
  -> Affects subgraph filtering and waterlogging cost model
  Zero changes needed to routing logic.

Both options: next /api/route call automatically picks up updated state.
PADA-R cost function already reads decay_engine.get_penalty() and edge data.
DARR candidate generator already reads decay_engine.get_penalty().
Collapse predictor already reads decay_engine.events for future prediction.

ESP32+MPU6050 specifically: can detect gait disturbance (surface quality), slope (pitch angle), stair detection (step-impact pattern). The primary value is closing the data sparsity gap in slope and surface attributes, which are sparse in VIT OSM data. A confirmed 8% slope on a path currently tagged unknown would meaningfully change wheelchair routing.

---

## SECTION 18: PATENT-RELEVANT MECHANISMS

| Mechanism | Implemented | Location | Description |
|---|---|---|---|
| PADA-R | YES | pada_r/router.py, cost_model.py, profiles.py | Dijkstra with 9-component weighted cost function |
| Signal Decay | YES | signal_decay/engine.py | D(t) = D0 x exp(-lambda x t), multi-event per-edge |
| AOC | YES | darr/resilience.py:calculate_aoc() | Max-flow unit capacities |
| ARL | YES | darr/resilience.py:calculate_arl() | Jaccard-overlap-adjusted AOC with bottleneck penalty |
| CAD | YES | darr/resilience.py:calculate_cad_for_edge() | Bridge detection + degree analysis |
| MAL | YES | darr/counterfactual.py:simulate_assignment() | ARL before/after simulated pedestrian load |
| Collapse Prediction | YES | darr/collapse_predictor.py | 300s forward Signal Decay projection -> predicted ARL |
| Flexible traffic redistribution | YES | darr/scorer.py | MAL-aware route selection - general pedestrians rerouted to protect wheelchair corridors |
| VIT accessibility graph | YES | data/vit_vellore/processed/ | OSMnx-derived campus graph |
| Multiple candidate routes | YES | darr/candidate_generator.py | 3 Dijkstra variants + Yens fallback |
| Profile-specific routing | YES | 4 profiles with distinct cost weights and hard gates | general/elderly/pregnant/wheelchair |
| Accessible subgraph | YES | darr/subgraph.py | Dynamic per-profile edge filtering |
| Live weather integration | YES | weather/service.py + impact.py | Open-Meteo + profile sensitivity |
| Route stability | YES | pada_r/router.py:74-118 | Retains current route if improvement < threshold |

Custom (non-standard) implementations:
- PADA-R multi-profile 9-component cost model
- Signal Decay exponential engine with multi-event accumulation
- DARR 3-candidate diversity with penalty-copy-graph forcing
- AOC/ARL/CAD/MAL resilience measurement framework
- MAL counterfactual via graph-copy perturbation
- Forward collapse prediction by projecting decay events to future ARL

Standard technology used:
- Dijkstra (NetworkX), OSMnx/GraphML/GeoJSON, Open-Meteo API, React+Vite, FastAPI, Max-flow (NetworkX)

Strongest technically distinctive mechanism already implemented:
MAL-aware flexible reallocation + Signal Decay combination.
When a general pedestrian is routed, DARR checks whether the fastest path imposes MAL > 0.4 on wheelchair corridors (by simulating 25 pedestrian loads via graph perturbation). If yes and alternative within 180s extra, slower route is selected to preserve wheelchair network resilience. Fully implemented, runs every request, combines counterfactual simulation + ARL theory + profile-aware sacrifice.

NOTE: Not a legal patent assessment. Technical observations only.

---

## SECTION 19: CRITICAL GAPS

Biggest remaining technical gap:
The entire dynamic system operates on zero dynamic input at runtime.
- Signal Decay engine: zero events
- Congestion penalties: always 0
- Waterlogging depths: always 0
- Weather costs: work but are tiny relative to base costs

The three DARR candidate routes differ only by:
1. Static distance
2. Static CAD (bridge analysis on static graph)
3. Static MAL (simulated, not measured)

All three candidates respond to identical costs. There is NO genuine dynamic differentiation at runtime.

What ESP32+MPU6050 specifically contributes:
Primary value = closing the data sparsity gap. OSM VIT data has sparse slope/surface attributes. An MPU6050 wearable can confirm actual slope (pitch angle) and surface quality (gait disturbance). A confirmed 8% slope on a path currently tagged slope_percent=None would gate that path for wheelchair routing, which currently it does not. This is the highest-leverage sensor contribution.

---

## SECTION 20: LIMITATIONS

CRITICAL:
- No dynamic event source: Signal Decay/congestion/waterlogging have no injectors in production
- No automatic rerouting: handleRecalculate() exists but never called by anything
- /api/sensors and /api/signals: missing endpoints called by MapCanvas.jsx every page load (404 errors)

HIGH:
- Ramps/barriers data: ramps.geojson and barriers.geojson are 45 bytes each (empty). Wheelchair routing = absence of stairs, not confirmed ramp presence.
- VIT OSM accessibility data: smoothness, tactile_paving, width_m effectively empty. Code reads them but contributes nothing.
- Candidate diversity not guaranteed on sparse graph
- README.md: completely describes Melbourne/Streamlit app. Entirely wrong.
- Dead frontend components: SignalDecayMonitor, RouteExplanationPanel, StatsOverlay mounted nowhere

MEDIUM:
- No user GPS: From/To are dropdown selections only, not real position
- No persistent state: all dynamic state resets on server restart
- requests library not in requirements.txt but used by weather/service.py
- Dead source files not deleted: src/data/melbourne_loader.py, src/data/fetch_datasets.py
- Empty directories still present: src/simulation/, src/congestion/, src/traffic/
- scratch/test_waterlogging.py imports non-existent modules (crashes if run)

LOW:
- No integration tests against real VIT graph (3 test files, all unit tests only)
- Nearest-node search is O(N) - iterates all nodes
- DARRDecisionPanel hardcodes Protected Threshold: 2.0
- WeatherState.is_valid checks for FRESH but service sets LIVE (works but naming inconsistent)

---

## SECTION 21: FACTUAL HANDOFF FOR NEXT AI SESSION

SYSTEM: FastAPI backend + React 19/Vite frontend. VIT Vellore campus pedestrian routing. Accessibility-aware multi-route generation. Functional end-to-end. Melbourne gone from production paths. Simulation UI gone.

DATASET: VIT Vellore campus OSMnx-derived pedestrian network at data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl. 9 manually verified VIT locations (MGR, SMV, TT, SJT, PRP, Gandhi Block, Anna Auditorium, Parking Lot, CTS). Ramps/barriers files essentially empty (45 bytes each).

FRONTEND: React 19 + Vite 8 + MapLibre GL. Active: Sidebar, MapCanvas, DARRDecisionPanel, CandidateRoutesPanel, WeatherPanel, MapLegend. Dead (exist but not mounted): SignalDecayMonitor, RouteExplanationPanel, StatsOverlay. MapCanvas calls /api/sensors and /api/signals which dont exist -> 404 errors every page load.

BACKEND: FastAPI. Single process. Global G_base MultiGraph. No DB, no message queue, no background workers. decay_engine and weather_service are module-level singletons.

ROUTING (PADA-R): Dijkstra in nx.shortest_path with custom pada_weight_func. Inputs: origin/destination [lon,lat], profile. Nearest node by Euclidean distance O(N). Cost = distance + accessibility_multipliers + congestion(0) + signal_decay(0) + weather + waterlogging(0). Profile hard gates: wheelchair blocks stairs and slope>6%. Route stability retains current if improvement < threshold.

DARR: 3 candidates on accessible subgraph using 3 Dijkstra objectives. MAL, CAD, collapse risk per candidate. MAL-aware selection for general profile. All computed per request synchronously.

SIGNAL DECAY: Engine fully implemented (signal_decay/engine.py). D(t) = D0*exp(-lambda*t), lambda=0.005/s, epsilon=0.1. Multi-event per edge. Wired into every cost calculation. HAS ZERO ACTIVE EVENTS AT ALL TIMES. add_penalty() never called by any running code.

WEATHER: Open-Meteo live at VIT Vellore (12.9692, 79.1559). 5min cache. Profile-specific penalties. Works correctly.

ACCESSIBILITY: stairs/slopes/surfaces/crossings/subways present (varying sparsity). Ramps: effectively absent. Barriers: effectively absent. Wheelchair tag: sparse. congestion_penalty and water_depth in edge model but always 0.0.

API: 12 active endpoints. Key: POST /api/route (primary), GET /api/landmarks, GET /api/academic_blocks, GET /api/weather, GET /api/pedestrian_network, GET /api/pedestrian_network/stats, GET /api/accessibility/* (3 endpoints), POST /api/routing/simulate-assignment. MISSING (called by frontend): GET /api/sensors, GET /api/signals.

TESTS: 3 unit test files only. test_signal_decay.py (4 math tests), test_darr.py, test_routing_dynamic.py. No integration tests against real VIT graph.

BUGS:
1. MapCanvas.jsx: /api/sensors and /api/signals -> 404 on every page load
2. scratch/test_weather_decay.py: imports set_simulation_override() which doesnt exist
3. scratch/test_waterlogging.py: imports src.simulation.waterlogging_engine and src.simulation.controller which dont exist
4. requests library not in requirements.txt but used by weather/service.py
5. README.md describes Melbourne/Streamlit app - entirely wrong

HARDWARE: NONE. Zero references to ESP32, MPU6050, accelerometer, IMU, GPS anywhere.

BEST IOT INSERTION POINT: decay_engine.add_penalty(u, v, penalty_value, event_type). New POST /api/events/sensor endpoint calling this immediately propagates to PADA-R and DARR with zero changes to routing logic.

STRONGEST CURRENT MECHANISM: MAL-aware flexible traffic redistribution. General pedestrians rerouted away from wheelchair-optimal corridor when MAL > 0.4 and alternative within 180s extra. Runs every request. Combines counterfactual ARL simulation + profile-aware altruistic routing.

BIGGEST GAP: Signal Decay has no input. Dynamic routing is static at runtime. Closing this gap with any event source (sensors, reported incidents, external data) transforms it from sophisticated static router to genuinely adaptive system.
