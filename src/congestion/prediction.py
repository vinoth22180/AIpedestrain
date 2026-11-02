from typing import List, Dict, Any
from .manager import CongestionState
from .config import CongestionConfig

def calculate_trend_and_prediction(history: List[CongestionState], horizon_minutes: int = 10) -> Dict[str, Any]:
    if len(history) < 3:
        return {
            "prediction_available": False,
            "message": "More observations required."
        }
    
    # We need to make sure history is sorted by timestamp just in case
    sorted_history = sorted(history, key=lambda x: x.timestamp)
    
    # Consider only the recent MAX_OBSERVATIONS for trend to keep it responsive (e.g. last 5)
    recent = sorted_history[-5:]
    
    scores = [obs.congestion_score for obs in recent]
    times = [obs.timestamp for obs in recent]
    
    # Calculate Moving Average (simple average of recent)
    moving_average = sum(scores) / len(scores)
    
    # Calculate Slope (linear regression over time)
    # Time is in seconds. Let's convert time to minutes relative to the first observation in 'recent'
    t0 = times[0]
    t_mins = [(t - t0) / 60.0 for t in times]
    
    n = len(recent)
    sum_t = sum(t_mins)
    sum_s = sum(scores)
    sum_ts = sum(t * s for t, s in zip(t_mins, scores))
    sum_tt = sum(t * t for t in t_mins)
    
    # Avoid division by zero if all timestamps are identical (shouldn't happen in real use, but defensive)
    denominator = (n * sum_tt - sum_t * sum_t)
    if denominator == 0:
        slope_per_min = 0.0
    else:
        slope_per_min = (n * sum_ts - sum_t * sum_s) / denominator
        
    # Determine trend category
    # If slope changes score by more than 0.01 per minute, it's a clear trend
    trend = "STABLE"
    if slope_per_min > 0.01:
        trend = "INCREASING"
    elif slope_per_min < -0.01:
        trend = "DECREASING"
        
    # Short-term Extrapolation
    # We extrapolate from the last observation
    last_score = scores[-1]
    
    # Extrapolate
    raw_predicted_score = last_score + (slope_per_min * horizon_minutes)
    
    # Clamp to [0, 1]
    predicted_score = max(0.0, min(1.0, raw_predicted_score))
    
    # Convert to level
    predicted_level = CongestionConfig.get_level(predicted_score)
    
    return {
        "prediction_available": True,
        "predicted_score": round(predicted_score, 2),
        "predicted_level": predicted_level,
        "horizon_minutes": horizon_minutes,
        "trend": trend,
        "slope": round(slope_per_min, 4),
        "moving_average": round(moving_average, 2),
        "observation_count": len(history),
        "method": "Short-term trend extrapolation"
    }
