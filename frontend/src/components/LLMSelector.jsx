/**
 * @typedef {'auto'|'claude'|'gpt'|'local'} LlmPreference
 */

/**
 * @typedef {Object} LlmOption
 * @property {LlmPreference} value
 * @property {string} label
 * @property {string} description
 */

/** @type {LlmOption[]} */
const LLM_OPTIONS = [
  {
    value: 'auto',
    label: 'Auto',
    description: 'Prefer configured providers automatically, including local Ollama'
  },
  {
    value: 'local',
    label: 'Local (Ollama)',
    description: 'Free local models via Ollama — recommended for self-hosted demos'
  },
  {
    value: 'claude',
    label: 'Claude BYOK',
    description: 'Use your own Anthropic key for higher-accuracy hosted reviews'
  },
  {
    value: 'gpt',
    label: 'OpenAI BYOK',
    description: 'Use your own OpenAI key as a hosted fallback provider'
  }
]

/**
 * Radio group for selecting the preferred LLM provider.
 *
 * @param {{ value: LlmPreference, onChange: (value: LlmPreference) => void }} props
 * @returns {React.ReactElement}
 */
export function LLMSelector({ value, onChange }) {
  return (
    <fieldset>
      <legend className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
        LLM Provider
      </legend>
      <div className="space-y-2">
        {LLM_OPTIONS.map(option => {
          const isSelected = value === option.value
          return (
            <label
              key={option.value}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                isSelected
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-950 dark:border-blue-400'
                  : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
              }`}
            >
              <input
                type="radio"
                name="llm-preference"
                value={option.value}
                checked={isSelected}
                onChange={() => onChange(option.value)}
                className="mt-0.5 accent-blue-500"
                aria-describedby={`llm-desc-${option.value}`}
              />
              <div className="flex flex-col min-w-0">
                <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
                  {option.label}
                </span>
                <span
                  id={`llm-desc-${option.value}`}
                  className="text-xs text-gray-500 dark:text-gray-400 mt-0.5"
                >
                  {option.description}
                </span>
              </div>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}
