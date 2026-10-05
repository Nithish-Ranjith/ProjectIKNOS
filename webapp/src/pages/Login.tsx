import React, { useState } from 'react'
import { supabase } from '../lib/supabase'
import { useNavigate } from 'react-router-dom'

export const Login: React.FC = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('user') 
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const navigate = useNavigate()

  const handleDemoLogin = async (demoRole: string, demoEmail: string) => {
    setLoading(true)
    setError(null)
    localStorage.setItem('demo_session', JSON.stringify({ email: demoEmail, role: demoRole }))
    if (demoRole === 'surveyor') navigate('/surveyor/home')
    else if (demoRole === 'admin') navigate('/admin/home')
    else navigate('/user/home')
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    if (email.endsWith('@demo.com')) {
      localStorage.setItem('demo_session', JSON.stringify({ email, role }))
      if (role === 'surveyor') navigate('/surveyor/home')
      else if (role === 'admin') navigate('/admin/home')
      else navigate('/user/home')
      return
    }

    const { error: signInError } = await supabase.auth.signInWithPassword({ email, password })

    if (signInError) {
      setError('Invalid email or password. Use the Quick Access buttons below for the demo.')
      setLoading(false)
      return
    }

    setLoading(false)
    if (role === 'surveyor') navigate('/surveyor/home')
    else if (role === 'admin') navigate('/admin/home')
    else navigate('/user/home')
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', width: '100%',
      background: 'linear-gradient(135deg, #05070a 0%, #0a0c14 100%)',
      fontFamily: 'var(--font-ui)',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Background decorations */}
      <div style={{ position: 'absolute', top: '-20%', left: '-10%', width: '50%', height: '50%', background: 'radial-gradient(circle, rgba(47,129,247,0.05) 0%, transparent 70%)', borderRadius: '50%', filter: 'blur(60px)' }} />
      <div style={{ position: 'absolute', bottom: '-20%', right: '-10%', width: '60%', height: '60%', background: 'radial-gradient(circle, rgba(124,58,237,0.05) 0%, transparent 70%)', borderRadius: '50%', filter: 'blur(80px)' }} />
      
      <div style={{
        width: '100%', maxWidth: '440px', zIndex: 1,
        background: 'rgba(15, 18, 25, 0.6)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '2.5rem',
        boxShadow: '0 24px 48px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)',
        animation: 'fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1)'
      }}>
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 48, height: 48, borderRadius: 12, background: 'linear-gradient(135deg, #2f81f7, #7c3aed)', marginBottom: '1rem', boxShadow: '0 8px 16px rgba(47,129,247,0.3)' }}>
            <span style={{ color: '#fff', fontWeight: 800, fontSize: '24px', letterSpacing: '-1px' }}>I</span>
          </div>
          <h2 style={{ fontSize: '24px', fontWeight: 700, color: '#fff', letterSpacing: '-0.02em', margin: 0 }}>Project IKNOS</h2>
          <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.5)', marginTop: '0.5rem', fontWeight: 500 }}>Secure Identity Gateway</p>
        </div>

        {error && (
          <div style={{ background: 'rgba(248,81,73,0.1)', border: '1px solid rgba(248,81,73,0.3)', color: '#f85149', padding: '12px 16px', borderRadius: '8px', fontSize: '13px', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: '16px' }}>⚠</span>
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'rgba(255,255,255,0.7)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Authorization Role</label>
            <div style={{ position: 'relative' }}>
              <select 
                value={role} 
                onChange={e => setRole(e.target.value)}
                style={{
                  width: '100%', appearance: 'none', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.1)',
                  padding: '12px 16px', borderRadius: '8px', color: '#fff', fontSize: '14px', outline: 'none',
                  transition: 'all 0.2s', cursor: 'pointer'
                }}
                onFocus={e => e.target.style.borderColor = '#2f81f7'}
                onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
              >
                <option value="user" style={{ background: '#0f1219' }}>Landowner (Citizen)</option>
                <option value="surveyor" style={{ background: '#0f1219' }}>Drone Surveyor (Field Ops)</option>
                <option value="admin" style={{ background: '#0f1219' }}>Settlement Officer (HQ)</option>
              </select>
              <div style={{ position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'rgba(255,255,255,0.4)', fontSize: '10px' }}>▼</div>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'rgba(255,255,255,0.7)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Access ID (Email)</label>
            <input 
              type="email" required value={email} onChange={e => setEmail(e.target.value)}
              placeholder="Enter your email"
              style={{
                width: '100%', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.1)',
                padding: '12px 16px', borderRadius: '8px', color: '#fff', fontSize: '14px', outline: 'none',
                transition: 'all 0.2s'
              }}
              onFocus={e => e.target.style.borderColor = '#2f81f7'}
              onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'rgba(255,255,255,0.7)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Security Key</label>
            <input 
              type="password" required value={password} onChange={e => setPassword(e.target.value)}
              placeholder="Enter your password"
              style={{
                width: '100%', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.1)',
                padding: '12px 16px', borderRadius: '8px', color: '#fff', fontSize: '14px', outline: 'none',
                transition: 'all 0.2s'
              }}
              onFocus={e => e.target.style.borderColor = '#2f81f7'}
              onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
            />
          </div>

          <button 
            type="submit" 
            disabled={loading}
            style={{
              width: '100%', padding: '14px', borderRadius: '8px', marginTop: '0.5rem',
              background: 'linear-gradient(90deg, #2f81f7, #1f6ce6)',
              border: 'none', color: '#fff', fontSize: '14px', fontWeight: 600, letterSpacing: '0.02em',
              cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.7 : 1,
              transition: 'all 0.2s', boxShadow: '0 4px 12px rgba(47,129,247,0.3)'
            }}
          >
            {loading ? 'Authenticating...' : 'Initialize Session'}
          </button>
        </form>

        {/* Demo Quick Access */}
        <div style={{ marginTop: '2.5rem', paddingTop: '1.5rem', borderTop: '1px dashed rgba(255,255,255,0.1)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.1em', textAlign: 'center', marginBottom: '1rem' }}>
            Development Quick Access
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button 
              onClick={() => handleDemoLogin('user', 'user@demo.com')}
              disabled={loading}
              style={{ flex: 1, padding: '10px 0', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '6px', color: 'rgba(255,255,255,0.6)', fontSize: '12px', fontWeight: 500, cursor: loading ? 'not-allowed' : 'pointer', transition: 'all 0.2s' }}
              onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
              onMouseOut={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
            >
              Citizen
            </button>
            <button 
              onClick={() => handleDemoLogin('surveyor', 'drone1@demo.com')}
              disabled={loading}
              style={{ flex: 1, padding: '10px 0', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '6px', color: 'rgba(255,255,255,0.6)', fontSize: '12px', fontWeight: 500, cursor: loading ? 'not-allowed' : 'pointer', transition: 'all 0.2s' }}
              onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
              onMouseOut={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
            >
              Surveyor
            </button>
            <button 
              onClick={() => handleDemoLogin('admin', 'admin@demo.com')}
              disabled={loading}
              style={{ flex: 1, padding: '10px 0', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '6px', color: 'rgba(255,255,255,0.6)', fontSize: '12px', fontWeight: 500, cursor: loading ? 'not-allowed' : 'pointer', transition: 'all 0.2s' }}
              onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
              onMouseOut={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
            >
              HQ Admin
            </button>
          </div>
        </div>
      </div>
      
      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
