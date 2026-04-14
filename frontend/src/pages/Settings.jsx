import { useState, useEffect, useCallback } from 'react'
import { useApi } from '@/hooks/useApi.js'
import { LLMSelector } from '@/components/LLMSelector.jsx'

/**
 * @typedef {Object} Settings
 * @property {string} plan
 * @property {boolean} api_key_claude_set
 * @property {boolean} api_key_gpt_set
 * @property {boolean} ollama_enabled
 * @property {string|null} ollama_host
 * @property {string[]} default_agents
 * @property {string} lm_preference
 */

/**
 * @typedef {Object} TestResult
 * @property {boolean} claude_available
 * @property {boolean} gpt_available
 * @property {boolean} ollama_available
 */

const ALL_AGENTS = [
  { id: 'security', label: 'Security', description: 'SQL injection, XSS, hardcoded secrets' },
  { id: 'performance', label: 'Performance', description: 'N+1 queries, O(n²) loops, memory leaks' },
  { id: 'style', label: 'Style', description: 'Naming, line length, missing docstrings' },
  { id: 'logic', label: 'Logic', description: 'Off-by-one, null checks, type mismatches' },
]

/**
 * Password-style input with show/hide toggle and set-indicator.
 *
 * @param {{
 *   id: string,
 *   label: string,
 *   value: string,
 *   onChange: (v: string) => void,
 *   placeholder?: string,
 *   isSet?: boolean
 * }} props
 * @returns {React.ReactElement}
 */
function ApiKeyInput({ id, label, value, onChange, placeholder, isSet }) {
  const [visible, setVisible] = useState(false)

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        {label}
        {isSet && !value && (
          <span className="ml-2 text-xs text-green-600 dark:text-green-400 font-normal">● set</span>
        )}
      </label>
      <div className="relative">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={isSet ? '••••••••  (leave blank to keep current)' : placeholder}
          className="w-full pr-10 px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="button"
          onClick={() => setVisible(v => !v)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          aria-label={visible ? 'Hide key' : 'Show key'}
        >
          {visible ? (
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10 3C5 3 1.73 7.11 1 10c.73 2.89 4 7 9 7s8.27-4.11 9-7c-.73-2.89-4-7-9-7zm0 12a5 5 0 110-10 5 5 0 010 10zm0-8a3 3 0 100 6 3 3 0 000-6z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M3.707 2.293a1 1 0 00-1.414 1.414l14 14a1 1 0 001.414-1.414l-1.473-1.473A10.014 10.014 0 0019.542 10C18.268 5.943 14.478 3 10 3a9.958 9.958 0 00-4.512 1.074l-1.78-1.781zm4.261 4.26l1.514 1.515a2.003 2.003 0 012.45 2.45l1.514 1.514a4 4 0 00-5.478-5.478zM9.613 9.07a2 2 0 00-.07.43v.002a2 2 0 002 2h.002a2 2 0 00.43-.07L9.613 9.07z" clipRule="evenodd" />
              <path d="M12.454 16.697L9.75 13.992a4 4 0 01-3.742-3.741L2.335 6.578A9.98 9.98 0 00.458 10c1.274 4.057 5.065 7 9.542 7 .847 0 1.669-.105 2.454-.303z" />
            </svg>
          )}
        </button>
      </div>
    </div>
  )
}

/**
 * Availability dot indicator used in the test results panel.
 * @param {{ available: boolean, label: string }} props
 * @returns {React.ReactElement}
 */
