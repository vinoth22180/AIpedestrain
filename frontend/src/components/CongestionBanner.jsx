import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';

export default function CongestionBanner({ refreshTrigger }) {
  const [congestedAreas, setCongestedAreas] = useState([]);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/congestion/map')
      .then(res => res.json())
      .then(data => {
        if(data.congested_areas) setCongestedAreas(data.congested_areas);
      })
      .catch(console.error);
  }, [refreshTrigger]);

  if (congestedAreas.length === 0) {
    return (
      <div style={{
        position: 'absolute',
        top: '24px',
        left: '50%',
        transform: 'translateX(-50%)',
        backgroundColor: 'var(--panel-bg)',
        backdropFilter: 'blur(var(--panel-blur))',
        padding: '8px 16px',
        borderRadius: 'var(--radius-full)',
        boxShadow: 'var(--shadow-md)',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        zIndex: 10,
        border: '1px solid var(--border-color)',
        animation: 'slideInUp 0.3s ease-out'
      }}>
        <CheckCircle2 size={16} color="var(--success-color)" />
        <span style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
          NORMAL PEDESTRIAN FLOW
        </span>
      </div>
    );
  }

  const primaryCongestion = congestedAreas.reduce((prev, current) => (prev.congestion_score > current.congestion_score) ? prev : current);

  const rawLevel = primaryCongestion.congestion_level;
  const displayLevel = (rawLevel === 'SEVERE' || rawLevel === 'HIGH') ? 'HIGH' : (rawLevel === 'MODERATE' || rawLevel === 'MEDIUM') ? 'MEDIUM' : 'LOW';

  const isRising = primaryCongestion.prediction && 
                   primaryCongestion.prediction.trend === 'INCREASING' && 
                   (primaryCongestion.prediction.predicted_level === 'HIGH' || primaryCongestion.prediction.predicted_level === 'SEVERE');

  return (
    <div style={{
      position: 'absolute',
      top: '24px',
      left: '50%',
      transform: 'translateX(-50%)',
      backgroundColor: displayLevel === 'HIGH' ? 'var(--danger-bg)' : displayLevel === 'MEDIUM' ? 'var(--warning-bg)' : 'var(--panel-bg)',
      backdropFilter: 'blur(var(--panel-blur))',
      padding: '8px 16px',
      borderRadius: 'var(--radius-full)',
      boxShadow: displayLevel === 'HIGH' ? '0 4px 12px rgba(239, 68, 68, 0.2)' : 'var(--shadow-md)',
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      zIndex: 10,
      border: displayLevel === 'HIGH' ? '1px solid #fecaca' : displayLevel === 'MEDIUM' ? '1px solid #fde68a' : '1px solid var(--border-color)',
      animation: 'slideInUp 0.3s ease-out'
    }}>
      <AlertTriangle size={16} color={displayLevel === 'HIGH' ? 'var(--danger-color)' : 'var(--warning-color)'} />
      
      {isRising ? (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
           <div style={{ fontSize: '0.75rem', fontWeight: '800', color: 'var(--danger-color)' }}>
              ⚠ CONGESTION RISING
           </div>
           <div style={{ fontSize: '0.65rem', fontWeight: '600', color: '#991b1b', marginTop: '2px' }}>
              {primaryCongestion.location} pedestrian density is increasing.<br/>
              High congestion is estimated within {primaryCongestion.prediction.horizon_minutes} minutes.
           </div>
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span style={{ fontSize: '0.75rem', fontWeight: '700', color: displayLevel === 'HIGH' ? 'var(--danger-color)' : 'var(--warning-color)' }}>
            {displayLevel} CONGESTION
          </span>
          <span style={{ fontSize: '0.75rem', fontWeight: '500', color: displayLevel === 'HIGH' ? '#991b1b' : 'var(--text-secondary)' }}>
            • {primaryCongestion.location} ({primaryCongestion.average_people} avg pedestrians)
          </span>
        </div>
      )}
    </div>
  );
}
