"""
PCVC Phase 6 Master Experiment Runner
======================================
Executes all 5 research experiments in sequence and writes a
consolidated machine-readable manifest.

Usage:
    .venv/Scripts/python.exe experiments/run_all_experiments.py

Experiments:
    Exp 1 â€“ Accessibility Attribute Uncertainty Census
    Exp 2 â€“ Counterfactual Impact Analysis (AOC / ARL / MAL / CAD)
    Exp 3 â€“ Priority Score Ranking Validation (Full PCVC Pipeline)
    Exp 4 â€“ Probe Safety & Closed-Loop Return Validation
    Exp 5 â€“ Network-Wide CAD Census

Outputs (in experiments/results/):
    exp1_uncertainty_census.json / exp1_summary.csv
    exp2_counterfactual_impact.json / exp2_counterfactual_summary.csv
    exp3_priority_ranking.json / exp3_priority_ranking.csv
    exp4_probe_safety.json / exp4_probe_safety.csv
    exp5_cad_census.json / exp5_cad_summary.csv
    experiment_manifest.json   â† consolidated run metadata
"""

import os
import sys
import json
import time
import traceback
import logging

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RESULTS_DIR = os.path.join(ROOT, "experiments", "results")
LOGS_DIR    = os.path.join(ROOT, "experiments", "logs")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

log_path = os.path.join(LOGS_DIR, "run_all_experiments.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def run_experiment(name: str, module_path: str) -> dict:
    """Import and run a single experiment module, returning status metadata."""
    t0 = time.time()
    status = "SUCCESS"
    error_msg = None

    log.info("\n" + "â–ˆ" * 70)
    log.info(f"  STARTING: {name}")
    log.info("â–ˆ" * 70)

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, module_path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.run()
    except Exception as e:
        status = "FAILED"
        error_msg = traceback.format_exc()
        log.error(f"Experiment FAILED: {name}\n{error_msg}")

    elapsed = round(time.time() - t0, 2)
    log.info(f"\n{name} â†’ {status} in {elapsed}s")
    return {
        "name":       name,
        "module":     module_path,
        "status":     status,
        "elapsed_s":  elapsed,
        "error":      error_msg,
    }


def main():
    log.info("=" * 70)
    log.info("PCVC Phase 6 â€“ Master Experiment Runner")
    log.info(f"Root: {ROOT}")
    log.info("=" * 70)

    EXPERIMENTS_DIR = os.path.join(ROOT, "experiments")
    experiments = [
        ("Exp1_UncertaintyCensus",       os.path.join(EXPERIMENTS_DIR, "exp1_uncertainty_census.py")),
        ("Exp2_CounterfactualImpact",     os.path.join(EXPERIMENTS_DIR, "exp2_counterfactual_impact.py")),
        ("Exp3_PriorityRankingValidation",os.path.join(EXPERIMENTS_DIR, "exp3_priority_ranking.py")),
        ("Exp4_ProbeSafetyValidation",    os.path.join(EXPERIMENTS_DIR, "exp4_probe_safety.py")),
        ("Exp5_CADCensus",               os.path.join(EXPERIMENTS_DIR, "exp5_cad_census.py")),
    ]

    total_t0 = time.time()
    run_results = []

    for exp_name, exp_path in experiments:
        result = run_experiment(exp_name, exp_path)
        run_results.append(result)

    total_elapsed = round(time.time() - total_t0, 2)
    n_success = sum(1 for r in run_results if r["status"] == "SUCCESS")
    n_failed  = sum(1 for r in run_results if r["status"] == "FAILED")

    log.info("\n" + "=" * 70)
    log.info("EXPERIMENT RUN COMPLETE")
    log.info(f"  Total time   : {total_elapsed}s")
    log.info(f"  Succeeded    : {n_success}/{len(experiments)}")
    log.info(f"  Failed       : {n_failed}/{len(experiments)}")
    log.info("=" * 70)

    for r in run_results:
        symbol = "âœ“" if r["status"] == "SUCCESS" else "âœ—"
        log.info(f"  {symbol} {r['name']:<40} {r['elapsed_s']:>8.2f}s")

    # â”€â”€ Save manifest â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    manifest = {
        "pcvc_phase":    6,
        "graph_dataset": "vit_vellore_academic_pedestrian_network",
        "profiles":      ["wheelchair", "elderly", "pregnant", "general"],
        "total_elapsed_s": total_elapsed,
        "n_success":     n_success,
        "n_failed":      n_failed,
        "experiments":   run_results,
        "output_files": {
            "exp1": {
                "json": "experiments/results/exp1_uncertainty_census.json",
                "csv":  "experiments/results/exp1_summary.csv",
            },
            "exp2": {
                "json": "experiments/results/exp2_counterfactual_impact.json",
                "csv":  "experiments/results/exp2_counterfactual_summary.csv",
            },
            "exp3": {
                "json": "experiments/results/exp3_priority_ranking.json",
                "csv":  "experiments/results/exp3_priority_ranking.csv",
            },
            "exp4": {
                "json": "experiments/results/exp4_probe_safety.json",
                "csv":  "experiments/results/exp4_probe_safety.csv",
            },
            "exp5": {
                "json": "experiments/results/exp5_cad_census.json",
                "csv":  "experiments/results/exp5_cad_summary.csv",
            },
        },
    }

    manifest_path = os.path.join(RESULTS_DIR, "experiment_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    log.info(f"\nManifest saved â†’ {manifest_path}")

    if n_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

