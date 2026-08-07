import { useMutation, useQueryClient } from "@tanstack/react-query";

import { inquirePas, patchPasBundle, preparePas, submitPas } from "@/api/pas";
import type { PASBundleEdits } from "@/types";

export function usePreparePas(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => preparePas(sessionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions", sessionId] }),
  });
}

export function usePatchPasBundle(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (edits: PASBundleEdits) => patchPasBundle(sessionId, edits),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions", sessionId] }),
  });
}

export function useSubmitPas(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => submitPas(sessionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions", sessionId] }),
  });
}

export function useInquirePas(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => inquirePas(sessionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions", sessionId] }),
  });
}
