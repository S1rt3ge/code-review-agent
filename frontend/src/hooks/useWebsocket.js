import { useState, useEffect, useCallback } from 'react'
import { apiUrl, WS_BASE_URL } from '@/config.js'
import { useAuthStore } from '@/store/index.js'

const MAX_RECONNECT_ATTEMPTS = 5

/**
 * @typedef {'pending'|'running'|'done'|'error'} AgentStatusValue
 */

/**
 * @typedef {Object} WsProgressMessage
 * @property {string} agent_name - The agent that sent this update
 * @property {AgentStatusValue} status - Current status of that agent
 */

/**
 * Connect to the backend WebSocket for real-time review progress.
 * Automatically reconnects when reviewId changes and cleans up on unmount.
 *
 * @param {string|null} reviewId - The review to subscribe to, or null to disconnect
 * @returns {{
 *   agentStatuses: Object.<string, AgentStatusValue>,
 *   isConnected: boolean,
 *   wsError: string|null
 * }}
 */
export function useWebsocket(reviewId) {
  /** @type {[Object.<string, AgentStatusValue>, function]} */
  const [agentStatuses, setAgentStatuses] = useState({})
  const [isConnected, setIsConnected] = useState(false)
  const [wsError, setWsError] = useState(null)
  const token = useAuthStore(s => s.token)

  /**
   * Parse an incoming WebSocket message and update agent status map.
   * @param {MessageEvent} event
   */
  const handleMessage = useCallback(event => {
    try {
      /** @type {WsProgressMessage} */
      const data = JSON.parse(event.data)
      if (data.agent_name && data.status) {
        setAgentStatuses(prev => ({
          ...prev,
          [data.agent_name]: data.status
        }))
      }
    } catch {
      setWsError('Received malformed WebSocket message')
    }
  }, [])

  useEffect(() => {
    if (!reviewId || !token) {
      setAgentStatuses({})
      setIsConnected(false)
      setWsError(null)
      return
    }

    let ws = null
    let cancelled = false
    let reconnectTimer = null
    let attempts = 0

    const scheduleReconnect = () => {
      if (cancelled || attempts >= MAX_RECONNECT_ATTEMPTS) return
      const delay = Math.min(1000 * (2 ** attempts), 10000)
      attempts += 1
      reconnectTimer = window.setTimeout(connect, delay)
    }

    const connect = async () => {
      try {
        setWsError(null)
        const ticketResponse = await fetch(apiUrl(`/reviews/${reviewId}/ws-ticket`), {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!ticketResponse.ok) throw new Error(`Ticket request failed (${ticketResponse.status})`)
        const { ticket } = await ticketResponse.json()
        if (cancelled) return

        const url = `${WS_BASE_URL}/progress/${encodeURIComponent(reviewId)}?ticket=${encodeURIComponent(ticket)}`
        ws = new WebSocket(url)

        ws.onopen = () => {
          attempts = 0
          setIsConnected(true)
          setWsError(null)
        }

        ws.onmessage = handleMessage

        ws.onerror = () => {
          setIsConnected(false)
          setWsError('WebSocket connection error')
        }

        ws.onclose = () => {
          setIsConnected(false)
          scheduleReconnect()
        }
      } catch (err) {
        setIsConnected(false)
        setWsError(err instanceof Error ? err.message : 'WebSocket connection failed')
        scheduleReconnect()
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      if (ws) ws.close()
    }
  }, [reviewId, token, handleMessage])

  return { agentStatuses, isConnected, wsError }
}
