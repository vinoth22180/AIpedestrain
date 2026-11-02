# SIGNAL DECAY VALIDATION
**VIT Vellore Accessibility-Aware Dynamic Pedestrian Rerouting System**

## 1. MATHEMATICAL VERIFICATION
The Signal Decay implementation uses the exact formula:
`D(t) = D0 * exp(-lambda * t)`
where `lambda` = 0.005.

## 2. CONGESTION INJECTION & DECAY TEST
A test was performed on the TT → SJT corridor (Baseline Cost = 531.3).

1. **NO CONGESTION**: System selects shortest physical path (531.3m).
2. **HIGH CONGESTION INJECTED**: Penalty `D0 = 200.0` applied to a central route edge.
3. **IMMEDIATE REROUTING**: The system instantaneously drops the active path, finding a 543.6m alternative that avoids the congested edge entirely.
4. **SIMULATION TICK (300s)**: Penalty decays to `200 * exp(-0.005 * 300) = 44.62`.
5. **SIMULATION TICK (600s)**: Penalty decays to `9.95`.
6. **SIMULATION TICK (900s)**: Penalty decays to `2.22`.
7. **HYSTERESIS RECOVERY**: At 900s, the original path's total cost evaluates to `531.3 + 2.22 = 533.52`. The alternative route is `543.6`. The difference (`10.08`) is below the 15.0 `stability_threshold`. PADA-R holds the alternative route to prevent minor oscillation.
8. **SIMULATION TICK (1200s)**: Penalty decays to `0.49`.

## 3. CONCLUSION
Signal Decay successfully bridges the gap between active routing (PADA-R) and temporal event management. The penalty binds cleanly to graph tuples `(u, v)` and automatically dissolves over simulated time.
