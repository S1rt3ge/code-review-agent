import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { Settings } from '../Settings.jsx'
import { useAuthStore } from '@/store/index.js'

const BASE_SETTINGS = {
  plan: 'free',
  api_key_claude_set: false,
  api_key_gpt_set: false,
  ollama_enabled: false,
  ollama_host: 'http://localhost:11434',
  default_agents: ['security', 'performance', 'style', 'logic'],
  lm_preference: 'auto',
}

function renderSettings() {
  return render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>
  )
}

describe('Settings page', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({ token: 'test-token', user: { id: 'u1', email: 'a@b.com', plan: 'free' } })
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows Ollama-first provider setup and BYOK cost copy', async () => {
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(BASE_SETTINGS), { status: 200 })
    )

    renderSettings()

    await waitFor(() => {
      expect(screen.getByText('Provider Setup')).toBeInTheDocument()
    })

    expect(screen.getByText('Recommended free/local path')).toBeInTheDocument()
    expect(screen.getByText('Local Ollama (Free/Local Default)')).toBeInTheDocument()
    expect(screen.getByText(/Your keys stay encrypted locally\/server-side/i)).toBeInTheDocument()
    expect(screen.getByText(/Hosted Claude\/OpenAI usage is billed to your own provider account/i)).toBeInTheDocument()
    expect(screen.getAllByText('Not configured')).toHaveLength(3)
    expect(screen.getByText(/BYOK usage may be billed by Anthropic/i)).toBeInTheDocument()
    expect(screen.getByText(/BYOK usage may be billed by OpenAI/i)).toBeInTheDocument()
  })

  it('updates provider cards with live availability results', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ...BASE_SETTINGS,
        api_key_claude_set: true,
        ollama_enabled: true,
        lm_preference: 'local',
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        claude_available: true,
        gpt_available: false,
        ollama_available: true,
      }), { status: 200 }))

    renderSettings()

    await waitFor(() => {
      expect(screen.getByText('Provider Setup')).toBeInTheDocument()
    })
    expect(screen.getAllByText('Configured')).toHaveLength(2)
    expect(screen.getAllByText('Not configured')).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'Test LLM Connection' }))

    await waitFor(() => {
      expect(screen.getAllByText('Available').length).toBeGreaterThanOrEqual(2)
      expect(screen.getAllByText('Not reachable')).toHaveLength(1)
    })
  })
})
