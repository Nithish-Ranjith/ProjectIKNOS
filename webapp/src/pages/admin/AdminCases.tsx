import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { fetchDashboardStats, fetchCases } from '../../services/api'
import { ConfidenceBadge, StatusBadge } from '../../components/admin/Badges'
import { supabase } from '../../lib/supabase'
import styles from './AdminCases.module.css'

interface Filters {
  status: string
  min_confidence: string
}

const KPICard: React.FC<{ label: string; value: string | number; accent?: boolean }> = ({ label, value, accent }) => (
  <div className={`${styles.kpiCard} ${accent ? styles.kpiCardAccent : ''}`}>
    <div className={styles.kpiLabel}>{label}</div>
    <div className={`${styles.kpiValue} ${accent ? styles.kpiValueAccent : ''}`}>{value}</div>
  </div>
)

export const AdminCases: React.FC = () => {
  const navigate = useNavigate()

  const [filters, setFilters] = useState<Filters>({ status: '', min_confidence: '' })
  const [appliedFilters, setAppliedFilters] = useState<Filters>({ status: '', min_confidence: '' })

  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: fetchDashboardStats
  })

  const { data: casesRes, isLoading: casesLoading, error: casesError, refetch: refetchCases } = useQuery({
    queryKey: ['admin-cases', appliedFilters],
    queryFn: () => fetchCases({
      status: appliedFilters.status || undefined,
      min_confidence: appliedFilters.min_confidence ? Number(appliedFilters.min_confidence) : undefined,
    })
  })
  
  const cases = (casesRes?.cases || []).filter((c: any) => c.case_id === 'C01')

  const handleLogout = async () => {
    await supabase.auth.signOut()
    navigate('/login')
  }

  const applyFilters = () => setAppliedFilters({ ...filters })
  const clearFilters = () => { setFilters({ status: '', min_confidence: '' }); setAppliedFilters({ status: '', min_confidence: '' }) }

  return (
    <div className="app-container">
      <header className={styles.topbar}>
        <div className={styles.topbarBrand}>
          <span className={styles.brandText} onClick={() => navigate('/admin/home')}>IKNOS</span>
          <span className={styles.brandDivider}>|</span>
          <span className={styles.brandSubtitle}>Admin — Case Queue</span>
        </div>
        <div className={styles.topbarNav}>
          <button onClick={() => navigate('/admin/cases')} className="btn btn-outline" style={{ fontSize: '0.85rem' }}>Cases</button>
          <button onClick={() => navigate('/admin/records')} className="btn btn-outline" style={{ fontSize: '0.85rem' }}>Records</button>
          <button onClick={() => navigate('/admin/users')} className="btn btn-outline" style={{ fontSize: '0.85rem' }}>Users</button>
          <button onClick={handleLogout} className="btn btn-outline" style={{ fontSize: '0.85rem' }}>Logout</button>
        </div>
      </header>

      <main className="main-content">
        {/* KPI Cards */}
        <section className={styles.section}>
          <h2 className={styles.sectionHeader}>Dashboard Overview</h2>
          {statsError && <div className={styles.errorState}>{statsError instanceof Error ? statsError.message : 'Error fetching stats'}</div>}
          <div className={styles.kpiGrid}>
            {statsLoading ? (
              <div className={styles.loadingState}>
                <span className="spinner"></span> Loading stats...
              </div>
            ) : stats ? (
              <>
                <KPICard label="Open Cases" value={stats.open_cases} />
                <KPICard label="SLA Breaches" value={stats.sla_breaches} accent={stats.sla_breaches > 0} />
                <KPICard label="Avg Resolution (days)" value={stats.avg_resolution_days.toFixed(1)} />
                <KPICard label="Cases This Week" value={stats.cases_this_week} />
              </>
            ) : null}
          </div>
        </section>

        {/* Case Queue */}
        <section>
          <div className={styles.filterHeader}>
            <h2 className={styles.filterHeaderTitle}>Case Queue</h2>
            <div className={styles.filterBar}>
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

          {casesLoading && (
            <div className={styles.loadingState}>
              <span className="spinner"></span> Loading cases...
            </div>
          )}

          {!casesLoading && casesError && (
            <div className={styles.errorState}>
              <span>{casesError instanceof Error ? casesError.message : 'Error fetching cases'}</span>
              <button className="btn btn-outline" style={{ padding: '0.25rem 0.75rem' }} onClick={() => refetchCases()}>Retry</button>
            </div>
          )}

          {!casesLoading && !casesError && (
            <div className={styles.tableContainer}>
              {cases.length === 0 ? (
                <div style={{ padding: '80px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-3)' }}>
                  <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16, border: '1px solid var(--border)' }}>
                    <Search size={24} style={{ color: 'var(--text-4)' }} />
                  </div>
                  <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-1)', marginBottom: 4 }}>No cases found</div>
                  <div style={{ fontSize: '14px' }}>No cases match the selected filters.</div>
                </div>
              ) : (
                <table className={styles.table}>
                  <thead>
                    <tr>
                      {['Parcel ID', 'Village / District', 'Owner', 'Mismatch', 'Shift', 'Risk Score', 'Status', 'Created'].map(h => (
                        <th key={h} className={styles.th}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {cases.map((c) => (
                      <tr key={c.case_id} onClick={() => navigate(`/admin/cases/${c.case_id}`)} className={styles.tr}>
                        <td className={`${styles.td} ${styles.tdMono} ${styles.tdId}`}>{c.parcel_id}</td>
                        <td className={styles.td}>{c.village}<br /><span className={styles.tdSubtext}>{c.district}</span></td>
                        <td className={styles.td}>{c.owner_name ?? '—'}</td>
                        <td className={`${styles.td} ${styles.tdMono}`}>{c.spatial_mismatch_pct.toFixed(1)}%</td>
                        <td className={`${styles.td} ${styles.tdMono}`}>{c.boundary_shift_m.toFixed(1)} m</td>
                        <td className={styles.td}><ConfidenceBadge score={c.confidence_score} /></td>
                        <td className={styles.td}><StatusBadge status={c.status} /></td>
                        <td className={`${styles.td} ${styles.tdMono} ${styles.tdSubtext}`}>{c.created_at ? new Date(c.created_at).toLocaleDateString('en-IN') : '—'}</td>
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
