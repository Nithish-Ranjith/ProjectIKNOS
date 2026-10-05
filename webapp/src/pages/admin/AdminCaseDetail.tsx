import React, { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchCase, fetchEvidence, fetchReasoning, fetchGeometryLayers, submitDecision, fetchSurveyors, assignCase, fetchAuditTrail, verifyAuditChain } from '../../services/api'
import type { EvidenceBundle, ReasoningTrace, Surveyor } from '../../types'
import { ConfidenceBadge, StatusBadge } from '../../components/admin/Badges'
import { MapboxMap } from '../../components/MapboxMap'
import { CaseTimeline } from '../../components/CaseTimeline'
import { SentinelTimelapse } from '../../components/SentinelTimelapse'
import { supabase } from '../../lib/supabase'
import { toast } from 'sonner'
import styles from './AdminCaseDetail.module.css'

const AuditTrailViewer: React.FC<{ caseId: string }> = ({ caseId }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['audit-trail', caseId],
    queryFn: async () => {
      const [logs, verification] = await Promise.all([
        fetchAuditTrail(caseId),
        verifyAuditChain(caseId)
      ])
      return { logs, verification }
    }
  })

  if (isLoading || !data) return <div style={{ padding: '1rem', color: 'var(--text-2)' }}>Verifying cryptography...</div>

  const { logs, verification } = data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className={verification.valid ? styles.auditSuccess : styles.auditFail}>
        {verification.valid ? '✓ HASH CHAIN VERIFIED (CRYPTOGRAPHICALLY IMMUTABLE)' : '⚠ HASH CHAIN CORRUPTED!'}
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {logs.map((log: any) => (
          <div key={log.audit_id} className={styles.logEntry}>
            <div className={styles.logHeader}>
              [{log.seq}] {log.event_type} <span className={styles.logActor}>by {log.actor_role} ({log.actor_id})</span>
            </div>
            <div className={styles.logHash}>
              <span style={{ color: 'var(--text-3)' }}>PREV:</span> {log.previous_hash}<br/>
              <span style={{ color: 'var(--text-1)' }}>HASH:</span> {log.current_hash}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const EvidenceTabs: React.FC<{ bundle: EvidenceBundle, parcelId: string, caseId: string }> = ({ bundle, parcelId, caseId }) => {
  const [tab, setTab] = useState<'spatial' | 'temporal' | 'records' | 'audit'>('spatial')

  const Row: React.FC<{ label: string; value: React.ReactNode; mono?: boolean }> = ({ label, value, mono }) => (
    <tr>
      <td className={styles.rowLabel}>{label}</td>
      <td className={`${styles.rowValue} ${mono ? styles.rowValueMono : ''}`}>{value}</td>
    </tr>
  )

  return (
    <div>
      <div className={styles.tabsContainer}>
        {(['spatial', 'temporal', 'records', 'audit'] as const).map(t => (
          <button key={t} className={`${styles.tab} ${tab === t ? styles.tabActive : ''}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'spatial' && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            <Row label="Cadastral Area" value={`${bundle.spatial.cadastral_area_sqm.toLocaleString()} m²`} mono />
            <Row label="Drone-derived Area" value={bundle.spatial.drone_area_sqm ? `${bundle.spatial.drone_area_sqm.toLocaleString()} m²` : <span style={{ color: 'var(--text-2)' }}>Awaiting inference</span>} mono />
            <Row label="Area Mismatch" value={<span style={{ color: bundle.spatial.area_diff_pct > 5 ? 'var(--red)' : 'var(--green)' }}>{bundle.spatial.area_diff_pct.toFixed(1)}%</span>} mono />
            <Row label="Boundary Shift" value={`${bundle.spatial.boundary_shift_m.toFixed(1)} m`} mono />
            <Row label="Registration Conflict" value={bundle.spatial.registration_conflict ? <span style={{ color: 'var(--red)' }}> Yes</span> : <span style={{ color: 'var(--green)' }}> No</span>} />
          </tbody>
        </table>
      )}

      {tab === 'temporal' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              <Row label="Instability Score" value={<span style={{ color: bundle.temporal.instability_score > 0.5 ? 'var(--red)' : 'var(--green)' }}>{bundle.temporal.instability_score.toFixed(2)}</span>} mono />
              <Row label="Estimated Onset Year" value={bundle.temporal.onset_year ?? '—'} mono />
              <Row label="NDVI Series" value={bundle.temporal.ndvi_series_uri ? <a href={bundle.temporal.ndvi_series_uri} target="_blank" rel="noreferrer">View Chart</a> : <span style={{ color: 'var(--text-2)' }}>Not available</span>} />
            </tbody>
          </table>
          <div style={{ marginTop: '0.5rem' }}>
            <SentinelTimelapse parcelId={parcelId} />
          </div>
        </div>
      )}

      {tab === 'records' && bundle.records.ror && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            <Row label="Khasra No." value={bundle.records.ror.khasra_no} mono />
            <Row label="Owner (RoR)" value={bundle.records.ror.owner_name} />
            <Row label="Recorded Area" value={`${bundle.records.ror.area_recorded} m²`} mono />
            <Row label="Record Date" value={bundle.records.ror.record_date} mono />
            <Row label="Mutation Status" value={<span style={{ textTransform: 'capitalize' }}>{bundle.records.mutation?.mutation_status ?? '—'}</span>} />
            <Row label="Registration Deed" value={bundle.records.registration_deed_present ? ' Present' : 'Not found'} />
          </tbody>
        </table>
      )}

      {tab === 'audit' && <AuditTrailViewer caseId={caseId} />}
    </div>
  )
}

const ReasoningTracePanel: React.FC<{ trace: ReasoningTrace }> = ({ trace }) => {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button onClick={() => setOpen(o => !o)} className={styles.accordionBtn}>
        {open ? '▲' : '▼'} Confidence Reasoning Trace
      </button>
      {open && (
        <div style={{ marginTop: '0.75rem', overflowX: 'auto' }}>
          <table className={styles.reasoningTable}>
            <thead>
              <tr>
                {['Rule', 'Weight', 'Input', 'Contribution', 'Pass?'].map(h => (
                  <th key={h} className={styles.reasoningTh}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trace.rules.map(r => (
                <tr key={r.rule_id} className={styles.reasoningTr}>
                  <td className={styles.reasoningTd}>{r.description}</td>
                  <td className={`${styles.reasoningTd} ${styles.reasoningTdMono}`}>{(r.weight * 100).toFixed(0)}%</td>
                  <td className={`${styles.reasoningTd} ${styles.reasoningTdMono}`}>{String(r.input_value)}</td>
                  <td className={`${styles.reasoningTd} ${styles.reasoningTdMono}`} style={{ color: r.score_contribution > 0 ? 'var(--accent)' : 'inherit' }}>+{r.score_contribution}</td>
                  <td className={styles.reasoningTd}>{r.passed ? '' : '—'}</td>
                </tr>
              ))}
              <tr style={{ background: 'var(--bg-raised)', fontWeight: 700 }}>
                <td colSpan={3} className={styles.reasoningTd}>Total Score</td>
                <td className={`${styles.reasoningTd} ${styles.reasoningTdMono}`}>{trace.total_score}</td>
                <td></td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const DecisionModal: React.FC<{ caseId: string, onClose: () => void, onSuccess: () => void }> = ({ caseId, onClose, onSuccess }) => {
  const [decision, setDecision] = useState<'approve' | 'reject' | 'escalate'>('approve')
  const [reason, setReason] = useState('')
  const [authPin, setAuthPin] = useState('')
  const [step, setStep] = useState<'form' | 'auth'>('form')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const proceedToAuth = () => {
    if (!reason.trim()) { setError('Reason is required.'); return }
    setError(null)
    setStep('auth')
  }

  const confirmDecision = async () => {
    if (!authPin) { setError('PIN is required.'); return }
    setLoading(true)
    setError(null)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      await submitDecision(caseId, { decision, reason, decided_by: session?.user.email ?? 'unknown' })
      onSuccess()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalContent} onClick={e => e.stopPropagation()}>
        {step === 'form' ? (
          <>
            <h3 style={{ marginBottom: '1.25rem' }}>Record Decision</h3>
            {error && <div className="error-msg">{error}</div>}
            <div className="form-group">
              <label className="form-label">Decision</label>
              {(['approve', 'reject', 'escalate'] as const).map(d => (
                <label key={d} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem', cursor: 'pointer' }}>
                  <input type="radio" name="decision" value={d} checked={decision === d} onChange={() => setDecision(d)} />
                  <span style={{ textTransform: 'capitalize', fontWeight: decision === d ? 700 : 400 }}>{d}</span>
                </label>
              ))}
            </div>
            <div className="form-group">
              <label className="form-label">Reason <span style={{ color: 'var(--red)' }}>*</span></label>
              <textarea className="form-input" rows={3} value={reason} onChange={e => setReason(e.target.value)} />
            </div>
            <div className={styles.modalActions}>
              <button className="btn btn-outline" onClick={onClose}>Cancel</button>
              <button className="btn btn-primary" onClick={proceedToAuth}>Continue →</button>
            </div>
          </>
        ) : (
          <>
            <h3 style={{ marginBottom: '0.5rem' }}>Authenticate to Confirm</h3>
            <p style={{ color: 'var(--text-2)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>Enter your PIN to authorise.</p>
            {error && <div className="error-msg">{error}</div>}
            <div className="form-group">
              <label className="form-label">Auth PIN</label>
              <input type="password" className="form-input" value={authPin} onChange={e => setAuthPin(e.target.value)} maxLength={8} />
            </div>
            <div className={styles.modalActions}>
              <button className="btn btn-outline" onClick={() => setStep('form')}>← Back</button>
              <button className="btn btn-primary" onClick={confirmDecision} disabled={loading}>
                {loading ? 'Writing...' : 'Confirm'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

const AssignModal: React.FC<{ surveyors: Surveyor[], onClose: () => void, onAssign: (id: string) => void, loading: boolean }> = ({ surveyors, onClose, onAssign, loading }) => {
  const [selected, setSelected] = useState('')
  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalContent} onClick={e => e.stopPropagation()}>
        <h3 style={{ marginBottom: '1.25rem' }}>Assign to Surveyor</h3>
        <div className="form-group">
          <label className="form-label">Surveyor</label>
          <select className="form-input" value={selected} onChange={e => setSelected(e.target.value)}>
            <option value="">— Select —</option>
            {surveyors.map(s => <option key={s.id} value={s.id}>{s.name} ({s.assigned_case_count} active)</option>)}
          </select>
        </div>
        <div className={styles.modalActions}>
          <button className="btn btn-outline" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={!selected || loading} onClick={() => onAssign(selected)}>
            {loading ? 'Assigning...' : 'Assign'}
          </button>
        </div>
      </div>
    </div>
  )
}

export const AdminCaseDetail: React.FC = () => {
  const { id: caseId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [showDecision, setShowDecision] = useState(false)
  const [showAssign, setShowAssign] = useState(false)
  const [assignLoading, setAssignLoading] = useState(false)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const { data: caseData, isLoading: caseLoading, error: caseError, refetch: refetchCase } = useQuery({
    queryKey: ['case-detail', caseId],
    queryFn: () => fetchCase(caseId!),
    enabled: !!caseId
  })

  const { data: evidence, isLoading: evidenceLoading, error: evidenceError } = useQuery({
    queryKey: ['case-evidence', caseId],
    queryFn: () => fetchEvidence(caseId!),
    enabled: !!caseId
  })

  const { data: reasoning, isLoading: reasoningLoading } = useQuery({
    queryKey: ['case-reasoning', caseId],
    queryFn: () => fetchReasoning(caseId!),
    enabled: !!caseId
  })

  const { data: layers, isLoading: layersLoading } = useQuery({
    queryKey: ['case-layers', caseId],
    queryFn: () => fetchGeometryLayers(caseId!),
    enabled: !!caseId
  })

  const { data: surveyors = [] } = useQuery({
    queryKey: ['surveyors'],
    queryFn: fetchSurveyors,
  })

  const handleAssign = async (surveyorId: string) => {
    setAssignLoading(true)
    try {
      await assignCase(caseId!, surveyorId)
      setShowAssign(false)
      toast.success('Surveyor assigned. The case will appear in their queue.')
    } catch (e: any) {
      toast.error(e.message)
    } finally {
      setAssignLoading(false)
    }
  }

  const handleDecisionSuccess = () => {
    setShowDecision(false)
    setSuccessMsg('Decision recorded. The case has been updated.')
    refetchCase()
  }

  if (caseLoading) return <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center' }}><span className="spinner"></span></div>
  if (caseError) return <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center' }}><div className="error-msg">Error: {caseError instanceof Error ? caseError.message : String(caseError)}</div></div>

  return (
    <div className="app-container">
      {showDecision && caseId && <DecisionModal caseId={caseId} onClose={() => setShowDecision(false)} onSuccess={handleDecisionSuccess} />}
      {showAssign && <AssignModal surveyors={surveyors} onClose={() => setShowAssign(false)} onAssign={handleAssign} loading={assignLoading} />}

      <header className={styles.topbar}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button onClick={() => navigate('/admin/cases')} style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', fontSize: '1.2rem' }}>←</button>
          <span style={{ fontFamily: 'var(--font-ui)', fontWeight: 700, color: 'var(--text-1)' }}>Case Detail</span>
          {caseData && <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-3)' }}>{caseData.case_id}</span>}
        </div>
        <button onClick={async () => { await supabase.auth.signOut(); navigate('/login') }} className="btn btn-outline" style={{ fontSize: '0.85rem' }}>Logout</button>
      </header>

      <main className={styles.mainContent}>
        {successMsg && (
          <div style={{ background: 'var(--green-dim)', color: 'var(--green)', padding: '0.75rem 1rem', borderRadius: '4px', marginBottom: '1.25rem', display: 'flex', justifyContent: 'space-between', border: '1px solid var(--green)' }}>
             {successMsg}
            <button onClick={() => setSuccessMsg(null)} style={{ background: 'none', border: 'none', color: 'var(--green)', cursor: 'pointer' }}>✕</button>
          </div>
        )}

        {caseData && (
          <div className={styles.card} style={{ marginBottom: '1.5rem' }}>
            <div className={styles.caseHeader}>
              <div>
                <h2 className={styles.caseTitle}>{caseData.parcel_id}</h2>
                <p className={styles.caseMeta}>{caseData.village}, {caseData.district} · Owner: <strong>{caseData.owner_name}</strong></p>
              </div>
              <div className={styles.badges}>
                <ConfidenceBadge score={caseData.confidence_score} />
                <StatusBadge status={caseData.status} />
              </div>
            </div>
          </div>
        )}

        {caseData && <CaseTimeline status={caseData.status} />}

        <div className={styles.grid}>
          <div className={styles.col}>
            {/* Map */}
            <div className={styles.card}>
              <h3 className={styles.cardTitle}>Evidence Map</h3>

              {/* Pipeline status banner */}
              {layers?.pipeline && (() => {
                const pl = layers.pipeline!
                const statusColors: Record<string, { bg: string; color: string; border: string }> = {
                  SUCCESS:                { bg: 'var(--green-dim)',  color: 'var(--green)',  border: 'var(--green)' },
                  LOW_CONFIDENCE:         { bg: 'var(--amber-dim)',  color: 'var(--amber)',  border: 'var(--amber)' },
                  NO_DETECTION:           { bg: 'var(--red-dim)',    color: 'var(--red)',    border: 'var(--red)'   },
                  ORTHOMOSAIC_UNAVAILABLE:{ bg: 'var(--red-dim)',    color: 'var(--red)',    border: 'var(--red)'   },
                  MODEL_UNAVAILABLE:      { bg: 'var(--red-dim)',    color: 'var(--red)',    border: 'var(--red)'   },
                  RUNNING:                { bg: 'var(--accent-dim)', color: 'var(--accent)', border: 'var(--accent)' },
                  QUEUED:                 { bg: 'var(--accent-dim)', color: 'var(--accent)', border: 'var(--accent)' },
                  PRECOMPUTED:            { bg: 'var(--amber-dim)',  color: 'var(--amber)',  border: 'var(--amber)' },
                }
                const c = statusColors[pl.status] ?? { bg: 'var(--bg)', color: 'var(--text-2)', border: 'var(--border)' }
                const provenance = layers.ai_boundary?.properties?.provenance as string | undefined
                return (
                  <div style={{ margin: '0 0 12px', padding: '8px 12px', borderRadius: '4px', background: c.bg, border: `1px solid ${c.border}`, color: c.color, fontSize: '0.78rem', fontFamily: 'var(--font-mono)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '6px' }}>
                    <span><strong>AI BOUNDARY:</strong> {pl.status} — {pl.message}</span>
                    {provenance && <span style={{ opacity: 0.7 }}>{provenance}</span>}
                  </div>
                )
              })()}

              {layersLoading ? (
                <div style={{ height: '380px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-2)' }}>
                  <span className="spinner"></span>&nbsp;Loading layers...
                </div>
              ) : layers ? (
                <MapboxMap
                  layers={layers}
                  showAILayer={true}
                  height="420px"
                />
              ) : (
                <div style={{ height: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-3)', fontSize: '0.85rem' }}>
                  No geometry layers available
                </div>
              )}
            </div>

            {/* Evidence Tabs */}
            <div className={styles.card}>
              <h3 className={styles.cardTitle}>Evidence</h3>
              {evidenceLoading && <div style={{ color: 'var(--text-2)', fontSize: '0.85rem' }}><span className="spinner"></span> Loading evidence...</div>}
              {evidenceError && <div className="error-msg">{evidenceError instanceof Error ? evidenceError.message : String(evidenceError)}</div>}
              {!evidenceLoading && !evidenceError && evidence && caseData && <EvidenceTabs bundle={evidence} parcelId={caseData.parcel_id} caseId={caseData.case_id} />}
            </div>

            {/* Reasoning Trace */}
            <div className={styles.card}>
              {reasoningLoading ? (
                <span style={{ color: 'var(--text-2)', fontSize: '0.85rem' }}>Loading reasoning trace...</span>
              ) : reasoning ? (
                <ReasoningTracePanel trace={reasoning} />
              ) : null}
            </div>
          </div>

          <div className={styles.col}>
            <div className={styles.card}>
              <h3 className={styles.cardTitle}>Actions</h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {caseData?.status === 'open' && (
                  <button className="btn btn-outline" style={{ width: '100%', justifyContent: 'flex-start' }} onClick={() => setShowAssign(true)}>
                    Request Field Visit
                  </button>
                )}

                <button
                  className="btn btn-primary"
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                  onClick={() => setShowDecision(true)}
                  disabled={caseData?.status === 'closed'}
                >
                   Record Decision
                </button>
              </div>

              {caseData && caseData.audit_trail.length > 0 && (
                <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
                  <p style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem', color: 'var(--text-1)' }}>Audit Trail</p>
                  {caseData.audit_trail.map((entry: any, i: number) => (
                    <div key={i} style={{ fontSize: '0.78rem', color: 'var(--text-2)', marginBottom: '0.3rem' }}>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{new Date(entry.timestamp).toLocaleString('en-IN')}</span> · {entry.actor} · {entry.action}
                    </div>
                  ))}
                </div>
              )}

              {caseData?.officer_decision && (
                <div className={styles.decisionPanel}>
                  <p style={{ fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--green)' }}>Decision Recorded</p>
                  <p style={{ fontSize: '0.85rem', marginTop: '0.25rem', color: 'var(--green)' }}><strong style={{ textTransform: 'capitalize' }}>{caseData.officer_decision.decision}</strong> · {caseData.officer_decision.decided_by}</p>
                  <p style={{ fontSize: '0.78rem', color: 'var(--green)' }}>{caseData.officer_decision.reason}</p>
                </div>
              )}
            </div>

            {caseData && caseData.evidence_refs.length > 0 && (
              <div className={styles.card}>
                <h3 className={styles.cardTitle}>Evidence References</h3>
                {caseData.evidence_refs.map((ref: string) => (
                  <div key={ref} style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', marginBottom: '0.25rem', wordBreak: 'break-all' }}>
                     {ref}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
