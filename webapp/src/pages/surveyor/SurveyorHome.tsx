import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchSurveyorAssignments } from '../../services/api'
import { Search } from 'lucide-react'
import styles from './SurveyorHome.module.css'

export const SurveyorHome: React.FC = () => {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'mission' | 'field_visit'>('mission')
  const [search, setSearch] = useState('')

  const { data: assignments = [], isLoading } = useQuery({
    queryKey: ['surveyor-assignments', activeTab],
    queryFn: () => fetchSurveyorAssignments(activeTab)
  })

  const filtered = assignments.filter((a: any) =>
    (a.parcel_id.toLowerCase().includes(search.toLowerCase()) ||
    (a.village || '').toLowerCase().includes(search.toLowerCase())) &&
    a.case_id === 'C01'
  )

  return (
    <div className={styles.container}>
      {/* HEADER */}
      <div className={styles.header}>
        <div className={styles.titleWrapper}>
          <h1 className={styles.title}>Cases</h1>
        </div>
        <div>
          <div className={styles.searchContainer}>
            <Search size={16} className={styles.searchIcon} />
            <input 
              type="text" 
              placeholder="Search cases..." 
              value={search}
              onChange={e => setSearch(e.target.value)}
              className={styles.searchInput}
            />
          </div>
        </div>
      </div>

      {/* FILTERS */}
      <div className={styles.filterBar}>
        <div className={styles.filterTabs}>
          <div 
            onClick={() => setActiveTab('mission')}
            className={`${styles.tab} ${activeTab === 'mission' ? styles.tabActive : ''}`}
          >
            Assigned Missions
          </div>
          <div 
            onClick={() => setActiveTab('field_visit')}
            className={`${styles.tab} ${activeTab === 'field_visit' ? styles.tabActive : ''}`}
          >
            Assigned Field Visits
          </div>
        </div>
      </div>

      {/* TABLE */}
      <div className={styles.tableArea}>
        <div className={styles.tableContainer}>
          <table className={styles.table}>
            <thead className={styles.thead}>
              <tr>
                <th className={styles.th}>Parcel</th>
                <th className={styles.th}>ID</th>
                <th className={styles.th}>Village</th>
                <th className={styles.th}>Type</th>
                <th className={styles.th}>Status</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={5} className={styles.tdEmpty}>Loading...</td></tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className={styles.tdEmpty}>
                    <div style={{ padding: '60px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-3)' }}>
                      <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'var(--bg-raised)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16, border: '1px solid var(--border)' }}>
                        <Search size={24} style={{ color: 'var(--text-4)' }} />
                      </div>
                      <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-1)', marginBottom: 4 }}>No cases found</div>
                      <div style={{ fontSize: '13px' }}>There are currently no cases matching your filters.</div>
                    </div>
                  </td>
                </tr>
              ) : filtered.map((a: any) => (
                <tr 
                  key={a.assignment_id} 
                  onClick={() => {
                    if (a.type === 'field_visit') {
                      navigate(`/surveyor/visit/${a.case_id}`)
                    } else {
                      navigate(`/surveyor/mission/${a.case_id}`)
                    }
                  }}
                  className={styles.tr}
                >
                  <td className={styles.td}>
                    <div style={{ width: 40, height: 40, background: 'var(--bg-raised)', borderRadius: 8, border: '1px solid var(--border)' }} />
                  </td>
                  <td className={`${styles.td} ${styles.tdId}`}>{a.parcel_id}</td>
                  <td className={styles.td}>{a.village || '—'}</td>
                  <td className={styles.td} style={{ textTransform: 'capitalize' }}>{a.type.replace('_', ' ')}</td>
                  <td className={styles.td}>
                    <span className={styles.statusBadge}>{a.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
