import os
import pickle
import logging
from shapely.geometry import LineString

from src.config.loader import DATASETS_CONFIG

logger = logging.getLogger(__name__)

ACTIVE_DATASET = DATASETS_CONFIG.get("active", "vit_vellore")

if ACTIVE_DATASET == "vit_vellore":
    GRAPH_CACHE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data", "vit_vellore", "processed",
        "vit_vellore_academic_pedestrian_network.pkl"
    )
else:
    GRAPH_CACHE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data", f"graph_cache_{ACTIVE_DATASET}.pkl"
    )


def _ensure_edge_geometry(G):
    """
    Post-load pass: every edge must have a Shapely LineString stored under
    the key 'geometry'.  If OSMnx omitted it (straight-line segment) we
    reconstruct it from the endpoint node coordinates.
    """
    missing = 0
    invalid = 0
    for u, v, k, data in G.edges(keys=True, data=True):
        geom = data.get('geometry')
        if geom is None:
            # Straight-line fallback from node coordinates
            u_data = G.nodes[u]
            v_data = G.nodes[v]
            if 'x' in u_data and 'y' in u_data and 'x' in v_data and 'y' in v_data:
                data['geometry'] = LineString([
                    (u_data['x'], u_data['y']),
                    (v_data['x'], v_data['y'])
                ])
                missing += 1
            else:
                invalid += 1
                logger.warning(f"Edge ({u},{v},{k}) missing geometry and node coords – skipping.")
        elif not hasattr(geom, 'coords'):
            # Stored as WKT string – parse it back
            try:
                from shapely import wkt
                data['geometry'] = wkt.loads(str(geom))
            except Exception:
                invalid += 1
                logger.warning(f"Edge ({u},{v},{k}) has unparseable geometry string.")

    logger.info(
        f"Geometry check: {len(G.edges())} total edges, "
        f"{missing} rebuilt from endpoints, {invalid} invalid."
    )
    return G


def load_or_build_graph():
    """
    Loads the graph from the pickle cache and ensures every edge has
    a Shapely LineString 'geometry' attribute.
    """
    if os.path.exists(GRAPH_CACHE_PATH):
        logger.info(f"Loading precomputed graph from {GRAPH_CACHE_PATH}...")
        with open(GRAPH_CACHE_PATH, 'rb') as f:
            G = pickle.load(f)
        G = _ensure_edge_geometry(G)
        logger.info(f"Graph loaded: {len(G.nodes)} nodes, {len(G.edges())} edges.")
        return G

    raise FileNotFoundError(
        f"Graph cache not found at {GRAPH_CACHE_PATH}. "
        "Run scripts/build_vit_dataset.py first."
    )

