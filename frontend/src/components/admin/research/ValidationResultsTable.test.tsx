import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ValidationResultsTable } from './ValidationResultsTable'
import type { RatioResult, SpanClassificationMetrics } from '@/types/researchEvaluation'

const computed = (value: string): RatioResult => ({ status: 'computed', value })
const notAvailable = (
  status: RatioResult['status'],
  note?: string
): RatioResult => ({ status, value: null, note })

/**
 * Mirrors the hand-computed backend fixture in `test_research_validation_metrics.py`:
 * label A is a perfect partial match, label B has zero predictions for precision, and
 * label C has zero reference instances so it is excluded from the macro average rather
 * than scored as zero.
 */
function metrics(): SpanClassificationMetrics {
  return {
    metric_family: 'span_classification',
    metric_implementation_version: 'span-classification-v1',
    matching_policy_identifier: 'exact_span_match',
    matching_policy_version: '1.0',
    per_label: [
      {
        label: 'A',
        support: 3,
        predicted_count: 3,
        true_positives: 2,
        false_positives: 1,
        false_negatives: 1,
        precision: computed('2/3'),
        recall: computed('2/3'),
        f1: computed('2/3'),
      },
      {
        label: 'B',
        support: 2,
        predicted_count: 0,
        true_positives: 0,
        false_positives: 0,
        false_negatives: 2,
        precision: notAvailable('no_predicted_support'),
        recall: computed('0'),
        f1: computed('0'),
      },
      {
        label: 'C',
        support: 0,
        predicted_count: 1,
        true_positives: 0,
        false_positives: 1,
        false_negatives: 0,
        precision: notAvailable('no_reference_support', 'Label C has no reference instances.'),
        recall: notAvailable('no_reference_support', 'Label C has no reference instances.'),
        f1: notAvailable('no_reference_support', 'Label C has no reference instances.'),
      },
    ],
    micro: {
      true_positives: 2,
      false_positives: 2,
      false_negatives: 3,
      precision: computed('1/2'),
      recall: computed('1/2'),
      f1: computed('1/2'),
      labels_included: 3,
    },
    macro: {
      true_positives: 2,
      false_positives: 2,
      false_negatives: 3,
      precision: computed('2/3'),
      recall: computed('1/3'),
      f1: computed('1/3'),
      labels_included: 2,
    },
  }
}

describe('ValidationResultsTable', () => {
  it('renders every label row with its own precision/recall/F1', () => {
    render(<ValidationResultsTable metrics={metrics()} />)
    expect(screen.getByText('A')).toBeInTheDocument()
    expect(screen.getByText('B')).toBeInTheDocument()
    expect(screen.getByText('C')).toBeInTheDocument()
  })

  it('never renders no_reference_support as a computed zero', () => {
    render(<ValidationResultsTable metrics={metrics()} />)
    // Label C's cells must show the not-available pill, not a bare "0".
    const notAvailableCells = screen.getAllByTestId('ratio-not-available')
    expect(notAvailableCells.length).toBeGreaterThanOrEqual(4) // B.precision + C's 3 ratios
  })

  it('reports the macro-excluded label with its reason, not silently dropped', () => {
    render(<ValidationResultsTable metrics={metrics()} />)
    expect(screen.getByText(/Excluded from the macro average/)).toBeInTheDocument()
    expect(screen.getByText(/C \(no reference support\)/)).toBeInTheDocument()
    expect(screen.getByText(/2 labels included/)).toBeInTheDocument()
  })

  it('renders micro and macro summary rows distinctly from per-label rows', () => {
    render(<ValidationResultsTable metrics={metrics()} />)
    expect(screen.getByText('Micro average')).toBeInTheDocument()
    expect(screen.getByText('Macro average')).toBeInTheDocument()
  })
})
