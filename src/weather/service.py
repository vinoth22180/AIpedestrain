import requests
import time
from src.models.edge_state import WeatherState
from typing import Optional

class WeatherService:
    def __init__(self):
        # VIT Vellore coordinates
        self.lat = 12.9692
        self.lon = 79.1559
        self.cache_ttl = 300 # 5 minutes
        self.stale_threshold = 3600 # 1 hour
        self.current_weather = WeatherState()
        self.last_fetch_time = 0

    def get_current_weather(self) -> WeatherState:

        now = time.time()
        
        # Check cache
        if now - self.last_fetch_time < self.cache_ttl and self.current_weather.freshness != "UNAVAILABLE":
            # Update freshness if needed
            if now - self.last_fetch_time > self.stale_threshold:
                self.current_weather.freshness = "STALE"
            return self.current_weather

        # Fetch from Open-Meteo
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={self.lat}&longitude={self.lon}&current=temperature_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m,relative_humidity_2m"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            current = data.get("current", {})
            
            # Map weather code to condition
            code = current.get("weather_code", 0)
            condition = "Clear"
            if code in [1, 2, 3]: condition = "Cloudy"
            elif code in [45, 48]: condition = "Fog"
            elif code in [51, 53, 55, 56, 57]: condition = "Drizzle"
            elif code in [61, 63, 65, 66, 67, 80, 81, 82]: condition = "Rain"
            elif code in [95, 96, 99]: condition = "Thunderstorm"

            self.current_weather = WeatherState(
                temperature=current.get("temperature_2m"),
                apparent_temperature=current.get("apparent_temperature"),
                precipitation=current.get("precipitation"),
                precipitation_probability=None, # Not in current weather usually
                humidity=current.get("relative_humidity_2m"),
                wind_speed=current.get("wind_speed_10m"),
                weather_condition=condition,
                timestamp=current.get("time"),
                retrieved_timestamp=now,
                source="Open-Meteo",
                freshness="LIVE"
            )
            self.last_fetch_time = now
        except Exception as e:
            print(f"[WEATHER SERVICE] Error fetching weather: {e}")
            if self.current_weather.freshness != "UNAVAILABLE":
                if now - self.last_fetch_time > self.stale_threshold:
                    self.current_weather.freshness = "STALE"
            else:
                self.current_weather = WeatherState(freshness="UNAVAILABLE")

        return self.current_weather

weather_service = WeatherService()
