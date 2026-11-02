import React, { useState, useEffect, useRef } from 'react';
import { Video, Activity, Users, FileVideo2, TrendingUp, TrendingDown, Minus, Clock, ChevronRight, ChevronLeft } from 'lucide-react';
import './CongestionPanel.css';

const CongestionPanel = ({ 
  onRecalculate, 
  onRefreshMap,
  setAppStatus,
  isMapSelectionMode,
  selectedMapLocation,
  onStartMapSelection,
  onCancelMapSelection,
  onClearSelectedMapLocation,
  isCollapsed: externalIsCollapsed,
  onToggleCollapse
}) => {
  const [internalIsCollapsed, setInternalIsCollapsed] = useState(false);
  const isCollapsed = externalIsCollapsed !== undefined ? externalIsCollapsed : internalIsCollapsed;

  const handleToggle = (nextVal) => {
    if (onToggleCollapse) {
      onToggleCollapse(nextVal);
    } else {
      setInternalIsCollapsed(nextVal);
    }
  };

  const [locations, setLocations] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState('');
  const [videoFile, setVideoFile] = useState(null);
  const [status, setStatus] = useState('');
  const [result, setResult] = useState(null);
  const [jobId, setJobId] = useState(null);

  const displayLocation = selectedMapLocation ? selectedMapLocation.display_name : selectedLocation;
  const apiLocation = selectedMapLocation ? selectedMapLocation.edge_id : selectedLocation;

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/academic_blocks')
      .then(res => res.json())
      .then(data => {
        if (data.features) {
          const locs = data.features.map(f => f.properties.short_name || f.properties.name);
          setLocations([...new Set(locs)].sort());
        }
      })
      .catch(console.error);
  }, []);

  const [trendData, setTrendData] = useState(null);
  const [historyData, setHistoryData] = useState([]);

  useEffect(() => {
    let interval;
    if (jobId && status.startsWith('processing')) {
      interval = setInterval(() => {
        fetch(`http://127.0.0.1:8000/api/congestion/status/${jobId}`)
          .then(res => res.json())
          .then(data => {
            if (data.status === 'completed') {
              setStatus('completed');
              setResult(data);
              clearInterval(interval);
              setAppStatus('CONGESTION_ACTIVE', `${data.location} • ${data.congestion_level}`, 'warning');
              
              // Fetch history and trend after completion
              Promise.all([
                fetch(`http://127.0.0.1:8000/api/congestion/history/${data.location}`).then(r => r.json()),
                fetch(`http://127.0.0.1:8000/api/congestion/trend/${data.location}`).then(r => r.json())
              ]).then(([histRes, trendRes]) => {
                if (histRes.history) setHistoryData(histRes.history);
                if (trendRes.prediction) setTrendData(trendRes.prediction);
                
                // Trigger recalculation which handles routing updates based on current congestion
                if (onRecalculate) onRecalculate();
              }).catch(console.error);

            } else if (data.status === 'failed') {
              setStatus('failed');
              clearInterval(interval);
              setAppStatus('ERROR', `Video processing failed for ${selectedLocation}.`, 'danger');
            } else if (data.status === 'processing' && data.progress) {
              const msg = `processing (${data.progress.percent}%)`;
              if (status !== msg) {
                setStatus(msg);
              }
            }
          })
          .catch(console.error);
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [jobId, status, onRecalculate, setAppStatus, selectedLocation, selectedMapLocation]);

  const [decayState, setDecayState] = useState(null);
  const lastDecayLevelRef = useRef(null);

  // Poll active decayed congestion for live updates
  useEffect(() => {
    const activeLoc = result?.location || apiLocation;
    if (!activeLoc || !status.startsWith('completed')) return;

    let isSubscribed = true;
    const pollInterval = setInterval(() => {
      fetch('http://127.0.0.1:8000/api/congestion/active')
        .then(res => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then(data => {
          if (!isSubscribed) return;
          const activeList = data?.active_congestions || [];
          const matched = activeList.find(c => c.location === activeLoc) || (activeList.length > 0 ? activeList[0] : null);
          
          if (matched) {
            setDecayState(matched);
            
            // Check if effective level crossed threshold (e.g. HIGH -> MODERATE, MODERATE -> LOW)
            if (lastDecayLevelRef.current && lastDecayLevelRef.current !== matched.effective_level) {
              setAppStatus(
                'CONGESTION_ACTIVE',
                `${matched.location} congestion influence decayed to ${matched.effective_level} (${Math.round(matched.effective_score * 100)}%)`,
                matched.effective_level === 'LOW' ? 'success' : 'warning'
              );
              if (onRecalculate) onRecalculate();
            } else if (!lastDecayLevelRef.current) {
              lastDecayLevelRef.current = matched.effective_level;
            }
            lastDecayLevelRef.current = matched.effective_level;
            
            // Trigger visual map refresh
            if (onRefreshMap) onRefreshMap();
          } else {
            setDecayState(prev => prev ? { ...prev, status: 'expired', effective_score: 0.0, effective_level: 'LOW' } : null);
          }
        })
        .catch(err => {
          console.warn('Failed to poll active congestion:', err);
        });
    }, 4000); // 4-second refresh

    return () => {
      isSubscribed = false;
      clearInterval(pollInterval);
    };
  }, [result, apiLocation, status, onRecalculate, onRefreshMap, setAppStatus]);

  const handleProcess = async () => {
    if (!apiLocation || !videoFile) {
      alert("Please select a location and video.");
      return;
    }

    const formData = new FormData();
    formData.append('location', apiLocation);
    formData.append('file', videoFile);

    setStatus('uploading');
    setAppStatus('ANALYZING', `Uploading video for ${displayLocation}...`, 'neutral');
    setResult(null);
    setDecayState(null);
    lastDecayLevelRef.current = null;

    try {
      const res = await fetch('http://127.0.0.1:8000/api/congestion/video', {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        setJobId(data.job_id);
        setStatus('processing');
        setAppStatus('ANALYZING', `Analyzing pedestrian density at ${displayLocation}...`, 'neutral');
      } else {
        setStatus('failed');
        setAppStatus('ERROR', `Upload failed.`, 'danger');
      }
    } catch (e) {
      console.error(e);
      setStatus('failed');
      setAppStatus('ERROR', `Upload failed.`, 'danger');
    }
  };

  const normalizeLevel = (level) => {
    if (!level) return 'LOW';
    if (level === 'SEVERE') return 'HIGH';
    if (level === 'MODERATE') return 'MEDIUM';
    return level;
  };

  const getLevelColor = (level) => {
    const l = normalizeLevel(level);
    switch (l) {
      case 'HIGH': return 'var(--danger-color)';
      case 'MEDIUM': return 'var(--warning-color)';
      case 'LOW': return 'var(--success-color)';
      default: return 'var(--success-color)';
    }
  };

  const getLevelDesc = (level) => {
    const l = normalizeLevel(level);
    switch (l) {
      case 'HIGH': return 'High congestion (Avoid for General & Vulnerable profiles)';
      case 'MEDIUM': return 'Medium congestion (Avoid for Elderly, Pregnant & Wheelchair)';
      case 'LOW': return 'Low congestion (Acceptable for all profiles)';
      default: return 'Normal pedestrian flow';
    }
  };

  const isBusy = status.startsWith('processing') || status === 'uploading';

  const curEffectiveLevel = normalizeLevel(decayState ? decayState.effective_level : (result?.congestion_level || 'LOW'));
  const curEffectiveScore = decayState ? decayState.effective_score : (result?.congestion_score || 0.0);
  const observedScore = decayState?.observed_score ?? result?.congestion_score ?? 0.0;
  const observedLevel = normalizeLevel(decayState?.observed_level ?? result?.congestion_level ?? 'LOW');
  const ageSeconds = decayState ? decayState.age_seconds : 0.0;
  const decayStatus = decayState ? decayState.status : 'fresh';
  const decayHalfLife = decayState ? decayState.decay_half_life_seconds : 180.0;
  const observedTimestamp = decayState?.observed_at || (result ? Date.now() / 1000 : 0);

  return (
    <>
      {/* Floating expand control shown when panel is collapsed */}
      {isCollapsed && (
        <button
          type="button"
          onClick={() => handleToggle(false)}
          className="congestion-expand-tab"
          title="Expand crowd analysis panel"
          aria-label="Expand crowd analysis panel"
          aria-expanded={false}
        >
          <span className="tab-icon">
            <ChevronLeft size={18} />
          </span>
          <Activity size={16} color="var(--accent-color)" />
          <span>Crowd Analysis</span>
          {curEffectiveLevel && curEffectiveLevel !== 'LOW' && (
            <span 
              className="congestion-expand-badge-dot" 
              style={{ 
                backgroundColor: getLevelColor(curEffectiveLevel),
                boxShadow: `0 0 6px ${getLevelColor(curEffectiveLevel)}`
              }}
              title={`Active Congestion: ${curEffectiveLevel}`}
            />
          )}
        </button>
      )}

      {/* Main panel container */}
      <div 
        className={`glass-panel scroll-container congestion-panel-wrapper ${isCollapsed ? 'collapsed' : ''}`}
        aria-hidden={isCollapsed}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '0.95rem', fontWeight: '800', margin: 0, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            <Activity size={20} color="var(--accent-color)" /> Live Crowd Analysis
          </h2>
          <button
            type="button"
            onClick={() => handleToggle(true)}
            className="congestion-panel-toggle-btn"
            title="Minimize crowd analysis panel"
            aria-label="Minimize crowd analysis panel"
            aria-expanded={!isCollapsed}
          >
            <ChevronRight size={18} />
          </button>
        </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '24px' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '8px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Location
          </label>
          {selectedMapLocation ? (
             <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
               <div style={{ fontSize: '0.875rem', fontWeight: '600' }}>{selectedMapLocation.display_name}</div>
               <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Edge ID: {selectedMapLocation.edge_id}</div>
               <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Coordinates: {selectedMapLocation.latitude.toFixed(5)}, {selectedMapLocation.longitude.toFixed(5)}</div>
               <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                 <button className="btn-secondary" style={{ padding: '4px 8px', fontSize: '0.75rem', flex: 1 }} onClick={onClearSelectedMapLocation}>Clear</button>
                 <button className="btn-secondary" style={{ padding: '4px 8px', fontSize: '0.75rem', flex: 1 }} onClick={onStartMapSelection}>Reselect</button>
               </div>
             </div>
          ) : isMapSelectionMode ? (
             <div style={{ padding: '12px', backgroundColor: '#e0f2fe', borderRadius: '4px', border: '1px solid #7dd3fc', color: '#0369a1', fontSize: '0.875rem' }}>
               <div style={{ fontWeight: '600', marginBottom: '8px' }}>Map Selection Mode</div>
               <p style={{ margin: 0, marginBottom: '8px' }}>Click on a pedestrian path on the map.</p>
               <button className="btn-secondary" onClick={onCancelMapSelection} style={{ width: '100%' }}>Cancel Selection</button>
             </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <select className="select-control" value={selectedLocation} onChange={e => setSelectedLocation(e.target.value)}>
                <option value="">Select Predefined Location</option>
                {locations.map(loc => (
                  <option key={loc} value={loc}>{loc}</option>
                ))}
                {!locations.includes('SJT') && <option value="SJT">SJT</option>}
                {!locations.includes('TT') && <option value="TT">TT</option>}
                {!locations.includes('MGR') && <option value="MGR">MGR</option>}
                {!locations.includes('SMV') && <option value="SMV">SMV</option>}
                {!locations.includes('PRP') && <option value="PRP">PRP</option>}
              </select>
              <div style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>— or —</div>
              <button className="btn-secondary" onClick={onStartMapSelection} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '8px' }}>
                <span role="img" aria-label="map">📍</span> Select Location on Map
              </button>
            </div>
          )}
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '8px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Campus Video
          </label>
          <label style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
            padding: '12px', border: '1px dashed var(--accent-color)', borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--accent-light)', color: 'var(--accent-hover)', cursor: 'pointer',
            fontSize: '0.875rem', fontWeight: '600', transition: 'all 0.2s'
          }}>
            <FileVideo2 size={18} />
            {videoFile ? videoFile.name : 'Choose Video'}
            <input type="file" accept="video/*" onChange={e => setVideoFile(e.target.files[0])} style={{ display: 'none' }} />
          </label>
        </div>

        <button className="btn-primary" onClick={handleProcess} disabled={isBusy || !apiLocation || !videoFile} style={{ marginTop: '8px' }}>
          {isBusy ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div className="animate-spin" style={{ width: '16px', height: '16px', border: '2px solid white', borderTopColor: 'transparent', borderRadius: '50%' }} />
              {status === 'uploading' ? 'Uploading...' : 'Analyzing Crowd...'}
            </span>
          ) : (
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Video size={18} /> Analyze Crowd
            </span>
          )}
        </button>
      </div>
      
      {result && (
        <div className="floating-card animate-slide-up" style={{ padding: '20px', borderTop: `4px solid ${getLevelColor(curEffectiveLevel)}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
              Current Effective Status
            </h3>
            <span style={{
              fontSize: '0.65rem',
              fontWeight: '700',
              padding: '2px 8px',
              borderRadius: '12px',
              backgroundColor: decayStatus === 'fresh' ? '#dcfce7' : decayStatus === 'aging' ? '#fef3c7' : '#f1f5f9',
              color: decayStatus === 'fresh' ? '#15803d' : decayStatus === 'aging' ? '#b45309' : '#64748b'
            }}>
              {decayStatus === 'fresh' ? '● FRESH' : decayStatus === 'aging' ? '⏱ AGING' : '✓ DECAYED'}
            </span>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
            <div style={{ 
              width: '48px', height: '48px', borderRadius: '50%', 
              backgroundColor: `${getLevelColor(curEffectiveLevel)}20`,
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <div style={{ width: '16px', height: '16px', borderRadius: '50%', backgroundColor: getLevelColor(curEffectiveLevel), boxShadow: `0 0 12px ${getLevelColor(curEffectiveLevel)}` }} />
            </div>
            <div>
              <div style={{ fontSize: '1.25rem', fontWeight: '800', color: getLevelColor(curEffectiveLevel), lineHeight: '1.2' }}>
                {curEffectiveLevel}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                {getLevelDesc(curEffectiveLevel)}
              </div>
            </div>
          </div>

          {/* Time & Observation Age */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', backgroundColor: '#f1f5f9', borderRadius: 'var(--radius-sm)', marginBottom: '16px', fontSize: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
              <Clock size={14} /> Observation Age:
            </div>
            <div style={{ fontWeight: '700', color: 'var(--text-primary)' }}>
              {Math.floor(ageSeconds)}s ago
            </div>
          </div>
          
          {/* Observed vs Decayed Effective Comparison */}
          <div style={{ padding: '12px', backgroundColor: '#f8fafc', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', marginBottom: '16px', fontSize: '0.75rem' }}>
            <div style={{ fontWeight: '700', color: 'var(--text-primary)', marginBottom: '8px', display: 'flex', justifyContent: 'space-between' }}>
              <span>Influence Decay</span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Half-life: {decayHalfLife}s</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Original YOLO Score</span>
              <span style={{ fontWeight: '700' }}>{Number(observedScore).toFixed(2)} ({observedLevel})</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Effective Score (A*)</span>
              <span style={{ fontWeight: '700', color: getLevelColor(curEffectiveLevel) }}>{Number(curEffectiveScore).toFixed(2)} ({curEffectiveLevel})</span>
            </div>

            {/* Visual Decay Meter Bar */}
            <div style={{ width: '100%', height: '8px', backgroundColor: '#e2e8f0', borderRadius: '4px', overflow: 'hidden', position: 'relative', marginBottom: '8px' }}>
              <div style={{
                width: `${Math.min(100, Math.max(0, Math.round((curEffectiveScore / Math.max(0.01, observedScore)) * 100)))}%`,
                height: '100%',
                backgroundColor: getLevelColor(curEffectiveLevel),
                transition: 'width 0.5s ease'
              }} />
            </div>

            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
              Estimated congestion influence is decreasing over time.
            </div>
            <div style={{ fontSize: '0.65rem', color: '#94a3b8', marginTop: '4px', fontStyle: 'italic', lineHeight: '1.3' }}>
              Note: Model estimates decaying observation influence over time. Physical crowd density is not guaranteed cleared without a newer observation.
            </div>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>Avg People</div>
              <div style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Users size={16} color="var(--text-muted)" /> {result.average_people}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>Peak</div>
              <div style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                {result.peak_people}
              </div>
            </div>
          </div>

          <div style={{ padding: '8px 12px', backgroundColor: '#f8fafc', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.75rem', display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Observed Timestamp</span>
            <span style={{ fontWeight: '600' }}>{new Date(observedTimestamp * 1000).toLocaleTimeString()}</span>
          </div>

          
          {/* Trend Section */}
          <div style={{ marginTop: '24px', borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
            <h3 style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
              Trend
            </h3>
            
            {trendData && trendData.prediction_available ? (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontWeight: '700', fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                  {trendData.trend === 'INCREASING' && <TrendingUp size={18} color="var(--danger-color)" />}
                  {trendData.trend === 'DECREASING' && <TrendingDown size={18} color="var(--success-color)" />}
                  {trendData.trend === 'STABLE' && <Minus size={18} color="var(--warning-color)" />}
                  {trendData.trend.charAt(0) + trendData.trend.slice(1).toLowerCase()}
                </div>
                
                {/* SVG Trend Graph (Sparkline) */}
                {historyData && historyData.length > 1 && (
                  <div style={{ width: '100%', height: '60px', marginBottom: '16px', position: 'relative' }}>
                    <svg width="100%" height="100%" viewBox="0 0 100 40" preserveAspectRatio="none">
                      <path 
                        d={`M 0,${40 - (historyData[0]?.congestion_score || 0) * 40} ` + 
                          historyData.map((d, i) => `L ${(i / (historyData.length - 1)) * 100},${40 - (d.congestion_score * 40)}`).join(' ')}
                        fill="none" 
                        stroke={trendData.trend === 'INCREASING' ? 'var(--danger-color)' : trendData.trend === 'DECREASING' ? 'var(--success-color)' : 'var(--warning-color)'}
                        strokeWidth="2" 
                        strokeLinejoin="round" 
                        strokeLinecap="round" 
                      />
                      {historyData.map((d, i) => (
                        <circle 
                          key={i} 
                          cx={(i / (historyData.length - 1)) * 100} 
                          cy={40 - (d.congestion_score * 40)} 
                          r="2" 
                          fill="var(--panel-bg)"
                          stroke={trendData.trend === 'INCREASING' ? 'var(--danger-color)' : trendData.trend === 'DECREASING' ? 'var(--success-color)' : 'var(--warning-color)'}
                          strokeWidth="1"
                        />
                      ))}
                    </svg>
                  </div>
                )}
              </>
            ) : (
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: '16px' }}>
                {trendData ? trendData.message : "Calculating trend..."}
              </div>
            )}
          </div>

          {/* Short-Term Estimate Section */}
          <div style={{ marginTop: '8px', borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
            <h3 style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
              Short-Term Estimate
            </h3>
            
            {trendData && trendData.prediction_available ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ fontSize: '1.125rem', fontWeight: '800', color: getLevelColor(trendData.predicted_level) }}>
                      {trendData.predicted_level}
                    </div>
                    <div style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                      Score: {trendData.predicted_score}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: 'var(--text-secondary)', backgroundColor: '#f1f5f9', padding: '4px 8px', borderRadius: '12px' }}>
                    <Clock size={12} /> ~{trendData.horizon_minutes} min
                  </div>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Pedestrian density is {trendData.trend.toLowerCase()}. {trendData.trend === 'INCREASING' && trendData.predicted_level === 'HIGH' ? "Expect heavy congestion." : ""}
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                — More observations required.
              </div>
            )}
          </div>

        </div>
      )}
    </div>
    </>
  );
};

export default CongestionPanel;
