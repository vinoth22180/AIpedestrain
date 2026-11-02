"""
PCVC Experiment 3: Priority Score Ranking Validation
=====================================================
Runs the full PCVC Controller pipeline for each of the 4 profiles and
validates the multi-attribute Priority Score ranking:

  Priority_Score = w_U*U + w_Î”ARL*(Î”ARL/max_Î”ARL) + w_Î”AOC*(Î”AOC/max_Î”AOC)
                  + w_MAL*(MAL/max_MAL) + w_CAD*CAD

Outputs:
  experiments/results/exp3_priority_ranking.json    -- ranked candidates per profile
  experiments/results/exp3_priority_ranking.csv     -- flat CSV for paper table
  experiments/logs/exp3_priority_ranking.log

Paper Tables / Figures Addressed:
  Table VI  â€“ Top-5 verification targets per profile with Priority Scores
  Fig. 4    â€“ Priority Score composition breakdown (weight attribution)
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

PROFILES = ["wheelchair", "elderly", "pregnant", "general"]
TOP_K = 5
UNCERTAINTY_THRESHOLD = 0.4

RESULTS_DIR = os.path.join(ROOT, "experiments", "results")
LOGS_DIR    = os.path.join(ROOT, "experiments", "logs")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

log_path = os.path.join(LOGS_DIR, "exp3_priority_ranking.log")
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
    log.info("PCVC Experiment 3 â€“ Priority Score Ranking Validation")
    log.info("=" * 70)

    t0 = time.time()
    G = load_or_build_graph()
    log.info(f"Graph: {len(G.nodes())} nodes, {G.number_of_edges()} edges.")
    log.info(f"PCVC Weights: {DEFAULT_PCVC_WEIGHTS}")

    controller = PCVCController(weights=DEFAULT_PCVC_WEIGHTS)
    all_results: dict = {}
    flat_rows = []

    for profile in PROFILES:
        log.info(f"\n[{profile.upper()}] Running PCVC pipelineâ€¦")
        t_p = time.time()

        plan = controller.compute_verification_targets(
            G,
            target_profile=profile,
            top_k=TOP_K,
            uncertainty_threshold=UNCERTAINTY_THRESHOLD,
        )

        elapsed_p = time.time() - t_p
        log.info(f"  Pipeline complete in {elapsed_p:.2f}s")
        log.info(f"  Summary: {plan.summary}")
        log.info(f"  Ranked candidates ({len(plan.ranked_candidates)}):")

        candidate_dicts = []
        for rank, c in enumerate(plan.ranked_candidates, 1):
            cd = {
                "rank":           rank,
                "edge_id":        c.edge_id,
                "name":           c.name,
                "priority_score": c.priority_score,
                "uncertainty":    c.uncertainty,
                "delta_arl":      c.impact.delta_arl,
                "delta_aoc":      c.impact.delta_aoc,
                "mal_impact":     c.impact.mal_impact,
                "cad":            c.impact.cad,
                "is_cut_edge":    c.impact.is_cut_edge,
                "reason":         c.reason,
            }
            candidate_dicts.append(cd)

            log.info(
                f"    #{rank} [{c.priority_score:.3f}] {c.name[:40]:<42} "
                f"U={c.uncertainty:.3f} Î”ARL={c.impact.delta_arl:.3f} "
                f"CAD={c.impact.cad:.3f} Cut={c.impact.is_cut_edge}"
            )

            flat_rows.append({
                "profile":        profile,
                "rank":           rank,
                "edge_id":        c.edge_id,
                "name":           c.name,
                "priority_score": c.priority_score,
                "uncertainty":    c.uncertainty,
                "delta_arl":      c.impact.delta_arl,
                "delta_aoc":      c.impact.delta_aoc,
                "mal_impact":     c.impact.mal_impact,
                "cad":            c.impact.cad,
                "is_cut_edge":    c.impact.is_cut_edge,
            })

        # Probe selection for top target
        if plan.selected_target and plan.probe_selection:
            ps = plan.probe_selection
            log.info(
                f"  Selected Probe: {ps.selected_probe} | "
                f"Anchor: {ps.anchor_name} | Reason: {ps.selection_reason}"
            )
            if ps.eligible_probes:
                log.info("  Eligible probes:")
                for p in ps.eligible_probes:
                    log.info(
                        f"    {p.profile:<12} cost={p.travel_cost:.0f}m "
                        f"out={p.outbound_distance_m:.0f}m "
                        f"ret={p.return_distance_m:.0f}m"
                    )
            if ps.rejected_probes:
                log.info("  Rejected probes:")
                for p in ps.rejected_probes:
                    log.info(f"    {p.profile:<12} reason: {p.reason}")

        all_results[profile] = {
            "summary":           plan.summary,
            "ranked_candidates": candidate_dicts,
            "selected_target":   plan.selected_target.edge_id if plan.selected_target else None,
            "selected_probe":    plan.probe_selection.selected_probe if plan.probe_selection else None,
            "anchor_name":       plan.probe_selection.anchor_name if plan.probe_selection else None,
            "eligible_probes": [
                {
                    "profile":             p.profile,
                    "travel_cost":         p.travel_cost,
                    "outbound_distance_m": p.outbound_distance_m,
                    "return_distance_m":   p.return_distance_m,
                    "reason":              p.reason,
                }
                for p in (plan.probe_selection.eligible_probes if plan.probe_selection else [])
            ],
            "rejected_probes": [
                {"profile": p.profile, "reason": p.reason}
                for p in (plan.probe_selection.rejected_probes if plan.probe_selection else [])
            ],
        }

    # â”€â”€ Save JSON â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    json_path = os.path.join(RESULTS_DIR, "exp3_priority_ranking.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "experiment":    "exp3_priority_ranking",
                "pcvc_weights":  DEFAULT_PCVC_WEIGHTS,
                "top_k":         TOP_K,
                "profiles":      PROFILES,
                "per_profile":   all_results,
            },
            f, indent=2, default=str,
        )
    log.info(f"\nFull ranking results saved â†’ {json_path}")

    # â”€â”€ Save flat CSV â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    csv_path = os.path.join(RESULTS_DIR, "exp3_priority_ranking.csv")
    fieldnames = [
        "profile", "rank", "edge_id", "name",
        "priority_score", "uncertainty",
        "delta_arl", "delta_aoc", "mal_impact", "cad", "is_cut_edge",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)
    log.info(f"Flat ranking CSV saved â†’ {csv_path}")

    elapsed = time.time() - t0
    log.info(f"\nExperiment 3 completed in {elapsed:.2f}s")
    return all_results


if __name__ == "__main__":
    run()

