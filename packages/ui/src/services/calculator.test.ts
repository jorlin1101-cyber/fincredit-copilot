// This project was developed with assistance from AI tools.

import { afterEach, describe, expect, it, vi } from 'vitest';
import { calculateAffordability } from './calculator';

const request = {
  gross_annual_income: 240_000,
  monthly_debts: 2_000,
  monthly_property_fee: 300,
  down_payment: 300_000,
  interest_rate: 3.5,
  loan_term_years: 30,
};

describe('calculateAffordability', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns the same deterministic result when the API is temporarily unavailable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'upstream unavailable' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    const result = await calculateAffordability(request);

    expect(result.estimated_purchase_price).toBe(2_000_000);
    expect(result.max_loan_amount).toBe(1_700_000);
    expect(result.estimated_monthly_payment).toBe(7_633.76);
    expect(result.binding_constraint).toBe('down_payment');
    expect(result.ltv_ratio).toBe(85);
  });
});
