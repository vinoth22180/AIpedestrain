from src.models.edge_state import WeatherState, EdgeState

# Base weather sensitivities per profile.
# These act as algorithmic weights, not medical facts.
WEATHER_PROFILE_SENSITIVITY = {
    "general": {
        "rain": 1.0,
        "heat": 1.0,
        "surface_unpaved_rain_modifier": 1.5
    },
    "elderly": {
        "rain": 1.5,
        "heat": 1.3,
        "surface_unpaved_rain_modifier": 2.0
    },
    "pregnant": {
        "rain": 1.3,
        "heat": 1.4,
        "surface_unpaved_rain_modifier": 1.8
    },
    "wheelchair": {
        "rain": 1.2,
        "heat": 1.1,
        "surface_unpaved_rain_modifier": 3.0 # Wheelchairs are highly sensitive to muddy/unpaved wet surfaces
    }
}

def calculate_weather_impact(weather: WeatherState, edge: EdgeState, profile: str) -> float:
    if not weather.is_valid:
        return 0.0

    profile = profile.lower()
    sensitivity = WEATHER_PROFILE_SENSITIVITY.get(profile, WEATHER_PROFILE_SENSITIVITY["general"])
    
    impact = 0.0
    
    # 1. Rain / Precipitation Impact
    if weather.precipitation and weather.precipitation > 0:
        # Base rain penalty per unit length
        rain_penalty = weather.precipitation * 0.5 * sensitivity["rain"]
        
        # Surface interaction
        surface = edge.physical.surface
        if surface in ["unpaved", "dirt", "ground", "compacted"]:
            rain_penalty *= sensitivity["surface_unpaved_rain_modifier"]
        elif surface in ["asphalt", "paving_stones", "paved"]:
            pass # normal rain penalty
        elif surface == "unknown":
            pass # Do not automatically declare unknown as unsafe
            
        impact += rain_penalty

    # 2. Extreme Heat Impact
    # E.g., Apparent temperature > 35C adds a penalty
    if weather.apparent_temperature and weather.apparent_temperature > 35.0:
        heat_penalty = (weather.apparent_temperature - 35.0) * 0.2 * sensitivity["heat"]
        impact += heat_penalty

    # Normalize to base distance (similar to congestion)
    return impact * (edge.physical.distance / 100.0)

