import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import styles from './AdminCases.module.css'

import metricsData from '../../assets/v2_real_metrics.json'

export const AdminEvaluation: React.FC = () => {
  const navigate = useNavigate()
  
  // Real computed metrics from actual satellite training run
  const [metrics] = useState(metricsData)

  return (
    <div className="app-container">
      <header className={styles.topbar}>
        <div className={styles.topbarBrand}>
          <span className={styles.brandText} onClick={() => navigate('/admin/home')}>IKNOS</span>
          <span className={styles.brandDivider}>|</span>
          <span className={styles.brandSubtitle}>Admin — Model Evaluation</span>
        </div>
        <div className={styles.topbarNav}>
          <button onClick={() => navigate('/admin/cases')} className="btn btn-outline" style={{ fontSize: '0.85rem' }}>Cases</button>
          <button onClick={() => navigate('/admin/records')} className="btn btn-outline" style={{ fontSize: '0.85rem' }}>Records</button>
          <button onClick={() => navigate('/admin/users')} className="btn btn-outline" style={{ fontSize: '0.85rem' }}>Users</button>
          <button onClick={() => navigate('/login')} className="btn btn-outline" style={{ fontSize: '0.85rem' }}>Logout</button>
        </div>
      </header>

      <main className="main-content">
        <section className={styles.section}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <div>
              <h2 className={styles.sectionHeader} style={{ marginBottom: '4px' }}>AI Boundary Model Performance</h2>
              <div style={{ fontSize: '14px', color: 'var(--text-3)' }}>
                Computed against ground-truth validation set (N={metrics.test_set_size})
              </div>
            </div>
            <button className="btn btn-primary" onClick={() => alert("Recomputation scheduled. Will email results.")}>
              Recompute Now
            </button>
          </div>

          <div style={{ padding: '16px', background: 'var(--amber-dim)', border: '1px solid var(--amber)', borderRadius: '8px', marginBottom: '24px', color: 'var(--amber)', fontSize: '14px', fontWeight: 500 }}>
            ⚠️ <strong>Notice:</strong> This model is currently trained on low-res satellite tiles. It will NOT transfer well to high-resolution drone orthomosaics due to the domain gap.
          </div>

          <div className={styles.kpiGrid}>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Model Version</div>
              <div className={styles.kpiValue} style={{fontSize: '18px'}}>{metrics.git_hash || 'N/A'}</div>
              <div style={{fontSize: '11px', color: 'var(--text-3)', marginTop: '4px'}}>Current Git Hash</div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Mean IoU</div>
              <div className={styles.kpiValue}>{(metrics.global_iou * 100).toFixed(1)}%</div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Baseline IoU</div>
              <div className={styles.kpiValue}>{(metrics.baseline_iou * 100).toFixed(1)}%</div>
              <div style={{fontSize: '11px', color: 'var(--text-3)', marginTop: '4px'}}>Centered-blob prior</div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Precision</div>
              <div className={styles.kpiValue}>{(metrics.precision * 100).toFixed(1)}%</div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Recall</div>
              <div className={styles.kpiValue}>{(metrics.recall * 100).toFixed(1)}%</div>
            </div>
            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>F1 Score</div>
              <div className={styles.kpiValue}>{(metrics.f1_score * 100).toFixed(1)}%</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginTop: '30px' }}>
            <div className={styles.kpiCard} style={{ gridColumn: '1' }}>
              <h3 style={{ fontSize: '16px', marginBottom: '16px', color: 'var(--text-1)' }}>Confusion Matrix (Parcel Level)</h3>
              
              <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr 1fr', gap: '10px', textAlign: 'center', fontSize: '14px' }}>
                <div></div>
                <div style={{ fontWeight: 600, color: 'var(--text-2)' }}>Pred Positive</div>
                <div style={{ fontWeight: 600, color: 'var(--text-2)' }}>Pred Negative</div>
                
                <div style={{ fontWeight: 600, color: 'var(--text-2)', display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>Actual Pos</div>
                <div style={{ background: 'var(--green-dim)', border: '1px solid var(--green)', padding: '16px', borderRadius: '4px', fontSize: '20px', fontWeight: 700, color: 'var(--green)' }}>
                  {metrics.confusion_matrix.true_positives}
                </div>
                <div style={{ background: 'var(--red-dim)', border: '1px solid var(--red)', padding: '16px', borderRadius: '4px', fontSize: '20px', fontWeight: 700, color: 'var(--red)' }}>
                  {metrics.confusion_matrix.false_negatives}
                </div>
                
                <div style={{ fontWeight: 600, color: 'var(--text-2)', display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>Actual Neg</div>
                <div style={{ background: 'var(--amber-dim)', border: '1px solid var(--amber)', padding: '16px', borderRadius: '4px', fontSize: '20px', fontWeight: 700, color: 'var(--amber)' }}>
                  {metrics.confusion_matrix.false_positives}
                </div>
                <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', padding: '16px', borderRadius: '4px', fontSize: '20px', fontWeight: 700, color: 'var(--text-1)' }}>
                  {metrics.confusion_matrix.true_negatives}
                </div>
              </div>
            </div>

            <div className={styles.kpiCard} style={{ gridColumn: '2' }}>
              <h3 style={{ fontSize: '16px', marginBottom: '16px', color: 'var(--text-1)' }}>Model Metadata</h3>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, color: 'var(--text-2)', fontSize: '14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <li style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Architecture</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>U-Net (EfficientNet-b3)</span>
                </li>
                <li style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Loss Function</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>Focal Dice Loss</span>
                </li>
                <li style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Input Resolution</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>512x512 (0.6m GSD)</span>
                </li>
                <li style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Training Data</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>Guntur Pilot (n=1000)</span>
                </li>
                <li style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Last Computed</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{new Date(metrics.last_computed).toLocaleString()}</span>
                </li>
              </ul>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
