import { test, expect } from "@playwright/test";

test.describe("Job Board & Feed Interactions", () => {
  test.beforeEach(async ({ page, request }) => {
    const email = "playwright-smoke@example.com";
    const password = "SmokeTest123!";

    await request.post("http://127.0.0.1:8000/api/v1/auth/register", {
      data: { email, password },
    });
    await page.goto("/login");
    await page.getByLabel(/email/i).fill(email);
    await page.getByRole("textbox", { name: "Password" }).fill(password);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/jobs/);
  });

  test("loads jobs board and allows category filter interaction", async ({ page }) => {
    await page.goto("/jobs");

    // Board toolbar controls should render
    const categoryButton = page.getByRole("button", { name: "Category" });
    await expect(categoryButton).toBeVisible();

    // Selecting a category updates URL state without full page reload
    await categoryButton.click();
    await page.getByRole("option", { name: "FAANG+" }).click();
    await expect(page).toHaveURL(/category=FAANG%2B/);
  });

  test("debounces search input into URL query parameter", async ({ page }) => {
    await page.goto("/jobs");

    const searchInput = page.getByRole("searchbox", { name: /search role/i });
    await expect(searchInput).toBeVisible();

    await searchInput.fill("engineer");
    // After debounce interval, URL should synchronize
    await expect(page).toHaveURL(/q=engineer/, { timeout: 3_000 });
  });

  test("toggles mobile detail pane and back navigation", async ({ page, isMobile }) => {
    test.skip(!isMobile, "Mobile-specific split-pane flow");

    await page.goto("/jobs");

    // Locate job link items
    const jobLink = page.locator("a[href*='jobId=']").first();
    if (await jobLink.isVisible()) {
      await jobLink.click();

      // On mobile, detail pane should be visible and back button present
      const backBtn = page.getByRole("button", { name: /back to roles/i });
      await expect(backBtn).toBeVisible();

      // Clicking back button closes detail pane and restores job feed
      await backBtn.click();
      await expect(backBtn).not.toBeVisible();
      await expect(jobLink).toBeVisible();
    }
  });
});
