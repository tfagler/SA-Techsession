import { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { SessionPage } from './pages/Session'
import { QuizPage } from './pages/Quiz'
import { SettingsPage } from './pages/Settings'
import { Nav } from './components/Nav'
import { api } from './lib/api'

function getToken() {
  return localStorage.getItem('auth_token')
}

export default function App() {
  const [token, setToken] = useState<string | null>(getToken())
  const [checked, setChecked] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    function forceLogout() {
      localStorage.removeItem('auth_token')
      setToken(null)
      navigate('/')
    }
    window.addEventListener('auth:unauthorized', forceLogout as EventListener)
    return () => window.removeEventListener('auth:unauthorized', forceLogout as EventListener)
  }, [navigate])

  useEffect(() => {
    async function verify() {
      if (!token) {
        setChecked(true)
        return
      }
      try {
        await api('/auth/me', { token })
      } catch {
        localStorage.removeItem('auth_token')
        setToken(null)
      } finally {
        setChecked(true)
      }
    }
    verify()
  }, [token])

  if (!checked) return <div className="page">Loading...</div>

  if (!token) {
    return (
      <Login
        onAuth={(t) => {
          localStorage.setItem('auth_token', t)
          setToken(t)
          window.location.href = '/dashboard'
        }}
      />
    )
  }

  return (
    <div>
      <Nav
        onLogout={() => {
          localStorage.removeItem('auth_token')
          setToken(null)
          navigate('/')
          window.location.reload()
        }}
      />
      <Routes>
        <Route path="/dashboard" element={<Dashboard token={token} />} />
        <Route path="/session/:id" element={<SessionPage token={token} />} />
        <Route path="/quiz" element={<QuizPage token={token} />} />
        <Route path="/settings" element={<SettingsPage token={token} />} />
        <Route path="*" element={<Navigate to="/dashboard" />} />
      </Routes>
    </div>
  )
}
