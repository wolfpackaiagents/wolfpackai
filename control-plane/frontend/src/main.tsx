import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './i18n'
import './index.css'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Traces from './pages/Traces'
import TraceDetail from './pages/TraceDetail'
import Settings from './pages/Settings'
import Sessions from './pages/Sessions'
import SessionDetail from './pages/SessionDetail'
import Approvals from './pages/Approvals'
import Guardrails from './pages/Guardrails'
import Scores from './pages/Scores'
import Privacy from './pages/Privacy'
import Resilience from './pages/Resilience'
import Mesh from './pages/Mesh'
import Chat from './pages/Chat'
import Schedules from './pages/Schedules'
import Channels from './pages/Channels'
import { useAuthStore } from './stores/auth'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const apiKey = useAuthStore((s) => s.apiKey)
  if (!apiKey) return <Navigate to="/login" replace />
  return <>{children}</>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route path="/" element={<Dashboard />} />
          <Route path="/traces" element={<Traces />} />
          <Route path="/traces/:id" element={<TraceDetail />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/sessions/:id" element={<SessionDetail />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/guardrails" element={<Guardrails />} />
          <Route path="/scores" element={<Scores />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/resilience" element={<Resilience />} />
          <Route path="/mesh" element={<Mesh />} />
           <Route path="/chat" element={<Chat />} />
           <Route path="/chat/:conversationId" element={<Chat />} />
          <Route path="/schedules" element={<Schedules />} />
          <Route path="/channels" element={<Channels />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
