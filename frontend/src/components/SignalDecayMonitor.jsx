import React from 'react';

const SignalDecayMonitor = ({ activeEvents }) => {
  if (!activeEvents || activeEvents.length === 0) {
    return (
      <div style={{ padding: '15px', background: '#f5f5f5', borderRadius: '8px', marginTop: '10px' }}>
        <h3>Signal Decay Monitor</h3>
        <p>No active events.</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '15px', background: '#fff', borderRadius: '8px', marginTop: '10px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)', maxHeight: '300px', overflowY: 'auto' }}>
      <h3 style={{ margin: '0 0 10px 0' }}>Signal Decay Monitor</h3>
      {activeEvents.map((evt, idx) => {
        const percent = Math.min(100, Math.max(0, (evt.current_penalty / evt.initial_penalty) * 100));
        return (
          <div key={idx} style={{ marginBottom: '15px', borderBottom: '1px solid #eee', paddingBottom: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <strong>Event: {evt.event_type}</strong>
              <span style={{ color: percent > 50 ? 'red' : 'orange' }}>Active</span>
            </div>
            <div style={{ fontSize: '0.9em', color: '#555', marginTop: '5px' }}>
              <div>Initial Penalty: {evt.initial_penalty.toFixed(1)}</div>
              <div>Current Penalty: {evt.current_penalty.toFixed(1)}</div>
              <div>Decay Rate (λ): {evt.lambda_rate.toFixed(4)}</div>
              <div>Elapsed Time: {evt.elapsed_time.toFixed(1)}s</div>
            </div>
            <div style={{ marginTop: '8px', background: '#e0e0e0', height: '10px', borderRadius: '5px', overflow: 'hidden' }}>
              <div style={{ width: `${percent}%`, background: percent > 50 ? '#f44336' : (percent > 20 ? '#ff9800' : '#4caf50'), height: '100%' }}></div>
            </div>
            <div style={{ fontSize: '0.8em', textAlign: 'right', marginTop: '2px' }}>
              {percent.toFixed(1)}% remaining
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default SignalDecayMonitor;
