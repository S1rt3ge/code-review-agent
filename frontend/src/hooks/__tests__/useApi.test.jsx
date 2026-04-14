import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useApi } from '../useApi.js'
import { useAuthStore } from '@/store/index.js'

describe('useApi', () => {
  beforeEach(() => {
    localStorage.clear()
    // Reset the auth store to a clean state before each test
    useAuthStore.setState({ token: null, user: null })
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('throws "Not authenticated" when token is absent', async () => {
    const { result } = renderHook(() => useApi())
    await expect(act(() => result.current.get('/test'))).rejects.toThrow('Not authenticated')
  })

  it('includes Bearer token in Authorization header', async () => {
    useAuthStore.setState({ token: 'test-token' })
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    )

    const { result } = renderHook(() => useApi())
    await act(() => result.current.get('/test'))

    expect(fetch).toHaveBeenCalledWith(
      '/api/test',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' })
      })
    )
  })

  it('returns parsed JSON on success', async () => {
    useAuthStore.setState({ token: 'tok' })
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ data: 42 }), { status: 200 })
    )

    const { result } = renderHook(() => useApi())
    const data = await act(() => result.current.get('/data'))
    expect(data).toEqual({ data: 42 })
  })

  it('returns null for 204 No Content', async () => {
    useAuthStore.setState({ token: 'tok' })
    fetch.mockResolvedValueOnce(new Response(null, { status: 204 }))

    const { result } = renderHook(() => useApi())
    const data = await act(() => result.current.del('/item/1'))
    expect(data).toBeNull()
  })

  it('throws with server detail message on error response', async () => {
    useAuthStore.setState({ token: 'tok' })
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
    )

    const { result } = renderHook(() => useApi())
    await expect(act(() => result.current.get('/missing'))).rejects.toThrow('Not found')
  })

  it('clears auth state and throws on 401 response', async () => {
    useAuthStore.setState({ token: 'expired-token', user: { id: '1', email: 'x@y.com', plan: 'free' } })
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Unauthorized' }), { status: 401 })
    )

    const { result } = renderHook(() => useApi())

    let threw = false
    await act(async () => {
      try { await result.current.get('/protected') } catch { threw = true }
    })

    expect(threw).toBe(true)
    expect(useAuthStore.getState().token).toBeNull()
    expect(useAuthStore.getState().user).toBeNull()
  })

  it('sets loading=true during request and false after', async () => {
    useAuthStore.setState({ token: 'tok' })
    let resolveRequest
    fetch.mockReturnValueOnce(
      new Promise(resolve => { resolveRequest = resolve })
    )

    const { result } = renderHook(() => useApi())
    let fetchPromise
    act(() => { fetchPromise = result.current.get('/slow') })

    expect(result.current.loading).toBe(true)

    await act(async () => {
      resolveRequest(new Response(JSON.stringify({}), { status: 200 }))
      await fetchPromise
    })

    expect(result.current.loading).toBe(false)
  })

  it('sends body as JSON for POST requests', async () => {
    useAuthStore.setState({ token: 'tok' })
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ id: '123' }), { status: 201 })
    )

    const { result } = renderHook(() => useApi())
    await act(() => result.current.post('/reviews', { title: 'test' }))

    expect(fetch).toHaveBeenCalledWith(
      '/api/reviews',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ title: 'test' })
      })
    )
  })
})
