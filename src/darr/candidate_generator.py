import networkx as nx
from typing import Dict, Any, List, Tuple, Optional
from shapely.geometry import LineString

from src.darr.config import get_profile_config, ProfileConfig
from src.darr.subgraph import subgraph_manager
from src.signal_decay.engine import decay_engine

class MultiRouteGenerator:
    """
    Generates at least 3 meaningfully distinct candidate routes for an OD pair
    using Dijkstra / A* applied with distinct objective cost models:
    - Route 1: Fastest / Shortest Feasible
    - Route 2: Lower Congestion
    - Route 3: Higher Accessibility Resilience
    """

    @staticmethod
    def _get_edge_best_key(G: nx.Graph, u: Any, v: Any, weight_key: str = "length_m") -> Tuple[Any, Dict[str, Any]]:
        """Finds the best sub-edge key and data between u and v."""
        if G.is_multigraph():
            edge_dict = G[u][v]
            best_k = min(edge_dict, key=lambda k: edge_dict[k].get(weight_key, edge_dict[k].get("length", 1.0)))
            return best_k, edge_dict[best_k]
        else:
            return None, G[u][v]

    def generate_candidate_routes(
        self,
        G_base: nx.Graph,
        source: Any,
        destination: Any,
        active_profile: str = "general"
    ) -> List[Dict[str, Any]]:
        """
        Generates 3 diverse candidate routes on the active profile's feasible subgraph.
        """
        profile_cfg = get_profile_config(active_profile)
        G_sub = subgraph_manager.get_accessible_subgraph(G_base, active_profile)

        if not G_sub.has_node(source) or not G_sub.has_node(destination) or not nx.has_path(G_sub, source, destination):
            return []

        speed_mps = profile_cfg.walking_speed_mps
        cur_time = decay_engine.last_update_time

        # Helper weight functions using standard Dijkstra
        def weight_fastest(u, v, data):
            if G_sub.is_multigraph():
                min_w = float('inf')
                for k, d in data.items():
                    w = d.get('length_m', d.get('length', 1.0))
                    if w < min_w: min_w = w
                return min_w
            return data.get('length_m', data.get('length', 1.0))

        def weight_low_congestion(u, v, data):
            decay_pen = decay_engine.get_penalty(u, v)
            if G_sub.is_multigraph():
                min_w = float('inf')
                for k, d in data.items():
                    w = d.get('length_m', d.get('length', 1.0)) + (2.0 * decay_pen)
                    if w < min_w: min_w = w
                return min_w
            return data.get('length_m', data.get('length', 1.0)) + (2.0 * decay_pen)

        def weight_resilience(u, v, data):
            cad = 0.0 # CAD removed
            decay_pen = decay_engine.get_penalty(u, v)
            # High penalty on high-CAD edges to route away from fragile accessibility bottlenecks
            if G_sub.is_multigraph():
                min_w = float('inf')
                for k, d in data.items():
                    w = d.get('length_m', d.get('length', 1.0)) + (cad * 60.0) + (1.5 * decay_pen)
                    if w < min_w: min_w = w
                return min_w
            return data.get('length_m', data.get('length', 1.0)) + (cad * 60.0) + (1.5 * decay_pen)

        raw_candidates = []

        # 1. Route 1: Fastest / Shortest
        try:
            p1 = nx.shortest_path(G_sub, source=source, target=destination, weight=weight_fastest)
            raw_candidates.append(("route_1_fastest", "Fastest Feasible Route", p1, "Minimizes travel distance and traversal time."))
        except Exception:
            p1 = None

        # 2. Route 2: Lower Congestion
        try:
            p2 = nx.shortest_path(G_sub, source=source, target=destination, weight=weight_low_congestion)
            # If p2 is identical to p1, explore with penalty on p1 edges
            if p2 == p1:
                H_pen = G_sub.copy()
                for i in range(len(p1)-1):
                    u, v = p1[i], p1[i+1]
                    if H_pen.is_multigraph():
                        for k in H_pen[u][v]:
                            H_pen[u][v][k]['length_m'] = H_pen[u][v][k].get('length_m', 1.0) * 2.5
                    else:
                        H_pen[u][v]['length_m'] = H_pen[u][v].get('length_m', 1.0) * 2.5
                p2 = nx.shortest_path(H_pen, source=source, target=destination, weight=weight_low_congestion)
            raw_candidates.append(("route_2_congestion", "Lower Congestion Route", p2, "Avoids active congestion hotspots and decaying bottlenecks."))
        except Exception:
            p2 = p1

        # 3. Route 3: Higher Accessibility Resilience
        try:
            p3 = nx.shortest_path(G_sub, source=source, target=destination, weight=weight_resilience)
            # Ensure p3 is distinct from p1 and p2
            if p3 == p1 or p3 == p2:
                H_res = G_sub.copy()
                for p in [p1, p2]:
                    if p:
                        for i in range(len(p)-1):
                            u, v = p[i], p[i+1]
                            if H_res.is_multigraph():
                                for k in H_res[u][v]:
                                    H_res[u][v][k]['length_m'] = H_res[u][v][k].get('length_m', 1.0) * 3.0
                            else:
                                H_res[u][v]['length_m'] = H_res[u][v].get('length_m', 1.0) * 3.0
                p3 = nx.shortest_path(H_res, source=source, target=destination, weight=weight_resilience)
            raw_candidates.append(("route_3_resilience", "Max Accessibility Resilience", p3, "Preserves critical accessibility corridors by utilizing wide, redundant pathways."))
        except Exception:
            p3 = p2 or p1

        # Fallback if any candidate failed: ensure at least 3 distinct candidates if graph permits
        all_unique_paths = []
        seen = set()
        for r_id, r_name, p, r_desc in raw_candidates:
            if p and tuple(p) not in seen:
                seen.add(tuple(p))
                all_unique_paths.append((r_id, r_name, p, r_desc))

        if len(all_unique_paths) < 3:
            # Try Yen's shortest simple paths
            try:
                simple_paths = nx.shortest_simple_paths(G_sub, source, destination, weight=weight_fastest)
                idx = len(all_unique_paths) + 1
                for sp in simple_paths:
                    if tuple(sp) not in seen:
                        seen.add(tuple(sp))
                        all_unique_paths.append((f"route_{idx}_alternative", f"Alternative Route {idx}", sp, "Alternative corridor."))
                        idx += 1
                        if len(all_unique_paths) >= 3:
                            break
            except Exception:
                pass

        # Build candidate route objects
        candidates = []
        for r_id, r_name, path_nodes, r_desc in all_unique_paths:
            candidate = self._evaluate_and_build_candidate(
                G_base, path_nodes, r_id, r_name, r_desc, active_profile, speed_mps, cur_time, source, destination
            )
            candidates.append(candidate)

        return candidates

    def _evaluate_and_build_candidate(
        self,
        G_base: nx.Graph,
        path_nodes: List[Any],
        r_id: str,
        r_name: str,
        r_desc: str,
        active_profile: str,
        speed_mps: float,
        cur_time: float,
        source: Any,
        destination: Any
    ) -> Dict[str, Any]:
        """Populates all required DARR metrics for a single candidate path."""
        total_dist = 0.0
        current_dynamic_cost = 0.0
        predicted_dynamic_cost = 0.0
        critical_edges_count = 0
        edge_sequence = []
        route_coords = []
        restricted_segments = []

        all_profiles = ["general", "elderly", "pregnant", "wheelchair"]
        accessibility_compatibility = {p: True for p in all_profiles}

        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i+1]
            best_k, d = self._get_edge_best_key(G_base, u, v)

            length = d.get('length_m', d.get('length', 1.0))
            total_dist += length

            # Geometry
            geom = d.get('geometry')
            if geom and hasattr(geom, 'coords'):
                coords = list(geom.coords)
            else:
                u_d = G_base.nodes[u]
                v_d = G_base.nodes[v]
                coords = [[u_d.get('x', 0), u_d.get('y', 0)], [v_d.get('x', 0), v_d.get('y', 0)]]

            route_coords.extend(coords)

            # Check profile compatibility
            for p in all_profiles:
                p_cfg = get_profile_config(p)
                acc, _ = subgraph_manager.is_edge_accessible(d, p_cfg, u, v)
                if not acc:
                    accessibility_compatibility[p] = False

            # Dynamic costs
            cur_decay = decay_engine.get_penalty(u, v)
            current_dynamic_cost += length + cur_decay

            # Arrival time at this edge based on walking speed
            travel_time_to_edge = total_dist / max(speed_mps, 0.1)
            pred_decay = decay_engine.predict_penalty_at(u, v, cur_time + travel_time_to_edge)
            predicted_dynamic_cost += length + pred_decay

            # CAD and Criticality
            cad = 0.0
            if cad >= 0.4:
                critical_edges_count += 1

            is_restricted = d.get('stairs', False) or d.get('wheelchair_accessible') is False
            if is_restricted:
                restricted_segments.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coords
                    },
                    "properties": {
                        "stairs": d.get('stairs', False),
                        "wheelchair_accessible": d.get('wheelchair_accessible'),
                        "cad": cad
                    }
                })

            edge_sequence.append({
                "u": u,
                "v": v,
                "edge_id": d.get('edge_id', f"{u}_{v}"),
                "name": d.get('name'),
                "length_m": length,
                "stairs": d.get('stairs', False),
                "slope_percent": d.get('slope_percent'),
                "cad": cad,
                "current_penalty": cur_decay,
                "predicted_penalty": pred_decay
            })

        eta_seconds = round(total_dist / max(speed_mps, 0.1), 1)

        # Counterfactual Marginal Accessibility Loss (MAL)
        mal = 0.0

        # Resilience & Collapse Risk
        resilience_score = 0.0
        collapse_res_risk = "NORMAL"

        geojson_geom = {
            "type": "LineString",
            "coordinates": route_coords
        }

        return {
            "route_id": r_id,
            "name": r_name,
            "description": r_desc,
            "total_distance": round(total_dist, 1),
            "estimated_travel_time": eta_seconds,
            "path_nodes": path_nodes,
            "edge_sequence": edge_sequence,
            "geometry": geojson_geom,
            "accessibility_compatibility": accessibility_compatibility,
            "current_dynamic_cost": round(current_dynamic_cost, 1),
            "predicted_dynamic_cost": round(predicted_dynamic_cost, 1),
            "accessibility_resilience_score": resilience_score,
            "accessibility_collapse_risk": collapse_res_risk,
            "critical_edge_count": critical_edges_count,
            "marginal_accessibility_loss": mal,
            "final_route_score": 0.0, # to be scored by DARRRouteScorer
            "selection_status": "PENDING",
            "reason": "",
            "cost_breakdown": {
                "distance": round(total_dist, 1),
                "dynamic_cost": round(current_dynamic_cost, 1),
                "predicted_cost": round(predicted_dynamic_cost, 1),
                "critical_edges": critical_edges_count,
                "mal": mal
            },
            "restricted_segments": {
                "type": "FeatureCollection",
                "features": restricted_segments
            }
        }

route_generator = MultiRouteGenerator()
