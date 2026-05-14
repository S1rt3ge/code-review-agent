import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { AgentStatus } from '../AgentStatus.jsx'

describe('AgentStatus', () => {
  it('shows animated spinner for running status', () => {
    const { container } = render(<AgentStatus agentName="security" status="running" />)
    expect(container.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('shows no spinner for non-running statuses', () => {
    const { container } = render(<AgentStatus agentName="security" status="done" />)
    expect(container.querySelector('.animate-spin')).not.toBeInTheDocument()
  })

  it('renders friendly done status label', () => {
    render(<AgentStatus agentName="security" status="done" />)
    expect(screen.getByText('Complete')).toBeInTheDocument()
  })

  it('renders friendly error status label', () => {
    render(<AgentStatus agentName="security" status="error" />)
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })

  it('renders friendly pending status label', () => {
    render(<AgentStatus agentName="logic" status="pending" />)
    expect(screen.getByText('Queued')).toBeInTheDocument()
  })

  it('exposes the agent and status to assistive tech', () => {
    render(<AgentStatus agentName="security" status="running" />)
    expect(screen.getByLabelText('Security agent status: Running')).toBeInTheDocument()
  })

  it('maps known agent names to display labels', () => {
    render(<AgentStatus agentName="performance" status="done" />)
    expect(screen.getByText('Performance')).toBeInTheDocument()
  })

  it('renders unknown agent name as-is', () => {
    render(<AgentStatus agentName="custom_agent" status="pending" />)
    expect(screen.getByText('custom_agent')).toBeInTheDocument()
  })

  it('shows a dot placeholder for pending status', () => {
    const { container } = render(<AgentStatus agentName="style" status="pending" />)
    const dot = container.querySelector('.rounded-full.bg-gray-300, .rounded-full.dark\\:bg-gray-600')
    expect(dot).toBeInTheDocument()
  })
})
