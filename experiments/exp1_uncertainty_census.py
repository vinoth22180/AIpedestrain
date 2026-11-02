"""
PCVC Experiment 1: Accessibility Attribute Uncertainty Census
=============================================================
Sweeps the entire VIT Vellore pedestrian network and computes
edge-level uncertainty (U) for all 4 accessibility profiles.

Outputs:
  experiments/results/exp1_uncertainty_census.json   -- full per-edge records
  experiments/results/exp1_summary.csv               -- profile-level summary table
  experiments/logs/exp1_uncertainty_census.log       -- run log

Paper Tables Addressed:
  Table III â€“ Distribution of accessibility attribute uncertainty across profiles
  Table IV  â€“ Missing attribute breakdown by profile
"""

import os
import sys
import json
import csv
import logging
import time
from collections import defaultdict

# â”€â”€ path setup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.graph_manager import load_or_build_graph
from src.pcvc.uncertainty import (
    get_uncertain_edges,
    compute_edge_uncertainty,
    PROFILE_UNCERTAINTY_WEIGHTS,
)

# â”€â”€ constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PROFILES = ["wheelchair", "elderly", "pregnant", "general"]
RESULTS_DIR = os.path.join(ROOT, "experiments", "results")
LOGS_DIR    = os.path.join(ROOT, "experiments", "logs")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# â”€â”€ logging â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
log_path = os.path.join(LOGS_DIR, "exp1_uncertainty_census.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def band(u: float) -> str:
    """Bin uncertainty into Low/Medium/High/Critical bands."""
    if u < 0.33:  return "Low"
    if u < 0.67:  return "Medium"
    if u < 1.00:  return "High"
    return "Critical"


def run():
    log.info("=" * 70)
    log.info("PCVC Experiment 1 â€“ Accessibility Attribute Uncertainty Census")
    log.info("=" * 70)

    t0 = time.time()
    G = load_or_build_graph()
    n_nodes = len(G.nodes())
    n_edges = G.number_of_edges()
    log.info(f"Graph loaded: {n_nodes} nodes, {n_edges} edges.")

    # â”€â”€ per-profile uncertainty sweep â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    profile_records: dict[str, list] = {p: [] for p in PROFILES}

    edge_iter = (
        G.edges(keys=True, data=True)
        if G.is_multigraph()
        else [(u, v, 0, d) for u, v, d in G.edges(data=True)]
    )

    for u, v, k, data in edge_iter:
        for profile in PROFILES:
            conf, unc, missing, known = compute_edge_uncertainty(data, profile)
            profile_records[profile].append({
                "u": u, "v": v, "key": k,
                "name": data.get("name") or f"Walkway_{u}_{v}",
                "confidence": round(conf, 4),
                "uncertainty": round(unc, 4),
                "band": band(unc),
                "missing_attrs": missing,
                "known_attrs": list(known.keys()),
                "n_missing": len(missing),
                "n_known": len(known),
            })

    # â”€â”€ summary stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    summary_rows = []
    log.info("")
    log.info(f"{'Profile':<12} {'Edges':>7} {'U>0.4':>7} {'U>0.7':>7} "
             f"{'U_mean':>8} {'U_std':>8} "
             f"{'Low%':>7} {'Med%':>7} {'High%':>7} {'Crit%':>7}")
    log.info("-" * 85)

    for profile in PROFILES:
        recs = profile_records[profile]
        uncertainties = [r["uncertainty"] for r in recs]
        n = len(uncertainties)
        mean_u = sum(uncertainties) / n
        variance = sum((x - mean_u) ** 2 for x in uncertainties) / n
        std_u = variance ** 0.5

        n_gt04 = sum(1 for u in uncertainties if u >= 0.4)
        n_gt07 = sum(1 for u in uncertainties if u >= 0.7)

        band_counts = defaultdict(int)
        for u in uncertainties:
            band_counts[band(u)] += 1

        def pct(key):
            return round(100 * band_counts[key] / n, 1) if n else 0.0

        # Missing attribute frequency
        missing_freq: dict[str, int] = defaultdict(int)
        for r in recs:
            for attr in r["missing_attrs"]:
                missing_freq[attr] += 1
        top_missing = sorted(missing_freq.items(), key=lambda x: -x[1])[:5]

        log.info(
            f"{profile:<12} {n:>7} {n_gt04:>7} {n_gt07:>7} "
            f"{mean_u:>8.4f} {std_u:>8.4f} "
            f"{pct('Low'):>7} {pct('Medium'):>7} {pct('High'):>7} {pct('Critical'):>7}"
        )

        summary_rows.append({
            "profile":           profile,
            "total_edges":       n,
            "edges_uncertain_gt04": n_gt04,
            "edges_uncertain_gt07": n_gt07,
            "uncertainty_mean":  round(mean_u, 4),
            "uncertainty_std":   round(std_u, 4),
            "band_low_pct":      pct("Low"),
            "band_medium_pct":   pct("Medium"),
            "band_high_pct":     pct("High"),
            "band_critical_pct": pct("Critical"),
            "top_missing_attrs": [a for a, _ in top_missing],
            "top_missing_counts": [c for _, c in top_missing],
        })

    log.info("")
    log.info("Top missing attributes per profile:")
    for row in summary_rows:
        attrs = ", ".join(
            f"{a}({c})" for a, c in zip(row["top_missing_attrs"], row["top_missing_counts"])
        )
        log.info(f"  {row['profile']:<12}: {attrs}")

    # â”€â”€ save JSON (full per-edge records) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    json_path = os.path.join(RESULTS_DIR, "exp1_uncertainty_census.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "experiment": "exp1_uncertainty_census",
                "graph_nodes": n_nodes,
                "graph_edges": n_edges,
                "profiles": PROFILES,
                "per_profile": profile_records,
            },
            f, indent=2, default=str
        )
    log.info(f"Full per-edge records saved â†’ {json_path}")

    # â”€â”€ save CSV summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    csv_path = os.path.join(RESULTS_DIR, "exp1_summary.csv")
    fieldnames = [
        "profile", "total_edges",
        "edges_uncertain_gt04", "edges_uncertain_gt07",
        "uncertainty_mean", "uncertainty_std",
        "band_low_pct", "band_medium_pct", "band_high_pct", "band_critical_pct",
        "top_missing_attrs",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in summary_rows:
            row["top_missing_attrs"] = "; ".join(row["top_missing_attrs"])
            writer.writerow(row)
    log.info(f"Summary CSV saved â†’ {csv_path}")

    elapsed = time.time() - t0
    log.info(f"\nExperiment 1 completed in {elapsed:.2f}s")
    return summary_rows


if __name__ == "__main__":
    run()

