import React, { useState, useEffect } from 'react';
import { Layers, ChevronDown, ChevronUp, Eye, EyeOff } from 'lucide-react';

export default function MapLegend({ showPedestrianNetwork = true, onTogglePedestrianNetwork, isSidebarHidden = false }) {
  const [stats, setStats] = useState({
    stairs: 0,
    ramps: 0,
    slopes: 0,
    crossings: 0,
    barriers: 0,
    subways: 0
  });
  
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/pedestrian_network/stats')
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(console.error);
  }, []);

  const routeItems = [
    { label: 'Active Route', color: '#2563eb', casingColor: '#ffffff', type: 'cased-line', desc: 'Optimal profile-guided path' },
    { label: 'Alternative Route', color: '#6366f1', type: 'dashed-line', desc: 'Candidate pedestrian path' },
    { label: 'Start Point', color: '#10b981', type: 'marker', desc: 'Journey origin' },
    { label: 'Destination', color: '#ef4444', type: 'marker', desc: 'Journey destination' },
    { label: 'Selected Path', color: '#f59e0b', type: 'cased-line', casingColor: '#ffffff', desc: 'Selected for video congestion analysis' },
    { label: 'High Congestion Path', color: '#dc2626', type: 'dashed-line', desc: 'Heavy crowd (HIGH: avoid for General & Vulnerable)' },
    { label: 'Medium Congestion Path', color: '#f59e0b', type: 'dashed-line', desc: 'Medium crowd (MEDIUM: avoid for Vulnerable)' },
    { label: 'Low Congestion Path', color: '#10b981', type: 'dashed-line', desc: 'Normal crowd (LOW: acceptable for all)' },
  ];

  const networkItems = [
    { label: 'Campus Pedestrian Paths', color: '#334155', casingColor: '#ffffff', type: 'cased-line', count: null },
    { label: 'Perimeter / Vehicular Roads', color: '#94a3b8', type: 'dashed-line', count: null },
    { label: 'Stairs', icon: '🪜', color: '#b45309', type: 'line', dashArray: '3,3', count: stats.stairs },
    { label: 'Significant Slope (>4%)', icon: '↗', color: '#7c3aed', type: 'line', count: stats.slopes },
    { label: 'Crossing', icon: '🚸', color: '#0284c7', type: 'line', dashArray: '3,3', count: stats.crossings },
    { label: 'Barrier', icon: '🚧', color: '#b91c1c', type: 'line', count: stats.barriers },
    { label: 'Ramp', icon: '♿', color: '#059669', type: 'line', count: stats.ramps },
    { label: 'Pedestrian Subway', icon: '🚇', color: '#0891b2', type: 'line', dashArray: '1,2', count: stats.subways },
  ];

  return (
    <div 
      style={{
        position: 'absolute',
        top: '20px',
        left: isSidebarHidden ? '165px' : '20px',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(10px)',
        padding: isExpanded ? '16px' : '10px 16px',
        borderRadius: '12px',
        boxShadow: '0 4px 20px -2px rgba(0, 0, 0, 0.12), 0 2px 6px -1px rgba(0, 0, 0, 0.08)',
        zIndex: 10,
        pointerEvents: 'auto',
        minWidth: isExpanded ? '280px' : 'auto',
        maxWidth: '320px',
        border: '1px solid rgba(226, 232, 240, 0.9)',
        transition: 'all 0.25s ease',
        fontFamily: 'system-ui, -apple-system, sans-serif'
      }}
    >
      <div 
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          gap: '12px',
          cursor: 'pointer',
          userSelect: 'none'
        }}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Layers size={16} color="#3b82f6" />
          <h3 style={{ 
            margin: 0, 
            fontSize: '0.8rem', 
            fontWeight: '700',
            color: '#1e293b',
            letterSpacing: '0.02em'
          }}>
            Map Layers & Legend
          </h3>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {onTogglePedestrianNetwork && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onTogglePedestrianNetwork();
              }}
              title={showPedestrianNetwork ? 'Hide Pedestrian Network' : 'Show Pedestrian Network'}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                background: showPedestrianNetwork ? '#eff6ff' : '#f1f5f9',
                border: `1px solid ${showPedestrianNetwork ? '#bfdbfe' : '#cbd5e1'}`,
                borderRadius: '6px',
                padding: '3px 7px',
                fontSize: '0.7rem',
                fontWeight: '600',
                color: showPedestrianNetwork ? '#1d4ed8' : '#64748b',
                cursor: 'pointer'
              }}
            >
              {showPedestrianNetwork ? <Eye size={12} /> : <EyeOff size={12} />}
              <span>{showPedestrianNetwork ? 'Network On' : 'Network Off'}</span>
            </button>
          )}

          <button 
            style={{ 
              background: 'none', 
              border: 'none', 
              cursor: 'pointer', 
              padding: '2px',
              display: 'flex', 
              alignItems: 'center', 
              color: '#64748b' 
            }}
          >
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div style={{ marginTop: '14px', maxHeight: '70vh', overflowY: 'auto', paddingRight: '4px' }}>
          
          {/* Quick Toggle Controls */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 10px',
            backgroundColor: '#f8fafc',
            borderRadius: '8px',
            marginBottom: '12px',
            border: '1px solid #e2e8f0'
          }}>
            <span style={{ fontSize: '0.75rem', fontWeight: '600', color: '#334155' }}>
              Full Campus Network
            </span>
            <button
              onClick={onTogglePedestrianNetwork}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '4px 10px',
                fontSize: '0.72rem',
                fontWeight: '600',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: showPedestrianNetwork ? '#2563eb' : '#94a3b8',
                color: '#ffffff',
                cursor: 'pointer',
                transition: 'background-color 0.15s ease'
              }}
            >
              {showPedestrianNetwork ? <Eye size={13} /> : <EyeOff size={13} />}
              {showPedestrianNetwork ? 'Visible' : 'Hidden'}
            </button>
          </div>

          {/* Section: Navigation & Routing */}
          <div style={{ marginBottom: '14px' }}>
            <div style={{ 
              fontSize: '0.68rem', 
              fontWeight: '700', 
              textTransform: 'uppercase', 
              color: '#64748b', 
              letterSpacing: '0.05em',
              marginBottom: '8px'
            }}>
              Navigation & Status
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {routeItems.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {item.type === 'marker' ? (
                      <div style={{
                        width: '12px',
                        height: '12px',
                        borderRadius: '50%',
                        backgroundColor: item.color,
                        border: '2px solid #ffffff',
                        boxShadow: '0 0 0 1px rgba(0,0,0,0.15)'
                      }} />
                    ) : item.type === 'dashed-line' ? (
                      <div style={{
                        width: '18px',
                        height: '0px',
                        borderTop: `3px dashed ${item.color}`
                      }} />
                    ) : (
                      <div style={{
                        width: '18px',
                        height: '4px',
                        backgroundColor: item.color,
                        borderRadius: '2px',
                        boxShadow: '0 0 0 1px #ffffff'
                      }} />
                    )}

                    <span style={{ fontSize: '0.75rem', color: '#1e293b', fontWeight: '500' }}>
                      {item.label}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Section: Campus Walkway Network */}
          <div>
            <div style={{ 
              fontSize: '0.68rem', 
              fontWeight: '700', 
              textTransform: 'uppercase', 
              color: '#64748b', 
              letterSpacing: '0.05em',
              marginBottom: '8px'
            }}>
              Pedestrian Network Features
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
              {networkItems.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {item.icon ? (
                      <span style={{ fontSize: '13px', width: '18px', textAlign: 'center' }}>
                        {item.icon}
                      </span>
                    ) : item.type === 'dashed-line' ? (
                      <div style={{
                        width: '18px',
                        height: '0px',
                        borderTop: `2px dashed ${item.color}`
                      }} />
                    ) : (
                      <div style={{
                        width: '18px',
                        height: '3.5px',
                        backgroundColor: item.color,
                        borderRadius: '2px',
                        border: '1px solid #ffffff'
                      }} />
                    )}

                    <span style={{ fontSize: '0.73rem', color: '#334155', fontWeight: '500' }}>
                      {item.label}
                    </span>
                  </div>

                  {item.count !== null && item.count !== undefined && (
                    <span style={{ fontSize: '0.68rem', color: '#64748b', fontWeight: '600', backgroundColor: '#f1f5f9', padding: '1px 6px', borderRadius: '4px' }}>
                      {item.count}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div style={{ fontSize: '0.65rem', color: '#94a3b8', marginTop: '12px', borderTop: '1px solid #f1f5f9', paddingTop: '8px' }}>
            Slopes {'>'}4% are emphasized. Detailed labels appear when zoomed in.
          </div>
        </div>
      )}
    </div>
  );
}
