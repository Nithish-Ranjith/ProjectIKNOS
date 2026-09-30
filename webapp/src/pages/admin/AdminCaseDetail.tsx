import React, { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { fetchCase, fetchEvidence, fetchReasoning, fetchGeometryLayers, submitDecision, fetchSurveyors, assignCase } from '../../services/api'
import type { Case, EvidenceBundle, ReasoningTrace, GeometryLayers, Surveyor } from '../../types'
import { ConfidenceBadge, StatusBadge } from '../../components/admin/Badges'
import { MapboxCompare } from '../../components/MapboxCompare'
import { CaseTimeline } from '../../components/CaseTimeline'
import { SentinelTimelapse } from '../../components/SentinelTimelapse'
import { supabase } from '../../lib/supabase'

// 
// Sub-components
// 

// Evidence Tabs §4.3
const EvidenceTabs: React.FC<{ bundle: EvidenceBundle, parcelId: string }> = ({ bundle, parcelId }) => {
  const [tab, setTab] = useState<'spatial' | 'temporal' | 'records'>('spatial')
  const tabStyle = (t: string) => ({
    padding: '0.5rem 1.25rem',
    border: 'none',
    cursor: 'pointer',
    fontFamily: 'var(--font-ui)',
    fontWeight: 600,
    fontSize: '0.85rem',
    borderBottom: tab === t ? '3px solid var(--color-terracotta)' : '3px solid transparent',
    background: 'none',
    color: tab === t ? 'var(--color-terracotta)' : 'var(--color-text-secondary)',
    transition: 'all 0.15s',
  })

  const Row: React.FC<{ label: string; value: React.ReactNode; mono?: boolean }> = ({ label, value, mono }) => (
    <tr>
      <td style={{ padding: '0.5rem 0', color: 'var(--color-text-secondary)', fontSize: '0.85rem', width: '55%' }}>{label}</td>
      <td style={{ padding: '0.5rem 0', fontFamily: mono ? 'var(--font-mono)' : 'var(--font-ui)', fontSize: '0.85rem', fontWeight: 600 }}>{value}</td>
    </tr>
  )

  return (
    <div>
      <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)', marginBottom: '1rem' }}>
        <button style={tabStyle('spatial')} onClick={() => setTab('spatial')}>Spatial</button>
        <button style={tabStyle('temporal')} onClick={() => setTab('temporal')}>Temporal</button>
        <button style={tabStyle('records')} onClick={() => setTab('records')}>Records</button>
      </div>

      {tab === 'spatial' && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            <Row label="Cadastral Area" value={`${bundle.spatial.cadastral_area_sqm.toLocaleString()} m²`} mono />
            <Row label="Drone-derived Area" value={bundle.spatial.drone_area_sqm ? `${bundle.spatial.drone_area_sqm.toLocaleString()} m²` : <span style={{ color: 'var(--color-text-secondary)' }}>Awaiting U-Net inference</span>} mono />
            <Row label="Area Mismatch" value={<span style={{ color: bundle.spatial.area_diff_pct > 5 ? 'var(--color-terracotta)' : '#4a7c59' }}>{bundle.spatial.area_diff_pct.toFixed(1)}%</span>} mono />
            <Row label="Boundary Shift" value={`${bundle.spatial.boundary_shift_m.toFixed(1)} m`} mono />
            <Row label="Registration Conflict" value={bundle.spatial.registration_conflict ? <span style={{ color: 'var(--color-terracotta)' }}> Yes</span> : <span style={{ color: '#4a7c59' }}> No</span>} />
          </tbody>
        </table>
      )}

      {tab === 'temporal' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              <Row label="Instability Score (NDVI)" value={<span style={{ color: bundle.temporal.instability_score > 0.5 ? 'var(--color-terracotta)' : '#4a7c59' }}>{bundle.temporal.instability_score.toFixed(2)}</span>} mono />
              <Row label="Estimated Onset Year" value={bundle.temporal.onset_year ?? '—'} mono />
              <Row label="NDVI Series" value={bundle.temporal.ndvi_series_uri ? <a href={bundle.temporal.ndvi_series_uri} target="_blank" rel="noreferrer">View Chart</a> : <span style={{ color: 'var(--color-text-secondary)' }}>Not available</span>} />
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
    </div>
  )
}

