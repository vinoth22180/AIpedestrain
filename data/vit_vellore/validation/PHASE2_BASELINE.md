# Phase 2 Baseline Audit

## Phase 1 Implementation Status
- **EdgeState model**: Not found in the current codebase (likely missing from the repository state). Will be implemented concurrently with Phase 2 as the foundation.
- **PADA-R cost calculation**: Currently located in `src/pada_r/cost_model.py`. Operates directly on raw edge dictionary attributes rather than a structured EdgeState model.
- **SignalDecayEngine**: Located in `src/signal_decay/engine.py`. Manages temporal congestion decay events.
- **Congestion state**: Managed dynamically and injected via API.
- **Frontend state management**: React components with `SignalDecayMonitor.jsx` managing active decay events.
- **MapLibre layers**: Visualizes paths, congestion, and stairs/slopes, but has no weather layers.
- **API architecture**: FastAPI (`src/api.py`) with routes for routing, simulation steps, edge selection, and congestion injection.

## Goal for Phase 2
Since `EdgeState` is foundational for both Phase 1 and Phase 2 and is currently missing, the system will implement the `EdgeState` model (housing physical, accessibility, dynamic, temporal, and confidence states) alongside the `WeatherState` model. The PADA-R router will be updated to consume this unified state.