function AvailabilityRow({ available, label }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`w-2.5 h-2.5 rounded-full ${available ? 'bg-green-500' : 'bg-red-400'}`} />
      <span className="text-gray-700 dark:text-gray-300">{label}</span>
      <span className={`ml-auto text-xs font-medium ${available ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
        {available ? 'Available' : 'Not available'}
      </span>
    </div>
  )
}

/**
 * Settings page — configure LLM providers, API keys, agents, and Ollama.
 *
 * @returns {React.ReactElement}
 */
export function Settings() {
  const { get, put, post, loading } = useApi()

  /** @type {[Settings|null, function]} */
  const [settings, setSettings] = useState(null)
  const [fetchError, setFetchError] = useState(null)

  // Form state (only populated values are sent)
  const [apiKeyClaude, setApiKeyClaude] = useState('')
  const [apiKeyGpt, setApiKeyGpt] = useState('')
  const [ollamaEnabled, setOllamaEnabled] = useState(false)
  const [ollamaHost, setOllamaHost] = useState('http://localhost:11434')
  const [selectedAgents, setSelectedAgents] = useState(['security', 'performance', 'style', 'logic'])
  const [lmPreference, setLmPreference] = useState('auto')

  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState(null)

  /** @type {[TestResult|null, function]} */
  const [testResult, setTestResult] = useState(null)
  const [testing, setTesting] = useState(false)

  const loadSettings = useCallback(async () => {
    setFetchError(null)
    try {
      /** @type {Settings} */
      const data = await get('/settings')
      setSettings(data)
      setOllamaEnabled(data.ollama_enabled)
      setOllamaHost(data.ollama_host ?? 'http://localhost:11434')
      setSelectedAgents(data.default_agents ?? ['security', 'performance', 'style', 'logic'])
      setLmPreference(data.lm_preference ?? 'auto')
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : 'Failed to load settings')
    }
  }, [get])

  useEffect(() => {
    loadSettings()
  }, [loadSettings])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setSaveMsg(null)
    try {
      const payload = {
        ollama_enabled: ollamaEnabled,
        ollama_host: ollamaHost || null,
        default_agents: selectedAgents,
        lm_preference: lmPreference,
      }
      if (apiKeyClaude) payload.api_key_claude = apiKeyClaude
      if (apiKeyGpt) payload.api_key_gpt = apiKeyGpt

      const updated = await put('/settings', payload)
      setSettings(updated)
      setApiKeyClaude('')
      setApiKeyGpt('')
      setSaveMsg('Settings saved successfully.')
    } catch (err) {
      setSaveMsg(`Failed to save: ${err instanceof Error ? err.message : 'unknown error'}`)
    } finally {
      setSaving(false)
    }
  }, [put, apiKeyClaude, apiKeyGpt, ollamaEnabled, ollamaHost, selectedAgents, lmPreference])

  const handleTestLlm = useCallback(async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await post('/settings/test-llm', {})
      setTestResult(result)
    } catch (err) {
      setTestResult({ error: err instanceof Error ? err.message : 'Test failed' })
    } finally {
      setTesting(false)
    }
  }, [post])

  /**
   * Toggle an agent in the selectedAgents list.
   * @param {string} agentId
   */
  const toggleAgent = useCallback(agentId => {
    setSelectedAgents(prev =>
      prev.includes(agentId) ? prev.filter(a => a !== agentId) : [...prev, agentId]
    )
  }, [])

  if (loading && !settings) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-6 text-sm text-red-700 dark:text-red-400">
        {fetchError}
      </div>
    )
  }

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Settings</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Configure LLM providers, API keys, and default agents.
        </p>
      </div>

      {/* API Keys */}
      <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 space-y-4">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200">API Keys</h2>
        <ApiKeyInput
          id="api-key-claude"
          label="Anthropic Claude"
          value={apiKeyClaude}
          onChange={setApiKeyClaude}
          placeholder="sk-ant-..."
          isSet={settings?.api_key_claude_set}
        />
        <ApiKeyInput
          id="api-key-gpt"
          label="OpenAI GPT"
          value={apiKeyGpt}
          onChange={setApiKeyGpt}
          placeholder="sk-..."
          isSet={settings?.api_key_gpt_set}
        />
      </section>

      {/* LLM Provider preference */}
      <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200 mb-4">LLM Provider</h2>
        <LLMSelector value={lmPreference} onChange={setLmPreference} />
      </section>

      {/* Ollama */}
      <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200">Local Ollama</h2>
          <button
            type="button"
            role="switch"
            aria-checked={ollamaEnabled}
            onClick={() => setOllamaEnabled(v => !v)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
              ollamaEnabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                ollamaEnabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
        {ollamaEnabled && (
          <div>
            <label htmlFor="ollama-host" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Ollama Host URL
            </label>
            <input
              id="ollama-host"
              type="text"
              value={ollamaHost}
              onChange={e => setOllamaHost(e.target.value)}
              placeholder="http://localhost:11434"
              className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        )}
      </section>

      {/* Default agents */}
      <section className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200 mb-4">Default Agents</h2>
        <div className="space-y-2">
          {ALL_AGENTS.map(agent => {
            const checked = selectedAgents.includes(agent.id)
            return (
              <label
                key={agent.id}
                className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  checked
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-950 dark:border-blue-400'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleAgent(agent.id)}
                  className="mt-0.5 accent-blue-500"
                />
                <div className="flex flex-col min-w-0">
                  <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
                    {agent.label}
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {agent.description}
                  </span>
                </div>
              </label>
            )
          })}
        </div>
      </section>

      {/* Save + test */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="px-5 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? 'Saving…' : 'Save Settings'}
        </button>
        <button
          type="button"
          onClick={handleTestLlm}
          disabled={testing}
          className="px-5 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {testing ? 'Testing…' : 'Test LLM Connection'}
        </button>
      </div>

      {/* Save feedback */}
      {saveMsg && (
        <div className={`rounded-lg px-4 py-3 text-sm ${
          saveMsg.startsWith('Failed')
            ? 'bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800'
            : 'bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800'
        }`}>
          {saveMsg}
        </div>
      )}

      {/* LLM test results */}
      {testResult && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-2">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
            Connection Test Results
          </h3>
          {testResult.error ? (
            <p className="text-sm text-red-600 dark:text-red-400">{testResult.error}</p>
          ) : (
            <>
              <AvailabilityRow available={testResult.claude_available} label="Claude (Anthropic)" />
              <AvailabilityRow available={testResult.gpt_available} label="GPT (OpenAI)" />
              <AvailabilityRow available={testResult.ollama_available} label="Ollama (Local)" />
            </>
          )}
        </div>
      )}
    </div>
  )
}
