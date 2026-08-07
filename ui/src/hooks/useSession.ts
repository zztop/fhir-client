import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createSession, deleteSession, getSession, listSessions } from "@/api/sessions";
import type { Hook, ScenarioKey } from "@/types";

export function useSessions() {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions,
    refetchInterval: 5000,
  });
}

export function useSession(id: string | undefined) {
  return useQuery({
    queryKey: ["sessions", id],
    queryFn: () => getSession(id as string),
    enabled: Boolean(id),
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ hook, scenarioKey }: { hook: Hook; scenarioKey: ScenarioKey }) =>
      createSession(hook, scenarioKey),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });
}

export function useDeleteSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteSession(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });
}
