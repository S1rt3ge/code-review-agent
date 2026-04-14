import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { StatusBadge } from '../StatusBadge.jsx'

describe('StatusBadge', () => {
  it('renders "Pending" label for pending status', () => {
    render(<StatusBadge status="pending" />)
    expect(screen.getByText('Pending')).toBeInTheDocument()
  })

  it('renders "Analyzing" label for analyzing status', () => {
    render(<StatusBadge status="analyzing" />)
    expect(screen.getByText('Analyzing')).toBeInTheDocument()
  })

  it('renders "Done" label for done status', () => {
    render(<StatusBadge status="done" />)
    expect(screen.getByText('Done')).toBeInTheDocument()
  })

  it('renders "Error" label for error status', () => {
    render(<StatusBadge status="error" />)
    expect(screen.getByText('Error')).toBeInTheDocument()
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
