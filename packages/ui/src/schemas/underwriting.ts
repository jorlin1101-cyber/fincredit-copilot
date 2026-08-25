// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const RiskAssessmentSchema = z.object({
  id: z.number(),
  application_id: z.number(),
  dti_value: z.number().nullable().optional(),
  dti_rating: z.string().nullable().optional(),
  ltv_value: z.number().nullable().optional(),
  ltv_rating: z.string().nullable().optional(),
  credit_value: z.number().nullable().optional(),
  credit_rating: z.string().nullable().optional(),
  credit_source: z.string().nullable().optional(),
  income_stability_value: z.string().nullable().optional(),
  income_stability_rating: z.string().nullable().optional(),
  asset_sufficiency_value: z.number().nullable().optional(),
  asset_sufficiency_rating: z.string().nullable().optional(),
  predictive_model_result: z.string().nullable().optional(),
  predictive_model_available: z.boolean().nullable().optional(),
  compensating_factors: z.array(z.string()).nullable().optional(),
  warnings: z.array(z.string()).nullable().optional(),
  overall_risk: z.string().nullable().optional(),
  recommendation: z.string().nullable().optional(),
  recommendation_rationale: z.array(z.string()).nullable().optional(),
  recommendation_conditions: z.array(z.string()).nullable().optional(),
  assessed_by: z.string().nullable().optional(),
  created_at: z.string().nullable().optional(),
});

export type RiskAssessment = z.infer<typeof RiskAssessmentSchema>;

export const ComplianceResultSchema = z.object({
  id: z.number(),
  application_id: z.number(),
  ecoa_status: z.string().nullable().optional(),
  ecoa_rationale: z.string().nullable().optional(),
  ecoa_details: z.array(z.string()).nullable().optional(),
  atr_qm_status: z.string().nullable().optional(),
  atr_qm_rationale: z.string().nullable().optional(),
  atr_qm_details: z.array(z.string()).nullable().optional(),
  trid_status: z.string().nullable().optional(),
  trid_rationale: z.string().nullable().optional(),
  trid_details: z.array(z.string()).nullable().optional(),
  overall_status: z.string().nullable().optional(),
  can_proceed: z.boolean().nullable().optional(),
  checked_by: z.string().nullable().optional(),
  created_at: z.string().nullable().optional(),
});

export type ComplianceResultData = z.infer<typeof ComplianceResultSchema>;

const DeterministicMetricSchema = z.object({
  value: z.number().nullable(),
  rating: z.string().nullable(),
  formula: z.string(),
  inputs: z.record(z.number()),
  rule_version: z.string(),
});

export const DeterministicAssessmentSchema = z.object({
  id: z.number().nullable().optional(),
  application_id: z.number(),
  trace_id: z.string(),
  calculated_at: z.string(),
  dti: DeterministicMetricSchema,
  ltv: DeterministicMetricSchema,
  documents: z.object({
    required: z.array(z.string()),
    provided: z.array(z.string()),
    missing: z.array(z.string()),
    pending_human_review: z.array(z.string()),
    is_complete: z.boolean(),
  }),
  consistency_status: z.string(),
  consistency_issue_count: z.number(),
  suggestion: z.string(),
  rationale: z.array(z.string()),
  human_review_required: z.boolean(),
  confirmation_instruction: z.string(),
  rule_versions: z.record(z.string()),
});

export type DeterministicAssessment = z.infer<typeof DeterministicAssessmentSchema>;
