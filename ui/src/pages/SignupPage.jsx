// ui/src/pages/SignupPage.jsx
import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { Eye, EyeOff, Loader2, BrainCircuit, Mail, Lock, User, ArrowRight, AlertCircle, CheckCircle2 } from 'lucide-react'

// ── Password strength helper ────────────────────────────────────────────────
function getStrength(pwd) {
  if (!pwd) return { score: 0, label: '', color: '' }
  let score = 0
  if (pwd.length >= 8)             score++
  if (pwd.length >= 12)            score++
  if (/[A-Z]/.test(pwd))           score++
  if (/[0-9]/.test(pwd))           score++
  if (/[^A-Za-z0-9]/.test(pwd))   score++

  if (score <= 1) return { score, label: 'Weak',   color: 'bg-red-500' }
  if (score === 2) return { score, label: 'Fair',   color: 'bg-orange-400' }
  if (score === 3) return { score, label: 'Good',   color: 'bg-yellow-400' }
  return           { score, label: 'Strong', color: 'bg-indigo-400' }
}

export default function SignupPage({ onNavigate }) {
  const { signup } = useAuth()

  const [fullName, setFullName]     = useState('')
  const [email, setEmail]           = useState('')
  const [password, setPassword]     = useState('')
  const [confirm, setConfirm]       = useState('')
  const [showPwd, setShowPwd]       = useState(false)
  const [showConf, setShowConf]     = useState(false)
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState('')
  const [success, setSuccess]       = useState(false)

  const strength = getStrength(password)

  function validateEmail(v) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim())
  }

  async function handleSignup(e) {
    e.preventDefault()
    setError('')

    if (!fullName.trim()) {
      setError('Please enter your full name.')
      return
    }
    if (!validateEmail(email)) {
      setError('Please enter a valid email address.')
      return
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)
    const result = await signup({ email: email.trim(), password, fullName: fullName.trim() })
    setLoading(false)

    if (!result.success) {
      setError(result.error || 'Signup failed. Please try again.')
      return
    }

    // Supabase may require email confirmation — show success either way
    setSuccess(true)
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#0a0a16] px-4 py-8 font-[Inter,system-ui]">

      {/* Ambient background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/2 h-[600px] w-[600px] -translate-x-1/2 rounded-full bg-indigo-500/10 blur-[120px]" />
        <div className="absolute bottom-0 left-0 h-[400px] w-[400px] rounded-full bg-purple-600/8 blur-[100px]" />
        <div
          className="absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage: 'linear-gradient(rgba(99,102,241,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.5) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        />
      </div>

      <div className="relative w-full max-w-md">
        <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-8 shadow-2xl shadow-black/60 backdrop-blur-xl">

          {/* Logo + branding */}
          <div className="mb-8 flex flex-col items-center gap-3">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-indigo-500/40 bg-indigo-500/10 shadow-[0_0_32px_rgba(99,102,241,0.25)]">
              <BrainCircuit size={32} className="text-indigo-400" />
            </div>
            <div className="text-center">
              <h1 className="text-2xl font-bold tracking-tight text-white">
                Create your account
              </h1>
              <p className="mt-1 text-sm text-gray-400">Join Cognitive AI Tutor — learn smarter</p>
            </div>
          </div>

          {/* Success state */}
          {success ? (
            <div className="flex flex-col items-center gap-4 py-4 text-center animate-[fadein_300ms_ease-out]">
              <div className="flex h-16 w-16 items-center justify-center rounded-full border border-emerald-500/40 bg-emerald-950/40">
                <CheckCircle2 size={32} className="text-emerald-400" />
              </div>
              <div>
                <p className="text-lg font-semibold text-white">Account created!</p>
                <p className="mt-1 text-sm text-gray-400">
                  Check your email to confirm your account, then sign in.
                </p>
              </div>
              <button
                onClick={() => onNavigate('login')}
                className="mt-2 flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-indigo-400 px-6 py-2.5 text-sm font-semibold text-gray-950 shadow-lg shadow-indigo-500/20 hover:from-indigo-400 hover:to-indigo-300 transition-all duration-200"
              >
                Go to Sign In <ArrowRight size={14} />
              </button>
            </div>
          ) : (
            <form onSubmit={handleSignup} className="space-y-4" noValidate>

              {/* Error banner */}
              {error && (
                <div className="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm text-red-300 animate-[fadein_250ms_ease-out]">
                  <AlertCircle size={16} className="mt-0.5 shrink-0 text-red-400" />
                  {error}
                </div>
              )}

              {/* Full Name */}
              <div className="space-y-1.5">
                <label htmlFor="signup-name" className="block text-xs font-medium text-gray-300">Full Name</label>
                <div className="relative">
                  <User size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" />
                  <input
                    id="signup-name"
                    type="text"
                    autoComplete="name"
                    required
                    value={fullName}
                    onChange={e => { setFullName(e.target.value); setError('') }}
                    placeholder="Your full name"
                    className="w-full rounded-xl border border-gray-700 bg-gray-800/60 py-3 pl-10 pr-4 text-sm text-gray-100 placeholder-gray-600 transition-all duration-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                  />
                </div>
              </div>

              {/* Email */}
              <div className="space-y-1.5">
                <label htmlFor="signup-email" className="block text-xs font-medium text-gray-300">Email address</label>
                <div className="relative">
                  <Mail size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" />
                  <input
                    id="signup-email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={e => { setEmail(e.target.value); setError('') }}
                    placeholder="you@example.com"
                    className="w-full rounded-xl border border-gray-700 bg-gray-800/60 py-3 pl-10 pr-4 text-sm text-gray-100 placeholder-gray-600 transition-all duration-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <label htmlFor="signup-password" className="block text-xs font-medium text-gray-300">Password</label>
                <div className="relative">
                  <Lock size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" />
                  <input
                    id="signup-password"
                    type={showPwd ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    value={password}
                    onChange={e => { setPassword(e.target.value); setError('') }}
                    placeholder="Min. 6 characters"
                    className="w-full rounded-xl border border-gray-700 bg-gray-800/60 py-3 pl-10 pr-12 text-sm text-gray-100 placeholder-gray-600 transition-all duration-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                  />
                  <button
                    type="button"
                    tabIndex={-1}
                    onClick={() => setShowPwd(v => !v)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>

                {/* Strength bar */}
                {password && (
                  <div className="space-y-1.5 animate-[fadein_200ms_ease-out]">
                    <div className="flex gap-1">
                      {[1, 2, 3, 4].map(n => (
                        <div
                          key={n}
                          className={`h-1 flex-1 rounded-full transition-all duration-300 ${
                            strength.score >= n ? strength.color : 'bg-gray-700'
                          }`}
                        />
                      ))}
                    </div>
                    <p className="text-[11px] text-gray-500">
                      Strength:{' '}
                      <span className={`font-semibold ${
                        strength.score <= 1 ? 'text-red-400'
                        : strength.score === 2 ? 'text-orange-400'
                        : strength.score === 3 ? 'text-yellow-400'
                        : 'text-indigo-400'
                      }`}>
                        {strength.label}
                      </span>
                    </p>
                  </div>
                )}
              </div>

              {/* Confirm Password */}
              <div className="space-y-1.5">
                <label htmlFor="signup-confirm" className="block text-xs font-medium text-gray-300">Confirm Password</label>
                <div className="relative">
                  <Lock size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" />
                  <input
                    id="signup-confirm"
                    type={showConf ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    value={confirm}
                    onChange={e => { setConfirm(e.target.value); setError('') }}
                    placeholder="Repeat your password"
                    className={`w-full rounded-xl border bg-gray-800/60 py-3 pl-10 pr-12 text-sm text-gray-100 placeholder-gray-600 transition-all duration-200 focus:outline-none focus:ring-2 ${
                      confirm && confirm !== password
                        ? 'border-red-500/60 focus:border-red-500 focus:ring-red-500/20'
                        : confirm && confirm === password
                          ? 'border-indigo-500/60 focus:border-indigo-500 focus:ring-indigo-500/20'
                          : 'border-gray-700 focus:border-indigo-500 focus:ring-indigo-500/20'
                    }`}
                  />
                  <button
                    type="button"
                    tabIndex={-1}
                    onClick={() => setShowConf(v => !v)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    {showConf ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                  {confirm && confirm === password && (
                    <CheckCircle2 size={14} className="absolute right-10 top-1/2 -translate-y-1/2 text-indigo-400 animate-[fadein_200ms_ease-out]" />
                  )}
                </div>
              </div>

              {/* Submit */}
              <button
                id="signup-submit-btn"
                type="submit"
                disabled={loading}
                className="group mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-indigo-400 py-3 text-sm font-semibold text-gray-950 shadow-lg shadow-indigo-500/20 transition-all duration-200 hover:from-indigo-400 hover:to-indigo-300 hover:shadow-indigo-500/30 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <>
                    Create Account
                    <ArrowRight size={15} className="transition-transform duration-200 group-hover:translate-x-1" />
                  </>
                )}
              </button>

              {/* Sign in link */}
              <p className="text-center text-xs text-gray-500">
                Already have an account?{' '}
                <button
                  type="button"
                  onClick={() => onNavigate('login')}
                  className="font-medium text-indigo-400 hover:text-indigo-300 transition-colors"
                >
                  Sign in
                </button>
              </p>
            </form>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-gray-600">
          Cognitive Adaptive AI Tutor · Secure authentication via Supabase
        </p>
      </div>
    </div>
  )
}
