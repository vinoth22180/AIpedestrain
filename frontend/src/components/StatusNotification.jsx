import React, { useEffect, useState } from 'react';
import { CheckCircle2, AlertTriangle, Loader2, XCircle, Info } from 'lucide-react';

const StatusNotification = ({ appState }) => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (appState.status !== 'IDLE') {
      setVisible(true);
      
      // Auto-dismiss success and info states after 5 seconds
      if (['ROUTE_READY', 'IDLE'].includes(appState.status) && appState.type === 'success') {
        const timer = setTimeout(() => setVisible(false), 5000);
        return () => clearTimeout(timer);
      }
    } else {
      setVisible(false);
    }
  }, [appState]);

  if (!visible) return null;

  const getIcon = () => {
    switch (appState.type) {
      case 'success': return <CheckCircle2 size={20} color="var(--success-color)" />;
      case 'warning': return <AlertTriangle size={20} color="var(--warning-color)" />;
      case 'danger': return <XCircle size={20} color="var(--danger-color)" />;
      default:
        if (appState.status === 'ROUTING' || appState.status === 'ANALYZING') {
          return <Loader2 size={20} className="animate-spin" color="var(--accent-color)" />;
        }
        return <Info size={20} color="var(--accent-color)" />;
    }
  };

  const getTitle = () => {
    switch (appState.status) {
      case 'ROUTING': return 'Calculating Route';
      case 'ROUTE_READY': return 'Route Ready';
      case 'ANALYZING': return 'Processing Video';
      case 'CONGESTION_ACTIVE': return 'Crowd Analysis Complete';
      case 'ERROR': return 'Error';
      default: return 'Information';
    }
  };

  return (
    <div style={{
      position: 'absolute',
      bottom: '24px',
      left: '24px',
      zIndex: 1000,
      display: 'flex',
      alignItems: 'flex-start',
      gap: '12px',
      minWidth: '280px',
      maxWidth: '360px',
      padding: '16px',
      backgroundColor: 'var(--panel-bg)',
      backdropFilter: 'blur(var(--panel-blur))',
      border: '1px solid var(--border-color)',
      borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-float)',
      animation: 'slideInUp 0.3s ease-out forwards',
    }}>
      <div style={{ marginTop: '2px' }}>
        {getIcon()}
      </div>
      <div>
        <h4 style={{ margin: '0 0 4px 0', fontSize: '0.875rem', fontWeight: '600' }}>
          {getTitle()}
        </h4>
        <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
          {appState.message}
        </p>
      </div>
    </div>
  );
};

export default StatusNotification;
