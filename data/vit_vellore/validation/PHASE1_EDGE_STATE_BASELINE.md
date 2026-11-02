# Phase 1 Edge State Baseline Audit

## Graph Topology
- **Graph Type**: NetworkX MultiGraph (undirected underlying structure but uses NetworkX's `nx.MultiGraph` or standard `nx.Graph`? Wait, I should check this. Let me double check if `G.is_multigraph()` is True. `audit_graph.py` uses `G.edges(data=True)` which works on both, but `pada_r/router.py` does `if G.is_multigraph():`. I'll run one more check.)
- **Node Count**: 1551
- **Edge Count**: 1721

## Current Edge Attributes & Coverage

The current pedestrian routing edges (derived from OSM/GeoDataFrame) contain the following attributes and approximate distributions:

### Accessibility Features
- **stairs**: `False` (1714), `True` (7)
- **ramp**: `False` (1721)
- **slope_percent**: 2.0% (1393), 3.0% (304), 3.5% (12), 12.0% (5), `None` (7)
- **slope_status**: `measured` (1714), `down` (6), `up` (1)
- **crossing**: `no` (1698), `uncontrolled` (17), `marked` (6)
- **barrier**: `no` (1721)
- **subway**: `False` (1699), `True` (22)

### Static / Physical Features
- **highway**: `service` (553), `residential` (391), `footway` (329), `unclassified` (186), `primary` (158), `tertiary` (51), `track` (34), `path` (12), `steps` (7)
- **surface**: `unknown` (1114), `asphalt` (409), `unpaved` (129), `paving_stones` (38), `ground` (12), `paved` (10), `dirt` (6), `compacted` (3)
- **length**: Min 0.09m, Max 477.68m, Avg 32.37m

### Missing / Non-Explicit Attributes
- No unified accessibility cost structure (currently scattered attributes).
- No explicit confidence/freshness markers (e.g., source of truth, last verified time).
- No explicit severity ratings (e.g., stairs = HIGH severity).

## Current Routing Cost Fields
- `distance`
- `accessibility`
- `effort`
- `safety`
- `congestion`
- `signal`
- `decay`

## Current Dynamic Event Fields
- Managed independently by `SignalDecayEngine` using `uuid` keys.
- Edge events track: `initial_penalty`, `current_penalty`, `lambda_rate`, `created_time`, `last_update_time`, `event_type`.
- PADA-R looks up the total penalty directly from the engine per-edge using `decay_engine.get_penalty(u, v)`.
