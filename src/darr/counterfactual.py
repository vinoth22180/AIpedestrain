import networkx as nx
from typing import Dict, Any, List, Optional
from src.darr.config import DARR_CONFIG
from src.darr.subgraph import subgraph_manager
from src.darr.resilience import resilience_engine

class CounterfactualRouteEvaluator:
    """
    Evaluates the counterfactual impact of routing pedestrian traffic along a candidate route:
    Simulates: "What happens to accessibility resilience if additional pedestrian load is assigned to this route?"
    Calculates Marginal Accessibility Loss (MAL) for constrained profiles (e.g. wheelchair, elderly).
    """

    def __init__(self):
        cf_cfg = DARR_CONFIG.get("counterfactual", {})
        self.default_simulated_load = cf_cfg.get("simulated_pedestrian_load", 25)
        self.congestion_per_pedestrian = cf_cfg.get("congestion_increase_per_pedestrian", 2.0)

    def simulate_assignment(
        self,
        G_base: nx.Graph,
        candidate_path: List[Any],
        target_profile: str = "wheelchair",
        source: Optional[Any] = None,
        destination: Optional[Any] = None,
        simulated_load: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Simulates additional pedestrian load on candidate_path and measures impact on target_profile.
        Returns:
        - arl_before
        - arl_after
        - mal (Marginal Accessibility Loss)
        - critical_edges_impacted
        """
        load = simulated_load if simulated_load is not None else self.default_simulated_load
        src = source if source is not None else candidate_path[0]
        dst = destination if destination is not None else candidate_path[-1]

        # 1. Baseline ARL before assignment
        G_target_sub = subgraph_manager.get_accessible_subgraph(G_base, target_profile)
        arl_before = resilience_engine.calculate_arl(G_target_sub, src, dst)

        # 2. Identify candidate route edges
        route_edges = []
        for i in range(len(candidate_path) - 1):
            u, v = candidate_path[i], candidate_path[i+1]
            route_edges.append((u, v))

        # 3. Simulate counterfactual network state
        G_counterfactual = G_target_sub.copy()
        critical_edges_impacted = []

        for u, v in route_edges:
            if G_target_sub.has_edge(u, v):
                cad = resilience_engine.calculate_cad_for_edge(G_base, u, v, target_profile)
                if cad >= 0.4:
                    critical_edges_impacted.append({
                        "edge": (u, v),
                        "cad": cad
                    })
                # High pedestrian load on high-CAD edges creates high congestion/bottleneck
                simulated_penalty = load * self.congestion_per_pedestrian * (1.0 + cad)
                # If congestion pushes the corridor beyond capacity, mark it as degraded or remove it from high-capacity corridors
                if simulated_penalty >= 50.0 and cad >= 0.6:
                    if G_counterfactual.is_multigraph():
                        for k in list(G_counterfactual[u][v].keys()):
                            G_counterfactual.remove_edge(u, v, k)
                    else:
                        G_counterfactual.remove_edge(u, v)

        # 4. ARL after simulated load
        arl_after = resilience_engine.calculate_arl(G_counterfactual, src, dst)

        # 5. Marginal Accessibility Loss (MAL)
        mal = max(0.0, round(arl_before - arl_after, 2))

        return {
            "target_profile": target_profile,
            "simulated_load": load,
            "arl_before": arl_before,
            "arl_after": arl_after,
            "marginal_accessibility_loss": mal,
            "critical_edges_impacted_count": len(critical_edges_impacted),
            "critical_edges_impacted": critical_edges_impacted
        }

counterfactual_evaluator = CounterfactualRouteEvaluator()
