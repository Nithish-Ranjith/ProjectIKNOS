import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchDashboardStats } from '../services/api'
import { AlertCircle, Clock, CheckCircle, BarChart3, ChevronRight, Activity, Map, FileText } from 'lucide-react'
import styles from './AdminHome.module.css'

const KPICard: React.FC<{ title: string; value: string | number; icon: React.ReactNode; alert?: boolean }> = ({ title, value, icon, alert }) => (
  <div className={`${styles.kpiCard} ${alert ? styles.kpiCardAlert : ''}`}>
    {alert && <div className={styles.kpiCardAlertTop} />}
    <div className={styles.kpiHeader}>
      <div className={styles.kpiTitle}>{title}</div>
      <div className={`${styles.kpiIcon} ${alert ? styles.kpiIconAlert : ''}`}>{icon}</div>
    </div>
    <div className={`${styles.kpiValue} ${alert ? styles.kpiValueAlert : ''}`}>{value}</div>
  </div>
)

export const AdminHome: React.FC = () => {
  const navigate = useNavigate()

  const { data: stats, isLoading } = useQuery({
    queryKey: ['admin-dashboard-stats'],
    queryFn: fetchDashboardStats
  })

  return (
    <div className={styles.container}>
      <main className={styles.mainContent}>
        
        {/* Header */}
        <div className={styles.header}>
          <div>
            <h1 className={styles.headerTitle}>Command Center</h1>
            <p className={styles.headerSubtitle}>
              Live adjudication metrics and system health monitoring.
            </p>
          </div>
          <button 
            className={`btn btn-primary ${styles.btnPrimary}`} 
            onClick={() => navigate('/admin/cases')}
          >
            Access Case Queue <ChevronRight size={16} />
          </button>
        </div>

        {isLoading ? (
          <div className={styles.loadingState}>
            <Activity className="spinner" size={24} style={{ marginBottom: '16px' }} />
            <div>Initializing secure dashboard...</div>
          </div>
        ) : stats ? (
          <div className={styles.gridContent}>
            
            {/* KPI Grid */}
            <div className={styles.kpiGrid}>
              <KPICard title="Active Cases" value={stats.open_cases} icon={<FileText size={20} />} />
              <KPICard title="SLA Breaches" value={stats.sla_breaches} icon={<AlertCircle size={20} />} alert={stats.sla_breaches > 0} />
              <KPICard title="Avg Resolution" value={`${stats.avg_resolution_days.toFixed(1)}d`} icon={<Clock size={20} />} />
              <KPICard title="Weekly Volume" value={stats.cases_this_week} icon={<BarChart3 size={20} />} />
            </div>

            {/* Main Content Grid */}
            <div className={styles.mainGrid}>
              
              {/* System Alerts */}
              <div className={styles.cardPanel}>
                <h3 className={styles.panelTitle}>
                  <Activity size={18} color="var(--amber)" /> Priority Alerts
                </h3>
                
                <div className={styles.alertList}>
                  {stats.sla_breaches > 0 && (
                    <div className={`${styles.alertItem} ${styles.alertDanger}`}>
                      <AlertCircle size={20} color="var(--red)" style={{ flexShrink: 0 }} />
                      <div>
                        <div className={`${styles.alertTitle} ${styles.alertTitleDanger}`}>SLA Violation Detected</div>
                        <div className={styles.alertText}>
                          {stats.sla_breaches} cases have exceeded the mandatory 14-day adjudication SLA. Immediate intervention required by District Magistrate.
                        </div>
                      </div>
                    </div>
                  )}

                  <div className={`${styles.alertItem} ${styles.alertInfo}`}>
                    <Map size={20} color="var(--accent)" style={{ flexShrink: 0 }} />
                    <div>
                      <div className={`${styles.alertTitle} ${styles.alertTitleInfo}`}>Surveyor Field Sync</div>
                      <div className={styles.alertText}>
                        12 Drone Field Visits are currently cached offline and pending network sync to the master database.
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className={styles.cardPanel}>
                <h3 className={styles.panelTitle}>Administrative Actions</h3>
                <div className={styles.alertList}>
                  <button className={`btn btn-outline ${styles.actionBtn}`} onClick={() => navigate('/admin/cases')}>
                    <span className={styles.actionBtnText}><FileText size={18} /> Adjudicate Queue</span>
                    <ChevronRight size={16} />
                  </button>
                  <button className={`btn btn-outline ${styles.actionBtn}`} onClick={() => navigate('/admin/settings')}>
                    <span className={styles.actionBtnText}><CheckCircle size={18} /> ML Tolerance Settings</span>
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>

            </div>
          </div>
        ) : null}
      </main>
      <style>{`
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  )
}
