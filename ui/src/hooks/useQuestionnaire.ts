import { useMutation, useQueryClient } from "@tanstack/react-query";

import { nextQuestion, startDtr, submitDtr } from "@/api/dtr";
import type { AnsweredItem } from "@/types";

export function useStartDtr(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => startDtr(sessionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions", sessionId] }),
  });
}

export function useNextQuestion(sessionId: string) {
  return useMutation({
    mutationFn: (item: AnsweredItem) => nextQuestion(sessionId, item),
  });
}

export function useSubmitDtr(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (items?: AnsweredItem[]) => submitDtr(sessionId, items),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions", sessionId] }),
  });
}
