# Phase 2 Novelty Contribution

## Technical Implementation and Novelty
The technical novelty established in Phase 2 involves the creation of a fully integrated **Accessibility-Aware Dynamic Edge State** that consumes real-world environmental context and algorithmically interacts with profile-specific mobility constraints.

### The Unified Edge State Architecture
The fundamental advancement is moving beyond simple "distance + penalty" routing. The architecture now explicitly represents:
- **Static Environment**: Immutable geographic features.
- **Accessibility State**: Granular classifications of physical constraints (e.g., stairs, ramps, slopes).
- **Live Weather State**: Live observational context (e.g., precipitation, temperature) polled and cached from Open-Meteo.
- **Dynamic Congestion State**: Crowding penalties.
- **Temporal Event State**: Signal Decay metrics that handle congestion dissipation over time.

### Interaction Models
The system deterministically evaluates interactions rather than simply summing factors:
- **Weather ↔ Surface Interaction**: Rain does not equally penalize all paths. The engine dynamically assigns significantly higher traversal costs to unpaved or dirt paths during precipitation events, while paved paths receive lower baseline rain penalties.
- **Weather ↔ Profile Interaction**: The computed weather penalties are scaled by the mobility profile (e.g., Wheelchair profiles exhibit a `3.0x` sensitivity modifier to wet/muddy unpaved paths compared to General profiles).
- **Temporal Decoupling**: The architecture strictly decouples Weather (environmental context, updated via external polling) from Congestion (temporal events, decayed via exponential Signal Decay). This allows PADA-R to navigate multiple independent dynamic phenomena simultaneously without logical interference.

### Stability
Route hysteresis remains functional, ensuring that momentary weather-induced cost changes or decaying congestion do not cause the user's navigational instructions to aggressively oscillate, thereby solving a critical user-experience challenge in dynamic mobile routing.
