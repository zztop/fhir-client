import { cn } from "@/lib/utils";

export type StepStatus = "pending" | "active" | "complete" | "error";

export interface TimelineStep {
  label: string;
  status: StepStatus;
}

const DOT_CLASSES: Record<StepStatus, string> = {
  pending: "bg-slate-200 text-slate-500 dark:bg-slate-700 dark:text-slate-400",
  active: "bg-blue-600 text-white",
  complete: "bg-green-600 text-white",
  error: "bg-red-600 text-white",
};

export function StepTimeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol className="flex flex-col gap-1">
      {steps.map((step, i) => (
        <li key={step.label} className="flex items-start gap-3">
          <div className="flex flex-col items-center">
            <span
              className={cn(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium",
                DOT_CLASSES[step.status],
              )}
            >
              {step.status === "complete" ? "✓" : i + 1}
            </span>
            {i < steps.length - 1 && <span className="h-6 w-px bg-slate-200 dark:bg-slate-700" />}
          </div>
          <span
            className={cn(
              "pt-0.5 text-sm font-medium",
              step.status === "pending" ? "text-slate-400" : "text-slate-800 dark:text-slate-200",
            )}
          >
            {step.label}
          </span>
        </li>
      ))}
    </ol>
  );
}
