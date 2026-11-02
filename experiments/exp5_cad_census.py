"""
PCVC Experiment 5: Network-Wide Critical Accessibility Dependency (CAD) Census
===============================================================================
Scans the entire accessible subgraph for each profile and identifies all edges
with CAD â‰¥ 0.4 (high accessibility criticality). Also computes the differential
CAD (Î”_CAD = CAD_profile - CAD_general) to isolate profile-exclusive bottlenecks.

This experiment quantifies:
  - Total count and fraction of critical accessible edges per profile
  - Bridge/cut-edge prevalence across profiles
  - Profile-exclusive bottlenecks invisible to general routing

Outputs:
  experiments/results/exp5_cad_census.json       -- per-profile critical edge lists
  experiments/results/exp5_cad_summary.csv       -- profile-level summary
  experiments/logs/exp5_cad_census.log

Paper Tables / Figures Addressed:
  Table VIII â€“ CAD distribution and critical edge counts per profile
  Fig. 5     â€“ Differential CAD (Î”_CAD) heatmap across profiles
"""

import os
import sys
import json
import csv
import logging
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.graph_manager import load_or_build_graph
from src.darr.resilience import resilience_engine
from src.darr.subgraph import subgraph_manager

PROFILES = ["wheelchair", "elderly", "pregnant", "general"]
CAD_THRESHOLD = 0.4    # Minimum CAD to be considered "critical"
DIFF_CAD_THRESHOLD = 0.3  # Minimum Î”_CAD to be considered "profile-exclusive"

RESULTS_DIR = os.path.join(ROOT, "experiments", "results")
LOGS_DIR    = os.path.join(ROOT, "experiments", "logs")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

