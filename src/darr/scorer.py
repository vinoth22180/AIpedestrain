from typing import Dict, Any, List, Tuple
from src.darr.config import get_profile_config, ProfileConfig

class DARRRouteScorer:
    """
    Computes multi-factor route scores and performs proportional traffic allocation.
    Evaluates candidate routes, identifies trade-offs, and generates computed decision rationales.
    """

    @staticmethod
    def score_candidate(candidate: Dict[str, Any], profile_cfg: ProfileConfig) -> float:
        """
        Computes the unified multi-factor score:
        RouteScore = w_dist * d + w_time * t + w_dyn * c_dyn + w_crit * Crit + w_coll * Risk + w_mal * MAL
        Lower score is better (cost minimization).
        """
        w = profile_cfg.scoring_weights

        dist_cost = candidate["total_distance"] * w.distance_weight
        time_cost = candidate["estimated_travel_time"] * w.time_weight
        dyn_cost = candidate["predicted_dynamic_cost"] * w.dynamic_cost_weight
        crit_cost = candidate["critical_edge_count"] * 25.0 * w.criticality_penalty_weight

        # Collapse risk penalty mapping
        risk_map = {
            "NORMAL": 0.0,
            "ELEVATED": 30.0,
            "WARNING": 100.0,
            "CRITICAL": 250.0
        }
        coll_cost = risk_map.get(candidate["accessibility_collapse_risk"], 0.0) * w.collapse_risk_penalty_weight

        # Marginal Accessibility Loss (MAL) penalty
        mal_cost = candidate["marginal_accessibility_loss"] * 80.0 * w.marginal_accessibility_loss_weight

        total_score = dist_cost + time_cost + dyn_cost + crit_cost + coll_cost + mal_cost
        return round(total_score, 1)

    def select_best_route(
        self,
        candidates: List[Dict[str, Any]],
        profile_name: str
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Evaluates all candidates and applies the proportional flexible allocation rule:
        - If profile is general/flexible:
          If fastest route has high MAL (> 0.5) and an alternative route has lower MAL,
          prefer the alternative route IF added time <= MAX_ACCEPTABLE_ADDITIONAL_TIME.
        - Generates dynamic computed explanations for every route.
        """
        if not candidates:
            return None, []

        profile_cfg = get_profile_config(profile_name)

        # 1. Score all candidates
        for c in candidates:
            c["final_route_score"] = self.score_candidate(c, profile_cfg)

        # Sort candidates by score
        sorted_by_score = sorted(candidates, key=lambda x: x["final_route_score"])
        fastest_route = min(candidates, key=lambda x: x["estimated_travel_time"])
        min_mal_route = min(candidates, key=lambda x: (x["marginal_accessibility_loss"], x["final_route_score"]))

        selected_candidate = sorted_by_score[0]
        max_time_tolerance = profile_cfg.max_acceptable_additional_time

        # 2. Check flexible reallocation logic for General Profile
        is_flexible_profile = profile_name.lower() in ["general", "pedestrian"]
        if is_flexible_profile and fastest_route["marginal_accessibility_loss"] > 0.4:
            # Check if there is an alternative that preserves accessibility
            for alt in sorted(candidates, key=lambda x: x["marginal_accessibility_loss"]):
                if alt["route_id"] != fastest_route["route_id"]:
                    added_time = alt["estimated_travel_time"] - fastest_route["estimated_travel_time"]
                    if added_time <= max_time_tolerance and alt["marginal_accessibility_loss"] < fastest_route["marginal_accessibility_loss"]:
                        selected_candidate = alt
                        break

        # 3. Formulate natural computed explanations
        for c in candidates:
            if c["route_id"] == selected_candidate["route_id"]:
                c["selection_status"] = "SELECTED"
                if c["route_id"] == fastest_route["route_id"]:
                    if c["marginal_accessibility_loss"] == 0:
                        c["reason"] = f"Selected as the fastest feasible route ({c['estimated_travel_time']:.0f}s) with zero marginal accessibility impact on mobility-constrained corridors."
                    else:
                        c["reason"] = f"Selected because it offers the optimal balance of travel time ({c['estimated_travel_time']:.0f}s) and predicted conditions."
                else:
                    added_time = c["estimated_travel_time"] - fastest_route["estimated_travel_time"]
                    saved_mal = fastest_route["marginal_accessibility_loss"] - c["marginal_accessibility_loss"]
                    c["reason"] = (
                        f"Selected because {fastest_route['name']} would reduce accessible network resilience (MAL: {fastest_route['marginal_accessibility_loss']:.1f}), "
                        f"whereas {c['name']} preserves critical corridors with only {added_time:.0f}s additional travel time (within {max_time_tolerance:.0f}s threshold)."
                    )
            else:
                c["selection_status"] = "REJECTED"
                if c["marginal_accessibility_loss"] > selected_candidate["marginal_accessibility_loss"]:
                    c["reason"] = f"Rejected because assigning load to this route incurs Marginal Accessibility Loss of {c['marginal_accessibility_loss']:.1f} on wheelchair corridors."
                elif c["predicted_dynamic_cost"] > selected_candidate["predicted_dynamic_cost"]:
                    c["reason"] = f"Rejected due to higher dynamic/predicted congestion penalty (+{c['predicted_dynamic_cost'] - selected_candidate['predicted_dynamic_cost']:.1f})."
                elif c["total_distance"] > selected_candidate["total_distance"]:
                    c["reason"] = f"Rejected due to excessive detour (+{c['total_distance'] - selected_candidate['total_distance']:.1f}m) without sufficient resilience benefit."
                else:
                    c["reason"] = f"Alternative candidate (Score: {c['final_route_score']:.1f} vs {selected_candidate['final_route_score']:.1f})."

        return selected_candidate, candidates

route_scorer = DARRRouteScorer()
