// Playwright is installed per-run by CI/Make with --no-save, so it is absent
// during `tsc --noEmit`; skip typechecking this spec instead of adding the dep.
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-nocheck
import { expect, test } from "@playwright/test";

// Narrow smoke check: the public landing page and the admin login form render.
// Deeper flows live in unit tests; this guards against a broken build/deploy.
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

test.use({ baseURL });

test("home page returns 200", async ({ page }) => {
  const response = await page.goto("/", { waitUntil: "domcontentloaded" });
  expect(response?.status()).toBe(200);
  await expect(page.locator("body")).toBeVisible();
});

test("admin login page returns 200", async ({ page }) => {
  const response = await page.goto("/admin/login", { waitUntil: "domcontentloaded" });
  expect(response?.status()).toBe(200);
  await expect(page.locator("form")).toBeVisible();
});
