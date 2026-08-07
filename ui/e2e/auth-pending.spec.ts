import { expect, test } from "@playwright/test";

// Requires the full stack running: HAPI FHIR (8080), CDS/DTR/PAS stubs
// (3001-3003), and the EHR API (8000) — e.g. `docker compose up -d`.
//
// auth-pending sets pa_needed=true just like pa-required, so the CRD stub
// still returns a DTR launch card — DTR must be completed before "Prepare
// PAS Bundle" is enabled.
test("appointment-book / auth-pending: Pended -> Check Status -> Granted", async ({ page }) => {
  await page.goto("/sessions/new");

  await page.getByText("Appointment Booking", { exact: true }).click();
  await page.getByText("Auth Pending", { exact: true }).click();
  await page.getByRole("button", { name: "Send CRD Request" }).click();

  await expect(page).toHaveURL(/\/sessions\/[\w-]+$/);

  await page.getByRole("button", { name: "Start DTR" }).click();
  await page.getByRole("switch", { name: "Is this service medically necessary?" }).click();
  await page.getByLabel("Primary diagnosis code (ICD-10)").fill("M54.5");
  await page.getByLabel("Treating physician NPI").fill("1234567890");
  await page.getByLabel("Requested quantity / units").fill("30");
  await page.getByRole("button", { name: "Submit Answers" }).click();
  await expect(page.getByText("Documentation submitted ✓")).toBeVisible();

  await page.getByRole("button", { name: "Prepare PAS Bundle" }).click();
  await page.getByRole("button", { name: "Submit Prior Authorization" }).click();

  await expect(page.getByText(/Pended/)).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "Check Status" }).click();

  await expect(page.getByText(/Authorization Granted — Auth #/)).toBeVisible({ timeout: 15_000 });
});
