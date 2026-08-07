import { useState } from "react";

import { Button } from "@/components/ui/button";

export function JsonViewer({ data, label }: { data: unknown; label?: string }) {
  const [copied, setCopied] = useState(false);
  const json = JSON.stringify(data, null, 2);

  const copy = async () => {
    await navigator.clipboard.writeText(json);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-md border border-slate-200 dark:border-slate-800">
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-3 py-1.5 dark:border-slate-800 dark:bg-slate-800/50">
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400">{label ?? "JSON"}</span>
        <Button variant="ghost" className="h-6 px-2 py-0 text-xs" onClick={copy}>
          {copied ? "Copied!" : "Copy"}
        </Button>
      </div>
      <pre className="max-h-96 overflow-auto p-3 text-xs text-slate-700 dark:text-slate-300">{json}</pre>
    </div>
  );
}
