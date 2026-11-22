import { test, expect } from "@playwright/test";

test.describe("Job Board & Feed Interactions", () => {
  const credentials = {
    email: "playwright-smoke@example.com",
    password: "SmokePassword123!",
  };

  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.locator("form[data-hydrated='true']").waitFor();
    await page.getByLabel(/email/i).fill(credentials.email);
    await page.getByLabel(/^password$/i).fill(credentials.password);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/jobs/, { timeout: 10_000 });
  });

  test("loads jobs board and allows category filter interaction", async ({ page }) => {
    // Board toolbar category dropdown filter should render
    const categoryButton = page.getByRole("button", { name: "Category" });
    await expect(categoryButton).toBeVisible();

    // Selecting a category updates URL state without full page reload
    await categoryButton.click();
    await page.getByRole("option", { name: "FAANG+" }).click();
    await expect(page).toHaveURL(/category=FAANG%2B/);
  });

  test("debounces search input into URL query parameter", async ({ page }) => {
    const searchInput = page.getByRole("searchbox", { name: /search role/i });
    await expect(searchInput).toBeVisible();

    await searchInput.fill("engineer");
    // After debounce interval, URL should synchronize
    await expect(page).toHaveURL(/q=engineer/, { timeout: 3_000 });
  });

  test("toggles mobile detail pane and back navigation", async ({ page, isMobile }) => {
    test.skip(!isMobile, "Mobile-specific split-pane flow");

    // Locate job link items
    const jobLink = page.locator("a[href*='jobId=']").first();
    await jobLink.waitFor({ state: "visible", timeout: 5_000 }).catch(() => null);
    if (await jobLink.isVisible()) {
      await jobLink.click();

      // On mobile, detail pane should be visible and back button present
      const backBtn = page.getByRole("button", { name: /back to results/i });
      await expect(backBtn).toBeVisible();

      // Clicking back button closes detail pane and restores job feed
      await backBtn.click();
      await expect(backBtn).not.toBeVisible();
      await expect(jobLink).toBeVisible();
    }
  });
});
