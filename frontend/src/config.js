const trimTrailingSlash = value => value.replace(/\/$/, '')

export const API_BASE_URL = trimTrailingSlash(import.meta.env.VITE_API_BASE_URL || '/api')

const defaultWsBase = `${window.location.origin.replace(/^http/, 'ws')}/ws`
export const WS_BASE_URL = trimTrailingSlash(import.meta.env.VITE_WS_BASE_URL || defaultWsBase)

export function apiUrl(endpoint) {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  return `${API_BASE_URL}${path}`
}

export function absoluteApiUrl(endpoint) {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  if (/^https?:\/\//.test(API_BASE_URL)) return `${API_BASE_URL}${path}`
  return `${window.location.origin}${API_BASE_URL}${path}`
}
