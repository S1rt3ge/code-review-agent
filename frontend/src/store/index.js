import { create } from 'zustand'

/**
 * @typedef {Object} SettingsState
 * @property {string} apiKeyClaude - Anthropic Claude API key
 * @property {string} apiKeyGpt - OpenAI GPT API key
 * @property {boolean} ollamaEnabled - Whether local Ollama is enabled
 * @property {string} ollamaHost - Ollama host URL
 * @property {string[]} selectedAgents - List of enabled agent names
 * @property {'auto'|'claude'|'gpt'|'local'} lmPreference - Preferred LLM provider
 * @property {function(Partial<SettingsState>): void} updateSettings - Partial state updater
 */

/**
 * Zustand store for user LLM and agent settings.
 * @type {import('zustand').UseBoundStore<import('zustand').StoreApi<SettingsState>>}
 */
export const useSettingsStore = create(set => ({
  apiKeyClaude: '',
  apiKeyGpt: '',
  ollamaEnabled: false,
  ollamaHost: 'http://localhost:11434',
  selectedAgents: ['security', 'performance', 'style'],
  lmPreference: 'auto',

  /**
   * Merge partial settings into the store.
   * @param {Partial<SettingsState>} partial
   */
  updateSettings: partial => set(prev => ({ ...prev, ...partial })),

  /**
   * Clear all stored API keys.
   */
  clearApiKeys: () => set(prev => ({ ...prev, apiKeyClaude: '', apiKeyGpt: '' }))
}))

/**
 * @typedef {Object} Toast
 * @property {string} id - Unique toast identifier
 * @property {'success'|'error'|'info'} type - Visual style variant
 * @property {string} message - Human-readable message text
 */

/**
 * @typedef {Object} UiState
 * @property {boolean} darkMode - Whether dark theme is active
 * @property {Toast[]} toasts - Active toast notifications
 * @property {function(): void} toggleDarkMode
 * @property {function(Omit<Toast, 'id'>): void} addToast
 * @property {function(string): void} removeToast
 */

/**
 * Zustand store for UI state: dark mode and toast notifications.
 * @type {import('zustand').UseBoundStore<import('zustand').StoreApi<UiState>>}
 */
export const useUiStore = create(set => ({
  darkMode: false,
  toasts: [],

  /**
   * Toggle between light and dark theme.
   */
  toggleDarkMode: () => set(prev => ({ darkMode: !prev.darkMode })),

  /**
   * Add a toast notification. Auto-assigned a random id.
   * @param {{ type: Toast['type'], message: string }} toast
   */
  addToast: ({ type, message }) =>
    set(prev => ({
      toasts: [
        ...prev.toasts,
        { id: `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`, type, message }
      ]
    })),

  /**
   * Remove a toast notification by id.
   * @param {string} id
   */
  removeToast: id =>
    set(prev => ({ toasts: prev.toasts.filter(t => t.id !== id) }))
}))
