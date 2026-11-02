# VIT Vellore Academic Block Dataset
    
## Purpose
A highly focused, clean, academic-block-only pedestrian routing dataset for Signal Decay algorithm tests.

## Geometry and Topology
- **Nodes**: 1551
- **Edges**: 1697
- **Academic Blocks Mapped**: 10
- **Stairs Mapped**: 7
- **Ramps Mapped**: 0
- **Connected Components**: 9
- **Isolated Nodes**: 2
- **Self Loops**: 0

## Data Constraints Enforced
- **Strict Scope**: Only academic blocks (SJT, TT, MB, etc.) are included. Hostels, mess halls, and irrelevant facilities are aggressively filtered out.
- **Topological Integrity**: Dead-end edges unrelated to the academic routing core were iteratively pruned.

## Validation Results

## Old vs New Comparison
**OLD (Full Campus)**:
- Buildings: 156 (includes non-academic noise)
- Nodes: 271
- Edges: 377
- Pruning: None (dead-ends retained)

**NEW (Academic Blocks Only)**:
- Buildings: Strictly limited to Academic Blocks.
- Graph Topology: Subgraph connecting exactly the specified blocks, dead-ends dynamically pruned.
- Testing: Alternative Path guarantees established.
