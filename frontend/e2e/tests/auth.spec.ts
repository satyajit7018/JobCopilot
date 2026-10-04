import { expect, test } from "@playwright/test";
import { signIn, uniqueEmail, useSession } from "../helpers/api";

test.describe("Signing in", () => {
  test("sends signed-out visitors to the sign-in page", async ({ page }) => {
    await page.goto("/jobs");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  });

  test("creating an account starts first-run setup", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "Create an account" }).click();
    await page.getByLabel("Full name").fill("Priya Tester");
    await page.getByLabel("Email", { exact: true }).fill(uniqueEmail("register"));

    // Passwords under 12 characters are rejected before anything is sent.
    await page.getByLabel("Password").fill("short");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText(/at least 12 characters/i)).toBeVisible();

    await page.getByLabel("Password").fill(`E2e-${Date.now()}-long-pass`);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/setup$/);
    await expect(page.getByRole("heading", { name: "Start with your resume" })).toBeVisible();
  });

  test("a wrong password shows an error and stays on sign-in", async ({ page }) => {
    const email = uniqueEmail("wrongpw");
    await signIn(email);
    await page.goto("/login");
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password").fill("definitely-not-the-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  test("signing out ends the session", async ({ page }) => {
    const s = await signIn(uniqueEmail("signout"), "Sign Out Tester");
    await useSession(page, s);
    await page.goto("/settings");
    await page.getByRole("button", { name: /Sign Out Tester/ }).click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login$/);
    expect(await page.evaluate(() => localStorage.getItem("jobcopilot_access_token"))).toBeNull();
  });

  test("an expired session returns to sign-in instead of showing errors", async ({ page }) => {
    await useSession(page, { access_token: "expired.invalid.token", refresh_token: "expired.invalid.refresh" });
    await page.goto("/applications");
    await expect(page).toHaveURL(/\/login$/);
  });
});
