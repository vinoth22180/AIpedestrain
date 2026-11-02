from dataclasses import dataclass, field
from typing import Optional, Any

@dataclass
class PhysicalState:
    distance: float = 0.0
    highway: str = "unknown"
    surface: str = "unknown"

@dataclass
class AccessibilityState:
    stairs: bool = False
    ramp: bool = False
    slope_percent: Optional[float] = None
    slope_status: str = "unknown"
    crossing: str = "no"
    barrier: str = "no"
    subway: bool = False

@dataclass
class DynamicState:
    congestion_penalty: float = 0.0
    active_events: int = 0
    weather_impact: float = 0.0 # newly added for phase 2
    waterlogging_depth: float = 0.0 # newly added for phase 3

@dataclass
class TemporalState:
    simulation_time: float = 0.0

@dataclass
class ConfidenceState:
    source: str = "OSM"
    freshness: str = "static"

@dataclass
class RoutingCostState:
    base_cost: float = 0.0
    accessibility_cost: float = 0.0
    effort_cost: float = 0.0
    safety_cost: float = 0.0
    congestion_cost: float = 0.0
    signal_cost: float = 0.0
    decay_cost: float = 0.0
    weather_cost: float = 0.0
    waterlogging_cost: float = 0.0 # newly added for phase 3
    total_effective_cost: float = 0.0

@dataclass
class EdgeState:
    u: Any = None
    v: Any = None
    physical: PhysicalState = field(default_factory=PhysicalState)
    accessibility: AccessibilityState = field(default_factory=AccessibilityState)
    dynamic: DynamicState = field(default_factory=DynamicState)
    temporal: TemporalState = field(default_factory=TemporalState)
    confidence: ConfidenceState = field(default_factory=ConfidenceState)
    routing: RoutingCostState = field(default_factory=RoutingCostState)

@dataclass
class WeatherState:
    temperature: Optional[float] = None
    apparent_temperature: Optional[float] = None
    precipitation: Optional[float] = None
    precipitation_probability: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    weather_condition: str = "unknown"
    timestamp: Optional[float] = None
    retrieved_timestamp: Optional[float] = None
    source: str = "unknown"
    freshness: str = "UNAVAILABLE"
    
    @property
    def is_valid(self):
        return self.freshness in ["FRESH", "STALE", "LIVE"]
