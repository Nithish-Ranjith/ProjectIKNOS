import React, { useState } from 'react';
import { Settings, Brain, Map, Shield, Palette } from 'lucide-react';
import { toast } from 'sonner';

export const AdminSettings: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'ai' | 'drone' | 'security' | 'appearance'>('ai');

  // Settings State initialized from LocalStorage
  const [aiConfidence, setAiConfidence] = useState(() => parseFloat(localStorage.getItem('ai_confidence') || '0.85'));
  const [autoApprove, setAutoApprove] = useState(() => parseInt(localStorage.getItem('auto_approve') || '5'));
  const [altitude, setAltitude] = useState(() => parseInt(localStorage.getItem('drone_altitude') || '60'));
  const [mapProvider, setMapProvider] = useState(() => localStorage.getItem('map_provider') || 'mapbox');
  const [offlineCache, setOfflineCache] = useState(() => localStorage.getItem('offline_cache') !== 'false');
  const [auditLock, setAuditLock] = useState(() => localStorage.getItem('audit_lock') !== 'false');
  
  // Theme state
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return document.body.classList.contains('theme-light') ? 'light' : 'dark';
  });

  const toggleTheme = (newTheme: 'dark' | 'light') => {
    setTheme(newTheme);
    if (newTheme === 'light') {
      document.body.classList.add('theme-light');
      localStorage.setItem('theme', 'light');
    } else {
      document.body.classList.remove('theme-light');
      localStorage.setItem('theme', 'dark');
    }
  };

  const handleSave = () => {
    const savePromise = new Promise((resolve) => {
      setTimeout(() => {
        localStorage.setItem('ai_confidence', aiConfidence.toString());
        localStorage.setItem('auto_approve', autoApprove.toString());
        localStorage.setItem('drone_altitude', altitude.toString());
        localStorage.setItem('map_provider', mapProvider);
        localStorage.setItem('offline_cache', offlineCache.toString());
        localStorage.setItem('audit_lock', auditLock.toString());
        resolve(true);
      }, 1200); // Simulate network delay
    });

    toast.promise(savePromise, {
      loading: 'Saving configuration to cloud...',
      success: 'Configuration saved successfully.',
      error: 'Failed to save configuration.'
    });
  };

  const tabs = [
    { id: 'ai', label: 'AI & Automation', icon: <Brain size={16} /> },
    { id: 'drone', label: 'Drone & Mapping', icon: <Map size={16} /> },
    { id: 'security', label: 'Security & Audit', icon: <Shield size={16} /> },
    { id: 'appearance', label: 'Appearance', icon: <Palette size={16} /> },
  ];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--color-bg)', overflow: 'auto' }}>
      <main className="main-content" style={{ maxWidth: '1000px', margin: '0 auto', width: '100%', padding: '32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
          <div>
            <h1 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Settings size={28} color="var(--color-terracotta)" />
              Platform Settings
            </h1>
            <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', margin: 0 }}>
              Configure AI thresholds, drone defaults, and platform security.
            </p>
          </div>
          <button onClick={handleSave} className="btn btn-primary" style={{ padding: '8px 24px', position: 'relative' }}>
            Save Configuration
          </button>
        </div>

        <div style={{ display: 'flex', gap: '32px', alignItems: 'flex-start' }}>
          {/* Sidebar Tabs */}
          <div style={{ width: '220px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  padding: '12px 16px', borderRadius: '8px', border: 'none',
                  background: activeTab === tab.id ? 'var(--color-surface)' : 'transparent',
                  color: activeTab === tab.id ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                  fontWeight: activeTab === tab.id ? 600 : 500,
                  fontSize: '14px', cursor: 'pointer', textAlign: 'left',
                  boxShadow: activeTab === tab.id ? 'var(--shadow-subtle)' : 'none',
                  border: activeTab === tab.id ? '1px solid var(--color-border)' : '1px solid transparent',
                  transition: 'all 0.2s ease'
                }}
              >
                <span style={{ color: activeTab === tab.id ? 'var(--color-terracotta)' : 'inherit' }}>{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </div>

          {/* Settings Content */}
          <div className="card" style={{ flex: 1, padding: '32px', minHeight: '400px' }}>
            
            {activeTab === 'ai' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', animation: 'fadeIn 0.3s ease' }}>
                <div>
                  <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>Boundary Detection Confidence Threshold</h3>
                  <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
                    The minimum confidence score required from the U-Net model before a boundary is considered "Detected". Values below this will flag for manual review.
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                    <input 
                      type="range" min="0.5" max="0.99" step="0.01" 
                      value={aiConfidence} onChange={e => setAiConfidence(parseFloat(e.target.value))}
                      style={{ flex: 1, accentColor: 'var(--color-brand)' }}
                    />
                    <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--color-brand)', width: '60px' }}>
                      {aiConfidence.toFixed(2)}
                    </div>
                  </div>
                </div>

                <div style={{ height: '1px', background: 'var(--color-border)' }} />

                <div>
                  <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>Discrepancy Auto-Approval Tolerance</h3>
                  <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
                    If the drone surveyed area matches the cadastral record within this margin (%), the survey is automatically approved.
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                    <input 
                      type="range" min="1" max="15" step="1" 
                      value={autoApprove} onChange={e => setAutoApprove(parseInt(e.target.value))}
                      style={{ flex: 1, accentColor: 'var(--color-terracotta)' }}
                    />
                    <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--color-terracotta)', width: '60px' }}>
                      ±{autoApprove}%
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'drone' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', animation: 'fadeIn 0.3s ease' }}>
                <div>
                  <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>Default Flight Altitude</h3>
                  <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
                    Base altitude for automated lawnmower survey patterns. Lower altitudes provide better Ground Sampling Distance (GSD).
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                    <input 
                      type="range" min="30" max="120" step="5" 
                      value={altitude} onChange={e => setAltitude(parseInt(e.target.value))}
                      style={{ flex: 1, accentColor: 'var(--color-active)' }}
                    />
                    <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--color-active)', width: '60px' }}>
                      {altitude}m
                    </div>
                  </div>
                </div>

                <div style={{ height: '1px', background: 'var(--color-border)' }} />

                <div>
                  <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>Base Map Provider</h3>
                  <div style={{ display: 'flex', gap: '16px', marginTop: '16px' }}>
                    {['mapbox', 'sentinel', 'wms'].map(prov => (
                      <button 
                        key={prov} onClick={() => setMapProvider(prov)}
                        style={{
                          padding: '12px 24px', borderRadius: '8px', border: mapProvider === prov ? '2px solid var(--color-brand)' : '1px solid var(--color-border)',
                          background: mapProvider === prov ? 'var(--color-brand-light)' : 'transparent',
                          color: 'var(--color-text-primary)', cursor: 'pointer', fontWeight: 600,
                          textTransform: 'capitalize'
                        }}>
                        {prov === 'wms' ? 'Govt WMS' : prov}
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ height: '1px', background: 'var(--color-border)' }} />

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h3 style={{ fontSize: '16px', marginBottom: '4px' }}>Offline Field Caching</h3>
                    <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', margin: 0 }}>
                      Automatically cache 500MB of local map tiles for surveyors entering deep rural areas.
                    </p>
                  </div>
                  <button 
                    onClick={() => setOfflineCache(!offlineCache)}
                    style={{
                      width: '48px', height: '24px', borderRadius: '12px', border: 'none',
                      background: offlineCache ? 'var(--color-brand)' : 'var(--color-border)',
                      position: 'relative', cursor: 'pointer', transition: 'background 0.3s'
                    }}>
                    <div style={{
                      width: '20px', height: '20px', borderRadius: '50%', background: '#fff',
                      position: 'absolute', top: '2px', left: offlineCache ? '26px' : '2px',
                      transition: 'left 0.3s'
                    }} />
                  </button>
                </div>
              </div>
            )}

            {activeTab === 'security' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', animation: 'fadeIn 0.3s ease' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h3 style={{ fontSize: '16px', marginBottom: '4px' }}>Immutable Audit Logging</h3>
                    <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', margin: 0, maxWidth: '400px' }}>
                      Generate a cryptographic SHA-256 hash for all finalized survey reports to ensure legal evidence immutability.
                    </p>
                  </div>
                  <button 
                    onClick={() => setAuditLock(!auditLock)}
                    style={{
                      width: '48px', height: '24px', borderRadius: '12px', border: 'none',
                      background: auditLock ? 'var(--color-brand)' : 'var(--color-border)',
                      position: 'relative', cursor: 'pointer', transition: 'background 0.3s'
                    }}>
                    <div style={{
                      width: '20px', height: '20px', borderRadius: '50%', background: '#fff',
                      position: 'absolute', top: '2px', left: auditLock ? '26px' : '2px',
                      transition: 'left 0.3s'
                    }} />
                  </button>
                </div>
              </div>
            )}

            {activeTab === 'appearance' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', animation: 'fadeIn 0.3s ease' }}>
                <div>
                  <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>Interface Theme</h3>
                  <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
                    Select the visual appearance of the application. Light mode is optimized for high-glare field environments.
                  </p>
                  <div style={{ display: 'flex', gap: '16px' }}>
                    <button 
                      onClick={() => toggleTheme('dark')}
                      style={{
                        flex: 1, padding: '24px', borderRadius: '12px', 
                        border: theme === 'dark' ? '2px solid var(--color-active)' : '1px solid var(--color-border)',
                        background: '#0D1117', color: '#E6EDF3', cursor: 'pointer',
                        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px'
                      }}>
                      <div style={{ width: '48px', height: '32px', background: '#161B22', borderRadius: '4px', border: '1px solid #30363D' }} />
                      <span style={{ fontWeight: 600 }}>Dark Mode</span>
                    </button>
                    <button 
                      onClick={() => toggleTheme('light')}
                      style={{
                        flex: 1, padding: '24px', borderRadius: '12px', 
                        border: theme === 'light' ? '2px solid var(--color-active)' : '1px solid var(--color-border)',
                        background: '#F6F8FA', color: '#24292F', cursor: 'pointer',
                        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px'
                      }}>
                      <div style={{ width: '48px', height: '32px', background: '#FFFFFF', borderRadius: '4px', border: '1px solid #D0D7DE' }} />
                      <span style={{ fontWeight: 600 }}>Light Mode</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

          </div>
        </div>
      </main>
      <style>{`
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
};
