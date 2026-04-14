import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/index.js'

/**
 * Wraps a route element so only authenticated users can access it.
 * Unauthenticated users are redirected to /login, with the intended
 * path saved in location state so Login can redirect back after auth.
 *
 * @param {{ children: React.ReactNode }} props
 * @returns {React.ReactElement}
 */
export function ProtectedRoute({ children }) {
  const token = useAuthStore(s => s.token)
  const location = useLocation()

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
