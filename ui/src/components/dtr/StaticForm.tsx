import { useState } from "react";

import { Button } from "@/components/ui/button";
import { answerToFhir, isAnswered, QuestionItem, type AnswerValue } from "@/components/dtr/QuestionItem";
import type { AnsweredItem, QuestionItem as QuestionItemType } from "@/types";

export function StaticForm({
  questions,
  onSubmit,
  submitting,
}: {
  questions: QuestionItemType[];
  onSubmit: (items: AnsweredItem[]) => void;
  submitting: boolean;
}) {
  const [values, setValues] = useState<Record<string, AnswerValue>>({});

  const setValue = (linkId: string, value: AnswerValue) => {
    setValues((prev) => ({ ...prev, [linkId]: value }));
  };

  const allAnswered = questions.every((q) => isAnswered(q, values[q.linkId]));

  const handleSubmit = () => {
    const items: AnsweredItem[] = questions.map((q) => ({
      linkId: q.linkId,
      answer: answerToFhir(q, values[q.linkId]),
    }));
    onSubmit(items);
  };

  return (
    <div className="flex flex-col gap-4">
      {questions.map((q) => (
        <QuestionItem key={q.linkId} item={q} value={values[q.linkId]} onChange={setValue} />
      ))}
      <Button className="self-start" disabled={!allAnswered || submitting} onClick={handleSubmit}>
        {submitting ? "Submitting…" : "Submit Answers"}
      </Button>
    </div>
  );
}
