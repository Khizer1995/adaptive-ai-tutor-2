// ui/src/context/AuthContext.jsx
// Global React context that provides authentication state + actions.

import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { supabase } from '../lib/supabase'
import { signIn, signUp, signOut, resetPassword } from '../lib/auth'

const AuthContext = createContext(null)

/** Derive student_id from Supabase user UUID — must match Python backend. */
function deriveStudentId(userId) {
  return `USER-${userId.slice(0, 8)}`
}

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)   // Supabase User object
  const [session, setSession] = useState(null)   // Supabase Session object
  const [loading, setLoading] = useState(true)   // true while resolving initial session

  // ── Bootstrap: restore session from storage & subscribe to changes ──────
  useEffect(() => {
    // Get the persisted session immediately.
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Subscribe to future auth state changes.
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        setUser(session?.user ?? null)
        setLoading(false)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  // ── Actions ──────────────────────────────────────────────────────────────

  const login = useCallback(async ({ email, password }) => {
    const { data, error } = await signIn({ email, password })
    if (error) return { success: false, error: error.message }
    return { success: true, user: data.user, session: data.session }
  }, [])

  const signup = useCallback(async ({ email, password, fullName }) => {
    const { data, error } = await signUp({ email, password, fullName })
    if (error) return { success: false, error: error.message }
    return { success: true, user: data.user, session: data.session }
  }, [])

  const logout = useCallback(async () => {
    await signOut()
  }, [])

  const sendPasswordReset = useCallback(async (email) => {
    const { error } = await resetPassword(email)
    if (error) return { success: false, error: error.message }
    return { success: true }
  }, [])

  // ── Derived values ───────────────────────────────────────────────────────

  const accessToken = session?.access_token ?? null
  const studentId   = user ? deriveStudentId(user.id) : null
  const userName    = user?.user_metadata?.full_name
                   || user?.user_metadata?.name
                   || user?.email?.split('@')[0]
                   || 'Student'

  return (
    <AuthContext.Provider value={{
      user,
      session,
      loading,
      accessToken,
      studentId,
      userName,
      login,
      signup,
      logout,
      sendPasswordReset,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

/** Hook to consume auth context — throws if used outside AuthProvider. */
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
