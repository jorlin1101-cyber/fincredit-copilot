// This project was developed with assistance from AI tools.

import { useQuery } from '@tanstack/react-query';
import { ApiError } from '@/lib/api-client';
import {
  fetchApplications,
  fetchApplication,
  type ApplicationsQueryParams,
} from '@/services/applications';

const RETRIABLE_SERVICE_STATUSES = new Set([429, 502, 503, 504]);

function shouldRetryServiceRequest(failureCount: number, error: unknown): boolean {
  if (failureCount >= 6) return false;
  if (error instanceof ApiError) return RETRIABLE_SERVICE_STATUSES.has(error.status);
  return true;
}

function serviceRetryDelay(attemptIndex: number): number {
  return Math.min(2_000 * 2 ** attemptIndex, 30_000);
}

export function useApplications() {
  return useQuery({
    queryKey: ['applications'],
    queryFn: () => fetchApplications(),
    retry: shouldRetryServiceRequest,
    retryDelay: serviceRetryDelay,
  });
}

export function usePipelineApplications(params: ApplicationsQueryParams) {
  return useQuery({
    queryKey: ['applications', 'pipeline', params],
    queryFn: () => fetchApplications(params),
  });
}

export function useApplication(id: number | undefined) {
  return useQuery({
    queryKey: ['applications', id],
    queryFn: () => fetchApplication(id!),
    enabled: id != null,
  });
}
