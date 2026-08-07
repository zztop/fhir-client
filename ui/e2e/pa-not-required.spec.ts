import { expect, test } from "@playwright/test";

// Requires the full stack running: HAPI FHIR (8080), CDS/DTR/PAS stubs
// (3001-3003), and the EHR API (8000) — e.g. `docker compose up -d`.
test("order-sign / pa-not-required: no DTR, no PAS", async ({ page }) => {
  await page.goto("/sessions/new");

  await page.getByText("Order Signing", { exact: true }).click();
  await page.getByText("PA Not Required", { exact: true }).click();
  await page.getByRole("button", { name: "Send CRD Request" }).click();

  await expect(page).toHaveURL(/\/sessions\/[\w-]+$/);
  await expect(page.getByText("No Prior Authorization Required", { exact: true })).toBeVisible();

  await expect(page.getByRole("button", { name: "Start DTR" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Prepare PAS Bundle" })).toHaveCount(0);
});
