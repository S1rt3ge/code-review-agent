import { useState, useCallback } from 'react'
import { useApi } from '@/hooks/useApi.js'
import { useSettingsStore } from '@/store/index.js'

/**
 * @typedef {import('@/store/index.js').SettingsState} SettingsState
 */

/**
 * @typedef {Object} LlmTestResult
 * @property {boolean} claude_available
 * @property {boolean} gpt_available
 * @property {boolean} ollama_available
 */

/**
 * Hook for loading, saving, and testing user settings.
 * Combines useApi with the Zustand settings store so components stay in sync.
 *
 * @returns {{
 *   settings: SettingsState,
 *   loadSettings: () => Promise<void>,
 *   saveSettings: (data: Partial<SettingsState>) => Promise<void>,
 *   testLlm: () => Promise<LlmTestResult>,
 *   testing: boolean,
 *   testResult: LlmTestResult|null
 * }}
 */
export function useSettings() {
  const { get, post, put } = useApi()
  const settings = useSettingsStore(state => state)
  const updateSettings = useSettingsStore(state => state.updateSettings)

  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)

  /**
   * Fetch settings from the API and sync them into the store.
   * @returns {Promise<void>}
   */
  const loadSettings = useCallback(async () => {
    const data = await get('/settings')
    updateSettings(data)
  }, [get, updateSettings])

  /**
   * Persist settings via the API and sync the store on success.
   * @param {Partial<SettingsState>} data
   * @returns {Promise<void>}
   */
  const saveSettings = useCallback(
    async data => {
      const updated = await put('/settings', data)
      updateSettings(updated)
    },
    [put, updateSettings]
  )

  /**
   * Test LLM connectivity for all configured providers.
   * @returns {Promise<LlmTestResult>}
   */
  const testLlm = useCallback(async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await post('/settings/test-llm', {})
      setTestResult(result)
      return result
    } finally {
      setTesting(false)
    }
  }, [post])

  return { settings, loadSettings, saveSettings, testLlm, testing, testResult }
}
