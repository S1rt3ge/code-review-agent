import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiUrl } from '@/config.js'

async function publicPost(endpoint, body) {
  const res = await fetch(apiUrl(endpoint), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const err = await res.json()
      if (err?.detail) detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail)
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return res.json()
}

function AuthCard({ title, subtitle, children }) {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{title}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{subtitle}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm p-6 space-y-4">
          {children}
        </div>
      </div>
    </div>
  )
}

export function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async e => {
    e.preventDefault()
    setLoading(true)
    setMessage(null)
    setError(null)
    try {
      const res = await publicPost('/auth/password-reset/request', { email })
      setMessage(res.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthCard title="Forgot password" subtitle="We will send you a secure reset link.">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="fp-email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
          <input
            id="fp-email"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        {message && <p className="text-sm text-green-700 dark:text-green-400">{message}</p>}
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 px-4 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Sending…' : 'Send reset link'}
        </button>
      </form>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Remembered it? <Link to="/login" className="text-blue-600 dark:text-blue-400 hover:underline">Back to sign in</Link>
      </p>
    </AuthCard>
  )
}

export function ResetPassword() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const tokenFromUrl = useMemo(() => searchParams.get('token') || '', [searchParams])
  const [token, setToken] = useState(tokenFromUrl)
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (tokenFromUrl) navigate('/reset-password', { replace: true })
  }, [navigate, tokenFromUrl])

  const handleSubmit = async e => {
    e.preventDefault()
    setLoading(true)
    setMessage(null)
    setError(null)
    if (newPassword.length < 8) {
      setLoading(false)
      setError('Password must be at least 8 characters')
      return
    }
    if (newPassword !== confirm) {
      setLoading(false)
      setError('Passwords do not match')
      return
    }
    try {
      const res = await publicPost('/auth/password-reset/confirm', {
        token,
        new_password: newPassword,
      })
      setMessage(res.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reset failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthCard title="Set new password" subtitle="Use the token from your email to complete reset.">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="rp-token" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Reset token</label>
          <input
            id="rp-token"
            type="text"
            value={token}
            onChange={e => setToken(e.target.value)}
            required
            className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label htmlFor="rp-pass" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">New password</label>
          <input
            id="rp-pass"
            type="password"
            value={newPassword}
            onChange={e => setNewPassword(e.target.value)}
            required
            className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label htmlFor="rp-confirm" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Confirm password</label>
          <input
            id="rp-confirm"
            type="password"
            value={confirm}
            onChange={e => setConfirm(e.target.value)}
            required
            className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        {message && <p className="text-sm text-green-700 dark:text-green-400">{message}</p>}
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 px-4 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Updating…' : 'Reset password'}
        </button>
      </form>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Back to <Link to="/login" className="text-blue-600 dark:text-blue-400 hover:underline">sign in</Link>
      </p>
    </AuthCard>
  )
}

export function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const tokenFromUrl = useMemo(() => searchParams.get('token') || '', [searchParams])
  const [token, setToken] = useState(tokenFromUrl)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (tokenFromUrl) navigate('/verify-email', { replace: true })
  }, [navigate, tokenFromUrl])

  const handleSubmit = async e => {
    e.preventDefault()
    setLoading(true)
    setMessage(null)
    setError(null)
    try {
      const res = await publicPost('/auth/email-verification/confirm', { token })
      setMessage(res.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthCard title="Verify email" subtitle="Confirm your account email with the token from message.">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="ve-token" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Verification token</label>
          <input
            id="ve-token"
            type="text"
            value={token}
            onChange={e => setToken(e.target.value)}
            required
            className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        {message && <p className="text-sm text-green-700 dark:text-green-400">{message}</p>}
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 px-4 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Verifying…' : 'Verify email'}
        </button>
      </form>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Need another link? <Link to="/resend-verification" className="text-blue-600 dark:text-blue-400 hover:underline">Resend verification</Link>
      </p>
    </AuthCard>
  )
}

export function ResendVerification() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async e => {
    e.preventDefault()
    setLoading(true)
    setMessage(null)
    setError(null)
    try {
      const res = await publicPost('/auth/email-verification/request', { email })
      setMessage(res.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthCard title="Resend verification" subtitle="Send a fresh email verification link.">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="rv-email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
          <input
            id="rv-email"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        {message && <p className="text-sm text-green-700 dark:text-green-400">{message}</p>}
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 px-4 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Sending…' : 'Resend verification'}
        </button>
      </form>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Back to <Link to="/login" className="text-blue-600 dark:text-blue-400 hover:underline">sign in</Link>
      </p>
    </AuthCard>
  )
}
