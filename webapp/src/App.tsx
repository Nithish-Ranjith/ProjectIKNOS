import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthRoute } from './components/AuthRoute'

// Auth
import { Login } from './pages/Login'

import { UserHome }        from './pages/user/UserHome'
import { UserParcelDetail} from './pages/user/UserParcelDetail'
import { UserGrievance }   from './pages/user/UserGrievance'
import { SurveyorHome }      from './pages/surveyor/SurveyorHome'
import { SurveyorFieldVisit } from './pages/surveyor/SurveyorFieldVisit'
import { SurveyorMission }    from './pages/surveyor/SurveyorMission'
import { SurveyorHistory }    from './pages/surveyor/SurveyorHistory'
import { SurveyorProfile }    from './pages/surveyor/SurveyorProfile'
import { AppShell }           from './components/layout/AppShell'
import { AdminHome }          from './pages/AdminHome'

import { AdminCases }      from './pages/admin/AdminCases'
import { AdminCaseDetail } from './pages/admin/AdminCaseDetail'
import ErrorBoundary from './ErrorBoundary'

function App() {
  return (
    <ErrorBoundary>
      <Router>
      <Routes>
        {/* Auth (Architecture §1.2) */}
        <Route path="/login" element={<Login />} />

        {/* USER role — Architecture §2 */}
        <Route element={<AuthRoute allowedRoles={['user']} />}>
          <Route path="/user/home" element={<UserHome />} />
          <Route path="/user/parcel/:id" element={<UserParcelDetail />} />
          <Route path="/user/parcel/:id/grievance" element={<UserGrievance />} />
        </Route>

        {/* SURVEYOR role — Architecture §3 (New App Shell) */}
        <Route element={<AuthRoute allowedRoles={['surveyor']} />}>
          <Route element={<AppShell />}>
            {/* Navigation roots */}
            <Route path="/surveyor/home"           element={<SurveyorHome />} />
            <Route path="/surveyor/history"        element={<SurveyorHistory />} />
            <Route path="/surveyor/profile"        element={<SurveyorProfile />} />
            
            {/* Field Visit Flow (Admin layout context) */}
            <Route path="/surveyor/field-visit/:id" element={<SurveyorFieldVisit />} />
          </Route>
          
          {/* Mission Flow (Full-Screen Immersive Field UI, NO sidebar) */}
          <Route path="/surveyor/mission/:id/*"  element={<SurveyorMission />} />

          <Route path="/surveyor/cases" element={<Navigate to="/surveyor/home" replace />} />
        </Route>

        {/* ADMIN / OFFICER role — Architecture §4 */}
        <Route element={<AuthRoute allowedRoles={['admin']} />}>
          <Route path="/admin/home"         element={<AdminHome />} />
          <Route path="/admin/cases"        element={<AdminCases />} />
          <Route path="/admin/cases/:id"    element={<AdminCaseDetail />} />
          {/* Stub routes — to be filled in subsequent build steps */}
          <Route path="/admin/records"  element={<AdminHome />} />
          <Route path="/admin/users"    element={<AdminHome />} />
          <Route path="/admin/settings" element={<AdminHome />} />
        </Route>

        {/* Root redirects */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </Router>
    </ErrorBoundary>
  )
}

export default App
