import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Login } from '../Login.jsx'
import { useAuthStore } from '@/store/index.js'

// Wrap Login in a router so useNavigate works
function renderLogin() {
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>
  )
}

function renderLoginWithRedirectState() {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/login', state: { from: { pathname: '/reviews/rev-1' } } }]}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/reviews/rev-1" element={<div>Review detail route</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('Login page', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({ token: null, user: null })
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  // --- Tab switching ---

  it('renders login form by default (email + password, no confirm)', () => {
    renderLogin()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.queryByLabelText('Confirm Password')).not.toBeInTheDocument()
    expect(screen.getByText('Forgot password?')).toBeInTheDocument()
  })

  it('switches to register form when "Create account" tab is clicked', () => {
    renderLogin()
    // First button with this name is the tab (tab comes before submit)
    fireEvent.click(screen.getAllByRole('button', { name: 'Create account' })[0])
    expect(screen.getByLabelText('Confirm Password')).toBeInTheDocument()
  })

  it('switches back to login form when "Sign in" tab is clicked', () => {
    renderLogin()
    fireEvent.click(screen.getAllByRole('button', { name: 'Create account' })[0])
    // First "Sign in" button is the tab
    fireEvent.click(screen.getAllByRole('button', { name: 'Sign in' })[0])
    expect(screen.queryByLabelText('Confirm Password')).not.toBeInTheDocument()
  })

  // --- Register form validation (no API call needed) ---

  it('shows error when passwords do not match', async () => {
    renderLogin()
    // Click the tab (first "Create account" button)
    fireEvent.click(screen.getAllByRole('button', { name: 'Create account' })[0])

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a@b.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Abcdef12' } })
    fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: 'different' } })
    // Submit the form (last "Create account" button is the submit button)
    fireEvent.submit(screen.getByLabelText('Confirm Password').closest('form'))

    await waitFor(() => {
      expect(screen.getByText('Passwords do not match')).toBeInTheDocument()
    })
  })

  it('shows error when password is too short', async () => {
    renderLogin()
    fireEvent.click(screen.getAllByRole('button', { name: 'Create account' })[0])

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a@b.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'short' } })
    fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: 'short' } })
    fireEvent.submit(screen.getByLabelText('Confirm Password').closest('form'))

    await waitFor(() => {
      expect(screen.getByText('Password must be at least 8 characters')).toBeInTheDocument()
    })
  })

  // --- Login form: API error ---

  it('shows error message on failed login', async () => {
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Invalid email or password' }), { status: 401 })
    )

    renderLogin()
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'bad@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrongpass' } })
    fireEvent.submit(screen.getByLabelText('Email').closest('form'))

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password')).toBeInTheDocument()
    })
  })

  it('calls setAuth and shows loading state during successful login', async () => {
    fetch
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: 'tok-123' }), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 'u1', email: 'a@b.com', plan: 'free' }), { status: 200 })
      )

    renderLogin()
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a@b.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'MyPass123!' } })
    fireEvent.submit(screen.getByLabelText('Email').closest('form'))

    // Button goes into loading state
    expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled()

    await waitFor(() => {
      expect(useAuthStore.getState().token).toBe('tok-123')
    })
  })

  it('redirects back to intended route after successful login', async () => {
    fetch
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: 'tok-123' }), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 'u1', email: 'a@b.com', plan: 'free' }), { status: 200 })
      )

    renderLoginWithRedirectState()
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a@b.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'MyPass123!' } })
    fireEvent.submit(screen.getByLabelText('Email').closest('form'))

    await waitFor(() => {
      expect(screen.getByText('Review detail route')).toBeInTheDocument()
    })
  })

  it('shows verification required message when login blocked by unverified email', async () => {
    fetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ detail: 'Email is not verified. Check your inbox or request a new verification link.' }),
        { status: 403 }
      )
    )

    renderLogin()
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'u@test.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'MyPass123!' } })
    fireEvent.submit(screen.getByLabelText('Email').closest('form'))

    await waitFor(() => {
      expect(screen.getByText(/email is not verified/i)).toBeInTheDocument()
    })
  })

  it('register flow does not auto-login and shows success prompt', async () => {
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ access_token: 'tok-123', email: 'new@test.com', username: 'new' }), { status: 201 })
    )

    renderLogin()
    fireEvent.click(screen.getAllByRole('button', { name: 'Create account' })[0])
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'new@test.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'MyPass123!' } })
    fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: 'MyPass123!' } })
    fireEvent.submit(screen.getByLabelText('Confirm Password').closest('form'))

    await waitFor(() => {
      expect(screen.getByText(/account created/i)).toBeInTheDocument()
      expect(useAuthStore.getState().token).toBeNull()
    })
  })
})
