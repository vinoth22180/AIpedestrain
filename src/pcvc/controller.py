import networkx as nx
from typing import Dict, Any, List, Optional, Tuple
from src.pcvc.models import (
    VerificationPlanResponse,
    VerificationCandidate,
    CounterfactualImpact,
    ProbeSelectionResult
)
from src.pcvc.uncertainty import get_uncertain_edges, format_edge_id
from src.pcvc.counterfactual import evaluate_counterfactual_impact
from src.pcvc.probe_selector import select_best_probe, find_nearest_landmark_anchor
from src.darr.resilience import resilience_engine
from src.darr.subgraph import subgraph_manager

DEFAULT_PCVC_WEIGHTS = {
    "w_uncertainty": 0.25,
    "w_delta_arl": 0.25,
    "w_delta_aoc": 0.15,
    "w_mal": 0.15,
    "w_cad": 0.15,
    "w_cost": 0.03,
    "w_risk": 0.02
}

class PCVCController:
    """
    Profile-Coupled Counterfactual Verification Controller (PCVC).
    Orchestrates:
    1. Identification of uncertain edges for target profile.
    2. Counterfactual edge removal and resilience degradation analysis (AOC, ARL, MAL, CAD).
    3. Multi-attribute normalized verification priority ranking.
    4. Closed-loop safe-return probe selection across all 4 profiles.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_PCVC_WEIGHTS

    def _get_edge_coordinates(self, G: nx.Graph, u: Any, v: Any, key: Any) -> Optional[List[List[float]]]:
        """Extracts GeoJSON coordinate array [[lon, lat], ...] for the edge."""
        edge_data = None
        if G.is_multigraph():
            if G.has_edge(u, v, key=key):
                edge_data = G.get_edge_data(u, v, key=key)
            elif G.has_edge(u, v):
                k_first = next(iter(G[u][v].keys()))
                edge_data = G.get_edge_data(u, v, key=k_first)
        else:
            if G.has_edge(u, v):
                edge_data = G.get_edge_data(u, v)

        if not edge_data:
            return None

        geom = edge_data.get("geometry")
        if geom and hasattr(geom, "coords"):
            return [list(pt) for pt in geom.coords]

        # Fallback to endpoint coordinates
        if G.has_node(u) and G.has_node(v):
            u_d = G.nodes[u]
            v_d = G.nodes[v]
            if "x" in u_d and "y" in u_d and "x" in v_d and "y" in v_d:
                return [[u_d["x"], u_d["y"]], [v_d["x"], v_d["y"]]]

        return None

    def compute_verification_targets(
        self,
        G: nx.Graph,
        target_profile: str = "wheelchair",
        top_k: int = 5,
        uncertainty_threshold: float = 0.4,
        candidate_limit: int = 40
    ) -> VerificationPlanResponse:
        """
        Main PCVC pipeline:
        1. Scan graph for candidate uncertain edges.
        2. Evaluate counterfactual impact for each candidate under target_profile.
        3. Rank candidates by normalized priority score.
        4. Select top target and evaluate safe probe profiles.
        """
        # 1. Detect candidate uncertain edges
        uncertain_states = get_uncertain_edges(
            G,
            profile=target_profile,
            uncertainty_threshold=uncertainty_threshold,
            limit=candidate_limit # Evaluate up to candidate_limit candidates for responsiveness
        )

        if not uncertain_states:
            return VerificationPlanResponse(
                target_profile=target_profile,
                selected_target=None,
                probe_selection=None,
                ranked_candidates=[],
                summary=f"No uncertain edges detected above threshold ({uncertainty_threshold}) for profile '{target_profile}'."
            )

        # Precompute bridges for fast CAD / cut-edge evaluation
        G_sub = subgraph_manager.get_accessible_subgraph(G, target_profile)
        bridge_cache = resilience_engine._get_bridges(G_sub)

        # 2. Evaluate counterfactual impact for each candidate
        candidates: List[VerificationCandidate] = []
        for state in uncertain_states:
            impact = evaluate_counterfactual_impact(
                G,
                state.u,
                state.v,
                state.key,
                target_profile=target_profile,
                bridge_cache=bridge_cache
            )
            coords = self._get_edge_coordinates(G, state.u, state.v, state.key)

            candidates.append(VerificationCandidate(
                edge_id=state.edge_id,
                u=state.u,
                v=state.v,
                key=state.key,
                name=state.name or f"Walkway_{state.u}_{state.v}",
                priority_score=0.0, # Computed next
                uncertainty=state.accessibility_uncertainty,
                impact=impact,
                reason="",
                coordinates=coords
            ))

        # 3. Normalize quantities and compute Priority Score
        max_delta_arl = max([c.impact.delta_arl for c in candidates] + [1.0])
        max_delta_aoc = max([c.impact.delta_aoc for c in candidates] + [1])
        max_mal = max([c.impact.mal_impact for c in candidates] + [1.0])

        w = self.weights
        for c in candidates:
            norm_unc = c.uncertainty
            norm_d_arl = c.impact.delta_arl / max_delta_arl if max_delta_arl > 0 else 0.0
            norm_d_aoc = c.impact.delta_aoc / max_delta_aoc if max_delta_aoc > 0 else 0.0
            norm_mal = c.impact.mal_impact / max_mal if max_mal > 0 else 0.0
            norm_cad = c.impact.cad # already in [0, 1]

            score = (
                w["w_uncertainty"] * norm_unc +
                w["w_delta_arl"] * norm_d_arl +
                w["w_delta_aoc"] * norm_d_aoc +
                w["w_mal"] * norm_mal +
                w["w_cad"] * norm_cad
            )
            c.priority_score = round(score, 3)

            # Construct human-readable reason
            if c.impact.is_cut_edge:
                c.reason = f"Essential accessible cut-edge: failure severs corridor connectivity for {target_profile} users (CAD=1.0, uncertainty={c.uncertainty*100:.0f}%)."
            elif c.impact.delta_arl > 0.3:
                c.reason = f"High accessibility impact: counterfactual failure causes ΔARL={c.impact.delta_arl:.1f} and ΔAOC={c.impact.delta_aoc} under {target_profile} constraints."
            elif c.impact.cad >= 0.5:
                c.reason = f"High bottleneck dependency (CAD={c.impact.cad}) with {c.uncertainty*100:.0f}% attribute uncertainty."
            else:
                c.reason = f"Pathway with {c.uncertainty*100:.0f}% uncertainty in accessibility tags."

        # Sort candidates descending by priority score
        candidates.sort(key=lambda x: (x.priority_score, x.impact.cad, x.uncertainty), reverse=True)
        top_candidates = candidates[:top_k]

        # 4. Probe Selection for the top candidate
        selected_target = top_candidates[0] if top_candidates else None
        probe_result: Optional[ProbeSelectionResult] = None

        if selected_target:
            probe_result = select_best_probe(
                G,
                selected_target.u,
                selected_target.v,
                selected_target.key
            )

        summary = (
            f"Evaluated {len(candidates)} uncertain edges for '{target_profile}'. "
            f"Top priority target: {selected_target.name} (Score: {selected_target.priority_score:.2f}). "
            f"Selected probe: {probe_result.selected_probe if probe_result else 'None'}."
        )

        return VerificationPlanResponse(
            target_profile=target_profile,
            selected_target=selected_target,
            probe_selection=probe_result,
            ranked_candidates=top_candidates,
            summary=summary
        )

pcvc_controller = PCVCController()
