// ui/src/lib/auth.js
import { supabase } from './supabase'

export async function signIn({ email, password }) {
  return await supabase.auth.signInWithPassword({ email, password })
}

export async function signUp({ email, password, fullName }) {
  return await supabase.auth.signUp({
    email,
    password,
    options: {
      data: {
        full_name: fullName,
      },
    },
  })
}

export async function signOut() {
  return await supabase.auth.signOut()
}

export async function resetPassword(email) {
  return await supabase.auth.resetPasswordForEmail(email)
}
