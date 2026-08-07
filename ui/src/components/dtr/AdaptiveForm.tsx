import { useState } from "react";

import { Button } from "@/components/ui/button";
import { answerToFhir, isAnswered, QuestionItem, type AnswerValue } from "@/components/dtr/QuestionItem";
import type { AnsweredItem, QuestionItem as QuestionItemType } from "@/types";

export function AdaptiveForm({
  currentQuestion,
  answeredCount,
  done,
  onNext,
  onSubmit,
  submitting,
}: {
  currentQuestion: QuestionItemType | null;
  answeredCount: number;
  done: boolean;
  onNext: (item: AnsweredItem) => void;
  onSubmit: () => void;
  submitting: boolean;
}) {
  const [value, setValue] = useState<AnswerValue>(undefined);

  const handleChange = (_linkId: string, next: AnswerValue) => setValue(next);

  const handleNext = () => {
    if (!currentQuestion) return;
    onNext({ linkId: currentQuestion.linkId, answer: answerToFhir(currentQuestion, value) });
    setValue(undefined);
  };

  if (done || !currentQuestion) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-slate-600 dark:text-slate-400">
          All questions answered ({answeredCount}).
        </p>
        <Button className="self-start" disabled={submitting} onClick={onSubmit}>
          {submitting ? "Submitting…" : "Submit"}
        </Button>
      </div>
    );
  }

  const canAdvance = isAnswered(currentQuestion, value);

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-slate-500 dark:text-slate-400">{answeredCount} questions answered</p>
      <QuestionItem item={currentQuestion} value={value} onChange={handleChange} />
      <div className="flex gap-2">
        <Button variant="secondary" disabled className="self-start">
          ← Previous
        </Button>
        <Button className="self-start" disabled={!canAdvance} onClick={handleNext}>
          Next →
        </Button>
      </div>
    </div>
  );
}
