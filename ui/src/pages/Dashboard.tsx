import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { AlertDialog } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useDeleteSession, useSessions } from "@/hooks/useSession";

export function Dashboard() {
  const { data: sessions, isLoading } = useSessions();
  const deleteSession = useDeleteSession();
  const navigate = useNavigate();
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Prior Authorization Sessions</h1>
        <Button onClick={() => navigate("/sessions/new")}>New Prior Auth Request</Button>
      </div>

      <div className="mt-6 overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900 dark:text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">Session</th>
              <th className="px-4 py-2 font-medium">Hook</th>
              <th className="px-4 py-2 font-medium">Scenario</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Created</th>
              <th className="px-4 py-2 font-medium">Disposition</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {isLoading &&
              Array.from({ length: 3 }).map((_, i) => (
                <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                  <td colSpan={7} className="px-4 py-3">
                    <div className="h-4 w-full animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
                  </td>
                </tr>
              ))}

            {!isLoading && sessions?.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                  <p>No sessions yet</p>
                  <Button className="mt-3" onClick={() => navigate("/sessions/new")}>
                    Create your first request
                  </Button>
                </td>
              </tr>
            )}

            {sessions?.map((session) => (
              <tr
                key={session.id}
                className="cursor-pointer border-t border-slate-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50"
                onClick={() => navigate(`/sessions/${session.id}`)}
              >
                <td className="px-4 py-2 font-mono text-xs">
                  <Link to={`/sessions/${session.id}`} onClick={(e) => e.stopPropagation()}>
                    {session.id.slice(0, 8)}
                  </Link>
                </td>
                <td className="px-4 py-2">{session.hook}</td>
                <td className="px-4 py-2">{session.scenario_key}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={session.status} />
                </td>
                <td className="px-4 py-2 text-slate-500">{new Date(session.created_at).toLocaleString()}</td>
                <td className="px-4 py-2">{session.disposition ?? "—"}</td>
                <td className="px-4 py-2 text-right">
                  <button
                    type="button"
                    className="text-slate-400 hover:text-red-600"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPendingDelete(session.id);
                    }}
                    aria-label="Delete session"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <AlertDialog
        open={pendingDelete !== null}
        title="Delete session?"
        description="This permanently deletes the session and all associated CRD, DTR, and PAS data."
        confirmLabel="Delete"
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) deleteSession.mutate(pendingDelete);
          setPendingDelete(null);
        }}
      />
    </div>
  );
}
