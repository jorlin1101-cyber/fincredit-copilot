// This project was developed with assistance from AI tools.

import { ApiError, apiFetch } from '@/lib/api-client';
import { calculateAffordabilityLocally } from '@/lib/affordability-calculator';
import {
  AffordabilityResponseSchema,
  type AffordabilityRequest,
  type AffordabilityResponse,
} from '@/schemas/affordability';

export async function calculateAffordability(
  req: AffordabilityRequest,
): Promise<AffordabilityResponse> {
  try {
    const data = await apiFetch<unknown>('/api/public/calculate-affordability', {
      method: 'POST',
      body: JSON.stringify(req),
      signal: AbortSignal.timeout(6_000),
    });
    return AffordabilityResponseSchema.parse(data);
  } catch (error) {
    if (shouldUseLocalFallback(error)) {
      return calculateAffordabilityLocally(req);
    }
    throw error;
  }
}

function shouldUseLocalFallback(error: unknown): boolean {
  if (error instanceof ApiError) {
    return [408, 429, 500, 502, 503, 504].includes(error.status);
  }

  return (
    error instanceof TypeError ||
    (error instanceof DOMException &&
      ['AbortError', 'TimeoutError'].includes(error.name))
  );
}
