import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { ForgotPassword, ResetPassword, VerifyEmail, ResendVerification } from '../AuthActions.jsx'

function renderWithRouter(node, initialEntries = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      {node}
    </MemoryRouter>
  )
}

describe('AuthActions pages', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('submits forgot password request', async () => {
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ message: 'If an account with that email exists, a password reset link has been sent.' }), { status: 200 })
    )

    renderWithRouter(<ForgotPassword />)
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'u@test.com' } })
    fireEvent.submit(screen.getByLabelText('Email').closest('form'))

    await waitFor(() => {
      expect(screen.getByText(/password reset link/i)).toBeInTheDocument()
    })
  })

  it('rejects reset when passwords do not match', async () => {
    renderWithRouter(<ResetPassword />)

    fireEvent.change(screen.getByLabelText('Reset token'), { target: { value: 'tok' } })
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'Pass1234!' } })
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'Mismatch1!' } })
    fireEvent.submit(screen.getByLabelText('Confirm password').closest('form'))

    await waitFor(() => {
      expect(screen.getByText('Passwords do not match')).toBeInTheDocument()
    })
  })

  it('prefills verify token from querystring and submits', async () => {
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ message: 'Email verified successfully.' }), { status: 200 })
    )

    renderWithRouter(<VerifyEmail />, ['/verify-email?token=abc123'])
    fireEvent.submit(screen.getByLabelText('Verification token').closest('form'))

    await waitFor(() => {
      expect(screen.getByText(/verified successfully/i)).toBeInTheDocument()
    })
  })

  it('submits resend verification request', async () => {
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ message: 'If the account exists and is unverified, a verification link has been sent.' }), { status: 200 })
    )

    renderWithRouter(<ResendVerification />)
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'u@test.com' } })
    fireEvent.submit(screen.getByLabelText('Email').closest('form'))

    await waitFor(() => {
      expect(screen.getByText(/verification link/i)).toBeInTheDocument()
    })
  })
})
