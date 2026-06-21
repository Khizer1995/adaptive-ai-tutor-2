// ui/src/lib/auth.js
// Thin wrapper around Supabase Auth — keeps auth logic out of components.

import { supabase } from './supabase'

/** Sign up a new user.  Returns { data, error }. */
export async function signUp({ email, password, fullName }) {
  return supabase.auth.signUp({
    email,
    password,
    options: {
      data: { full_name: fullName || email.split('@')[0] },
    },
  })
}

/** Sign in with email + password.  Returns { data, error }. */
export async function signIn({ email, password }) {
  return supabase.auth.signInWithPassword({ email, password })
}

/** Sign out the current session.  Returns { error }. */
export async function signOut() {
  return supabase.auth.signOut()
}

/** Send a password-reset email.  Returns { data, error }. */
export async function resetPassword(email) {
  return supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/reset-password`,
  })
}

/** Get the current session (null if not logged in). */
export async function getSession() {
  const { data } = await supabase.auth.getSession()
  return data.session
}

/** Get the current user (null if not logged in). */
export async function getUser() {
  const { data } = await supabase.auth.getUser()
  return data.user
}
