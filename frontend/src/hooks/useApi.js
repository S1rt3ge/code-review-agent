import { useState, useCallback } from 'react'
import { useAuthStore } from '@/store/index.js'
import { apiUrl } from '@/config.js'

/**
 * Hook providing typed API methods with shared loading and error state.
 *
 * All requests include a Bearer token from localStorage and expect JSON responses.
 * On non-2xx responses, throws an Error with the server's `detail` field or a
 * fallback `HTTP <status>` message.
 *
 * @returns {{
 *   get: (endpoint: string) => Promise<any>,
 *   post: (endpoint: string, body: any) => Promise<any>,
 *   put: (endpoint: string, body: any) => Promise<any>,
 *   patch: (endpoint: string, body: any) => Promise<any>,
 *   del: (endpoint: string) => Promise<any>,
 *   loading: boolean,
 *   error: string|null
 * }}
 */
export function useApi() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const token = useAuthStore(s => s.token)
  const clearAuth = useAuthStore(s => s.clearAuth)

  /**
   * Internal request helper shared by all HTTP methods.
   * @param {string} method - HTTP method (GET, POST, PUT, DELETE)
   * @param {string} endpoint - Path relative to /api (e.g. '/reviews')
   * @param {unknown} [body] - Optional request body (will be JSON-encoded)
   * @returns {Promise<any>} Parsed JSON response
   */
  const request = useCallback(async (method, endpoint, body) => {
    setLoading(true)
    setError(null)

    try {
      if (!token) throw new Error('Not authenticated')

      /** @type {RequestInit} */
      const options = {
        method,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        }
      }

      if (body !== undefined) {
        options.body = JSON.stringify(body)
      }

      const response = await fetch(apiUrl(endpoint), options)

      if (!response.ok) {
        // Token expired or revoked — clear auth so ProtectedRoute redirects to login
        if (response.status === 401) {
          clearAuth()
        }
        let detail = `HTTP ${response.status}`
        try {
          const errorBody = await response.json()
          if (errorBody && typeof errorBody.detail === 'string') {
            detail = errorBody.detail
          }
        } catch {
          // Response body is not JSON — keep the default message
        }
        throw new Error(detail)
      }

      // 204 No Content has no body
      if (response.status === 204) {
        return null
      }

      return response.json()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [token, clearAuth])

  /**
   * HTTP GET request.
   * @param {string} endpoint
   * @returns {Promise<any>}
   */
  const get = useCallback(endpoint => request('GET', endpoint), [request])

  /**
   * HTTP POST request.
   * @param {string} endpoint
   * @param {unknown} body
   * @returns {Promise<any>}
   */
  const post = useCallback((endpoint, body) => request('POST', endpoint, body), [request])

  /**
   * HTTP PUT request.
   * @param {string} endpoint
   * @param {unknown} body
   * @returns {Promise<any>}
   */
  const put = useCallback((endpoint, body) => request('PUT', endpoint, body), [request])

  /**
   * HTTP PATCH request.
   * @param {string} endpoint
   * @param {unknown} body
   * @returns {Promise<any>}
   */
  const patch = useCallback((endpoint, body) => request('PATCH', endpoint, body), [request])

  /**
   * HTTP DELETE request.
   * @param {string} endpoint
   * @returns {Promise<any>}
   */
  const del = useCallback(endpoint => request('DELETE', endpoint), [request])

  return { get, post, put, patch, del, loading, error }
}
