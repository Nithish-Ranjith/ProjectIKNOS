import React, { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { supabase } from '../lib/supabase'

interface AuthRouteProps {
  allowedRoles?: string[]
}

export const AuthRoute: React.FC<AuthRouteProps> = ({ allowedRoles }) => {
  const [session, setSession] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [role, setRole] = useState<string | null>(null)

  useEffect(() => {
    const demo = localStorage.getItem('demo_session')
    if (demo) {
      const parsed = JSON.parse(demo)
      setSession({ user: { email: parsed.email, user_metadata: { role: parsed.role } } })
      setRole(parsed.role)
      setLoading(false)
      return
    }

    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      if (session) {
        setRole(session.user.user_metadata?.role || 'user')
      }
      setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (session) {
        setRole(session.user.user_metadata?.role || 'user')
      } else {
        setRole(null)
      }
      setLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [])

  if (loading) {
    return (
      <div style={{
        height: '100vh', width: '100vw', 
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', 
        background: '#0a1628', color: 'white', fontFamily: 'var(--font-ui)'
      }}>
        <div style={{
          width: 48, height: 48, background: 'var(--color-terracotta)', clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)', marginBottom: '16px',
          animation: 'pulse 2s infinite'
        }} />
        <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700, letterSpacing: '-0.03em' }}>IKNOS</h1>
        <p style={{ marginTop: '8px', color: 'rgba(255,255,255,0.6)', fontSize: '13px' }}>Loading session...</p>
      </div>
    )
  }

  if (!session) {
    return <Navigate to="/login" replace />
  }

  if (allowedRoles && role && !allowedRoles.includes(role)) {
    if (role === 'surveyor') return <Navigate to="/surveyor/home" replace />
    if (role === 'admin') return <Navigate to="/admin/home" replace />
    return <Navigate to="/user/home" replace />
  }

  return <Outlet />
}
