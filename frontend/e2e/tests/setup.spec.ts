import { expect, test } from "@playwright/test";
import { SAMPLE_RESUME, signIn, uniqueEmail, useSession } from "../helpers/api";

test.describe("First-run setup", () => {
  test("reads a pasted resume, saves preferences, and can be finished later", async ({ page }) => {
    await useSession(page, await signIn(uniqueEmail("setup")));
    await page.goto("/");
    await expect(page).toHaveURL(/\/setup$/);

    await page.getByRole("button", { name: /Paste the text instead/ }).click();
    await page.getByLabel("Resume text").fill(SAMPLE_RESUME);
    await page.getByRole("button", { name: "Use this text" }).click();

    // Step 2 is filled in from the resume.
    // Check what we read: the employer comes from the resume, and corrections are saved.
    await expect(page.getByRole("heading", { name: "Check what we read" })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByLabel("Company").first()).toHaveValue("Example Payments");
    await page.getByLabel("Add skills").fill("GraphQL, gRPC");
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByRole("button", { name: "Remove gRPC" })).toBeVisible();
    await page.getByRole("button", { name: "Looks right, continue" }).click();

    await expect(page.getByRole("heading", { name: "What kind of role are you after?" })).toBeVisible();
    await expect(page.getByLabel("Where you live")).toHaveValue(/Pune/);
    await page.getByText("Remote only").click();
    await page.getByLabel("Expected salary").fill("30 LPA");
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 3. The real search reaches external job boards, so the suite stops here.
    await expect(page.getByRole("heading", { name: "Where should we look?" })).toBeVisible();
    await page.getByRole("button", { name: "Finish later" }).click();
    await expect(page).toHaveURL(/\/$/);

    // The answers were saved.
    await page.goto("/profile");
    await expect(page.getByText("gRPC", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Expected salary")).toHaveValue("30 LPA");
    await expect(page.getByRole("radio", { name: "Remote only" })).toBeChecked();
  });
});
