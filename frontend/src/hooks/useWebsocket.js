import { useState, useEffect, useCallback } from 'react'

const WS_BASE_URL = window.location.origin.replace(/^http/, 'ws')

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
 *   isConnected: boolean
 * }}
 */
export function useWebsocket(reviewId) {
  /** @type {[Object.<string, AgentStatusValue>, function]} */
  const [agentStatuses, setAgentStatuses] = useState({})
  const [isConnected, setIsConnected] = useState(false)

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
      // Ignore malformed messages
    }
  }, [])

  useEffect(() => {
    if (!reviewId) {
      setAgentStatuses({})
      setIsConnected(false)
      return
    }

    const token = localStorage.getItem('token')
    const url = token
      ? `${WS_BASE_URL}/ws/progress/${reviewId}?token=${encodeURIComponent(token)}`
      : `${WS_BASE_URL}/ws/progress/${reviewId}`

    const ws = new WebSocket(url)

    ws.onopen = () => {
      setIsConnected(true)
    }

    ws.onmessage = handleMessage

    ws.onerror = () => {
      setIsConnected(false)
    }

    ws.onclose = () => {
      setIsConnected(false)
    }

    return () => {
      ws.close()
    }
  }, [reviewId, handleMessage])

  return { agentStatuses, isConnected }
}
