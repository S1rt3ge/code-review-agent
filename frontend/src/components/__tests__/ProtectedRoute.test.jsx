import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, beforeEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from '../ProtectedRoute.jsx'
import { useAuthStore } from '@/store/index.js'

function renderProtected() {
  return render(
    <MemoryRouter initialEntries={['/private']}>
      <Routes>
        <Route path="/login" element={<div>Login route</div>} />
        <Route
          path="/private"
          element={(
            <ProtectedRoute>
              <div>Private route</div>
            </ProtectedRoute>
          )}
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({ token: null, user: null })
  })

  it('redirects and clears malformed tokens', async () => {
    localStorage.setItem('token', 'not-a-jwt')
    useAuthStore.setState({ token: 'not-a-jwt', user: null })

    renderProtected()

    await waitFor(() => {
      expect(screen.getByText('Login route')).toBeInTheDocument()
      expect(useAuthStore.getState().token).toBeNull()
    })
  })
})
