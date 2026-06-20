// ui/src/pages/LoginPage.jsx
import { useState, useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import { Eye, EyeOff, Loader2, BrainCircuit, Mail, Lock, ArrowRight, AlertCircle, CheckCircle2 } from 'lucide-react'

export default function LoginPage({ onNavigate }) {
  const { login, sendPasswordReset } = useAuth()

  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd]   = useState(false)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  // Forgot-password state
  const [forgotOpen, setForgotOpen]     = useState(false)
  const [resetEmail, setResetEmail]     = useState('')
  const [resetLoading, setResetLoading] = useState(false)
  const [resetMsg, setResetMsg]         = useState('')

  const emailRef = useRef(null)

  // ── Validation ─────────────────────────────────────────────────────────
  function validateEmail(v) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim())
  }

  // ── Login submit ───────────────────────────────────────────────────────
  async function handleLogin(e) {
    e.preventDefault()
    setError('')

    if (!validateEmail(email)) {
      setError('Please enter a valid email address.')
      return
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.')
      return
    }

    setLoading(true)
    const result = await login({ email: email.trim(), password })
    setLoading(false)

    if (!result.success) {
      setError(result.error || 'Login failed. Please try again.')
    }
    // On success, AuthContext updates user → App.jsx detects & renders dashboard
  }

  // ── Password reset ─────────────────────────────────────────────────────
  async function handleReset(e) {
    e.preventDefault()
    setResetMsg('')
    if (!validateEmail(resetEmail)) {
      setResetMsg('error:Please enter a valid email address.')
      return
    }
    setResetLoading(true)
    const result = await sendPasswordReset(resetEmail.trim())
    setResetLoading(false)
    if (result.success) {
      setResetMsg('ok:Reset link sent! Check your inbox.')
    } else {
      setResetMsg(`error:${result.error}`)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gray-950 px-4 font-[Inter,system-ui]">

      {/* ── Ambient background ──────────────────────────────────────────── */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/2 h-[600px] w-[600px] -translate-x-1/2 rounded-full bg-teal-500/10 blur-[120px]" />
        <div className="absolute bottom-0 right-0 h-[400px] w-[400px] rounded-full bg-purple-600/8 blur-[100px]" />
        {/* grid pattern */}
        <div
          className="absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage: 'linear-gradient(rgba(20,184,166,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(20,184,166,0.5) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        />
      </div>

      <div className="relative w-full max-w-md">

        {/* ── Card ──────────────────────────────────────────────────────── */}
        <div className="rounded-3xl border border-gray-800/80 bg-gray-900/70 p-8 shadow-2xl shadow-black/60 backdrop-blur-xl">

          {/* Logo + branding */}
          <div className="mb-8 flex flex-col items-center gap-3">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-teal-500/40 bg-teal-500/10 shadow-[0_0_32px_rgba(20,184,166,0.25)]">
              <BrainCircuit size={32} className="text-teal-400" />
            </div>
            <div className="text-center">
              <h1 className="text-2xl font-bold tracking-tight text-white">
                Cognitive<span className="text-teal-400"> AI Tutor</span>
              </h1>
              <p className="mt-1 text-sm text-gray-400">Adaptive learning, personalised for you</p>
            </div>
          </div>

          {/* Error banner */}
          {error && (
            <div className="mb-5 flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm text-red-300 animate-[fadein_250ms_ease-out]">
              <AlertCircle size={16} className="mt-0.5 shrink-0 text-red-400" />
              {error}
            </div>
          )}

          {/* ── Login form ──────────────────────────────────────────────── */}
          {!forgotOpen ? (
            <form onSubmit={handleLogin} className="space-y-5" noValidate>
              {/* Email */}
              <div className="space-y-1.5">
                <label htmlFor="login-email" className="block text-xs font-medium text-gray-300">
                  Email address
                </label>
                <div className="relative">
                  <Mail size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" />
                  <input
                    id="login-email"
                    ref={emailRef}
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={e => { setEmail(e.target.value); setError('') }}
                    placeholder="you@example.com"
                    className="w-full rounded-xl border border-gray-700 bg-gray-800/60 py-3 pl-10 pr-4 text-sm text-gray-100 placeholder-gray-600 transition-all duration-200 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label htmlFor="login-password" className="block text-xs font-medium text-gray-300">
                    Password
                  </label>
                  <button
                    type="button"
                    onClick={() => { setForgotOpen(true); setResetEmail(email); setError('') }}
                    className="text-xs text-teal-400 hover:text-teal-300 transition-colors"
                  >
                    Forgot password?
                  </button>
                </div>
                <div className="relative">
                  <Lock size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" />
                  <input
                    id="login-password"
                    type={showPwd ? 'text' : 'password'}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={e => { setPassword(e.target.value); setError('') }}
                    placeholder="••••••••"
                    className="w-full rounded-xl border border-gray-700 bg-gray-800/60 py-3 pl-10 pr-12 text-sm text-gray-100 placeholder-gray-600 transition-all duration-200 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                  />
                  <button
                    type="button"
                    tabIndex={-1}
                    onClick={() => setShowPwd(v => !v)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                    aria-label={showPwd ? 'Hide password' : 'Show password'}
                  >
                    {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {/* Submit */}
              <button
                id="login-submit-btn"
                type="submit"
                disabled={loading}
                className="group flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-teal-500 to-teal-400 py-3 text-sm font-semibold text-gray-950 shadow-lg shadow-teal-500/20 transition-all duration-200 hover:from-teal-400 hover:to-teal-300 hover:shadow-teal-500/30 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <>
                    Sign In
                    <ArrowRight size={15} className="transition-transform duration-200 group-hover:translate-x-1" />
                  </>
                )}
              </button>

              {/* Sign up link */}
              <p className="text-center text-xs text-gray-500">
                Don't have an account?{' '}
                <button
                  type="button"
                  onClick={() => onNavigate('signup')}
                  className="font-medium text-teal-400 hover:text-teal-300 transition-colors"
                >
                  Create one free
                </button>
              </p>
            </form>

          ) : (
            /* ── Forgot password panel ──────────────────────────────────── */
            <form onSubmit={handleReset} className="space-y-5" noValidate>
              <div className="text-center">
                <h2 className="text-lg font-semibold text-white">Reset your password</h2>
                <p className="mt-1 text-sm text-gray-400">We'll send a reset link to your email.</p>
              </div>

              {resetMsg && (
                <div className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm animate-[fadein_250ms_ease-out] ${
                  resetMsg.startsWith('ok:')
                    ? 'border-green-500/30 bg-green-950/40 text-green-300'
                    : 'border-red-500/30 bg-red-950/40 text-red-300'
                }`}>
                  {resetMsg.startsWith('ok:')
                    ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-green-400" />
                    : <AlertCircle size={16} className="mt-0.5 shrink-0 text-red-400" />}
                  {resetMsg.replace(/^(ok|error):/, '')}
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="reset-email" className="block text-xs font-medium text-gray-300">Email address</label>
                <div className="relative">
                  <Mail size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" />
                  <input
                    id="reset-email"
                    type="email"
                    required
                    value={resetEmail}
                    onChange={e => { setResetEmail(e.target.value); setResetMsg('') }}
                    placeholder="you@example.com"
                    className="w-full rounded-xl border border-gray-700 bg-gray-800/60 py-3 pl-10 pr-4 text-sm text-gray-100 placeholder-gray-600 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20 transition-all duration-200"
                  />
                </div>
              </div>

              <button
                id="reset-submit-btn"
                type="submit"
                disabled={resetLoading}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-teal-500 to-teal-400 py-3 text-sm font-semibold text-gray-950 shadow-lg shadow-teal-500/20 transition-all duration-200 hover:from-teal-400 hover:to-teal-300 disabled:opacity-60"
              >
                {resetLoading ? <Loader2 size={16} className="animate-spin" /> : 'Send Reset Link'}
              </button>

              <button
                type="button"
                onClick={() => { setForgotOpen(false); setResetMsg(''); setError('') }}
                className="w-full text-center text-xs text-gray-500 hover:text-gray-300 transition-colors"
              >
                ← Back to sign in
              </button>
            </form>
          )}
        </div>

        {/* Footer */}
        <p className="mt-6 text-center text-xs text-gray-600">
          Cognitive Adaptive AI Tutor · Secure authentication via Supabase
        </p>
      </div>
    </div>
  )
}
