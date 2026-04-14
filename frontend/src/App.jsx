import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Navbar } from '@/components/Navbar.jsx'
import { ProtectedRoute } from '@/components/ProtectedRoute.jsx'
import { useUiStore } from '@/store/index.js'

const Login = lazy(() => import('@/pages/Login.jsx').then(m => ({ default: m.Login })))
const Dashboard = lazy(() => import('@/pages/Dashboard.jsx').then(m => ({ default: m.Dashboard })))
const ReviewDetail = lazy(() => import('@/pages/ReviewDetail.jsx').then(m => ({ default: m.ReviewDetail })))
const Settings = lazy(() => import('@/pages/Settings.jsx').then(m => ({ default: m.Settings })))
const Repositories = lazy(() => import('@/pages/Repositories.jsx').then(m => ({ default: m.Repositories })))

/**
 * Loading fallback shown while lazy pages are being fetched.
 * @returns {React.ReactElement}
 */
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-64">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm text-gray-500 dark:text-gray-400">Loading...</span>
      </div>
    </div>
  )
}

/**
 * Root application component. Sets up routing, dark mode, and lazy-loaded pages.
 * Public route: /login. All other routes require authentication.
 *
 * @returns {React.ReactElement}
 */
export function App() {
  const darkMode = useUiStore(state => state.darkMode)

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [darkMode])

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 transition-colors duration-200">
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public */}
            <Route path="/login" element={<Login />} />

            {/* Protected — Navbar shown inside so login page stays fullscreen */}
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <Navbar />
                  <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <Suspense fallback={<PageLoader />}>
                      <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/reviews/:id" element={<ReviewDetail />} />
                        <Route path="/repositories" element={<Repositories />} />
                        <Route path="/settings" element={<Settings />} />
                        <Route path="*" element={<Navigate to="/" replace />} />
                      </Routes>
                    </Suspense>
                  </main>
                </ProtectedRoute>
              }
            />
          </Routes>
        </Suspense>
      </div>
    </BrowserRouter>
  )
}
