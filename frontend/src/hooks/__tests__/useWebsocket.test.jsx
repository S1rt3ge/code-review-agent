import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useWebsocket } from '../useWebsocket.js'
import { useAuthStore } from '@/store/index.js'

class MockWebSocket {
  static instances = []

  constructor(url) {
    this.url = url
    this.close = vi.fn(() => {
      this.onclose?.()
    })
    MockWebSocket.instances.push(this)
    setTimeout(() => this.onopen?.(), 0)
  }
}

describe('useWebsocket', () => {
  beforeEach(() => {
    localStorage.clear()
    MockWebSocket.instances = []
    useAuthStore.setState({ token: 'jwt-token', user: null })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ticket: 'ws-ticket' }), { status: 200 })
    ))
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests a short-lived ticket and does not put JWT in websocket URL', async () => {
    const { result } = renderHook(() => useWebsocket('review-1'))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/reviews/review-1/ws-ticket',
        expect.objectContaining({
          method: 'POST',
          headers: { Authorization: 'Bearer jwt-token' },
        })
      )
      expect(MockWebSocket.instances[0].url).toContain('ticket=ws-ticket')
      expect(MockWebSocket.instances[0].url).not.toContain('jwt-token')
      expect(result.current.isConnected).toBe(true)
    })
  })

  it('surfaces malformed websocket messages', async () => {
    const { result } = renderHook(() => useWebsocket('review-1'))

    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1))
    MockWebSocket.instances[0].onmessage({ data: 'not-json' })

    await waitFor(() => {
      expect(result.current.wsError).toBe('Received malformed WebSocket message')
    })
  })
})
