import { defineConfig, devices } from "@playwright/test";

// E2E prerequisites: HAPI FHIR (8080), CDS/DTR/PAS stubs (3001-3003), and the
// EHR API (8000) must all be running — e.g. via `docker compose up -d`.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
