import React, { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchCase, fetchEvidence, fetchGeometryLayers, submitFieldVerification } from '../../services/api'
import type { GeoJSONFeature } from '../../types'
import { MapboxMap } from '../../components/MapboxMap'
import { SentinelTimelapse } from '../../components/SentinelTimelapse'
import styles from './SurveyorFieldVisit.module.css'

export const SurveyorFieldVisit: React.FC = () => {
  const { id: caseId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [editedBoundary, _setEditedBoundary] = useState<GeoJSONFeature | null>(null)
  const [fullMap, setFullMap] = useState(false)
  const [activePanel, setActivePanel] = useState<'details' | 'sentinel' | 'neighbors'>('details')

  const { data, isLoading, error } = useQuery({
    queryKey: ['field-visit', caseId],
    queryFn: async () => {
      if (!caseId) throw new Error("No case ID")
      const [c, bundle, layers] = await Promise.all([
        fetchCase(caseId),
        fetchEvidence(caseId),
        fetchGeometryLayers(caseId)
      ])
      return { c, bundle, layers }
    },
    enabled: !!caseId
  })

  if (isLoading || !data) return (
    <div className={styles.loadingState}>
      {error ? `ERROR: ${error instanceof Error ? error.message : 'Failed'}` : 'INITIALIZING FIELD MODULE...'}
    </div>
  )

  const { c, bundle, layers } = data

  return (
    <div className={styles.container}>
      <header className={styles.topbar}>
        <div className={styles.breadcrumb}>
          <button onClick={() => navigate('/surveyor/home')} className={styles.backBtn}>← BACK</button>
          <div className={styles.dividerVertical} />
          <span className={styles.breadcrumbId}>{c.parcel_id}</span>
          <span className={styles.breadcrumbLoc}>{c.village}, {c.district}</span>
          <span className={styles.badgeBlue}>FIELD VISIT</span>
        </div>

        <div className={styles.actions}>
          <button className="btn btn-ghost" onClick={() => setFullMap(f => !f)} style={{ fontSize: '0.75rem', padding: '5px 8px' }}>
            {fullMap ? '⊟ PANEL' : '⊞ FULL MAP'}
          </button>
          <button className="btn btn-outline" style={{ fontSize: '0.75rem', padding: '5px 10px' }}>SAVE DRAFT</button>
          <button
            className="btn btn-primary"
            style={{ fontSize: '0.75rem', padding: '5px 14px' }}
            onClick={async () => {
              try {
                if (!caseId) return;
                await submitFieldVerification(caseId, {
                  discrepancy_confirmed: true,
                  findings: 'Field visit conducted and discrepancies noted.',
                  photo_uris: [],
                  submitted_by: 'surveyor'
                });
                alert('Field verification submitted successfully!');
                navigate('/surveyor');
              } catch (err: any) {
                alert(`Failed to submit: ${err.message}`);
              }
            }}
          >
            CONFIRM →
          </button>
        </div>
      </header>

      <div className={styles.mainArea}>
        <div className={styles.mapArea}>
          <MapboxMap layers={layers} showAILayer={true} />

          <div className={styles.statsBanner}>
            <div className={styles.statItem}>
              <span className={styles.statWarning}>⚠ Spatial Mismatch</span>
              <span className={styles.statValue}>{c.spatial_mismatch_pct.toFixed(1)}%</span>
            </div>
            <div className={styles.dividerVertical} />
            <div className={styles.statItem}>
              <span>Boundary Shift</span>
              <span className={styles.statValue}>{c.boundary_shift_m.toFixed(1)} m</span>
            </div>
            <div className={styles.dividerVertical} />
            <div className={styles.statItem}>
              <span>Boundary Edited</span>
              <span className={editedBoundary ? styles.statGood : ''} style={{ fontWeight: 600 }}>{editedBoundary ? '● YES' : '○ NO'}</span>
            </div>
          </div>

          <div className={styles.mapLegend}>
            <div className={styles.legendItem}>
              <div className={styles.legendLineCadastral} />
              <span>Cadastral (Old)</span>
            </div>
            <div className={styles.legendItem}>
              <div className={styles.legendLineAI} />
              <span>AI Identified</span>
            </div>
            <div className={styles.legendItem}>
              <div className={styles.legendLineEdit} />
              <span>Your Edit</span>
            </div>
          </div>
        </div>

        {!fullMap && (
          <div className={styles.rightPanel}>
            <div className={styles.tabStrip}>
              {(['details', 'sentinel', 'neighbors'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActivePanel(tab)}
                  className={`${styles.panelTab} ${activePanel === tab ? styles.panelTabActive : ''}`}
                >
                  {tab === 'details' ? 'PARCEL' : tab === 'sentinel' ? 'SENTINEL' : 'NEIGHBORS'}
                </button>
              ))}
            </div>

            {activePanel === 'details' && (
              <div className={styles.panelContent}>
                <div>
                  <div className={styles.panelLabel}>PARCEL DETAILS</div>
                  <div className={styles.detailsGrid}>
                    {[
                      { label: 'Owner', value: bundle?.records?.ror?.owner_name || c.owner_name || 'Unassigned' },
                      { label: 'Khasra #', value: bundle?.records?.ror?.khasra_no || 'Unassigned', mono: true },
                      { label: 'Cadastral Area', value: bundle?.spatial?.cadastral_area_sqm ? `${bundle.spatial.cadastral_area_sqm.toLocaleString()} m²` : 'N/A', mono: true },
                      { label: 'Recorded', value: bundle?.records?.ror?.record_date || 'Unknown', mono: true },
                    ].map(f => (
                      <div key={f.label}>
                        <div className={styles.detailFieldLabel}>{f.label}</div>
                        <div className={`${styles.detailFieldValue} ${f.mono ? styles.detailFieldValueMono : ''}`}>{f.value}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className={styles.divider} />

                <div>
                  <div className={styles.panelLabel}>MUTATION STATUS</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: '0.88rem', fontWeight: 600, textTransform: 'capitalize' }} className={c.mutation_status === 'pending' ? styles.mutationStatusPending : styles.mutationStatusGood}>
                        {c.mutation_status}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-2)', marginTop: '2px' }}>
                        {c.mutation_status === 'pending' ? '3 active records' : 'No active disputes'}
                      </div>
                    </div>
                    <button className="btn btn-outline" style={{ fontSize: '0.7rem', padding: '4px 8px' }}>DETAILS</button>
                  </div>
                </div>

                <div className={styles.divider} />

                <div>
                  <div className={styles.panelLabel}>AI CONFIDENCE</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ flex: 1, height: '4px', background: 'var(--border)', borderRadius: '2px', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${c.confidence_score}%`, background: 'var(--accent)', borderRadius: '2px' }} />
                    </div>
                    <span className={`${styles.detailFieldValue} ${styles.detailFieldValueMono}`}>
                      {c.confidence_score}%
                    </span>
                  </div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-2)', marginTop: '4px' }}>
                    Based on boundary model v2.3
                  </div>
                </div>
              </div>
            )}

            {activePanel === 'sentinel' && (
              <div className={styles.panelContent}>
                {c?.parcel_id && <SentinelTimelapse parcelId={c.parcel_id} />}
              </div>
            )}

            {activePanel === 'neighbors' && (
              <div className={styles.panelContent}>
                <div className={styles.panelLabel}>NEIGHBOR PARCELS</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {Array.from({ length: 4 }).map((_, i) => {
                    const hash = c.parcel_id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
                    const nId = `P${(hash % 900 + i * 7 + 100).toString().padStart(3, '0')}`;
                    const nOwner = ['Ranga Rao', 'Subbamma', 'Krishna Murthy', 'Lakshmi Devi', 'Venkateswara Rao', 'Siva Reddy'][(hash + i) % 6];
                    const p = `${nId} — ${nOwner}`;
                    return (
                      <div key={p} className={styles.neighborItem}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--text-2)' }}>{p}</span>
                        <span style={{ color: 'var(--text-2)', fontSize: '0.8rem' }}>→</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
