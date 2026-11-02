"""
PCVC Phase 6 Experiment E6: Probe Correctness Verification
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Audits probe assignments and path trajectories to verify that no safety or accessibility
constraints are violated during physical verification dispatch:
1. Target edge satisfies selected probe profile constraints
2. Outbound route satisfies selected probe profile constraints
3. Return route satisfies selected probe profile constraints
4. Wheelchair probes NEVER traverse stairs (highway=steps or stairs=True)
5. Slope constraints are strictly respected (< max_slope)
6. Width constraints are strictly respected (>= min_width)

Primary Metric: Constraint Violation Rate (expected ideal = 0.0%)

Outputs:
- results/pcvc/e6/raw/probe_correctness_evaluations.csv
- results/pcvc/e6/summary/probe_correctness_summary.csv
- results/pcvc/e6/summary/e6_summary.json
- results/pcvc/e6/figures/constraint_violation_breakdown.png
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Ensure project root is accessible
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.experiments.common import (
    load_active_graph,
    graph_statistics,
    get_environment_info,
    ensure_result_dirs,
    save_csv,
    save_json,
    get_edge_id
)
from src.pcvc.uncertainty import get_uncertain_edges
from src.pcvc.probe_selector import (
    select_best_probe,
    is_safe_probe,
    _get_edge_length
)
from src.darr.config import get_profile_config
from src.darr.subgraph import subgraph_manager

PROFILES = ["wheelchair", "elderly", "pregnant", "general"]
EVALUATION_CANDIDATE_LIMIT = 50


def verify_edge_against_profile(edge_data: Dict[str, Any], profile_name: str) -> List[str]:
    """
    Directly checks an edge against profile hard constraints:
    Returns list of violation strings (empty if valid).
    """
    violations = []
    cfg = get_profile_config(profile_name)

    # 1. Stairs check
    has_stairs = edge_data.get("stairs", False) or "steps" in str(edge_data.get("highway", ""))
    if not cfg.stairs_allowed and has_stairs:
        violations.append(f"STAIRS_VIOLATION: profile '{profile_name}' cannot traverse stairs/steps")

    # 2. Slope check
    slope = edge_data.get("slope_percent")
    if slope is not None and hasattr(slope, "iloc"):
        slope = slope.iloc[0]
    if cfg.max_slope_percent is not None and isinstance(slope, (int, float)):
        if slope > cfg.max_slope_percent:
            violations.append(f"SLOPE_VIOLATION: slope {slope}% exceeds max {cfg.max_slope_percent}% for '{profile_name}'")

    # 3. Width check
    width = edge_data.get("width_m")
    if width is not None and hasattr(width, "iloc"):
        width = width.iloc[0]
    if cfg.min_width_m > 0 and isinstance(width, (int, float)) and width > 0:
        if width < cfg.min_width_m:
            violations.append(f"WIDTH_VIOLATION: width {width}m below min {cfg.min_width_m}m for '{profile_name}'")

    # 4. Wheelchair tag check
    if profile_name.lower() == "wheelchair":
        wc = edge_data.get("wheelchair")
        wc_acc = edge_data.get("wheelchair_accessible")
        if wc == "no" or wc_acc is False:
            violations.append(f"WHEELCHAIR_INACCESSIBLE: edge explicitly marked wheelchair=no")

    return violations


def reconstruct_path_edges(G: nx.Graph, path_nodes: List[Any]) -> List[Tuple[Any, Any, Any, Dict[str, Any]]]:
    """Extracts edge dictionaries along a node sequence path."""
    edges = []
    for i in range(len(path_nodes) - 1):
        u, v = path_nodes[i], path_nodes[i + 1]
        if G.is_multigraph():
            if G.has_edge(u, v):
                # Pick edge data with min length
                k_best = min(G[u][v].keys(), key=lambda k: _get_edge_length(G[u][v][k]))
                edges.append((u, v, k_best, G[u][v][k_best]))
        else:
            if G.has_edge(u, v):
                edges.append((u, v, 0, G[u][v]))
    return edges


def run_e6(candidate_limit: int = EVALUATION_CANDIDATE_LIMIT) -> Dict[str, Any]:
    dirs = ensure_result_dirs("e6")
    raw_dir = dirs["raw"]
    summary_dir = dirs["summary"]
    figures_dir = dirs["figures"]

    print("=" * 75)
    print("PCVC Experiment E6: Probe Correctness Verification")
    print("=" * 75)

    G = load_active_graph()
    g_stats = graph_statistics(G)
    env_info = get_environment_info()

    # Pre-build subgraphs for all 4 profiles for route reconstruction
    subgraphs = {p: subgraph_manager.get_accessible_subgraph(G, p) for p in PROFILES}

    eval_records: List[Dict[str, Any]] = []
    violation_counts = {
        "stairs": 0,
        "slope": 0,
        "width": 0,
        "other": 0
    }
    violation_examples: List[Dict[str, Any]] = []

    # Test candidate targets across all 4 profiles
    for target_prof in PROFILES:
        cands = get_uncertain_edges(G, profile=target_prof, uncertainty_threshold=0.40, limit=candidate_limit)
        print(f"Verifying probe routes for {len(cands)} candidate targets under profile '{target_prof}'...")

        for cand in cands:
            u, v, k = cand.u, cand.v, cand.key
            eid = cand.edge_id

            # Probe selection
            probe_res = select_best_probe(G, u, v, k)
            selected_probe = probe_res.selected_probe
            anchor_node = probe_res.anchor_node

            if not selected_probe:
                # No probe available; skip path checks
                continue

            G_sub = subgraphs[selected_probe]
            target_edge_data = G[u][v][k] if G.is_multigraph() else G[u][v]

            # 1. Audit Target Edge
            target_violations = verify_edge_against_profile(target_edge_data, selected_probe)

            # 2. Audit Outbound Path
            outbound_violations = []
            if anchor_node != u and G_sub.has_node(anchor_node) and G_sub.has_node(u) and nx.has_path(G_sub, anchor_node, u):
                try:
                    out_path = nx.shortest_path(G_sub, anchor_node, u)
                    out_edges = reconstruct_path_edges(G_sub, out_path)
                    for oe in out_edges:
                        outbound_violations.extend(verify_edge_against_profile(oe[3], selected_probe))
                except Exception as e:
                    outbound_violations.append(f"OUTBOUND_ROUTING_EXCEPTION: {str(e)}")

            # 3. Audit Return Path
            return_violations = []
            if v != anchor_node and G_sub.has_node(v) and G_sub.has_node(anchor_node) and nx.has_path(G_sub, v, anchor_node):
                try:
                    ret_path = nx.shortest_path(G_sub, v, anchor_node)
                    ret_edges = reconstruct_path_edges(G_sub, ret_path)
                    for re in ret_edges:
                        return_violations.extend(verify_edge_against_profile(re[3], selected_probe))
                except Exception as e:
                    return_violations.append(f"RETURN_ROUTING_EXCEPTION: {str(e)}")

            all_violations = target_violations + outbound_violations + return_violations
            is_valid = (len(all_violations) == 0)

            for v_str in all_violations:
                v_lower = v_str.lower()
                if "stairs" in v_lower:
                    violation_counts["stairs"] += 1
                elif "slope" in v_lower:
                    violation_counts["slope"] += 1
                elif "width" in v_lower:
                    violation_counts["width"] += 1
                else:
                    violation_counts["other"] += 1

                if len(violation_examples) < 10:
                    violation_examples.append({
                        "edge_id": eid,
                        "selected_probe": selected_probe,
                        "violation": v_str
                    })

            eval_records.append({
                "target_profile": target_prof,
                "edge_id": eid,
                "u": u, "v": v, "key": k,
                "selected_probe": selected_probe,
                "anchor_node": anchor_node,
                "is_valid": is_valid,
                "num_violations": len(all_violations),
                "target_edge_violations": len(target_violations),
                "outbound_violations": len(outbound_violations),
                "return_violations": len(return_violations),
                "violation_details": "; ".join(all_violations) if all_violations else "NONE"
            })

    df_eval = pd.DataFrame(eval_records)
    save_csv(df_eval, raw_dir / "probe_correctness_evaluations.csv")

    total_assignments = len(df_eval)
    valid_assignments = int(df_eval["is_valid"].sum()) if total_assignments > 0 else 0
    invalid_assignments = total_assignments - valid_assignments
    violation_rate_pct = round(invalid_assignments / total_assignments * 100.0, 2) if total_assignments > 0 else 0.0

    summary_df = pd.DataFrame([{
        "total_evaluated_assignments": total_assignments,
        "valid_assignments": valid_assignments,
        "invalid_assignments": invalid_assignments,
        "constraint_violation_rate_pct": violation_rate_pct,
        "stairs_violations": violation_counts["stairs"],
        "slope_violations": violation_counts["slope"],
        "width_violations": violation_counts["width"],
        "other_violations": violation_counts["other"]
    }])
    save_csv(summary_df, summary_dir / "probe_correctness_summary.csv")

    # Figure: Violation Breakdown
    fig, ax = plt.subplots(figsize=(6, 4), dpi=300)
    cats = ["Stairs", "Slope", "Width", "Other"]
    vals = [violation_counts["stairs"], violation_counts["slope"], violation_counts["width"], violation_counts["other"]]
    if sum(vals) == 0:
        ax.bar(cats, [0, 0, 0, 0], color="#10b981")
        ax.set_ylim(0, 5)
        ax.text(1.5, 2.5, "Zero Constraint Violations (0.0%)\nAll Probe Paths Completely Compliant",
                ha="center", va="center", fontsize=11, fontweight="bold", color="#047857")
    else:
        ax.bar(cats, vals, color="#ef4444")
        ax.set_ylabel("Violation Count")

    ax.set_title("PCVC E6: Probe Safety Constraint Audit", fontsize=11, fontweight="bold")
    plt.tight_layout()
    plt.savefig(figures_dir / "constraint_violation_breakdown.png")
    plt.close(fig)

    e6_json = {
        "experiment": "E6_Probe_Correctness",
        "description": "Trajectory-level safety and accessibility constraint audit for dispatched probes",
        "total_evaluated_assignments": total_assignments,
        "valid_assignments": valid_assignments,
        "invalid_assignments": invalid_assignments,
        "constraint_violation_rate_pct": violation_rate_pct,
        "violation_counts_by_constraint": violation_counts,
        "violation_examples": violation_examples,
        "environment": env_info
    }
    save_json(e6_json, summary_dir / "e6_summary.json")

    print("\n--- E6 PROBE CORRECTNESS SUMMARY ---")
    print(f"Total Assignments Evaluated: {total_assignments}")
    print(f"Valid Assignments: {valid_assignments} ({(100.0 - violation_rate_pct):.2f}%)")
    print(f"Invalid Assignments: {invalid_assignments} (Violation Rate: {violation_rate_pct:.2f}%)")
    print(f"Violations by Constraint: Stairs={violation_counts['stairs']}, Slope={violation_counts['slope']}, Width={violation_counts['width']}")

    return e6_json


if __name__ == "__main__":
    run_e6()
