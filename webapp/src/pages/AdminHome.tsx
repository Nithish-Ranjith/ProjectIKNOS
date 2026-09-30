import React, { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { useNavigate } from 'react-router-dom'
import { fetchDashboardStats } from '../services/api'
import type { DashboardStats } from '../types'

const KPICard: React.FC<{ label: string; value: string | number; accent?: boolean }> = ({ label, value, accent }) => (
  <div className="card" style={{
    flex: '1 1 200px',
    padding: '1.5rem',
    borderLeft: accent ? '4px solid var(--color-terracotta)' : '4px solid var(--color-navy)',
  }}>
    <div style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
    <div style={{ fontSize: '2.5rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: accent ? 'var(--color-terracotta)' : 'var(--color-navy)', marginTop: '0.5rem' }}>{value}</div>
  </div>
)

export const AdminHome: React.FC = () => {
  const navigate = useNavigate()
  
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetchDashboardStats()
      .then(setStats)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const handleLogout = async () => { await supabase.auth.signOut(); navigate('/login'); }

  return (
    <div className="app-container">
      <header className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{ cursor: 'pointer', fontFamily: 'var(--font-ui)', fontSize: '1.25rem', fontWeight: 700 }}
            onClick={() => navigate('/admin/home')}>
             TerraTrace
          </span>
          <span style={{ opacity: 0.5 }}>|</span>
          <span style={{ opacity: 0.8 }}>Admin — Dashboard</span>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button onClick={() => navigate('/admin/cases')} className="btn btn-outline" style={{ color: 'white', borderColor: 'rgba(255,255,255,0.4)', fontSize: '0.85rem' }}>Cases</button>
          <button onClick={() => navigate('/admin/records')} className="btn btn-outline" style={{ color: 'white', borderColor: 'rgba(255,255,255,0.4)', fontSize: '0.85rem' }}>Records</button>
          <button onClick={() => navigate('/admin/users')} className="btn btn-outline" style={{ color: 'white', borderColor: 'rgba(255,255,255,0.4)', fontSize: '0.85rem' }}>Users</button>
          <button onClick={handleLogout} className="btn btn-outline" style={{ color: 'white', borderColor: 'white', fontSize: '0.85rem' }}>Logout</button>
        </div>
      </header>

      <main className="main-content" style={{ maxWidth: '1200px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '1.5rem' }}>
          <div>
            <h2 style={{ fontSize: '1.8rem', marginBottom: '0.25rem' }}>Overview</h2>
            <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>System health and adjudication metrics.</p>
          </div>
          <button className="btn btn-primary" onClick={() => navigate('/admin/cases')}>Go to Case Queue →</button>
        </div>

        {error && <div className="error-msg"> {error}</div>}

        {loading ? (
          <div style={{ textAlign: 'center', padding: '4rem' }}>
            <span className="spinner" style={{ borderColor: 'var(--color-border)', borderTopColor: 'var(--color-navy)' }}></span> Loading metrics...
          </div>
        ) : stats ? (
          <>
            <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginBottom: '2rem' }}>
              <KPICard label="Open Cases" value={stats.open_cases} accent />
              <KPICard label="SLA Breaches" value={stats.sla_breaches} accent={stats.sla_breaches > 0} />
              <KPICard label="Avg Resolution (days)" value={stats.avg_resolution_days.toFixed(1)} />
              <KPICard label="Cases This Week" value={stats.cases_this_week} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '1.5rem' }}>
              {/* Alert Panel */}
              <div className="card">
                <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.5rem' }}> Action Required</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <div style={{ background: '#fff3e0', padding: '0.75rem 1rem', borderRadius: '4px', borderLeft: '4px solid var(--color-terracotta)', fontSize: '0.9rem' }}>
                    <strong>3 Cases</strong> breached 14-day SLA. High priority review required.
                  </div>
                  <div style={{ background: '#e3f2fd', padding: '0.75rem 1rem', borderRadius: '4px', borderLeft: '4px solid #1565C0', fontSize: '0.9rem' }}>
                    <strong>12 Surveyor Field Visits</strong> pending submission.
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="card">
                <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.5rem' }}>Quick Actions</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <button className="btn btn-outline" style={{ justifyContent: 'flex-start' }} onClick={() => navigate('/admin/cases')}> Review Open Cases</button>
                  <button className="btn btn-outline" style={{ justifyContent: 'flex-start' }}> View Regional Map</button>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </main>
    </div>
  )
}
