import { expect, test } from "@playwright/test";

// Requires the full stack running: HAPI FHIR (8080), CDS/DTR/PAS stubs
// (3001-3003), and the EHR API (8000) — e.g. `docker compose up -d`.
test("order-sign / pa-required: CRD -> DTR -> PAS -> Granted", async ({ page }) => {
  await page.goto("/sessions/new");

  await page.getByText("Order Signing", { exact: true }).click();
  await page.getByText("PA Required", { exact: true }).click();
  await page.getByRole("button", { name: "Send CRD Request" }).click();

  await expect(page).toHaveURL(/\/sessions\/[\w-]+$/);
  await expect(
    page.getByText("Documentation Required — complete the DTR questionnaire before submitting PA"),
  ).toBeVisible();

  await expect(page.getByText("Prior Authorization Required", { exact: true })).toBeVisible();
  await expect(page.getByText("Complete Prior Authorization Documentation")).toBeVisible();

  await page.getByRole("button", { name: "Start DTR" }).click();

  await page.getByRole("switch", { name: "Is this service medically necessary?" }).click();
  await page.getByLabel("Primary diagnosis code (ICD-10)").fill("M54.5");
  await page.getByLabel("Treating physician NPI").fill("1234567890");
  await page.getByLabel("Requested quantity / units").fill("30");
  await page.getByRole("button", { name: "Submit Answers" }).click();

  await expect(page.getByText("Documentation submitted ✓")).toBeVisible();

  await page.getByRole("button", { name: "Prepare PAS Bundle" }).click();
  await expect(page.getByRole("button", { name: "Edit Fields" })).toBeVisible();

  await page.getByLabel("Diagnosis Code").fill("M54.5");

  await page.getByRole("button", { name: "Submit Prior Authorization" }).click();

  await expect(page.getByText(/Authorization Granted — Auth #/)).toBeVisible({ timeout: 15_000 });
});
