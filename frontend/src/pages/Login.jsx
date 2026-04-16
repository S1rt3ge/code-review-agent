import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/index.js'

const API_BASE = '/api'

/**
 * POST to the API without an auth token (used for login/register).
 * @param {string} endpoint
 * @param {Object} body
 * @returns {Promise<any>}
 */
async function publicPost(endpoint, body) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const err = await res.json()
      if (err?.detail) detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail)
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json()
}

/**
 * Reusable labeled text input.
 * @param {{ id: string, label: string, type?: string, value: string, onChange: (v: string) => void, placeholder?: string, autoComplete?: string }} props
 * @returns {React.ReactElement}
 */
function Field({ id, label, type = 'text', value, onChange, placeholder, autoComplete }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required
        className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  )
}

/**
 * Login form. POSTs to /auth/token (OAuth2 form-encoded) and stores the JWT.
 * @param {{ onSuccess: () => void }} props
 * @returns {React.ReactElement}
 */
function LoginForm({ onSuccess }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const setAuth = useAuthStore(s => s.setAuth)

  const handleSubmit = useCallback(async e => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      // /auth/token uses OAuth2 form encoding
      const res = await fetch(`${API_BASE}/auth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email, password }),
      })
      if (!res.ok) {
        let detail = `HTTP ${res.status}`
        try {
          const err = await res.json()
          if (err?.detail) detail = typeof err.detail === 'string' ? err.detail : 'Invalid credentials'
        } catch { /* ignore */ }
        throw new Error(detail)
      }
      const data = await res.json()
      const token = data.access_token

      // Fetch current user info
      const meRes = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const user = meRes.ok ? await meRes.json() : { id: '', email, plan: 'free' }

      setAuth(token, user)
      onSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }, [email, password, setAuth, onSuccess])

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Field
        id="login-email"
        label="Email"
        type="email"
        value={email}
        onChange={setEmail}
        placeholder="you@example.com"
        autoComplete="email"
      />
      <Field
        id="login-password"
        label="Password"
        type="password"
        value={password}
        onChange={setPassword}
        placeholder="••••••••"
        autoComplete="current-password"
      />
      {error && (
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      )}
      <div className="text-right">
        <a href="/forgot-password" className="text-xs text-blue-600 dark:text-blue-400 hover:underline">
          Forgot password?
        </a>
      </div>
      <button
        type="submit"
        disabled={loading}
        className="w-full py-2 px-4 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  )
}

/**
 * Register form. Creates account and prompts for email verification.
 * @param {{ onRegistered: () => void }} props
 * @returns {React.ReactElement}
 */
function RegisterForm({ onRegistered }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [success, setSuccess] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = useCallback(async e => {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    setLoading(true)
    try {
      await publicPost('/auth/register', { email, password })
      setSuccess('Account created. Check your email for a verification link before signing in.')
      setPassword('')
      setConfirm('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }, [email, password, confirm])

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Field
        id="reg-email"
        label="Email"
        type="email"
        value={email}
        onChange={setEmail}
        placeholder="you@example.com"
        autoComplete="email"
      />
      <Field
        id="reg-password"
        label="Password"
        type="password"
        value={password}
        onChange={setPassword}
        placeholder="Min 8 characters"
        autoComplete="new-password"
      />
      <Field
        id="reg-confirm"
        label="Confirm Password"
        type="password"
        value={confirm}
        onChange={setConfirm}
        placeholder="Repeat password"
        autoComplete="new-password"
      />
      {error && (
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      )}
      {success && (
        <p className="text-sm text-green-700 dark:text-green-400">{success}</p>
      )}
      <p className="text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-900 rounded-md px-3 py-2">
        After registration, check your email to verify your account.
      </p>
      {success && (
        <button
          type="button"
          onClick={onRegistered}
          className="w-full py-2 px-4 text-sm font-medium rounded-lg border border-blue-300 text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/30"
        >
          Go to sign in
        </button>
      )}
      <button
        type="submit"
        disabled={loading}
        className="w-full py-2 px-4 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? 'Creating account…' : 'Create account'}
      </button>
    </form>
  )
}

/**
 * Full-page login/register screen shown to unauthenticated users.
 * Switches between Login and Register tabs.
 *
 * @returns {React.ReactElement}
 */
export function Login() {
  const navigate = useNavigate()
  const [tab, setTab] = useState(/** @type {'login'|'register'} */ ('login'))

  const handleSuccess = useCallback(() => {
    navigate('/', { replace: true })
  }, [navigate])

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Brand header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Code Review Agent</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            AI-powered PR reviews in seconds
          </p>
        </div>

        {/* Card */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-gray-200 dark:border-gray-700">
            {/** @type {Array<{id: 'login'|'register', label: string}>} */
              [{ id: 'login', label: 'Sign in' }, { id: 'register', label: 'Create account' }].map(t => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTab(t.id)}
                  className={`flex-1 py-3 text-sm font-medium transition-colors ${
                    tab === t.id
                      ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 -mb-px bg-white dark:bg-gray-800'
                      : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 bg-gray-50 dark:bg-gray-900'
                  }`}
                >
                  {t.label}
                </button>
              ))
            }
          </div>

          {/* Form body */}
          <div className="p-6">
            {tab === 'login'
              ? <LoginForm onSuccess={handleSuccess} />
              : <RegisterForm onRegistered={() => setTab('login')} />}
          </div>
        </div>
      </div>
    </div>
  )
}