log_path = os.path.join(LOGS_DIR, "exp5_cad_census.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def run():
    log.info("=" * 70)
    log.info("PCVC Experiment 5 â€“ Network-Wide CAD Census")
    log.info("=" * 70)

    t0 = time.time()
    G = load_or_build_graph()
    n_nodes = len(G.nodes())
    n_edges = G.number_of_edges()
    log.info(f"Graph: {n_nodes} nodes, {n_edges} edges.")

    # Pre-compute bridge caches for all profiles
    log.info("Pre-computing bridge caches for all profilesâ€¦")
    bridge_caches: dict = {}
    subgraph_sizes: dict = {}
    for profile in PROFILES:
        G_sub = subgraph_manager.get_accessible_subgraph(G, profile)
        bridge_caches[profile] = resilience_engine._get_bridges(G_sub)
        subgraph_sizes[profile] = {
            "nodes": len(G_sub.nodes()),
            "edges": G_sub.number_of_edges(),
        }
        log.info(
            f"  [{profile}] subgraph: {subgraph_sizes[profile]['nodes']} nodes, "
            f"{subgraph_sizes[profile]['edges']} edges, "
            f"{len(bridge_caches[profile])//2} bridges"
        )

    # â”€â”€ Main CAD Scan â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    all_results: dict[str, list] = {}
    summary_rows = []

    for profile in PROFILES:
        log.info(f"\n[{profile.upper()}] Identifying critical edges (CADâ‰¥{CAD_THRESHOLD})â€¦")
        t_p = time.time()

        critical = resilience_engine.identify_critical_edges(
            G,
            profile_name=profile,
            threshold=CAD_THRESHOLD,
        )

        # Count CAD distribution
        cad_1_0 = sum(1 for e in critical if e["cad"] >= 1.0)
        cad_0_5 = sum(1 for e in critical if 0.5 <= e["cad"] < 1.0)
        cad_0_4 = sum(1 for e in critical if 0.4 <= e["cad"] < 0.5)
        n_cut   = sum(1 for e in critical if e["is_cut_edge"])
        n_diff  = sum(1 for e in critical if e.get("differential_cad", 0) >= DIFF_CAD_THRESHOLD)
        n_sub_edges = subgraph_sizes[profile]["edges"]
        n_total_critical = len(critical)
        pct_critical = round(100 * n_total_critical / n_sub_edges, 2) if n_sub_edges else 0.0

        elapsed_p = time.time() - t_p
        log.info(
            f"  Critical edges: {n_total_critical}/{n_sub_edges} ({pct_critical}%) "
            f"| Cut: {n_cut} | CAD=1.0: {cad_1_0} | "
            f"Profile-exclusive (Î”_CADâ‰¥{DIFF_CAD_THRESHOLD}): {n_diff} | "
            f"time={elapsed_p:.1f}s"
        )

        log.info(f"  Top-10 critical edges:")
        log.info(
            f"    {'Name':<40} {'CAD':>6} {'Î”_CAD':>7} {'Cut':>5}"
        )
        for e in critical[:10]:
            name_trunc = e["name"][:38] if len(e["name"]) > 38 else e["name"]
            log.info(
                f"    {name_trunc:<40} {e['cad']:>6.3f} "
                f"{e.get('differential_cad', 0.0):>7.3f} "
                f"{str(e['is_cut_edge']):>5}"
            )

        all_results[profile] = critical

        summary_rows.append({
            "profile":               profile,
            "subgraph_nodes":        subgraph_sizes[profile]["nodes"],
            "subgraph_edges":        subgraph_sizes[profile]["edges"],
            "n_critical":            n_total_critical,
            "pct_critical":          pct_critical,
            "n_cut_edges":           n_cut,
            "n_cad_1_0":             cad_1_0,
            "n_cad_0_5_to_1":        cad_0_5,
            "n_cad_0_4_to_0_5":      cad_0_4,
            "n_profile_exclusive":   n_diff,
            "top_edge_name":         critical[0]["name"] if critical else "N/A",
            "top_edge_cad":          critical[0]["cad"] if critical else 0.0,
        })

    # â”€â”€ Cross-profile comparison â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    log.info("\n" + "=" * 70)
    log.info("Cross-Profile CAD Summary:")
    log.info(
        f"{'Profile':<12} {'SubEdges':>9} {'Critical':>9} {'%':>7} "
        f"{'Cut':>6} {'Excl':>6}"
    )
    log.info("-" * 60)
    for row in summary_rows:
        log.info(
            f"{row['profile']:<12} {row['subgraph_edges']:>9} "
            f"{row['n_critical']:>9} {row['pct_critical']:>7.2f}% "
            f"{row['n_cut_edges']:>6} {row['n_profile_exclusive']:>6}"
        )

    # â”€â”€ Save JSON â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Strip non-serializable coords for the JSON (keep metadata only)
    serializable_results = {}
    for profile, edges in all_results.items():
        serializable_results[profile] = [
            {k: v for k, v in e.items() if k != "coordinates"}
            for e in edges
        ]

    json_path = os.path.join(RESULTS_DIR, "exp5_cad_census.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "experiment":      "exp5_cad_census",
                "cad_threshold":   CAD_THRESHOLD,
                "diff_threshold":  DIFF_CAD_THRESHOLD,
                "profiles":        PROFILES,
                "subgraph_sizes":  subgraph_sizes,
                "per_profile":     serializable_results,
            },
            f, indent=2, default=str,
        )
    log.info(f"\nFull CAD census â†’ {json_path}")

    # â”€â”€ Save CSV â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    csv_path = os.path.join(RESULTS_DIR, "exp5_cad_summary.csv")
    fieldnames = [
        "profile", "subgraph_nodes", "subgraph_edges",
        "n_critical", "pct_critical",
        "n_cut_edges", "n_cad_1_0", "n_cad_0_5_to_1", "n_cad_0_4_to_0_5",
        "n_profile_exclusive", "top_edge_name", "top_edge_cad",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)
    log.info(f"CAD summary CSV â†’ {csv_path}")

    elapsed = time.time() - t0
    log.info(f"\nExperiment 5 completed in {elapsed:.2f}s")
    return all_results


if __name__ == "__main__":
    run()

