import { useState } from "react";

import { JsonViewer } from "@/components/shared/JsonViewer";

export function RawJsonPanel({ data, label }: { data: unknown; label: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        type="button"
        className="text-xs font-medium text-blue-600 hover:underline"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Hide" : "Show"} Raw JSON
      </button>
      {open && (
        <div className="mt-2">
          <JsonViewer data={data} label={label} />
        </div>
      )}
    </div>
  );
}
