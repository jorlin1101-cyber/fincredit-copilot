// This project was developed with assistance from AI tools.

import { apiGet, apiPost } from '@/lib/api-client';
import {
  DisclosureStatusResponseSchema,
  type DisclosureStatusResponse,
} from '@/schemas/disclosures';

export async function fetchDisclosureStatus(
  applicationId: number,
): Promise<DisclosureStatusResponse> {
  const data = await apiGet<unknown>(`/api/applications/${applicationId}/disclosures`);
  return DisclosureStatusResponseSchema.parse(data);
}

export async function acknowledgeDisclosure(
  applicationId: number,
  disclosureId: string,
): Promise<DisclosureStatusResponse> {
  const data = await apiPost<unknown>(
    `/api/applications/${applicationId}/disclosures/${disclosureId}/acknowledge`,
    { borrower_confirmation: '我已阅读并确认' },
  );
  return DisclosureStatusResponseSchema.parse(data);
}
