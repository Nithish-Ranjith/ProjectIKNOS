import React from 'react'
import { supabase } from '../lib/supabase'
import { useNavigate } from 'react-router-dom'

export const SurveyorHome: React.FC = () => {
  const navigate = useNavigate()
  const handleLogout = async () => { await supabase.auth.signOut(); navigate('/login'); }
  return (
    <div className="app-container">
      <header className="topbar">
        <h1>IKNOS | Surveyor Dashboard</h1>
        <button onClick={handleLogout} className="btn btn-outline" style={{ color: 'white', borderColor: 'white' }}>Logout</button>
      </header>
      <main className="main-content">
        <h2>Assigned Missions & Field Visits</h2>
        <p>Surveyor list of tasks and drone flight options here.</p>
      </main>
    </div>
  )
}
