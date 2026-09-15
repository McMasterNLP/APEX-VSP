import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RatioValueCell } from './RatioValueCell'
import type { RatioResult } from '@/types/researchEvaluation'

/**
 * This is the highest-risk-of-silent-bug part of Item 3B: a viewer skimming the results
 * table must never mistake `ineligible` / `no_reference_support` / `no_predicted_support`
 * for a real computed score of zero. Each status must render distinctly and legibly.
 */
describe('RatioValueCell', () => {
  it('renders a computed value as the fraction plus its decimal', () => {
    const ratio: RatioResult = { status: 'computed', value: '2/3' }
    render(<RatioValueCell ratio={ratio} />)
    expect(screen.getByText('2/3')).toBeInTheDocument()
    expect(screen.getByText('(0.667)')).toBeInTheDocument()
    expect(screen.queryByTestId('ratio-not-available')).not.toBeInTheDocument()
  })

  it('renders a computed zero as a real zero, not blank', () => {
    const ratio: RatioResult = { status: 'computed', value: '0' }
    render(<RatioValueCell ratio={ratio} />)
    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getByText('(0.000)')).toBeInTheDocument()
  })

  it('renders ineligible distinctly from a computed zero, with its reason', () => {
    const ratio: RatioResult = {
      status: 'ineligible',
      value: null,
      note: 'Requires exhaustive coverage.',
    }
    render(<RatioValueCell ratio={ratio} />)
    expect(screen.getByTestId('ratio-not-available')).toBeInTheDocument()
    expect(screen.getByText(/N\/A/)).toBeInTheDocument()
    expect(screen.getByText(/Ineligible/)).toBeInTheDocument()
    expect(screen.getByText('Requires exhaustive coverage.')).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('renders no_reference_support distinctly, never as a bare 0', () => {
    const ratio: RatioResult = { status: 'no_reference_support', value: null }
    render(<RatioValueCell ratio={ratio} />)
    expect(screen.getByTestId('ratio-not-available')).toBeInTheDocument()
    expect(screen.getByText(/No reference support/)).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('renders no_predicted_support distinctly, never as a bare 0', () => {
    const ratio: RatioResult = { status: 'no_predicted_support', value: null }
    render(<RatioValueCell ratio={ratio} />)
    expect(screen.getByTestId('ratio-not-available')).toBeInTheDocument()
    expect(screen.getByText(/No predicted support/)).toBeInTheDocument()
  })
})