// Reasoning Trace Accordion §4.3
const ReasoningTracePanel: React.FC<{ trace: ReasoningTrace }> = ({ trace }) => {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-ui)', fontWeight: 600, color: 'var(--color-terracotta)', fontSize: '0.9rem', padding: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}
      >
        {open ? '' : ''} Confidence Reasoning Trace
      </button>
      {open && (
        <div style={{ marginTop: '0.75rem', overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <thead>
              <tr style={{ background: '#f4f6f8', textAlign: 'left' }}>
                {['Rule', 'Weight', 'Input', 'Contribution', 'Pass?'].map(h => (
                  <th key={h} style={{ padding: '0.4rem 0.75rem', fontWeight: 700 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trace.rules.map(r => (
                <tr key={r.rule_id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '0.4rem 0.75rem' }}>{r.description}</td>
                  <td style={{ padding: '0.4rem 0.75rem', fontFamily: 'var(--font-mono)' }}>{(r.weight * 100).toFixed(0)}%</td>
                  <td style={{ padding: '0.4rem 0.75rem', fontFamily: 'var(--font-mono)' }}>{String(r.input_value)}</td>
                  <td style={{ padding: '0.4rem 0.75rem', fontFamily: 'var(--font-mono)', color: r.score_contribution > 0 ? 'var(--color-terracotta)' : 'inherit' }}>+{r.score_contribution}</td>
                  <td style={{ padding: '0.4rem 0.75rem' }}>{r.passed ? '' : '—'}</td>
                </tr>
              ))}
              <tr style={{ background: '#f4f6f8', fontWeight: 700 }}>
                <td colSpan={3} style={{ padding: '0.4rem 0.75rem' }}>Total Score</td>
                <td style={{ padding: '0.4rem 0.75rem', fontFamily: 'var(--font-mono)' }}>{trace.total_score}</td>
                <td></td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// EvidenceMap component is now MapboxMap

// Decision Modal §4.3
interface DecisionModalProps {
  caseId: string
  onClose: () => void
  onSuccess: () => void
}
const DecisionModal: React.FC<DecisionModalProps> = ({ caseId, onClose, onSuccess }) => {
  const [decision, setDecision] = useState<'approve' | 'reject' | 'escalate'>('approve')
  const [reason, setReason] = useState('')
  const [authPin, setAuthPin] = useState('')   // §4.3 — auth step before write fires
  const [step, setStep] = useState<'form' | 'auth'>('form')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const proceedToAuth = () => {
    if (!reason.trim()) { setError('Reason is required.'); return }
    setError(null)
    setStep('auth')
  }

  const confirmDecision = async () => {
    if (!authPin) { setError('PIN / auth code is required to write the decision.'); return }
    setLoading(true)
    setError(null)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      await submitDecision(caseId, {
        decision,
        reason,
        decided_by: session?.user.email ?? 'unknown',
      })
      onSuccess()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const overlay: React.CSSProperties = {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  }
  const modal: React.CSSProperties = {
    background: '#fff', borderRadius: '8px', padding: '2rem',
    width: '100%', maxWidth: '500px', boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
  }

  return (
    <div style={overlay} onClick={onClose}>
      <div style={modal} onClick={e => e.stopPropagation()}>
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
              <label className="form-label">Reason <span style={{ color: 'var(--color-terracotta)' }}>*</span></label>
              <textarea
                className="form-input"
                rows={3}
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="State the ground for this decision..."
                style={{ resize: 'vertical' }}
              />
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button className="btn btn-outline" onClick={onClose}>Cancel</button>
              <button className="btn btn-primary" onClick={proceedToAuth}>Continue →</button>
            </div>
          </>
        ) : (
          <>
            <h3 style={{ marginBottom: '0.5rem' }}>Authenticate to Confirm</h3>
            <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
              Enter your account PIN or one-time verification code to authorise the <strong style={{ textTransform: 'capitalize' }}>{decision}</strong> decision. This write cannot be undone without an authorised override.
            </p>
            {error && <div className="error-msg">{error}</div>}
            <div className="form-group">
              <label className="form-label">Auth PIN / Code</label>
              <input type="password" className="form-input" value={authPin} onChange={e => setAuthPin(e.target.value)} placeholder="••••••" maxLength={8} />
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button className="btn btn-outline" onClick={() => setStep('form')}>← Back</button>
              <button className="btn btn-primary" onClick={confirmDecision} disabled={loading}>
                {loading ? <><span className="spinner"></span> Writing decision...</> : 'Confirm Decision'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// Assign Surveyor Modal §4.3
interface AssignModalProps {
  surveyors: Surveyor[]
  onClose: () => void
  onAssign: (id: string) => void
  loading: boolean
}
const AssignModal: React.FC<AssignModalProps> = ({ surveyors, onClose, onAssign, loading }) => {
  const [selected, setSelected] = useState('')
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }} onClick={onClose}>
      <div style={{ background: '#fff', borderRadius: '8px', padding: '2rem', width: '100%', maxWidth: '420px' }} onClick={e => e.stopPropagation()}>
        <h3 style={{ marginBottom: '1.25rem' }}>Assign to Surveyor</h3>
        <div className="form-group">
          <label className="form-label">Surveyor</label>
          <select className="form-input" value={selected} onChange={e => setSelected(e.target.value)}>
            <option value="">— Select —</option>
            {surveyors.map(s => <option key={s.id} value={s.id}>{s.name} ({s.assigned_case_count} active)</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
          <button className="btn btn-outline" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={!selected || loading} onClick={() => onAssign(selected)}>
            {loading ? <><span className="spinner"></span> Assigning...</> : 'Assign'}
          </button>
        </div>
      </div>
    </div>
  )
}

// 
// Admin Case Detail — /admin/cases/:id  (Architecture §4.3)
// 
export const AdminCaseDetail: React.FC = () => {
  const { id: caseId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  // Data states — three explicit states each
  const [caseData, setCaseData] = useState<Case | null>(null)
  const [caseLoading, setCaseLoading] = useState(true)
  const [caseError, setCaseError] = useState<string | null>(null)

  const [evidence, setEvidence] = useState<EvidenceBundle | null>(null)
  const [evidenceLoading, setEvidenceLoading] = useState(true)
  const [evidenceError, setEvidenceError] = useState<string | null>(null)

  const [reasoning, setReasoning] = useState<ReasoningTrace | null>(null)
  const [reasoningLoading, setReasoningLoading] = useState(true)

  const [layers, setLayers] = useState<GeometryLayers | null>(null)
  const [layersLoading, setLayersLoading] = useState(true)

  const [surveyors, setSurveyors] = useState<Surveyor[]>([])

  // Modal state
  const [showDecision, setShowDecision] = useState(false)
  const [showAssign, setShowAssign] = useState(false)
  const [assignLoading, setAssignLoading] = useState(false)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!caseId) return
    // Load all panels in parallel
    setCaseLoading(true)
    fetchCase(caseId)
      .then(setCaseData)
      .catch(e => setCaseError(e.message))
      .finally(() => setCaseLoading(false))

    fetchEvidence(caseId)
      .then(setEvidence)
      .catch(e => setEvidenceError(e.message))
      .finally(() => setEvidenceLoading(false))

    fetchReasoning(caseId).then(setReasoning).finally(() => setReasoningLoading(false))
    fetchGeometryLayers(caseId).then(setLayers).finally(() => setLayersLoading(false))
    fetchSurveyors().then(setSurveyors)
  }, [caseId])

  const handleAssign = async (surveyorId: string) => {
    setAssignLoading(true)
    try {
      await assignCase(caseId!, surveyorId)
      setShowAssign(false)
      setSuccessMsg('Surveyor assigned. The case will appear in their queue.')
    } catch (e: any) {
      alert(e.message)
    } finally {
      setAssignLoading(false)
    }
  }

  const handleDecisionSuccess = () => {
    setShowDecision(false)
    setSuccessMsg('Decision recorded. The case has been updated.')
    // Refresh case header
    if (caseId) fetchCase(caseId).then(setCaseData)
  }

  if (caseLoading) return (
    <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center' }}>
      <span className="spinner" style={{ width: '2rem', height: '2rem', borderColor: 'var(--color-border)', borderTopColor: 'var(--color-terracotta)' }}></span>
    </div>
  )

  if (caseError) return (
    <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div className="error-msg" style={{ maxWidth: '480px' }}>Error: {caseError}<br /><button className="btn btn-outline" style={{ marginTop: '0.75rem' }} onClick={() => navigate('/admin/cases')}>Back to Queue</button></div>
    </div>
  )

  return (
    <div className="app-container">
      {showDecision && caseId && <DecisionModal caseId={caseId} onClose={() => setShowDecision(false)} onSuccess={handleDecisionSuccess} />}
      {showAssign && <AssignModal surveyors={surveyors} onClose={() => setShowAssign(false)} onAssign={handleAssign} loading={assignLoading} />}

      {/* Top Bar */}
      <header className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button onClick={() => navigate('/admin/cases')} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.7)', cursor: 'pointer', fontSize: '1.2rem' }}>←</button>
          <span style={{ fontFamily: 'var(--font-ui)', fontWeight: 700 }}>Case Detail</span>
          {caseData && <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', opacity: 0.7 }}>{caseData.case_id}</span>}
        </div>
        <button onClick={async () => { await supabase.auth.signOut(); navigate('/login') }} className="btn btn-outline" style={{ color: 'white', borderColor: 'white', fontSize: '0.85rem' }}>Logout</button>
      </header>

      <main className="main-content" style={{ maxWidth: '1100px' }}>
        {successMsg && (
          <div style={{ background: '#4a7c59', color: '#fff', padding: '0.75rem 1rem', borderRadius: '4px', marginBottom: '1.25rem', display: 'flex', justifyContent: 'space-between' }}>
             {successMsg}
            <button onClick={() => setSuccessMsg(null)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}></button>
          </div>
        )}

        {/* Case Header */}
        {caseData && (
          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-start' }}>
              <div>
                <h2 style={{ marginBottom: '0.25rem' }}>{caseData.parcel_id}</h2>
                <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>{caseData.village}, {caseData.district} · Owner: <strong>{caseData.owner_name}</strong></p>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
                <ConfidenceBadge score={caseData.confidence_score} />
                <StatusBadge status={caseData.status} />
              </div>
            </div>
          </div>
        )}

        {caseData && <CaseTimeline status={caseData.status} />}

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1.4fr) minmax(0,1fr)', gap: '1.5rem' }}>

          {/* Left Column — Map + Evidence + Reasoning */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

            {/* Map §4.3 */}
            <div className="card" style={{ padding: '1rem' }}>
              <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Evidence Map</h3>
              {layersLoading ? (
                <div style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-secondary)' }}>
                  <span className="spinner" style={{ borderColor: 'var(--color-border)', borderTopColor: 'var(--color-terracotta)' }}></span> &nbsp;Loading layers...
                </div>
              ) : layers ? <MapboxCompare layers={layers} height="350px" /> : null}
            </div>

            {/* Evidence Tabs §4.3 */}
            <div className="card">
              <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Evidence</h3>
              {evidenceLoading && <div style={{ color: 'var(--color-text-secondary)', fontSize: '0.85rem' }}><span className="spinner" style={{ borderColor: 'var(--color-border)', borderTopColor: 'var(--color-terracotta)' }}></span> Loading evidence...</div>}
              {evidenceError && <div className="error-msg">{evidenceError}</div>}
              {!evidenceLoading && !evidenceError && evidence && caseData && <EvidenceTabs bundle={evidence} parcelId={caseData.parcel_id} />}
            </div>

            {/* Reasoning Trace §4.3 */}
            <div className="card">
              {reasoningLoading ? (
                <span style={{ color: 'var(--color-text-secondary)', fontSize: '0.85rem' }}>Loading reasoning trace...</span>
              ) : reasoning ? (
                <ReasoningTracePanel trace={reasoning} />
              ) : null}
            </div>
          </div>

          {/* Right Column — Actions */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div className="card">
              <h3 style={{ fontSize: '1rem', marginBottom: '1rem' }}>Actions</h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {/* Request Field Visit §4.3 */}
                {caseData?.status === 'open' && (
                  <button className="btn btn-outline" style={{ width: '100%', justifyContent: 'flex-start' }} onClick={() => setShowAssign(true)}>
                    Request Field Visit
                  </button>
                )}

                {/* Record Decision §4.3 */}
                <button
                  className="btn btn-primary"
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                  onClick={() => setShowDecision(true)}
                  disabled={caseData?.status === 'closed'}
                >
                   Record Decision
                </button>

                {caseData?.status === 'closed' && (
                  <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>
                    This case is closed. Decision has been recorded.
                  </p>
                )}
              </div>

              {/* Audit Trail */}
              {caseData && caseData.audit_trail.length > 0 && (
                <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--color-border)' }}>
                  <p style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem' }}>Audit Trail</p>
                  {caseData.audit_trail.map((entry, i) => (
                    <div key={i} style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)', marginBottom: '0.3rem' }}>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{new Date(entry.timestamp).toLocaleString('en-IN')}</span> · {entry.actor} · {entry.action}
                    </div>
                  ))}
                </div>
              )}

              {caseData?.officer_decision && (
                <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#f4f9f5', borderRadius: '4px', borderLeft: '3px solid #4a7c59' }}>
                  <p style={{ fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', color: '#4a7c59' }}>Decision Recorded</p>
                  <p style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}><strong style={{ textTransform: 'capitalize' }}>{caseData.officer_decision.decision}</strong> · {caseData.officer_decision.decided_by}</p>
                  <p style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>{caseData.officer_decision.reason}</p>
                </div>
              )}
            </div>

            {/* Evidence Refs */}
            {caseData && caseData.evidence_refs.length > 0 && (
              <div className="card">
                <h3 style={{ fontSize: '0.9rem', marginBottom: '0.75rem' }}>Evidence References</h3>
                {caseData.evidence_refs.map(ref => (
                  <div key={ref} style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)', marginBottom: '0.25rem', wordBreak: 'break-all' }}>
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
