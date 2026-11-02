import React, { useState, useEffect } from 'react';
import { Navigation, MapPin, Search, ArrowDownUp, Info, AlertCircle, ChevronLeft } from 'lucide-react';
import WeatherPanel from './WeatherPanel';

const PROFILES = [
  { id: 'general', label: 'General', icon: '🚶', desc: 'Shortest efficient route' },
  { id: 'elderly', label: 'Elderly', icon: '👴', desc: 'Lower congestion and smoother paths' },
  { id: 'wheelchair', label: 'Wheelchair', icon: '♿', desc: 'Avoid stairs and inaccessible paths' },
  { id: 'pregnant', label: 'Pregnant', icon: '🤰', desc: 'Avoid steep slopes and high congestion' },
];

export default function Sidebar({ 
  onCalculate, 
  appState, 
  routeData, 
  activeCandidateId, 
  onSelectCandidate,
  isSidebarHidden = false,
  onToggleSidebar
}) {
  const [originIdx, setOriginIdx] = useState(0);
  const [destIdx, setDestIdx] = useState(1);
  const [locations, setLocations] = useState([]);
  const [profile, setProfile] = useState('general');

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/landmarks')
      .then(res => res.json())
      .then(data => {
        if (data && data.length > 0) {
          setLocations(data);
          setOriginIdx(0);
          setDestIdx(1 % data.length);
        }
      })
      .catch(console.error);
  }, []);

  const handleSwap = () => {
    setOriginIdx(destIdx);
    setDestIdx(originIdx);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (locations.length > 0) {
      onCalculate(
        locations[originIdx].coords, 
        locations[destIdx].coords, 
        profile,
        false, 
        locations[originIdx].name, 
        locations[destIdx].name
      );
    }
  };

  const isLoading = appState && appState.status === 'CALCULATING';
  const displayStats = routeData && routeData.stats ? routeData.stats : { distance: 0, cost: 0, congestion: 0 };
  const currentProfile = PROFILES.find(p => p.id === profile) || PROFILES[0];

  const getWalkingTime = (distanceMeters) => {
    return Math.round((distanceMeters / 1.4) / 60);
  };

  const activeCandidate = routeData?.candidate_routes?.find(c => c.route_id === (activeCandidateId || 'recommended'));
  const accessibility = routeData?.accessibility_summary || routeData?.stats?.accessibility || {};

  return (
    <div 
      className={`sidebar scroll-container ${isSidebarHidden ? 'hidden' : ''}`} 
      style={{ overflowY: 'auto' }}
      aria-hidden={isSidebarHidden}
    >
      {/* Brand Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ 
            width: '36px', height: '36px', borderRadius: 'var(--radius-md)', 
            backgroundColor: 'var(--accent-color)', display: 'flex', 
            alignItems: 'center', justifyContent: 'center', color: 'white',
            flexShrink: 0
          }}>
            <Navigation size={20} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.125rem', fontWeight: '700', lineHeight: '1.2', color: 'var(--text-primary)', margin: 0 }}>
              VIT WalkWise
            </h1>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Profile-Aware Pedestrian Navigation
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={() => onToggleSidebar && onToggleSidebar(true)}
          className="sidebar-toggle-btn"
          title="Hide navigation sidebar"
          aria-label="Hide navigation sidebar"
          aria-expanded={!isSidebarHidden}
        >
          <ChevronLeft size={18} />
        </button>
      </div>

      {/* Environmental Context */}
      <WeatherPanel />

      {/* Location Selection Form */}
      <div className="floating-card" style={{ marginBottom: '20px' }}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Origin (Starting Point)
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '24px', display: 'flex', justifyContent: 'center' }}>
                <MapPin size={18} color="var(--success-color)" />
              </div>
              <select className="select-control" value={originIdx} onChange={e => setOriginIdx(Number(e.target.value))}>
                {locations.map((loc, idx) => (
                  <option key={idx} value={idx}>{loc.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', margin: '-8px 0' }}>
            <button 
              type="button" 
              onClick={handleSwap}
              style={{
                background: 'none', border: '1px solid var(--border-color)', borderRadius: '50%',
                width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: 'pointer', color: 'var(--text-muted)', backgroundColor: 'white'
              }}
              title="Swap Origin and Destination"
            >
              <ArrowDownUp size={14} />
            </button>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Destination
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '24px', display: 'flex', justifyContent: 'center' }}>
                <MapPin size={18} color="var(--danger-color)" />
              </div>
              <select className="select-control" value={destIdx} onChange={e => setDestIdx(Number(e.target.value))}>
                {locations.map((loc, idx) => (
                  <option key={idx} value={idx}>{loc.name}</option>
                ))}
              </select>
            </div>
          </div>
          
          {/* STEP 18: Profile Selector */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <h3 style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
                Routing Profile
              </h3>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {PROFILES.map(p => (
                <label key={p.id} style={{
                  display: 'flex', alignItems: 'flex-start', gap: '8px',
                  padding: '8px 10px', borderRadius: 'var(--radius-md)',
                  border: `1.5px solid ${profile === p.id ? 'var(--accent-color)' : 'var(--border-color)'}`,
                  backgroundColor: profile === p.id ? 'var(--accent-light)' : 'white',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}>
                  <input 
                    type="radio" 
                    name="profile" 
                    value={p.id} 
                    checked={profile === p.id} 
                    onChange={() => setProfile(p.id)}
                    style={{ marginTop: '2px' }}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '1rem' }}>{p.icon}</span>
                      <span style={{ fontSize: '0.8125rem', fontWeight: '700', color: profile === p.id ? 'var(--accent-color)' : 'var(--text-primary)' }}>
                        {p.label}
                      </span>
                    </div>
                    <span style={{ display: 'block', fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {p.desc}
                    </span>
                  </div>
                </label>
              ))}
            </div>

            {/* STEP 19: Active Profile Status */}
            <div style={{
              marginTop: '10px',
              padding: '6px 10px',
              backgroundColor: '#f1f5f9',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.7rem'
            }}>
              <span style={{ fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                PROFILE ACTIVE
              </span>
              <span style={{ fontWeight: '700', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                {currentProfile.icon} {currentProfile.label}
              </span>
            </div>
          </div>

          <button type="submit" className="btn-primary" disabled={isLoading || locations.length === 0}>
            {isLoading ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div className="animate-spin" style={{ width: '16px', height: '16px', border: '2px solid white', borderTopColor: 'transparent', borderRadius: '50%' }} />
                Finding optimal route...
              </span>
            ) : (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Search size={18} /> Find Pedestrian Route
              </span>
            )}
          </button>
        </form>
      </div>

      {/* STEP 14: Clear No Route Found Card */}
      {routeData && routeData.error && (
        <div className="floating-card animate-slide-up" style={{ border: '2px solid var(--danger-color)', backgroundColor: '#fef2f2', marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <AlertCircle size={20} color="var(--danger-color)" />
            <h3 style={{ fontSize: '0.8125rem', fontWeight: '800', color: 'var(--danger-color)', margin: 0, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              NO ACCESSIBLE ROUTE FOUND
            </h3>
          </div>
          <p style={{ fontSize: '0.8125rem', color: '#991b1b', lineHeight: '1.5', margin: 0 }}>
            {routeData.error}
          </p>
          <div style={{ marginTop: '8px', fontSize: '0.7rem', color: '#b91c1c' }}>
            Active Profile: <strong>{currentProfile.icon} {currentProfile.label}</strong>
          </div>
        </div>
      )}

      {/* STEP 20: Route Result Card */}
      {routeData && routeData.stats && !isLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          <div className="floating-card animate-slide-up" style={{ border: '2px solid var(--accent-color)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '0.875rem', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--accent-color)', margin: 0 }}>
                  {activeCandidate ? activeCandidate.category : "Your Route"}
                </h3>
                <span style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                  {profile === 'wheelchair' ? '♿ Wheelchair Accessible' :
                   profile === 'pregnant' ? '🤰 Comfortable Route' :
                   profile === 'elderly' ? '👴 Gentle Route' : '🚶 Standard Pedestrian Route'}
                </span>
              </div>
              <span className="badge badge-neutral">{routeData.algorithm || 'A*'}</span>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '4px' }}>
              <span style={{ fontSize: '2rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                {(displayStats.distance / 1000).toFixed(2)}
              </span>
              <span style={{ fontSize: '1rem', fontWeight: '600', color: 'var(--text-secondary)' }}>km</span>
            </div>
            <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
              ~{getWalkingTime(displayStats.distance)} min walk
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Effective Cost</span>
                <span style={{ fontWeight: '600' }}>{Math.round(displayStats.cost)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Congestion Impact</span>
                {(() => {
                  const level = accessibility?.max_congestion_level || routeData?.congestion_level || (displayStats.congestion > 0 ? 'HIGH' : 'LOW');
                  if (level === 'HIGH' || level === 'SEVERE') {
                    return <span className="badge badge-danger" style={{ backgroundColor: '#fee2e2', color: '#991b1b', fontWeight: '700' }}>HIGH</span>;
                  } else if (level === 'MEDIUM' || level === 'MODERATE') {
                    return <span className="badge badge-warning" style={{ backgroundColor: '#fef3c7', color: '#92400e', fontWeight: '700' }}>MEDIUM</span>;
                  }
                  return <span className="badge badge-success" style={{ backgroundColor: '#dcfce7', color: '#166534', fontWeight: '700' }}>LOW</span>;
                })()}
              </div>
            </div>

            {/* Profile Accessibility Checklist */}
            <div style={{ marginTop: '14px', paddingTop: '12px', borderTop: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{ fontSize: '0.65rem', fontWeight: '800', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                ACCESSIBILITY & CONSTRAINTS
              </span>
              {profile === 'wheelchair' && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#166534', fontWeight: '500' }}>
                    <span>✓</span> <span>No stairs ({accessibility?.stairs_count || 0} stair segments)</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#166534', fontWeight: '500' }}>
                    <span>✓</span> <span>Slope within safe limits ({accessibility?.max_slope_percent || 0}% max)</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#166534', fontWeight: '500' }}>
                    <span>✓</span> <span>Avoids restricted paths</span>
                  </div>
                </>
              )}
              {profile === 'pregnant' && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#166534', fontWeight: '500' }}>
                    <span>✓</span> <span>Avoids steep slopes (Max: {accessibility?.max_slope_percent || 0}% &le; 5%)</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#166534', fontWeight: '500' }}>
                    <span>✓</span> <span>Minimizes exposure to high congestion</span>
                  </div>
                </>
              )}
              {profile === 'elderly' && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#166534', fontWeight: '500' }}>
                    <span>✓</span> <span>Lower congestion sensitivity applied</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#166534', fontWeight: '500' }}>
                    <span>✓</span> <span>Reduced difficult sections & slope</span>
                  </div>
                </>
              )}
              {profile === 'general' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: '500' }}>
                  <span>✓</span> <span>Standard campus pedestrian route</span>
                </div>
              )}
            </div>

            {/* Why This Route Explanation Card */}
            <div style={{ 
              marginTop: '16px', 
              padding: '12px', 
              backgroundColor: '#f8fafc', 
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              gap: '10px',
              alignItems: 'flex-start'
            }}>
              <Info size={16} color="var(--accent-color)" style={{ marginTop: '2px', flexShrink: 0 }} />
              <div>
                <span style={{ display: 'block', fontSize: '0.65rem', fontWeight: '800', color: 'var(--text-muted)', marginBottom: '4px' }}>WHY THIS ROUTE?</span>
                <p style={{ fontSize: '0.75rem', lineHeight: '1.5', color: 'var(--text-secondary)', margin: 0 }}>
                  {activeCandidate && activeCandidate.route_id === 'shortest' 
                    ? "This is the shortest physical path complying with profile constraints. Congestion penalties have been ignored."
                    : (routeData.route_explanation?.reason || "A* selected the lowest-cost pedestrian route based on your profile.")}
                </p>
              </div>
            </div>
          </div>

          {/* STEP 16: Alternative Routes */}
          {routeData.candidate_routes && routeData.candidate_routes.length > 1 && (
            <div>
              <h3 style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px', marginTop: '8px' }}>
                Alternative Routes ({currentProfile.label} Profile)
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {routeData.candidate_routes.map((candidate) => (
                  <div 
                    key={candidate.route_id}
                    onClick={() => onSelectCandidate && onSelectCandidate(candidate)}
                    style={{
                      padding: '12px',
                      borderRadius: 'var(--radius-md)',
                      border: `1px solid ${(activeCandidateId || 'recommended') === candidate.route_id ? 'var(--accent-color)' : 'var(--border-color)'}`,
                      backgroundColor: (activeCandidateId || 'recommended') === candidate.route_id ? 'var(--accent-light)' : 'white',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      boxShadow: (activeCandidateId || 'recommended') === candidate.route_id ? '0 0 0 1px var(--accent-color)' : 'var(--shadow-sm)'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontSize: '0.875rem', fontWeight: '700', color: (activeCandidateId || 'recommended') === candidate.route_id ? 'var(--accent-color)' : 'var(--text-primary)' }}>
                        {candidate.category}
                      </span>
                      {candidate.congestion_level === 'HIGH' || candidate.congestion_level === 'SEVERE' ? (
                        <span style={{ fontSize: '0.65rem', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#fee2e2', color: '#991b1b', fontWeight: '700' }}>HIGH CONG</span>
                      ) : candidate.congestion_level === 'MEDIUM' || candidate.congestion_level === 'MODERATE' ? (
                        <span style={{ fontSize: '0.65rem', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#fef3c7', color: '#92400e', fontWeight: '700' }}>MED CONG</span>
                      ) : (
                        <span style={{ fontSize: '0.65rem', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#dcfce7', color: '#166534', fontWeight: '700' }}>LOW CONG</span>
                      )}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      <span>{(candidate.distance / 1000).toFixed(2)} km</span>
                      <span>Cost: {Math.round(candidate.total_cost)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
        </div>
      )}
    </div>
  );
}
