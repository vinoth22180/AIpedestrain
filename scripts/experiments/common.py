"""
PCVC Phase 6 Research Experiment Harness - Common Utilities
Project: Profile-Coupled Counterfactual Verification Controller (PCVC)
Target publication: IEEE Access

Module: scripts/experiments/common.py
Provides reproducible, standardized helper functions for:
- Active graph loading (VIT Vellore)
- Graph topological statistics
- Edge ID formatting and parsing
- Safe in-memory graph duplication (no disk mutation)
- Deterministic random seed management
- Result directory tree management (raw/, summary/, figures/)
- Timestamp formatting
- Machine-readable CSV/JSON export
- Python environment and package version reporting
"""

import os
import sys
import copy
import json
import random
import datetime
import platform
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import networkx as nx

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.graph_manager import load_or_build_graph, GRAPH_CACHE_PATH
from src.pcvc.uncertainty import format_edge_id, parse_edge_id

ACTIVE_GRAPH_PATH = PROJECT_ROOT / "data" / "vit_vellore" / "processed" / "vit_vellore_academic_pedestrian_network.pkl"
RESULTS_BASE_DIR = PROJECT_ROOT / "results" / "pcvc"


def get_timestamp() -> str:
    """Returns ISO format timestamp for metadata reporting."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def get_environment_info() -> Dict[str, Any]:
    """Records Python interpreter, operating system, and key scientific library versions."""
    packages = {}
    for pkg_name in ["networkx", "numpy", "pandas", "scipy", "matplotlib", "shapely", "geopandas", "osmnx", "fastapi", "pydantic"]:
        try:
            mod = __import__(pkg_name)
            packages[pkg_name] = getattr(mod, "__version__", "unknown")
        except ImportError:
            packages[pkg_name] = None

    # Calculate active graph file md5 and mtime for audit trail
    graph_file_info = {}
    if ACTIVE_GRAPH_PATH.exists():
        content = ACTIVE_GRAPH_PATH.read_bytes()
        graph_file_info = {
            "path": str(ACTIVE_GRAPH_PATH),
            "size_bytes": len(content),
            "md5": hashlib.md5(content).hexdigest(),
            "mtime": ACTIVE_GRAPH_PATH.stat().st_mtime
        }

    return {
        "timestamp_utc": get_timestamp(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
        "processor": platform.processor(),
        "packages": packages,
        "dataset_audit": graph_file_info
    }


def set_seed(seed: int) -> None:
    """Sets deterministic random seed for Python random and NumPy."""
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
    except ImportError:
        pass


def load_active_graph() -> nx.MultiGraph:
    """
    Loads the active production VIT Vellore pedestrian network.
    Verifies that the graph matches the verified dimensions (1,551 nodes, 1,721 edges).
    Never mutates the file on disk.
    """
    G = load_or_build_graph()
    num_nodes = len(G.nodes)
    num_edges = len(G.edges)
    assert num_nodes == 1551, f"Expected 1551 nodes in active graph, found {num_nodes}"
    assert num_edges == 1721, f"Expected 1721 edges in active graph, found {num_edges}"
    assert isinstance(G, nx.MultiGraph), f"Expected MultiGraph, found {type(G)}"
    return G


def safe_copy_graph(G: nx.MultiGraph) -> nx.MultiGraph:
    """
    Creates an isolated deep copy of the graph in memory.
    Guarantees no modifications affect original graph or disk files.
    """
    return copy.deepcopy(G)


def get_edge_id(u: Any, v: Any, key: Any) -> str:
    """Standardized deterministic edge identifier formatted as u-v-key."""
    return format_edge_id(u, v, key)


def graph_statistics(G: nx.Graph) -> Dict[str, Any]:
    """Extracts topological and structural statistics from the pedestrian graph."""
    num_nodes = len(G.nodes)
    num_edges = len(G.edges)
    is_multi = G.is_multigraph()
    is_directed = G.is_directed()

    # Undirected components analysis
    if is_directed:
        undirected_view = G.to_undirected()
    else:
        undirected_view = G

    components = list(nx.connected_components(undirected_view))
    num_components = len(components)
    comp_sizes = sorted([len(c) for c in components], reverse=True)
    largest_comp_nodes = comp_sizes[0] if comp_sizes else 0

    return {
        "num_nodes": num_nodes,
        "num_edges": num_edges,
        "is_multigraph": is_multi,
        "is_directed": is_directed,
        "num_connected_components": num_components,
        "component_sizes": comp_sizes,
        "largest_component_nodes": largest_comp_nodes,
        "largest_component_ratio": round(largest_comp_nodes / num_nodes, 4) if num_nodes > 0 else 0.0
    }


def ensure_result_dirs(exp_id: str) -> Dict[str, Path]:
    """
    Creates standardized output directory structure for an experiment:
    results/pcvc/eX/
        raw/
        summary/
        figures/
    """
    exp_dir = RESULTS_BASE_DIR / exp_id.lower()
    raw_dir = exp_dir / "raw"
    summary_dir = exp_dir / "summary"
    figures_dir = exp_dir / "figures"

    for d in [exp_dir, raw_dir, summary_dir, figures_dir]:
        d.mkdir(parents=True, exist_ok=True)

    return {
        "base": exp_dir,
        "raw": raw_dir,
        "summary": summary_dir,
        "figures": figures_dir
    }


def _json_serialize_fallback(obj: Any) -> Any:
    """Fallback handler for NumPy types, NaN, and Path objects in JSON."""
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    if isinstance(obj, (np.ndarray, list, tuple)):
        return [_json_serialize_fallback(x) for x in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    return str(obj)


def save_json(data: Any, file_path: Union[str, Path]) -> Path:
    """Saves structured data to JSON with pretty formatting and safe type conversions."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=_json_serialize_fallback)
    return path


def save_csv(data: Union[pd.DataFrame, List[Dict[str, Any]]], file_path: Union[str, Path]) -> Path:
    """Saves DataFrame or list of dicts to CSV format."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, pd.DataFrame):
        df = data
    else:
        df = pd.DataFrame(data)
    df.to_csv(path, index=False, encoding="utf-8")
    return path
