// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const AffordabilityRequestSchema = z.object({
  gross_annual_income: z.number(),
  monthly_debts: z.number(),
  monthly_property_fee: z.number().optional(),
  down_payment: z.number(),
  interest_rate: z.number().optional(),
  loan_term_years: z.number().optional(),
});

export const AffordabilityResponseSchema = z.object({
  max_loan_amount: z.number(),
  estimated_monthly_payment: z.number(),
  estimated_purchase_price: z.number(),
  dti_ratio: z.number(),
  housing_expense_ratio: z.number(),
  ltv_ratio: z.number(),
  down_payment_ratio: z.number(),
  housing_payment_cap: z.number(),
  total_debt_payment_cap: z.number(),
  binding_constraint: z.enum(['down_payment', 'repayment_capacity']),
  minimum_down_payment_ratio: z.number(),
  dti_warning: z.string().nullable().optional(),
  pmi_warning: z.string().nullable().optional(),
});

export type AffordabilityRequest = z.infer<typeof AffordabilityRequestSchema>;
export type AffordabilityResponse = z.infer<typeof AffordabilityResponseSchema>;
