// ui/src/AppRouter.jsx
// Lightweight hash-based router — no extra dependencies required.
// Routes:
//   #/login   → LoginPage
//   #/signup  → SignupPage
//   #/ or ""  → App (dashboard, protected)

import { useState, useEffect } from 'react'
import { useAuth } from './context/AuthContext'
import LoginPage  from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import App        from './App'

function getRoute() {
  const hash = window.location.hash.replace('#', '') || '/'
  if (hash.startsWith('/login'))  return 'login'
  if (hash.startsWith('/signup')) return 'signup'
  return 'app'
}

export default function AppRouter() {
  const { user, loading } = useAuth()
  const [route, setRoute] = useState(getRoute)

  // Keep route in sync with the URL hash
  useEffect(() => {
    const handler = () => setRoute(getRoute())
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  // While auth state is resolving, show a full-screen spinner
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-teal-500 border-t-transparent" />
          <p className="text-sm text-gray-400">Loading…</p>
        </div>
      </div>
    )
  }

  // Navigate helper passed to auth pages
  function navigate(to) {
    window.location.hash = `#/${to}`
    setRoute(to)
  }

  // ── Public routes ────────────────────────────────────────────────────────
  if (route === 'login') {
    // If already logged in, go straight to dashboard
    if (user) { navigate(''); return null }
    return <LoginPage onNavigate={navigate} />
  }

  if (route === 'signup') {
    if (user) { navigate(''); return null }
    return <SignupPage onNavigate={navigate} />
  }

  // ── Protected dashboard ──────────────────────────────────────────────────
  if (!user) {
    // Not authenticated → redirect to login
    navigate('login')
    return null
  }

  return <App />
}
