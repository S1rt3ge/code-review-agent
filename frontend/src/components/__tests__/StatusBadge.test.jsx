import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { StatusBadge } from '../StatusBadge.jsx'

describe('StatusBadge', () => {
  it('renders "Queued" label for pending status', () => {
    render(<StatusBadge status="pending" />)
    expect(screen.getByText('Queued')).toBeInTheDocument()
  })

  it('renders "Analyzing" label for analyzing status', () => {
    render(<StatusBadge status="analyzing" />)
    expect(screen.getByText('Analyzing')).toBeInTheDocument()
  })

  it('renders "Complete" label for done status', () => {
    render(<StatusBadge status="done" />)
    expect(screen.getByText('Complete')).toBeInTheDocument()
  })

  it('renders "Failed" label for error status', () => {
    render(<StatusBadge status="error" />)
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })

  it('exposes the readable status to assistive tech', () => {
    render(<StatusBadge status="done" />)
    expect(screen.getByLabelText('Review status: Complete')).toBeInTheDocument()
  })

  it('renders spinner for analyzing status', () => {
    const { container } = render(<StatusBadge status="analyzing" />)
    const spinner = container.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
  })

  it('does not render spinner for non-analyzing statuses', () => {
    const { container } = render(<StatusBadge status="done" />)
    const spinner = container.querySelector('.animate-spin')
    expect(spinner).not.toBeInTheDocument()
  })

  it('renders the raw status string for unknown status', () => {
    render(<StatusBadge status="unknown_status" />)
    expect(screen.getByText('unknown_status')).toBeInTheDocument()
  })

  it('applies extra className prop', () => {
    const { container } = render(<StatusBadge status="pending" className="my-custom-class" />)
    expect(container.firstChild).toHaveClass('my-custom-class')
  })
})
