import { test, expect } from "@playwright/test";

test.describe("Authentication Smoke Suite", () => {
  test("renders login page with credentials form", async ({ page }) => {
    await page.goto("/login");

    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Password" })).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
  });

  test("validates required fields before submitting", async ({ page }) => {
    await page.goto("/login");

    const submitBtn = page.getByRole("button", { name: /sign in/i });
    await submitBtn.click();

    // Native HTML5 or custom validation should prevent submission with empty fields
    const emailInput = page.getByLabel(/email/i);
    await expect(emailInput).toBeFocused();
  });

  test("navigates between login and registration", async ({ page }) => {
    await page.goto("/login");

    await page.getByRole("link", { name: /create one/i }).click();
    await expect(page).toHaveURL(/\/register/);
    await expect(page.getByRole("heading", { name: /create account/i })).toBeVisible();

    await page.getByRole("link", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });
});
