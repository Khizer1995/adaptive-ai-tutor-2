// ui/src/components/ProtectedRoute.jsx
// Redirects unauthenticated users to /login.

import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent" />
          <p className="text-sm text-gray-400">Loading session…</p>
        </div>
      </div>
    )
  }

  if (!user) {
    // Use window.location so we don't need react-router as a dep
    window.location.hash = '#/login'
    return null
  }

  return children
}
