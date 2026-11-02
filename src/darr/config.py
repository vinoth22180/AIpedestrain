import os
import yaml
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "config",
    "darr_config.yaml"
)

class ScoringWeights(BaseModel):
    distance_weight: float = 1.0
    time_weight: float = 1.0
    dynamic_cost_weight: float = 1.0
    criticality_penalty_weight: float = 0.5
    collapse_risk_penalty_weight: float = 1.0
    marginal_accessibility_loss_weight: float = 1.5

class ProfileConfig(BaseModel):
    name: str
    walking_speed_mps: float = 1.2
    min_accessibility_resilience: float = 1.0
    max_acceptable_additional_time: float = 120.0
    stairs_allowed: bool = True
    stairs_penalty: float = 0.0
    max_slope_percent: Optional[float] = None
    min_width_m: float = 0.0
    requires_wheelchair_tag: bool = False
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)

def load_darr_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        # Fallback dictionary if missing
        return {
            "profiles": {
                "general": {
                    "name": "General Pedestrian",
                    "walking_speed_mps": 1.4,
                    "min_accessibility_resilience": 0.0,
                    "max_acceptable_additional_time": 180.0,
                    "stairs_allowed": True,
                    "stairs_penalty": 0.5,
                    "max_slope_percent": None,
                    "min_width_m": 0.0,
                    "requires_wheelchair_tag": False,
                    "scoring_weights": {
                        "distance_weight": 1.0,
                        "time_weight": 1.0,
                        "dynamic_cost_weight": 1.0,
                        "criticality_penalty_weight": 0.2,
                        "collapse_risk_penalty_weight": 0.5,
                        "marginal_accessibility_loss_weight": 1.8
                    }
                },
                "elderly": {
                    "name": "Elderly",
                    "walking_speed_mps": 0.9,
                    "min_accessibility_resilience": 1.0,
                    "max_acceptable_additional_time": 90.0,
                    "stairs_allowed": True,
                    "stairs_penalty": 5.0,
                    "max_slope_percent": 8.0,
                    "min_width_m": 0.6,
                    "requires_wheelchair_tag": False,
                    "scoring_weights": {
                        "distance_weight": 0.8,
                        "time_weight": 1.2,
                        "dynamic_cost_weight": 1.5,
                        "criticality_penalty_weight": 1.5,
                        "collapse_risk_penalty_weight": 2.0,
                        "marginal_accessibility_loss_weight": 0.8
                    }
                },
                "pregnant": {
                    "name": "Pregnancy-Oriented",
                    "walking_speed_mps": 1.0,
                    "min_accessibility_resilience": 1.0,
                    "max_acceptable_additional_time": 90.0,
                    "stairs_allowed": True,
                    "stairs_penalty": 3.5,
                    "max_slope_percent": 8.0,
                    "min_width_m": 0.6,
                    "requires_wheelchair_tag": False,
                    "scoring_weights": {
                        "distance_weight": 0.8,
                        "time_weight": 1.2,
                        "dynamic_cost_weight": 1.5,
                        "criticality_penalty_weight": 1.5,
                        "collapse_risk_penalty_weight": 2.0,
                        "marginal_accessibility_loss_weight": 0.8
                    }
                },
                "wheelchair": {
                    "name": "Mobility-Constrained / Wheelchair",
                    "walking_speed_mps": 0.8,
                    "min_accessibility_resilience": 2.0,
                    "max_acceptable_additional_time": 60.0,
                    "stairs_allowed": False,
                    "stairs_penalty": 9999.0,
                    "max_slope_percent": 6.0,
                    "min_width_m": 0.9,
                    "requires_wheelchair_tag": False,
                    "scoring_weights": {
                        "distance_weight": 0.6,
                        "time_weight": 1.0,
                        "dynamic_cost_weight": 2.0,
                        "criticality_penalty_weight": 2.5,
                        "collapse_risk_penalty_weight": 3.0,
                        "marginal_accessibility_loss_weight": 0.2
                    }
                }
            },
            "resilience": {
                "overlap_penalty_factor": 0.6,
                "bottleneck_cut_threshold": 1,
                "cad_cut_edge_weight": 0.6,
                "cad_detour_weight": 0.4
            },
            "collapse_prediction": {
                "forecast_horizon_seconds": 300.0,
                "warning_arl_threshold": 1.5,
                "critical_arl_threshold": 0.5
            },
            "counterfactual": {
                "simulated_pedestrian_load": 25,
                "congestion_increase_per_pedestrian": 2.0
            },
            "fleet_simulation": {
                "total_pedestrians": 100,
                "composition": {
                    "general": 60,
                    "elderly": 15,
                    "pregnant": 15,
                    "wheelchair": 10
                }
            }
        }
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

DARR_CONFIG = load_darr_config()

def get_profile_config(profile_name: str) -> ProfileConfig:
    p_name = profile_name.lower().strip() if profile_name else "general"
    profiles_dict = DARR_CONFIG.get("profiles", {})
    if p_name not in profiles_dict:
        # map common aliases
        if "wheel" in p_name or "mobility" in p_name:
            p_name = "wheelchair"
        elif "eld" in p_name:
            p_name = "elderly"
        elif "preg" in p_name:
            p_name = "pregnant"
        else:
            p_name = "general"
    data = profiles_dict.get(p_name, profiles_dict.get("general"))
    return ProfileConfig(**data)
