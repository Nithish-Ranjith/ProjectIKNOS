import React, { useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { supabase } from '../../lib/supabase'
import { submitGrievance } from '../../services/api'

//  Photo thumbnail 
const PhotoThumb: React.FC<{ uri: string; onRemove: () => void }> = ({ uri, onRemove }) => (
  <div style={{ position: 'relative', width: '80px', height: '80px', border: '1px solid var(--color-border)' }}>
    <img src={uri} alt="Evidence" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    <button
      onClick={onRemove}
      style={{
        position: 'absolute', top: '-6px', right: '-6px',
        background: 'var(--color-terracotta)', color: '#000',
        border: 'none', width: '18px', height: '18px',
        cursor: 'pointer', fontSize: '0.65rem', lineHeight: '18px', textAlign: 'center', padding: 0,
        fontFamily: 'var(--font-mono)', fontWeight: 'bold'
      }}
    >X</button>
  </div>
)

export const UserGrievance: React.FC = () => {
  const { id: parcelId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)

  //  Form State 
  const [text, setText] = useState('')
  const [photoUris, setPhotoUris] = useState<string[]>([])
  const [photoError, setPhotoError] = useState<string | null>(null)

  //  Submit State 
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  //  Handlers 
  const handlePhotoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPhotoError(null)
    const files = Array.from(e.target.files ?? [])
    if (photoUris.length + files.length > 5) { setPhotoError('Maximum 5 photos per submission.'); return }
    const uris = files.map(f => URL.createObjectURL(f))
    setPhotoUris(prev => [...prev, ...uris])
    e.target.value = ''
  }

  const removePhoto = (idx: number) => {
    setPhotoUris(prev => {
      URL.revokeObjectURL(prev[idx])
      return prev.filter((_, i) => i !== idx)
    })
  }

  const handleSubmit = async () => {
    if (text.trim().length === 0 || !parcelId) return
    setSubmitting(true)
    setError(null)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      await submitGrievance({
        parcel_id: parcelId,
        text: text.trim(),
        photo_uris: photoUris, // Note: Ephemeral object URLs here; Supabase Storage in real app
        submitted_by: session?.user.email ?? 'unknown',
      })
      setSubmitted(true)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleLogout = async () => {
    await supabase.auth.signOut()
    navigate('/login')
  }

  //  Render 
  if (submitted) return (
    <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ maxWidth: '480px', textAlign: 'center', padding: '3rem' }}>
        <div style={{ fontSize: '3rem', marginBottom: '1rem', color: '#4a7c59' }}>[ OK ]</div>
        <h2 style={{ marginBottom: '0.75rem', letterSpacing: '0.1em' }}>Grievance Submitted</h2>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: '1.5rem', fontFamily: 'var(--font-mono)' }}>
          Your concern for parcel <strong>{parcelId}</strong> has been filed successfully. A government officer will review it shortly.
        </p>
        <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => navigate(`/user/parcel/${parcelId}`)}>← RETURN TO PARCEL</button>
      </div>
    </div>
  )

  const canSubmit = text.trim().length > 0 && photoUris.length > 0

  return (
    <div className="app-container">
      <header className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button onClick={() => navigate(`/user/parcel/${parcelId}`)} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.7)', cursor: 'pointer', fontSize: '1.2rem' }}>←</button>
          <span style={{ fontFamily: 'var(--font-ui)', fontWeight: 700 }}>Raise a Concern</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', opacity: 0.7 }}>{parcelId}</span>
        </div>
        <button onClick={handleLogout} className="btn btn-outline" style={{ color: 'white', borderColor: 'white', fontSize: '0.85rem' }}>Logout</button>
      </header>

      <main className="main-content" style={{ maxWidth: '700px' }}>
        <div className="card" style={{ marginBottom: '1.25rem' }}>
          <h2 style={{ fontSize: '1.25rem', marginBottom: '1rem' }}>File a Grievance</h2>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
            If you believe there is an error in your parcel boundary, area calculation, or mutation record, please describe the issue in detail below.
          </p>

          <div className="form-group">
            <label className="form-label">
              Description <span style={{ color: 'var(--color-terracotta)' }}>*</span>
            </label>
            <textarea
              className="form-input"
              rows={6}
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder="Describe the discrepancy clearly..."
              style={{ resize: 'vertical' }}
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              Supporting Evidence (Photos / Documents) <span style={{ color: 'var(--color-terracotta)' }}>*</span>
            </label>
            <p style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)', margin: '0 0 0.5rem' }}>
              Upload up to 5 images to support your claim (at least 1 is required).
            </p>

            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              style={{ display: 'none' }}
              onChange={handlePhotoSelect}
            />

            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-start' }}>
              {photoUris.map((uri, i) => (
                <PhotoThumb key={uri} uri={uri} onRemove={() => removePhoto(i)} />
              ))}
              {photoUris.length < 5 && (
                <button
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    width: '80px', height: '80px', border: '1px dashed var(--color-border)',
                    background: 'rgba(0,0,0,0.4)', cursor: 'pointer',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--color-text-secondary)', transition: 'all 0.15s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = '#4a7c59'; e.currentTarget.style.color = '#4a7c59'; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.color = 'var(--color-text-secondary)'; }}
                >
                  <span style={{ fontSize: '1.5rem', lineHeight: 1 }}>+</span>
                  <span style={{ fontSize: '0.6rem', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', marginTop: '4px' }}>Add</span>
                </button>
              )}
            </div>
            {photoError && <p style={{ color: 'var(--color-terracotta)', fontSize: '0.8rem', margin: '0.5rem 0 0', fontFamily: 'var(--font-mono)' }}>[ERR] {photoError}</p>}
          </div>
        </div>

        {error && <div className="error-msg" style={{ marginBottom: '1rem' }}> {error}</div>}

        <button
          className="btn btn-primary"
          style={{ width: '100%', padding: '0.75rem', fontSize: '1rem' }}
          disabled={!canSubmit || submitting}
          onClick={handleSubmit}
        >
          {submitting
            ? <><span className="spinner"></span> Submitting...</>
            : 'Submit Grievance'}
        </button>
      </main>
    </div>
  )
}
