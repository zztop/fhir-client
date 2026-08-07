import { createContext, useContext, useState, type ReactNode } from "react";

interface DevModeContextValue {
  devMode: boolean;
  setDevMode: (value: boolean) => void;
}

const DevModeContext = createContext<DevModeContextValue | undefined>(undefined);

export function DevModeProvider({ children }: { children: ReactNode }) {
  const [devMode, setDevModeState] = useState<boolean>(
    () => localStorage.getItem("devMode") === "true",
  );

  const setDevMode = (value: boolean) => {
    setDevModeState(value);
    localStorage.setItem("devMode", String(value));
  };

  return (
    <DevModeContext.Provider value={{ devMode, setDevMode }}>{children}</DevModeContext.Provider>
  );
}

export function useDevMode(): DevModeContextValue {
  const ctx = useContext(DevModeContext);
  if (!ctx) throw new Error("useDevMode must be used within DevModeProvider");
  return ctx;
}
