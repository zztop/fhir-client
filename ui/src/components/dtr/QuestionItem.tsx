import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import type { QuestionItem as QuestionItemType } from "@/types";

export type AnswerValue = boolean | string | number | undefined;

export function QuestionItem({
  item,
  value,
  onChange,
}: {
  item: QuestionItemType;
  value: AnswerValue;
  onChange: (linkId: string, value: AnswerValue) => void;
}) {
  const inputId = `question-${item.linkId}`;

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-slate-800 dark:text-slate-200">
        {item.text}
        {item.required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      {item.type === "boolean" && (
        <Switch
          id={inputId}
          checked={Boolean(value)}
          onCheckedChange={(checked) => onChange(item.linkId, checked)}
          aria-label={item.text}
        />
      )}
      {item.type === "string" && (
        <Input
          id={inputId}
          value={(value as string | undefined) ?? ""}
          onChange={(e) => onChange(item.linkId, e.target.value)}
        />
      )}
      {item.type === "integer" && (
        <Input
          id={inputId}
          type="number"
          min={0}
          value={(value as number | undefined) ?? ""}
          onChange={(e) => onChange(item.linkId, e.target.value === "" ? undefined : Number(e.target.value))}
        />
      )}
    </div>
  );
}

export function answerToFhir(item: QuestionItemType, value: AnswerValue): Record<string, unknown>[] {
  if (value === undefined) return [];
  if (item.type === "boolean") return [{ valueBoolean: Boolean(value) }];
  if (item.type === "integer") return [{ valueInteger: Number(value) }];
  return [{ valueString: String(value) }];
}

export function isAnswered(item: QuestionItemType, value: AnswerValue): boolean {
  if (!item.required) return true;
  if (item.type === "boolean") return value !== undefined;
  return value !== undefined && value !== "";
}
