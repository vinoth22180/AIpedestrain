import networkx as nx
from typing import Dict, Any, List, Tuple, Optional
from src.pcvc.models import EdgeEvidenceState, VerificationStatus

PROFILE_UNCERTAINTY_WEIGHTS = {
    "wheelchair": {
        "wheelchair": 0.35,
        "slope_percent": 0.20,
        "width_m": 0.15,
        "ramp": 0.10,
        "surface": 0.10,
        "smoothness_value": 0.05,
        "tactile_paving": 0.05,
    },
    "elderly": {
        "stairs": 0.25,
        "slope_percent": 0.25,
        "surface": 0.20,
        "width_m": 0.15,
        "smoothness_value": 0.10,
        "tactile_paving": 0.05,
    },
    "pregnant": {
        "stairs": 0.25,
        "slope_percent": 0.25,
        "surface": 0.20,
        "width_m": 0.15,
        "smoothness_value": 0.10,
        "tactile_paving": 0.05,
    },
    "general": {
        "surface": 0.30,
        "smoothness_value": 0.25,
        "width_m": 0.25,
        "slope_percent": 0.20,
    }
}

def format_edge_id(u: Any, v: Any, key: Any) -> str:
    """Deterministic edge identifier formatted as u-v-key."""
    return f"{u}-{v}-{key}"

def parse_edge_id(edge_id: str) -> Tuple[Any, Any, Any]:
    """Parses a deterministic u-v-key string back into node and key components."""
    parts = str(edge_id).split("-")
    if len(parts) >= 3:
        u_str = parts[0]
        v_str = parts[1]
        key_str = "-".join(parts[2:])
        # Convert numeric OSM IDs to int if applicable
        u = int(u_str) if u_str.isdigit() else u_str
        v = int(v_str) if v_str.isdigit() else v_str
        return u, v, key_str
    raise ValueError(f"Invalid edge_id format: {edge_id}. Expected 'u-v-key'.")

def is_attribute_known(attr_name: str, val: Any) -> bool:
    """Checks whether an attribute represents confirmed information rather than unknown/missing."""
    if val is None:
        return False
    if hasattr(val, 'iloc'):
        val = val.iloc[0]
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ["", "unknown", "none", "null"]:
            return False
        if attr_name == "wheelchair" and v == "unknown":
            return False
    if attr_name == "slope_percent":
        return isinstance(val, (int, float))
    if attr_name == "width_m":
        return isinstance(val, (int, float)) and val > 0
    return True

def compute_edge_uncertainty(edge_data: Dict[str, Any], profile: str = "wheelchair") -> Tuple[float, float, List[str], Dict[str, Any]]:
    """
    Evaluates missing vs confirmed accessibility attributes for an edge.
    Returns (confidence, uncertainty, missing_attributes, known_attributes).
    """
    weights = PROFILE_UNCERTAINTY_WEIGHTS.get(profile.lower(), PROFILE_UNCERTAINTY_WEIGHTS["general"])
    total_weight = sum(weights.values())
    
    known_weight = 0.0
    missing_attrs = []
    known_attrs = {}

    for attr, weight in weights.items():
        val = edge_data.get(attr)
        if attr == "surface" and not val:
            val = edge_data.get("surface_type")
        if attr == "wheelchair" and not val:
            val = edge_data.get("wheelchair_accessible")

        if is_attribute_known(attr, val):
            known_weight += weight
            known_attrs[attr] = val
        else:
            missing_attrs.append(attr)

    confidence = round(min(1.0, max(0.0, known_weight / total_weight if total_weight > 0 else 0.5)), 3)
    uncertainty = round(1.0 - confidence, 3)

    return confidence, uncertainty, missing_attrs, known_attrs

def get_uncertain_edges(
    G: nx.Graph,
    profile: str = "wheelchair",
    uncertainty_threshold: float = 0.4,
    limit: Optional[int] = 50
) -> List[EdgeEvidenceState]:
    """
    Scans the graph and identifies candidate edges that have insufficient accessibility evidence.
    Excludes edges that are already confirmed impassable (e.g., confirmed stairs for wheelchair).
    Returns a deterministic list of EdgeEvidenceState objects sorted by descending uncertainty.
    """
    results: List[EdgeEvidenceState] = []

    # Iterate MultiGraph or Graph
    edge_iter = G.edges(keys=True, data=True) if G.is_multigraph() else [(u, v, 0, d) for u, v, d in G.edges(data=True)]

    for u, v, k, data in edge_iter:
        # If target is wheelchair, and edge is confirmed to have stairs, it's not "uncertain" — it's known inaccessible.
        if profile.lower() == "wheelchair" and data.get("stairs") is True:
            continue

        conf, unc, missing, known = compute_edge_uncertainty(data, profile)

        if unc >= uncertainty_threshold:
            edge_id = format_edge_id(u, v, k)
            name = data.get("name") or data.get("display_name") or f"Walkway_{u}_{v}"
            status = VerificationStatus.UNCERTAIN if conf > 0.0 else VerificationStatus.UNKNOWN

            results.append(EdgeEvidenceState(
                edge_id=edge_id,
                u=u,
                v=v,
                key=k,
                name=name,
                accessibility_confidence=conf,
                accessibility_uncertainty=unc,
                last_verified=None,
                observation_count=0,
                verification_status=status,
                missing_attributes=missing,
                known_attributes=known
            ))

    # Sort descending by uncertainty
    results.sort(key=lambda x: x.accessibility_uncertainty, reverse=True)

    if limit is not None:
        return results[:limit]
    return results
