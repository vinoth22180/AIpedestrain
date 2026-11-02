"""
PCVC Experiment 2: Counterfactual Impact Analysis
==================================================
For each of the 4 accessibility profiles, identifies uncertain edges and
evaluates their counterfactual impact (AOC, ARL, MAL, CAD, cut-edge flag)
if each edge were to fail.

Computes Î”AOC, Î”ARL, MAL per profile and ranks edges by Priority Score.

Outputs:
  experiments/results/exp2_counterfactual_impact.json   -- full records
  experiments/results/exp2_counterfactual_summary.csv   -- per-profile summary
  experiments/logs/exp2_counterfactual_impact.log

Paper Tables / Figures Addressed:
  Table V  â€“ Counterfactual impact per profile (top-5 per profile)
  Fig. 3   â€“ Î”ARL distribution across profiles
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
from src.pcvc.uncertainty import get_uncertain_edges
from src.pcvc.counterfactual import evaluate_counterfactual_impact
from src.darr.subgraph import subgraph_manager
from src.darr.resilience import resilience_engine

PROFILES = ["wheelchair", "elderly", "pregnant", "general"]
UNCERTAINTY_THRESHOLD = 0.4
MAX_CANDIDATES_PER_PROFILE = 40

RESULTS_DIR = os.path.join(ROOT, "experiments", "results")
LOGS_DIR    = os.path.join(ROOT, "experiments", "logs")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

log_path = os.path.join(LOGS_DIR, "exp2_counterfactual_impact.log")
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
    log.info("PCVC Experiment 2 â€“ Counterfactual Impact Analysis")
    log.info("=" * 70)

    t0 = time.time()
    G = load_or_build_graph()
    log.info(f"Graph: {len(G.nodes())} nodes, {G.number_of_edges()} edges.")

    all_results: dict[str, list] = {}
    summary_rows = []

    for profile in PROFILES:
        log.info(f"\n[{profile.upper()}] Scanning uncertain edges (Uâ‰¥{UNCERTAINTY_THRESHOLD})â€¦")
        t_profile = time.time()

        uncertain_states = get_uncertain_edges(
            G,
            profile=profile,
            uncertainty_threshold=UNCERTAINTY_THRESHOLD,
            limit=MAX_CANDIDATES_PER_PROFILE,
        )

        n_candidates = len(uncertain_states)
        log.info(f"  Found {n_candidates} candidate edges.")

        # Pre-compute bridge cache for speed
        G_sub = subgraph_manager.get_accessible_subgraph(G, profile)
        bridge_cache = resilience_engine._get_bridges(G_sub)

        records = []
        n_cut = 0
        delta_arls = []
        delta_aocs = []
        cads = []

        for idx, state in enumerate(uncertain_states):
            impact = evaluate_counterfactual_impact(
                G, state.u, state.v, state.key,
                target_profile=profile,
                bridge_cache=bridge_cache,
            )
            record = {
                "rank":            idx + 1,
                "edge_id":         state.edge_id,
                "name":            state.name or f"Walkway_{state.u}_{state.v}",
                "u":               state.u,
                "v":               state.v,
                "key":             state.key,
                "uncertainty":     state.accessibility_uncertainty,
                "confidence":      state.accessibility_confidence,
                "missing_attrs":   state.missing_attributes,
                "baseline_aoc":    impact.baseline_aoc,
                "baseline_arl":    impact.baseline_arl,
                "cf_aoc":          impact.counterfactual_aoc,
                "cf_arl":          impact.counterfactual_arl,
                "delta_aoc":       impact.delta_aoc,
                "delta_arl":       impact.delta_arl,
                "mal_impact":      impact.mal_impact,
                "cad":             impact.cad,
                "is_cut_edge":     impact.is_cut_edge,
            }
            records.append(record)
            delta_arls.append(impact.delta_arl)
            delta_aocs.append(impact.delta_aoc)
            cads.append(impact.cad)
            if impact.is_cut_edge:
                n_cut += 1

        # Sort by Î”ARL descending for reporting
        records.sort(key=lambda x: (x["delta_arl"], x["cad"]), reverse=True)
        all_results[profile] = records

        def safe_mean(lst):
            return round(sum(lst) / len(lst), 4) if lst else 0.0

        def safe_max(lst):
            return round(max(lst), 4) if lst else 0.0

        elapsed_p = time.time() - t_profile
        log.info(
            f"  Candidates: {n_candidates} | Cut-edges: {n_cut} | "
            f"mean(Î”ARL)={safe_mean(delta_arls):.4f} | "
            f"max(Î”ARL)={safe_max(delta_arls):.4f} | "
            f"mean(CAD)={safe_mean(cads):.4f} | "
            f"time={elapsed_p:.1f}s"
        )

        # Print top-5
        log.info(f"  Top-5 edges by Î”ARL for [{profile}]:")
        log.info(
            f"    {'Edge':<40} {'U':>6} {'Î”ARL':>6} {'Î”AOC':>6} "
            f"{'MAL':>6} {'CAD':>6} {'Cut':>5}"
        )
        for r in records[:5]:
            name_trunc = r["name"][:38] if len(r["name"]) > 38 else r["name"]
            log.info(
                f"    {name_trunc:<40} {r['uncertainty']:>6.3f} "
                f"{r['delta_arl']:>6.3f} {r['delta_aoc']:>6} "
                f"{r['mal_impact']:>6.3f} {r['cad']:>6.3f} {str(r['is_cut_edge']):>5}"
            )

        summary_rows.append({
            "profile":          profile,
            "n_candidates":     n_candidates,
            "n_cut_edges":      n_cut,
            "mean_delta_arl":   safe_mean(delta_arls),
            "max_delta_arl":    safe_max(delta_arls),
            "mean_delta_aoc":   safe_mean(delta_aocs),
            "max_delta_aoc":    safe_max(delta_aocs),
            "mean_cad":         safe_mean(cads),
            "max_cad":          safe_max(cads),
            "top_edge_name":    records[0]["name"] if records else "N/A",
            "top_edge_delta_arl": records[0]["delta_arl"] if records else 0.0,
        })

    # â”€â”€ Save JSON â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    json_path = os.path.join(RESULTS_DIR, "exp2_counterfactual_impact.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "experiment":            "exp2_counterfactual_impact",
                "uncertainty_threshold": UNCERTAINTY_THRESHOLD,
                "max_candidates":        MAX_CANDIDATES_PER_PROFILE,
                "profiles":              PROFILES,
                "per_profile":           all_results,
            },
            f, indent=2, default=str,
        )
    log.info(f"\nFull impact records saved â†’ {json_path}")

    # â”€â”€ Save CSV summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    csv_path = os.path.join(RESULTS_DIR, "exp2_counterfactual_summary.csv")
    fieldnames = [
        "profile", "n_candidates", "n_cut_edges",
        "mean_delta_arl", "max_delta_arl",
        "mean_delta_aoc", "max_delta_aoc",
        "mean_cad", "max_cad",
        "top_edge_name", "top_edge_delta_arl",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)
    log.info(f"Summary CSV saved â†’ {csv_path}")

    elapsed = time.time() - t0
    log.info(f"\nExperiment 2 completed in {elapsed:.2f}s")
    return all_results


if __name__ == "__main__":
    run()

