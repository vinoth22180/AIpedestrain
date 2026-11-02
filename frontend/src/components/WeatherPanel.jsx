import React, { useState, useEffect } from 'react';
import { CloudRain, Sun, Wind, Cloud, Loader2 } from 'lucide-react';

export default function WeatherPanel() {
  const [weather, setWeather] = useState(null);
  const [error, setError] = useState(null);

  const fetchWeather = () => {
    fetch('http://127.0.0.1:8000/api/weather')
      .then(res => {
        if (!res.ok) throw new Error("Failed to fetch");
        return res.json();
      })
      .then(data => {
        setWeather(data);
        setError(null);
      })
      .catch(err => {
        setError("Unavailable");
      });
  };

  useEffect(() => {
    fetchWeather();
    const interval = setInterval(fetchWeather, 60000); // 1 min poll
    return () => clearInterval(interval);
  }, []);

  if (error || !weather) return null;

  const Icon = weather.precipitation > 0 ? CloudRain : (weather.temperature > 30 ? Sun : Cloud);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      backgroundColor: '#f8fafc',
      padding: '10px 16px',
      borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--border-color)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <Icon size={24} color={weather.precipitation > 0 ? '#3b82f6' : '#f59e0b'} />
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '1.125rem', fontWeight: '700', color: 'var(--text-primary)' }}>
              {weather.temperature !== null ? `${weather.temperature.toFixed(1)}°C` : '--'}
            </span>
            <span style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
              {weather.weather_condition}
            </span>
          </div>
          <div style={{ display: 'flex', gap: '12px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Wind size={12} /> {weather.wind_speed || 0} km/h
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <CloudRain size={12} /> {weather.precipitation || 0} mm
            </span>
          </div>
        </div>
      </div>
      
      {weather.freshness && (
        <span className={`badge ${weather.freshness === 'LIVE' ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: '0.6rem' }}>
          {weather.freshness}
        </span>
      )}
    </div>
  );
}
