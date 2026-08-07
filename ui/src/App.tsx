import { useEffect } from "react";
import { Route, Routes } from "react-router-dom";

import { bootstrap } from "@/api/util";
import { AppShell } from "@/components/layout/AppShell";
import { Dashboard } from "@/pages/Dashboard";
import { NewSession } from "@/pages/NewSession";
import { SessionDetail } from "@/pages/SessionDetail";

function App() {
  useEffect(() => {
    bootstrap().catch(() => {
      // Non-blocking: the app still works if fixtures are already loaded.
    });
  }, []);

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/sessions/new" element={<NewSession />} />
        <Route path="/sessions/:id" element={<SessionDetail />} />
      </Routes>
    </AppShell>
  );
}

export default App;
