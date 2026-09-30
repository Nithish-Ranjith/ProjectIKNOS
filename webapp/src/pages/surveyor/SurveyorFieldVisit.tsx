import React, { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { fetchCase, fetchEvidence, fetchGeometryLayers } from '../../services/api'
import type { Case, EvidenceBundle, GeometryLayers, GeoJSONFeature } from '../../types'
import { MapboxMap } from '../../components/MapboxMap'
import { SentinelTimelapse } from '../../components/SentinelTimelapse'

export const SurveyorFieldVisit: React.FC = () => {
  const { id: caseId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [c, setCase]           = useState<Case | null>(null)
  const [bundle, setBundle]    = useState<EvidenceBundle | null>(null)
  const [layers, setLayers]    = useState<GeometryLayers | null>(null)
  const [loading, setLoading]  = useState(true)
  const [editedBoundary, _setEditedBoundary] = useState<GeoJSONFeature | null>(null)
  const [fullMap, setFullMap]  = useState(false)   // full-screen map toggle
  const [activePanel, setActivePanel] = useState<'details' | 'sentinel' | 'neighbors'>('details')

  useEffect(() => {
    if (!caseId) return
    setLoading(true)
    Promise.all([fetchCase(caseId), fetchEvidence(caseId), fetchGeometryLayers(caseId)])
      .then(([cd, ev, gl]) => { setCase(cd); setBundle(ev); setLayers(gl) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [caseId])

  if (loading || !c) return (
    <div style={{
      position: 'fixed', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--color-bg)', fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--color-text-secondary)'
    }}>
      INITIALIZING FIELD MODULE...
    </div>
  )

  return (
    <div style={{ position: 'fixed', inset: 0, display: 'flex', flexDirection: 'column', background: 'var(--color-bg)' }}>

      {/* ── TopBar ─────────────────────────────────── */}
      <header style={{
        height: '44px', flexShrink: 0,
        background: 'rgba(8, 12, 18, 0.90)',
        borderBottom: '1px solid var(--color-border-mid)',
        backdropFilter: 'blur(16px)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', zIndex: 300,
        boxShadow: '0 1px 0 var(--color-border-mid)'
      }}>
        {/* Left: breadcrumb */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => navigate('/surveyor/home')}
            style={{
              background: 'none', border: 'none', color: 'var(--color-text-secondary)',
              cursor: 'pointer', padding: '4px', fontSize: '0.85rem',
              display: 'flex', alignItems: 'center', gap: '4px',
              transition: 'color 0.18s'
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--color-text-primary)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--color-text-secondary)'}
          >
            ← BACK
          </button>

          <div style={{ width: '1px', height: '14px', background: 'var(--color-border-mid)' }} />

          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.82rem', color: 'var(--color-text-primary)', fontWeight: 600 }}>
            {c.parcel_id}
          </span>
          <span style={{ color: 'var(--color-text-secondary)', fontSize: '0.8rem' }}>
            {c.village}, {c.district}
          </span>
          <span className="badge badge--blue" style={{ fontSize: '0.58rem' }}>FIELD VISIT</span>
        </div>

        {/* Right: actions */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {/* Full-screen map toggle */}
          <button
            className="btn btn-ghost"
            onClick={() => setFullMap(f => !f)}
            title={fullMap ? 'Show panel' : 'Full-screen map'}
            style={{ fontSize: '0.75rem', padding: '5px 8px' }}
          >
            {fullMap ? '⊟ PANEL' : '⊞ FULL MAP'}
          </button>

          <button className="btn btn-outline" style={{ fontSize: '0.75rem', padding: '5px 10px' }}>
            SAVE DRAFT
          </button>

          <button
            className="btn btn-primary"
            style={{ fontSize: '0.75rem', padding: '5px 14px' }}
            disabled={!editedBoundary}
            onClick={() => navigate(`/surveyor/field-visit/${caseId}/confirm`)}
          >
            CONFIRM →
          </button>
        </div>
      </header>

      {/* ── Main area ──────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* Map — always visible */}
        <div style={{ flex: 1, position: 'relative', minWidth: 0 }}>
          <MapboxMap 
            layers={layers}
            showAILayer={true}
          />

          {/* ── Floating bottom stats banner ─────── */}
          <div style={{
            position: 'absolute', bottom: '24px', left: '50%',
            transform: 'translateX(-50%)',
            background: 'rgba(8, 12, 18, 0.90)',
            backdropFilter: 'blur(12px)',
            border: '1px solid var(--color-border-mid)',
            borderRadius: '5px',
            padding: '10px 20px',
            display: 'flex', gap: '28px',
            fontFamily: 'var(--font-mono)', fontSize: '0.78rem',
            color: 'var(--color-text-secondary)', zIndex: 200,
            boxShadow: '0 4px 20px rgba(0,0,0,0.6)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--color-warning)' }}>⚠ Spatial Mismatch</span>
              <span style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>{c.spatial_mismatch_pct.toFixed(1)}%</span>
            </div>
            <div style={{ width: '1px', background: 'var(--color-border-mid)' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--color-text-secondary)' }}>Boundary Shift</span>
              <span style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>{c.boundary_shift_m.toFixed(1)} m</span>
            </div>
            <div style={{ width: '1px', background: 'var(--color-border-mid)' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--color-text-secondary)' }}>Boundary Edited</span>
              <span style={{ color: editedBoundary ? 'var(--color-sage)' : 'var(--color-border-mid)', fontWeight: 600 }}>
                {editedBoundary ? '● YES' : '○ NO'}
              </span>
            </div>
          </div>

          {/* Map legend — top left */}
          <div style={{
            position: 'absolute', top: '56px', left: '10px',
            background: 'rgba(8,12,18,0.85)', backdropFilter: 'blur(8px)',
            border: '1px solid var(--color-border-mid)',
            borderRadius: '4px', padding: '10px 14px',
            fontFamily: 'var(--font-mono)', fontSize: '0.68rem',
            display: 'flex', flexDirection: 'column', gap: '6px', zIndex: 100,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '20px', borderBottom: '2px dashed var(--color-navy)' }} />
              <span style={{ color: 'var(--color-text-secondary)' }}>Cadastral (Old)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '20px', borderBottom: '2px dashed var(--color-warning)' }} />
              <span style={{ color: 'var(--color-text-secondary)' }}>AI Identified</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '20px', borderBottom: '2px solid #E8EDF4' }} />
              <span style={{ color: 'var(--color-text-secondary)' }}>Your Edit</span>
            </div>
          </div>
        </div>

        {/* ── Right Panel (hidden in fullMap mode) ─── */}
        {!fullMap && (
          <div style={{
            width: '280px', flexShrink: 0,
            background: 'var(--color-bg-raised)',
            borderLeft: '1px solid var(--color-border)',
            display: 'flex', flexDirection: 'column',
            maxHeight: '100%', overflowY: 'auto',
            scrollbarWidth: 'thin',
            scrollbarColor: 'var(--color-border-mid) transparent',
          }}>

            {/* Panel tab strip */}
            <div style={{
              display: 'flex', borderBottom: '1px solid var(--color-border)',
              flexShrink: 0
            }}>
              {(['details', 'sentinel', 'neighbors'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActivePanel(tab)}
                  style={{
                    flex: 1, padding: '10px 0',
                    background: 'none', border: 'none',
                    borderBottom: `2px solid ${activePanel === tab ? 'var(--color-navy)' : 'transparent'}`,
                    color: activePanel === tab ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                    fontSize: '0.65rem', fontFamily: 'var(--font-mono)',
                    letterSpacing: '0.08em', textTransform: 'uppercase',
                    cursor: 'pointer', transition: 'all 0.18s',
                    marginBottom: '-1px'
                  }}
                >
                  {tab === 'details' ? 'PARCEL' : tab === 'sentinel' ? 'SENTINEL' : 'NEIGHBORS'}
                </button>
              ))}
            </div>

            {/* ── Details Panel ─────────────────── */}
            {activePanel === 'details' && (
              <div style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <div className="panel-label">PARCEL DETAILS</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px 12px' }}>
                    {[
                      { label: 'Owner',         value: bundle?.records?.ror?.owner_name || c.owner_name || 'Unassigned' },
                      { label: 'Khasra #',      value: bundle?.records?.ror?.khasra_no || 'Unassigned', mono: true },
                      { label: 'Cadastral Area', value: bundle?.spatial?.cadastral_area_sqm ? `${bundle.spatial.cadastral_area_sqm.toLocaleString()} m²` : 'N/A', mono: true },
                      { label: 'Recorded',      value: bundle?.records?.ror?.record_date || 'Unknown', mono: true },
                    ].map(f => (
                      <div key={f.label}>
                        <div style={{ fontSize: '0.62rem', color: 'var(--color-text-secondary)', marginBottom: '3px', letterSpacing: '0.06em' }}>
                          {f.label}
                        </div>
                        <div style={{
                          fontSize: '0.82rem', color: 'var(--color-text-primary)', fontWeight: 500,
                          fontFamily: f.mono ? 'var(--font-mono)' : undefined
                        }}>
                          {f.value}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="divider" />

                <div>
                  <div className="panel-label">MUTATION STATUS</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{
                        fontSize: '0.88rem', fontWeight: 600,
                        color: c.mutation_status === 'pending' ? 'var(--color-warning)' : 'var(--color-sage)',
                        textTransform: 'capitalize'
                      }}>
                        {c.mutation_status}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                        {c.mutation_status === 'pending' ? '3 active records' : 'No active disputes'}
                      </div>
                    </div>
                    <button className="btn btn-outline" style={{ fontSize: '0.7rem', padding: '4px 8px' }}>
                      DETAILS
                    </button>
                  </div>
                </div>

                <div className="divider" />

                {/* AI Confidence */}
                <div>
                  <div className="panel-label">AI CONFIDENCE</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ flex: 1, height: '4px', background: 'var(--color-border-mid)', borderRadius: '2px', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${c.confidence_score}%`, background: 'var(--color-navy)', borderRadius: '2px' }} />
                    </div>
                    <span style={{ fontSize: '0.82rem', fontFamily: 'var(--font-mono)', color: 'var(--color-text-primary)', fontWeight: 600 }}>
                      {c.confidence_score}%
                    </span>
                  </div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
                    Based on boundary model v2.3
                  </div>
                </div>
              </div>
            )}

            {/* ── Sentinel Panel ─────────────────── */}
            {activePanel === 'sentinel' && (
              <div style={{ padding: '16px 18px' }}>
                {c?.parcel_id && <SentinelTimelapse parcelId={c.parcel_id} />}
              </div>
            )}

            {/* ── Neighbors Panel ─────────────────── */}
            {activePanel === 'neighbors' && (
              <div style={{ padding: '16px 18px' }}>
                <div className="panel-label">NEIGHBOR PARCELS</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {Array.from({ length: 4 }).map((_, i) => {
                    // Generate dynamic neighbor IDs based on the current parcel ID
                    const hash = c.parcel_id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
                    const nId = `P${(hash % 900 + i * 7 + 100).toString().padStart(3, '0')}`;
                    const nOwner = ['Ranga Rao', 'Subbamma', 'Krishna Murthy', 'Lakshmi Devi', 'Venkateswara Rao', 'Siva Reddy'][(hash + i) % 6];
                    const p = `${nId} — ${nOwner}`;
                    return (
                    <div
                      key={p}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '10px 12px',
                        background: 'var(--bg-raised)',
                        border: '1px solid var(--color-border)',
                        borderRadius: '4px', cursor: 'pointer',
                        transition: 'all 0.18s'
                      }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--color-navy)'; e.currentTarget.style.background = 'var(transparent)'; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.background = 'var(--bg-raised)'; }}
                    >
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>{p}</span>
                      <span style={{ color: 'var(--color-text-secondary)', fontSize: '0.8rem' }}>→</span>
                    </div>
                  )})}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
