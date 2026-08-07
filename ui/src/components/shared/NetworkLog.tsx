import { useEffect, useState } from "react";

import { getNetworkLog, networkLogEvents, type NetworkLogEntry } from "@/api/client";

export function NetworkLog() {
  const [entries, setEntries] = useState<NetworkLogEntry[]>(getNetworkLog());

  useEffect(() => {
    const handler = () => setEntries([...getNetworkLog()]);
    networkLogEvents.addEventListener("entry", handler);
    return () => networkLogEvents.removeEventListener("entry", handler);
  }, []);

  if (entries.length === 0) return null;

  return (
    <div className="mt-8 rounded-md border border-slate-200 dark:border-slate-800">
      <div className="border-b border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-500 dark:border-slate-800 dark:bg-slate-800/50 dark:text-slate-400">
        Network Log
      </div>
      <div className="max-h-48 overflow-auto">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-white text-slate-400 dark:bg-slate-900">
            <tr>
              <th className="px-3 py-1 font-medium">Time</th>
              <th className="px-3 py-1 font-medium">Method</th>
              <th className="px-3 py-1 font-medium">URL</th>
              <th className="px-3 py-1 font-medium">Status</th>
              <th className="px-3 py-1 font-medium">Duration</th>
            </tr>
          </thead>
          <tbody>
            {[...entries].reverse().map((entry, i) => (
              <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                <td className="px-3 py-1 text-slate-500">{entry.timestamp.slice(11, 19)}</td>
                <td className="px-3 py-1 font-mono">{entry.method}</td>
                <td className="px-3 py-1 font-mono">{entry.url}</td>
                <td className={`px-3 py-1 ${entry.status >= 400 ? "text-red-600" : "text-green-600"}`}>
                  {entry.status}
                </td>
                <td className="px-3 py-1 text-slate-500">{entry.durationMs}ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
