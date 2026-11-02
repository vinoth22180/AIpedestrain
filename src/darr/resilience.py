import networkx as nx
from typing import Dict, Any, List, Tuple, Set, Optional
from src.darr.config import DARR_CONFIG, get_profile_config
from src.darr.subgraph import subgraph_manager

class AccessibilityResilienceEngine:
    """
    Evaluates the robustness of the accessible pedestrian network.
    Calculates:
    - Accessibility Option Count (AOC)
    - Accessibility Resilience Level (ARL)
    - Critical Accessibility Dependency (CAD)
    """

    def __init__(self):
        res_cfg = DARR_CONFIG.get("resilience", {})
        self.overlap_factor = res_cfg.get("overlap_penalty_factor", 0.6)
        self.cut_weight = res_cfg.get("cad_cut_edge_weight", 0.6)
        self.detour_weight = res_cfg.get("cad_detour_weight", 0.4)

    def _to_simple_graph(self, G: nx.Graph, weight_attr: str = "length_m") -> nx.Graph:
        """Converts a MultiGraph to a simple Graph with minimum edge weights for flow and connectivity."""
        if not G.is_multigraph():
            return G
        simple_G = nx.Graph()
        for n, d in G.nodes(data=True):
            simple_G.add_node(n, **d)
        for u, v, k, d in G.edges(keys=True, data=True):
            w = d.get(weight_attr, d.get("length", 1.0))
            if simple_G.has_edge(u, v):
                if w < simple_G[u][v].get("weight", float("inf")):
                    simple_G[u][v]["weight"] = w
                    simple_G[u][v]["edge_data"] = d
            else:
                simple_G.add_edge(u, v, weight=w, capacity=1.0, edge_data=d)
        return simple_G

    def calculate_aoc(self, G_sub: nx.Graph, source: Any, destination: Any) -> int:
        """
        Accessibility Option Count (AOC):
        Computes the maximum number of edge-disjoint independent corridors
        connecting source and destination in the profile-feasible subgraph.
        """
        if source == destination or not G_sub.has_node(source) or not G_sub.has_node(destination):
            return 0
        if not nx.has_path(G_sub, source, destination):
            return 0
            
        simple_G = self._to_simple_graph(G_sub)
        try:
            # Maximum edge-disjoint paths via max flow with unit capacities
            flow_val, _ = nx.maximum_flow(simple_G, source, destination, capacity="capacity")
            return int(flow_val)
        except Exception:
            # Fallback path search
            try:
                paths = list(nx.edge_disjoint_paths(simple_G, source, destination))
                return len(paths)
            except Exception:
                return 1 if nx.has_path(G_sub, source, destination) else 0

    def find_shared_bottlenecks(self, G_sub: nx.Graph, paths: List[List[Any]]) -> Dict[str, Any]:
        """
        Identifies shared critical nodes (articulation points) and shared edges
        across candidate accessible routes.
        """
        if not paths:
            return {"shared_edges": [], "shared_nodes": [], "is_single_corridor": True}
            
        if len(paths) == 1:
            return {"shared_edges": [], "shared_nodes": [], "is_single_corridor": True}

        # Edges per path
        path_edge_sets = []
        for p in paths:
            edges = set()
            for i in range(len(p) - 1):
                u, v = p[i], p[i+1]
                edges.add(tuple(sorted((u, v))))
            path_edge_sets.append(edges)

        # Intersection of all paths
        common_edges = set.intersection(*path_edge_sets) if path_edge_sets else set()
        
        # Intermediate nodes intersection
        path_node_sets = [set(p[1:-1]) for p in paths]
        common_nodes = set.intersection(*path_node_sets) if path_node_sets else set()

        return {
            "shared_edges": [list(e) for e in common_edges],
            "shared_nodes": list(common_nodes),
            "is_single_corridor": len(common_edges) > 0 or len(common_nodes) > 0
        }

    def calculate_arl(self, G_sub: nx.Graph, source: Any, destination: Any, candidate_paths: Optional[List[List[Any]]] = None) -> float:
        """
        Accessibility Resilience Level (ARL):
        A continuous metric measuring the number of independent accessible alternatives,
        penalizing shared critical edges, cut nodes, and path overlap.
        """
        aoc = self.calculate_aoc(G_sub, source, destination)
        if aoc == 0:
            return 0.0

        if candidate_paths is None or len(candidate_paths) == 0:
            return float(aoc)

        if len(candidate_paths) == 1:
            return 1.0

        # Calculate effective independent alternatives considering pairwise overlap
        path_edges = []
        for p in candidate_paths:
            edges = set(tuple(sorted((p[i], p[i+1]))) for i in range(len(p)-1))
            path_edges.append(edges)

        effective_alternatives = 1.0
        for i in range(1, len(path_edges)):
            overlap_penalty = 0.0
            for j in range(i):
                if not path_edges[i] or not path_edges[j]:
                    continue
                intersection = len(path_edges[i] & path_edges[j])
                union = len(path_edges[i] | path_edges[j])
                jaccard = intersection / union if union > 0 else 1.0
                overlap_penalty = max(overlap_penalty, jaccard)
            
            # Additional path contribution discounted by maximum overlap with existing paths
            effective_alternatives += max(0.0, 1.0 - (self.overlap_factor * overlap_penalty))

        # Check for shared bottleneck cut-edges or cut-nodes across all candidate paths
        bottlenecks = self.find_shared_bottlenecks(G_sub, candidate_paths)
        if bottlenecks["is_single_corridor"]:
            # If all paths depend on a shared junction or corridor, cap resilience
            shared_edge_count = len(bottlenecks["shared_edges"])
            shared_node_count = len(bottlenecks["shared_nodes"])
            bottleneck_penalty = min(0.6, 0.2 * shared_edge_count + 0.15 * shared_node_count)
            effective_alternatives *= (1.0 - bottleneck_penalty)

        # ARL cannot exceed total AOC
        return max(0.0, min(float(aoc), round(effective_alternatives, 2)))

    def _get_bridges(self, G_sub: nx.Graph) -> Set[Tuple[Any, Any]]:
        """Fast linear-time bridge detection on subgraph."""
        simple_G = self._to_simple_graph(G_sub)
        bridge_set = set()
        for u, v in nx.bridges(simple_G):
            bridge_set.add((u, v))
            bridge_set.add((v, u))
        return bridge_set

    def calculate_cad_for_edge(self, G_base: nx.Graph, u: Any, v: Any, profile_name: str, bridge_cache: Optional[Set[Tuple[Any, Any]]] = None) -> float:
        """
        Critical Accessibility Dependency (CAD):
        Estimates how strongly users of the given profile depend on edge (u, v).
        Instantaneous evaluation using precomputed bridge sets and local degree bottleneck analysis.
        """
        G_sub = subgraph_manager.get_accessible_subgraph(G_base, profile_name)
        if not G_sub.has_edge(u, v):
            return 0.0

        bridges = bridge_cache if bridge_cache is not None else self._get_bridges(G_sub)
        if (u, v) in bridges:
            return 1.0 # Essential cut edge; removal disconnects network

        # Degree-based bottleneck factor (nodes with degree 2 have only 1 alternative branch)
        deg_u = G_sub.degree(u) if G_sub.has_node(u) else 2
        deg_v = G_sub.degree(v) if G_sub.has_node(v) else 2
        min_deg = min(deg_u, deg_v)
        
        if min_deg <= 2:
            return 0.5 # High dependency, few alternatives
        elif min_deg == 3:
            return 0.3
        else:
            return 0.1 # Well-connected junction with multiple redundant branches

    def identify_critical_edges(self, G_base: nx.Graph, profile_name: str = "wheelchair", threshold: float = 0.4) -> List[Dict[str, Any]]:
        """
        Scans edges in the accessible network to identify critical bottlenecks with high CAD.
        Runs in linear time O(V + E) using bridge sets and degree metrics.
        """
        critical_edges = []
        G_sub = subgraph_manager.get_accessible_subgraph(G_base, profile_name)
        bridges_constrained = self._get_bridges(G_sub)
        
        G_gen_sub = subgraph_manager.get_accessible_subgraph(G_base, "general")
        bridges_gen = self._get_bridges(G_gen_sub)
        
        for u, v, k, d in (G_sub.edges(keys=True, data=True) if G_sub.is_multigraph() else [(u, v, None, d) for u, v, d in G_sub.edges(data=True)]):
            cad_constrained = self.calculate_cad_for_edge(G_base, u, v, profile_name, bridges_constrained)
            cad_general = self.calculate_cad_for_edge(G_base, u, v, "general", bridges_gen)
            differential_cad = max(0.0, cad_constrained - cad_general)
            
            if cad_constrained >= threshold or differential_cad >= 0.3:
                geom = d.get('geometry')
                coords = list(geom.coords) if geom and hasattr(geom, 'coords') else None
                critical_edges.append({
                    "u": u,
                    "v": v,
                    "key": k,
                    "name": d.get("name") or f"Segment_{u}_{v}",
                    "cad": cad_constrained,
                    "differential_cad": round(differential_cad, 3),
                    "is_cut_edge": (u, v) in bridges_constrained,
                    "coordinates": coords
                })
                
        return sorted(critical_edges, key=lambda x: x["cad"], reverse=True)

resilience_engine = AccessibilityResilienceEngine()
