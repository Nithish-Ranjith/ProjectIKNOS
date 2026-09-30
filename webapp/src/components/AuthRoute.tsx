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
      <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <p><span className="spinner"></span> Loading session...</p>
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
