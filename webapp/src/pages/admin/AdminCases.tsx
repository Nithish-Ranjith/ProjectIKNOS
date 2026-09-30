import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchDashboardStats, fetchCases } from '../../services/api'
import type { Case, DashboardStats } from '../../types'
import { ConfidenceBadge, StatusBadge } from '../../components/admin/Badges'
import { supabase } from '../../lib/supabase'

//  Filter state type 
interface Filters {
  status: string
  min_confidence: string
}

//  KPI Card 
const KPICard: React.FC<{ label: string; value: string | number; accent?: boolean }> = ({ label, value, accent }) => (
  <div className="card" style={{
    flex: '1 1 180px',
    padding: '1.25rem',
    borderLeft: accent ? '4px solid var(--color-terracotta)' : '4px solid var(--color-terracotta)',
  }}>
    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
    <div style={{ fontSize: '2rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: accent ? 'var(--color-terracotta)' : 'var(--color-terracotta)', marginTop: '0.25rem' }}>{value}</div>
  </div>
)

// 
// Admin Case Queue — /admin/cases  (Architecture §4.2)
// 
export const AdminCases: React.FC = () => {
  const navigate = useNavigate()

  // Dashboard stats
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [statsError, setStatsError] = useState<string | null>(null)

  // Case queue
  const [cases, setCases] = useState<Case[]>([])
  const [casesLoading, setCasesLoading] = useState(true)
  const [casesError, setCasesError] = useState<string | null>(null)

  // Filters (Architecture §4.2 filter bar)
  const [filters, setFilters] = useState<Filters>({ status: '', min_confidence: '' })
  const [appliedFilters, setAppliedFilters] = useState<Filters>({ status: '', min_confidence: '' })

  //  Fetch KPI stats 
  useEffect(() => {
    setStatsLoading(true)
    fetchDashboardStats()
      .then(setStats)
      .catch(err => setStatsError(err.message))
      .finally(() => setStatsLoading(false))
  }, [])

  //  Fetch case queue 
  const loadCases = useCallback(() => {
    setCasesLoading(true)
    setCasesError(null)
    fetchCases({
      status: appliedFilters.status || undefined,
      min_confidence: appliedFilters.min_confidence ? Number(appliedFilters.min_confidence) : undefined,
    })
      .then(res => setCases(res.cases))
      .catch(err => setCasesError(err.message))
      .finally(() => setCasesLoading(false))
  }, [appliedFilters])

  useEffect(() => { loadCases() }, [loadCases])

  const handleLogout = async () => {
    await supabase.auth.signOut()
    navigate('/login')
  }

  const applyFilters = () => setAppliedFilters({ ...filters })
  const clearFilters = () => { setFilters({ status: '', min_confidence: '' }); setAppliedFilters({ status: '', min_confidence: '' }) }

  return (
    <div className="app-container">

      {/*  Top Bar  */}
      <header className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{ cursor: 'pointer', fontFamily: 'var(--font-ui)', fontSize: '1.25rem', fontWeight: 700 }}
            onClick={() => navigate('/admin/home')}>
             TerraTrace
          </span>
          <span style={{ opacity: 0.5 }}>|</span>
          <span style={{ opacity: 0.8 }}>Admin — Case Queue</span>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button onClick={() => navigate('/admin/cases')} className="btn btn-outline" style={{ color: 'white', borderColor: 'rgba(255,255,255,0.4)', fontSize: '0.85rem' }}>Cases</button>
          <button onClick={() => navigate('/admin/records')} className="btn btn-outline" style={{ color: 'white', borderColor: 'rgba(255,255,255,0.4)', fontSize: '0.85rem' }}>Records</button>
          <button onClick={() => navigate('/admin/users')} className="btn btn-outline" style={{ color: 'white', borderColor: 'rgba(255,255,255,0.4)', fontSize: '0.85rem' }}>Users</button>
          <button onClick={handleLogout} className="btn btn-outline" style={{ color: 'white', borderColor: 'white', fontSize: '0.85rem' }}>Logout</button>
        </div>
      </header>

      <main className="main-content">

        {/*  KPI Cards §4.1  */}
        <section style={{ marginBottom: '2rem' }}>
          <h2 style={{ marginBottom: '1rem' }}>Dashboard Overview</h2>
          {statsError && <div className="error-msg">{statsError}</div>}
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            {statsLoading ? (
              <div className="card" style={{ flex: '1 1 100%', textAlign: 'center', padding: '2rem' }}>
                <span className="spinner" style={{ borderColor: 'var(--color-terracotta)', borderTopColor: 'var(--color-terracotta)' }}></span> Loading stats...
              </div>
            ) : stats ? (
              <>
                <KPICard label="Open Cases" value={stats.open_cases} accent />
                <KPICard label="SLA Breaches" value={stats.sla_breaches} accent={stats.sla_breaches > 0} />
                <KPICard label="Avg Resolution (days)" value={stats.avg_resolution_days.toFixed(1)} />
                <KPICard label="Cases This Week" value={stats.cases_this_week} />
              </>
            ) : null}
          </div>
        </section>

        {/*  Case Queue §4.2  */}
        <section>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <h2 style={{ margin: 0 }}>Case Queue</h2>

            {/* Filter Bar */}
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <select className="form-input" style={{ width: 'auto' }} value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}>
                <option value="">All Statuses</option>
                <option value="open">Open</option>
                <option value="field_verification">In Field Visit</option>
                <option value="closed">Closed</option>
              </select>
              <select className="form-input" style={{ width: 'auto' }} value={filters.min_confidence} onChange={e => setFilters(f => ({ ...f, min_confidence: e.target.value }))}>
                <option value="">Any Risk</option>
                <option value="70">High Risk (≥70)</option>
                <option value="45">Medium+ Risk (≥45)</option>
              </select>
              <button className="btn btn-primary" style={{ padding: '0.4rem 0.9rem' }} onClick={applyFilters}>Apply</button>
              <button className="btn btn-outline" style={{ padding: '0.4rem 0.9rem' }} onClick={clearFilters}>Clear</button>
            </div>
          </div>

          {/* Loading state */}
          {casesLoading && (
            <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--color-text-secondary)' }}>
              <span className="spinner" style={{ borderColor: 'var(--color-border)', borderTopColor: 'var(--color-terracotta)' }}></span>
              &nbsp;Loading cases...
            </div>
          )}

          {/* Error state */}
          {!casesLoading && casesError && (
            <div className="error-msg" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span> {casesError}</span>
              <button className="btn btn-outline" style={{ padding: '0.25rem 0.75rem' }} onClick={loadCases}>Retry</button>
            </div>
          )}

          {/* Success state — case table */}
          {!casesLoading && !casesError && (
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {cases.length === 0 ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
                  No cases match the selected filters.
                </div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'var(--color-terracotta)', color: 'white', textAlign: 'left' }}>
                      {['Parcel ID', 'Village / District', 'Owner', 'Mismatch', 'Shift', 'Risk Score', 'Status', 'Created'].map(h => (
                        <th key={h} style={{ padding: '0.75rem 1rem', fontFamily: 'var(--font-ui)', fontWeight: 600, fontSize: '0.8rem', letterSpacing: '0.04em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {cases.map((c, i) => (
                      <tr
                        key={c.case_id}
                        onClick={() => navigate(`/admin/cases/${c.case_id}`)}
                        style={{
                          cursor: 'pointer',
                          background: i % 2 === 0 ? '#fff' : '#f9fafc',
                          transition: 'background 0.15s',
                          borderBottom: '1px solid var(--color-border)',
                        }}
                        onMouseEnter={e => (e.currentTarget.style.background = '#eef2f7')}
                        onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? '#fff' : '#f9fafc')}
                      >
                        <td style={{ padding: '0.75rem 1rem', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--color-terracotta)', fontWeight: 600 }}>{c.parcel_id}</td>
                        <td style={{ padding: '0.75rem 1rem', fontSize: '0.85rem' }}>{c.village}<br /><span style={{ color: 'var(--color-text-secondary)', fontSize: '0.75rem' }}>{c.district}</span></td>
                        <td style={{ padding: '0.75rem 1rem', fontSize: '0.85rem' }}>{c.owner_name ?? '—'}</td>
                        <td style={{ padding: '0.75rem 1rem', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>{c.spatial_mismatch_pct.toFixed(1)}%</td>
                        <td style={{ padding: '0.75rem 1rem', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>{c.boundary_shift_m.toFixed(1)} m</td>
                        <td style={{ padding: '0.75rem 1rem' }}><ConfidenceBadge score={c.confidence_score} /></td>
                        <td style={{ padding: '0.75rem 1rem' }}><StatusBadge status={c.status} /></td>
                        <td style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)' }}>{c.created_at ? new Date(c.created_at).toLocaleDateString('en-IN') : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
