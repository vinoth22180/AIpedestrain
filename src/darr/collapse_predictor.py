import math
import networkx as nx
from typing import Dict, Any, List, Optional
from src.darr.config import DARR_CONFIG, get_profile_config
from src.darr.subgraph import subgraph_manager
from src.darr.resilience import resilience_engine
from src.signal_decay.engine import decay_engine

class AccessibilityCollapsePredictor:
    """
    Predicts whether dynamic conditions and congestion propagation will reduce
    accessible network resilience below protected thresholds before total corridor failure.
    """

    def __init__(self):
        collapse_cfg = DARR_CONFIG.get("collapse_prediction", {})
        self.forecast_horizon = collapse_cfg.get("forecast_horizon_seconds", 300.0) # 5 minutes

    def predict_future_edge_cost(self, G_base: nx.Graph, u: Any, v: Any, d: Dict[str, Any], future_time: float) -> float:
        """
        Projects edge dynamic cost into the future using Signal Decay and predictive trends.
        """
        base_dist = d.get('length_m', d.get('length', 10.0))
        predicted_decay = decay_engine.predict_penalty_at(u, v, future_time)
        return float(base_dist + predicted_decay)

    def predict_resilience(
        self,
        G_base: nx.Graph,
        source: Any,
        destination: Any,
        profile_name: str,
        forecast_seconds: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluates current vs predicted accessibility resilience for a given OD pair.
        Returns detailed risk assessment.
        """
        horizon = forecast_seconds if forecast_seconds is not None else self.forecast_horizon
        future_sim_time = decay_engine.last_update_time + horizon
        profile_cfg = get_profile_config(profile_name)

        # 1. Current State
        G_sub_current = subgraph_manager.get_accessible_subgraph(G_base, profile_name)
        current_aoc = resilience_engine.calculate_aoc(G_sub_current, source, destination)
        current_arl = resilience_engine.calculate_arl(G_sub_current, source, destination)

        # 2. Predicted State (simulate edges that might become impassable or heavily degraded)
        # Check active decay events directly
        G_sub_predicted = G_sub_current.copy()
        severely_degraded_edges = []

        for event in decay_engine.events.values():
            if event.is_active:
                u_evt, v_evt = event.edge
                future_decay = decay_engine.predict_penalty_at(u_evt, v_evt, future_sim_time)
                if future_decay >= 150.0 and profile_name in ["wheelchair", "elderly", "pregnant"]:
                    severely_degraded_edges.append((u_evt, v_evt))
                    if G_sub_predicted.is_multigraph():
                        if G_sub_predicted.has_edge(u_evt, v_evt):
                            for k in list(G_sub_predicted[u_evt][v_evt].keys()):
                                G_sub_predicted.remove_edge(u_evt, v_evt, k)
                    else:
                        if G_sub_predicted.has_edge(u_evt, v_evt):
                            G_sub_predicted.remove_edge(u_evt, v_evt)

        predicted_aoc = resilience_engine.calculate_aoc(G_sub_predicted, source, destination)
        predicted_arl = resilience_engine.calculate_arl(G_sub_predicted, source, destination)

        # 3. Collapse Risk Classification
        min_threshold = profile_cfg.min_accessibility_resilience
        
        if current_arl == 0.0 or predicted_arl == 0.0:
            risk_level = "CRITICAL"
            risk_score = 1.0
        elif predicted_arl < min_threshold:
            risk_level = "WARNING"
            risk_score = 0.8
        elif predicted_arl < current_arl or (min_threshold > 0 and predicted_arl <= min_threshold + 0.2):
            risk_level = "ELEVATED"
            risk_score = 0.4
        else:
            risk_level = "NORMAL"
            risk_score = 0.1

        # 4. Time to Critical State Estimation
        time_to_critical = None
        if risk_level in ["WARNING", "CRITICAL"]:
            # Active decay / congestion has already pushed or will push below threshold within horizon
            time_to_critical = max(0.0, round(horizon * 0.5, 1))
        elif predicted_arl < current_arl and current_arl > min_threshold:
            rate_of_loss = (current_arl - predicted_arl) / max(horizon, 1.0)
            margin = current_arl - min_threshold
            if rate_of_loss > 0:
                time_to_critical = round(margin / rate_of_loss, 1)

        return {
            "profile": profile_name,
            "min_resilience_threshold": min_threshold,
            "current_aoc": current_aoc,
            "current_arl": current_arl,
            "predicted_aoc": predicted_aoc,
            "predicted_arl": predicted_arl,
            "collapse_risk": risk_level,
            "risk_score": risk_score,
            "time_to_critical_seconds": time_to_critical,
            "severely_degraded_edges_count": len(severely_degraded_edges),
            "threatened": risk_level in ["WARNING", "CRITICAL"]
        }

    def evaluate_all_profiles(
        self,
        G_base: nx.Graph,
        source: Any,
        destination: Any,
        forecast_seconds: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Runs collapse risk forecasting across all 4 standard user profiles.
        """
        profiles = ["general", "elderly", "pregnant", "wheelchair"]
        results = {}
        affected_profiles = []
        overall_risk = "NORMAL"

        for p in profiles:
            pred = self.predict_resilience(G_base, source, destination, p, forecast_seconds)
            results[p] = pred
            if pred["threatened"]:
                affected_profiles.append(p)
                if pred["collapse_risk"] == "CRITICAL":
                    overall_risk = "CRITICAL"
                elif overall_risk != "CRITICAL":
                    overall_risk = "WARNING"

        return {
            "overall_collapse_risk": overall_risk,
            "affected_profiles": affected_profiles,
            "profiles": results
        }

collapse_predictor = AccessibilityCollapsePredictor()
