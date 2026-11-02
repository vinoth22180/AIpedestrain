"""
PCVC Experiment 4: Probe Safety & Closed-Loop Return Validation
===============================================================
For each profile's top-priority PCVC target, validates the Closed-Loop
Safe-Return Rule across all 4 probe candidate profiles:

  A probe is eligible IFF:
    (1) The probe profile can physically traverse the target edge
    (2) An accessible outbound path exists from anchor â†’ target edge
    (3) A safe return path exists from target edge â†’ anchor

Computes:
  - Probe eligibility matrix [profile Ã— probe]
  - Travel cost comparison (outbound + traversal + return)
  - Rejection reasons per ineligible probe

Outputs:
  experiments/results/exp4_probe_safety.json
  experiments/results/exp4_probe_safety.csv
  experiments/logs/exp4_probe_safety.log

Paper Tables / Figures Addressed:
  Table VII â€“ Probe eligibility matrix and travel cost per target-profile pair
  Section IV-D â€“ Closed-loop safe-return validation results
"""

import os
import sys
import json
import csv
import logging
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.graph_manager import load_or_build_graph
from src.pcvc.controller import PCVCController, DEFAULT_PCVC_WEIGHTS
from src.pcvc.probe_selector import select_best_probe, find_nearest_landmark_anchor

PROFILES = ["wheelchair", "elderly", "pregnant", "general"]
UNCERTAINTY_THRESHOLD = 0.4
TOP_K = 1  # We only need the single top target per profile for probe validation

RESULTS_DIR = os.path.join(ROOT, "experiments", "results")
LOGS_DIR    = os.path.join(ROOT, "experiments", "logs")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

log_path = os.path.join(LOGS_DIR, "exp4_probe_safety.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

PROBE_PROFILES = ["general", "elderly", "pregnant", "wheelchair"]


def run():
    log.info("=" * 70)
    log.info("PCVC Experiment 4 â€“ Probe Safety & Closed-Loop Return Validation")
    log.info("=" * 70)

    t0 = time.time()
    G = load_or_build_graph()
    log.info(f"Graph: {len(G.nodes())} nodes, {G.number_of_edges()} edges.")

    controller = PCVCController(weights=DEFAULT_PCVC_WEIGHTS)
    all_results = {}
    flat_rows = []

    for target_profile in PROFILES:
        log.info(f"\n[TARGET PROFILE: {target_profile.upper()}]")
        plan = controller.compute_verification_targets(
            G,
            target_profile=target_profile,
            top_k=TOP_K,
            uncertainty_threshold=UNCERTAINTY_THRESHOLD,
        )

        if not plan.selected_target:
            log.warning(f"  No verification target found for profile '{target_profile}'.")
            all_results[target_profile] = {
                "target": None,
                "probe_results": [],
            }
            continue

        target = plan.selected_target
        log.info(
            f"  Top target: {target.name} (Priority={target.priority_score:.3f} "
            f"U={target.uncertainty:.3f} Î”ARL={target.impact.delta_arl:.3f} "
            f"CAD={target.impact.cad:.3f} Cut={target.impact.is_cut_edge})"
        )

        # Find nearest landmark anchor for this edge
        anchor_name, anchor_node, anchor_coords = find_nearest_landmark_anchor(G, target.u)
        if anchor_node is None:
            anchor_node = target.u
            anchor_name = f"Node_{target.u}"
            anchor_coords = None

        log.info(f"  Anchor: {anchor_name} (node={anchor_node})")

        # Run closed-loop safe-return check for ALL probe profiles
        probe_results = select_best_probe(
            G,
            target.u,
            target.v,
            target.key,
            anchor_node=anchor_node,
            anchor_name=anchor_name,
            candidate_profiles=PROBE_PROFILES,
        )

        # Matrix row header
        log.info(
            f"\n  {'Probe':<12} {'Eligible':>8} {'Out(m)':>8} {'Ret(m)':>8} "
            f"{'Cost(m)':>8} {'Reason'}"
        )
        log.info("  " + "-" * 80)

        probe_records = []
        for p in probe_results.eligible_probes + probe_results.rejected_probes:
            log.info(
                f"  {p.profile:<12} {'âœ“' if p.eligible else 'âœ—':>8} "
                f"{p.outbound_distance_m:>8.0f} {p.return_distance_m:>8.0f} "
                f"{'inf' if p.travel_cost == float('inf') else p.travel_cost:>8} "
                f"  {p.reason[:60]}"
            )
            record = {
                "target_profile":      target_profile,
                "target_edge_id":      target.edge_id,
                "target_edge_name":    target.name,
                "target_priority":     target.priority_score,
                "target_uncertainty":  target.uncertainty,
                "target_delta_arl":    target.impact.delta_arl,
                "target_cad":          target.impact.cad,
                "target_is_cut":       target.impact.is_cut_edge,
                "anchor_name":         anchor_name,
                "probe_profile":       p.profile,
                "eligible":            p.eligible,
                "outbound_dist_m":     p.outbound_distance_m,
                "return_dist_m":       p.return_distance_m,
                "travel_cost_m":       p.travel_cost if p.travel_cost != float("inf") else "inf",
                "rejection_reason":    "" if p.eligible else p.reason,
            }
            probe_records.append(record)
            flat_rows.append(record)

        log.info(
            f"\n  Selected probe: {probe_results.selected_probe or 'NONE'} | "
            f"Reason: {probe_results.selection_reason}"
        )

        all_results[target_profile] = {
            "target": {
                "edge_id":        target.edge_id,
                "name":           target.name,
                "priority_score": target.priority_score,
                "uncertainty":    target.uncertainty,
                "delta_arl":      target.impact.delta_arl,
                "cad":            target.impact.cad,
                "is_cut_edge":    target.impact.is_cut_edge,
            },
            "anchor_name":    anchor_name,
            "anchor_node":    anchor_node,
            "selected_probe": probe_results.selected_probe,
            "probe_results":  probe_records,
        }

    # â”€â”€ Save JSON â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    json_path = os.path.join(RESULTS_DIR, "exp4_probe_safety.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "experiment":    "exp4_probe_safety",
                "probe_profiles": PROBE_PROFILES,
                "per_target_profile": all_results,
            },
            f, indent=2, default=str,
        )
    log.info(f"\nFull probe safety records â†’ {json_path}")

    # â”€â”€ Save flat CSV â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    csv_path = os.path.join(RESULTS_DIR, "exp4_probe_safety.csv")
    fieldnames = [
        "target_profile", "target_edge_id", "target_edge_name",
        "target_priority", "target_uncertainty", "target_delta_arl",
        "target_cad", "target_is_cut",
        "anchor_name",
        "probe_profile", "eligible",
        "outbound_dist_m", "return_dist_m", "travel_cost_m",
        "rejection_reason",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)
    log.info(f"Probe safety CSV â†’ {csv_path}")

    elapsed = time.time() - t0
    log.info(f"\nExperiment 4 completed in {elapsed:.2f}s")
    return all_results


if __name__ == "__main__":
    run()

