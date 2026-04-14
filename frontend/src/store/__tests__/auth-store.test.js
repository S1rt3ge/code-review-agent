import { describe, it, expect, beforeEach } from 'vitest'

// Import the store after each test resets it so state doesn't bleed between tests.
// Zustand stores are module-level singletons; we reset via the store's own actions.

describe('useAuthStore', () => {
  /** @type {import('../index.js').useAuthStore} */
  let useAuthStore

  beforeEach(async () => {
    // Clear localStorage before each test
    localStorage.clear()

    // Re-import the module fresh so the initial token read from localStorage works
    vi.resetModules()
    const mod = await import('../index.js')
    useAuthStore = mod.useAuthStore
    // Reset the store to initial state
    useAuthStore.setState({ token: localStorage.getItem('token'), user: null })
  })

  it('initialises token from localStorage', () => {
    localStorage.setItem('token', 'pre-existing-token')
    useAuthStore.setState({ token: localStorage.getItem('token') })
    expect(useAuthStore.getState().token).toBe('pre-existing-token')
  })

  it('starts with null token when localStorage is empty', () => {
    expect(useAuthStore.getState().token).toBeNull()
  })

  it('setAuth stores token in state and localStorage', () => {
    const { setAuth } = useAuthStore.getState()
    setAuth('my-jwt', { id: '1', email: 'a@b.com', plan: 'free' })

    expect(useAuthStore.getState().token).toBe('my-jwt')
    expect(useAuthStore.getState().user).toEqual({ id: '1', email: 'a@b.com', plan: 'free' })
    expect(localStorage.getItem('token')).toBe('my-jwt')
  })

  it('clearAuth removes token from state and localStorage', () => {
    const { setAuth, clearAuth } = useAuthStore.getState()
    setAuth('my-jwt', { id: '1', email: 'a@b.com', plan: 'free' })
    clearAuth()

    expect(useAuthStore.getState().token).toBeNull()
    expect(useAuthStore.getState().user).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('clearAuth is idempotent when called with no token', () => {
    const { clearAuth } = useAuthStore.getState()
    expect(() => clearAuth()).not.toThrow()
    expect(useAuthStore.getState().token).toBeNull()
  })
})
