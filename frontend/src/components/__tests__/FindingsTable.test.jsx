import { render, screen, fireEvent, within } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { FindingsTable } from '../FindingsTable.jsx'

/** @type {import('../FindingsTable.jsx').Finding[]} */
const SAMPLE_FINDINGS = [
  {
    id: '1',
    agentName: 'security',
    severity: 'critical',
    filePath: 'src/auth/login.js',
    lineNumber: 42,
    message: 'SQL injection risk',
    suggestion: 'Use parameterized queries'
  },
  {
    id: '2',
    agentName: 'style',
    severity: 'info',
    filePath: 'src/utils/helper.js',
    lineNumber: 10,
    message: 'Missing docstring',
    suggestion: null
  },
  {
    id: '3',
    agentName: 'performance',
    severity: 'warning',
    filePath: 'src/api/client.js',
    lineNumber: 99,
    message: 'N+1 query detected',
    suggestion: 'Use eager loading'
  }
]

describe('FindingsTable', () => {
  it('renders empty state when there are no findings', () => {
    render(<FindingsTable findings={[]} />)
    expect(screen.getByText('No findings')).toBeInTheDocument()
    expect(
      screen.getByText('No actionable issues were detected by the selected review agents.')
    ).toBeInTheDocument()
  })

  it('renders a severity summary for non-empty findings', () => {
    render(<FindingsTable findings={SAMPLE_FINDINGS} />)
    expect(
      screen.getByText('Findings are sorted by severity so the riskiest issues are reviewed first.')
    ).toBeInTheDocument()

    const summary = screen.getByLabelText('Findings severity summary')
    expect(within(summary).getByText('High Risk')).toBeInTheDocument()
    expect(within(summary).getByText('Medium Risk')).toBeInTheDocument()
    expect(within(summary).getByText('Low / Info')).toBeInTheDocument()
    expect(summary).toHaveTextContent('2High Risk')
    expect(summary).toHaveTextContent('0Medium Risk')
    expect(summary).toHaveTextContent('1Low / Info')
  })

  it('renders all column headers when findings exist', () => {
    render(<FindingsTable findings={SAMPLE_FINDINGS} />)
    expect(screen.getByText('Severity')).toBeInTheDocument()
    expect(screen.getByText('Agent')).toBeInTheDocument()
    expect(screen.getByText('File')).toBeInTheDocument()
    expect(screen.getByText('Line')).toBeInTheDocument()
    expect(screen.getByText('Message')).toBeInTheDocument()
    expect(screen.getByText('Suggestion')).toBeInTheDocument()
  })

  it('renders a row for each finding', () => {
    render(<FindingsTable findings={SAMPLE_FINDINGS} />)
    expect(screen.getByText('SQL injection risk')).toBeInTheDocument()
    expect(screen.getByText('Missing docstring')).toBeInTheDocument()
    expect(screen.getByText('N+1 query detected')).toBeInTheDocument()
  })

  it('sorts findings by severity: critical first, then warning, then info', () => {
    render(<FindingsTable findings={SAMPLE_FINDINGS} />)
    const rows = screen.getAllByRole('row')
    // row 0 = header, row 1 = critical, row 2 = warning, row 3 = info
    expect(rows[1]).toHaveTextContent('critical')
    expect(rows[2]).toHaveTextContent('warning')
    expect(rows[3]).toHaveTextContent('info')
  })

  it('displays suggestion text when provided', () => {
    render(<FindingsTable findings={SAMPLE_FINDINGS} />)
    expect(screen.getByText('Use parameterized queries')).toBeInTheDocument()
    expect(screen.getByText('Use eager loading')).toBeInTheDocument()
  })

  it('displays dash placeholder when suggestion is absent', () => {
    render(<FindingsTable findings={SAMPLE_FINDINGS} />)
    // The info-severity finding has no suggestion — expect the em-dash placeholder
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(1)
  })

  it('truncates deeply nested file paths to last two segments', () => {
    const finding = {
      id: '99',
      agentName: 'logic',
      severity: 'info',
      filePath: 'a/b/c/d/deep/file.js',
      lineNumber: 1,
      message: 'test',
      suggestion: null
    }
    render(<FindingsTable findings={[finding]} />)
    expect(screen.getByText('.../deep/file.js')).toBeInTheDocument()
  })

  it('calls onSelectFinding when a row is clicked', () => {
    const handler = vi.fn()
    render(<FindingsTable findings={SAMPLE_FINDINGS} onSelectFinding={handler} />)
    fireEvent.click(screen.getByText('SQL injection risk'))
    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ id: '1', message: 'SQL injection risk' })
    )
  })

  it('does not crash when onSelectFinding is not provided', () => {
    render(<FindingsTable findings={SAMPLE_FINDINGS} />)
    // Click without handler — should not throw
    expect(() => fireEvent.click(screen.getByText('SQL injection risk'))).not.toThrow()
  })
})
