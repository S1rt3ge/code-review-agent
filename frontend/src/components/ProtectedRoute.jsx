import { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/index.js'

/**
 * Decode a JWT and return the payload, or null if invalid.
 * Does NOT verify the signature — that is the server's job.
 * Used only to check the `exp` claim client-side to avoid a stale-token flash.
 * @param {string} token
 * @returns {Record<string, unknown>|null}
 */
function decodeJwt(token) {
  try {
    const payload = token.split('.')[1]
    return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
  } catch {
    return null
  }
}

/**
 * Wraps a route element so only authenticated users can access it.
 * Unauthenticated or expired-token users are redirected to /login,
 * with the intended path saved in location state so Login can redirect back.
 *
 * @param {{ children: React.ReactNode }} props
 * @returns {React.ReactElement}
 */
export function ProtectedRoute({ children }) {
  const token = useAuthStore(s => s.token)
  const clearAuth = useAuthStore(s => s.clearAuth)
  const location = useLocation()

  // Proactively clear expired tokens so we don't briefly show protected UI.
  const payload = token ? decodeJwt(token) : null
  const expiresAt = Number(payload?.exp || 0) * 1000
  const tokenInvalid = Boolean(token) && (!payload || !expiresAt || expiresAt < Date.now())

  useEffect(() => {
    if (token && tokenInvalid) clearAuth()
  }, [clearAuth, token, tokenInvalid])

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (tokenInvalid) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
