// This project was developed with assistance from AI tools.

import { useEffect, useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { acknowledgeDisclosure, fetchDisclosureStatus } from '@/services/disclosures';
import type { DisclosureStatusResponse } from '@/schemas/disclosures';

export function useDisclosures(applicationId: number | undefined) {
  const queryKey = useMemo(
    () => ['applications', applicationId, 'disclosures'] as const,
    [applicationId],
  );
  const queryClient = useQueryClient();

  useEffect(() => {
    const handler = () => queryClient.invalidateQueries({ queryKey });
    window.addEventListener('chat-done', handler);
    return () => window.removeEventListener('chat-done', handler);
  }, [queryClient, queryKey]);

  return useQuery({
    queryKey,
    queryFn: () => fetchDisclosureStatus(applicationId!),
    enabled: applicationId != null,
  });
}

export function useAcknowledgeDisclosure(applicationId: number | undefined) {
  const queryClient = useQueryClient();
  const queryKey = useMemo(
    () => ['applications', applicationId, 'disclosures'] as const,
    [applicationId],
  );

  return useMutation({
    mutationFn: (disclosureId: string) =>
      acknowledgeDisclosure(applicationId!, disclosureId),
    onMutate: async (disclosureId) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<DisclosureStatusResponse>(queryKey);

      if (previous) {
        const disclosures = previous.disclosures.map((item) =>
          item.id === disclosureId ? { ...item, acknowledged: true } : item,
        );
        queryClient.setQueryData<DisclosureStatusResponse>(queryKey, {
          ...previous,
          disclosures,
          all_acknowledged: disclosures.every((item) => item.acknowledged),
        });
      }

      return { previous };
    },
    onError: (_error, _disclosureId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(queryKey, data);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });
}
