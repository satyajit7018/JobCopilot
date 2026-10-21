import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { seedAnswer, seedProfile, signIn, uniqueEmail, useSession } from "../helpers/api";

// The answers page is hidden behind a server switch until prepared applications ship.
// These tests turn it on in the browser only; the server's answer addresses always work.
async function withPreparedApplications(page: Page) {
  await page.route("**/api/auth/public-config", async (r) => {
    const res = await r.fetch();
    await r.fulfill({ response: res, json: { ...(await res.json()), prepared_applications: true } });
  });
}

test.describe("Application answers", () => {
  test("hidden while the switch is off", async ({ page }) => {
    const s = await signIn(uniqueEmail("answers-off"));
    await seedProfile(s);
    await useSession(page, s);

    await page.goto("/profile");
    await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Application answers" })).toHaveCount(0);
    await page.goto("/profile/answers");
    await expect(page).toHaveURL(/\/profile$/);
  });

  test("answer a common question, then change it", async ({ page }) => {
    const s = await signIn(uniqueEmail("answers"));
    await seedProfile(s);
    await useSession(page, s);
    await withPreparedApplications(page);

    await page.goto("/profile");
    await page.getByRole("link", { name: "Application answers" }).click();
    await expect(page.getByRole("heading", { name: "Application answers" })).toBeVisible();
    // Profile facts are shown, never guessed: nothing has been saved in Profile yet.
    await expect(page.getByText("Expected salary")).toBeVisible();
    await expect(page.getByText("Not saved yet").first()).toBeVisible();

    await page.getByRole("button", { name: "Answer Why should we hire you?" }).click();
    await page.getByLabel("Your answer").fill("I ship small, careful changes quickly.");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(page.getByText("I ship small, careful changes quickly.")).toBeVisible();
    await expect(page.getByText("Updated just now").first()).toBeVisible();

    // Personal questions start at "Prefer not to say" and are optional.
    await page.getByRole("button", { name: "Change Gender" }).click();
    await page.getByText("Woman", { exact: true }).click();
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(page.getByRole("button", { name: "Edit Gender" })).toBeVisible();

    await page.reload();
    await expect(page.getByText("I ship small, careful changes quickly.")).toBeVisible();
    await expect(page.getByText("Woman", { exact: true })).toBeVisible();
  });

  test("edit and delete a saved answer", async ({ page }) => {
    const s = await signIn(uniqueEmail("answers-saved"));
    await seedProfile(s);
    await seedAnswer(s, "Which timezone are you in?", "IST");
    await useSession(page, s);
    await withPreparedApplications(page);

    await page.goto("/profile/answers");
    const question = page.getByRole("paragraph").filter({ hasText: "Which timezone are you in?" });
    await expect(question).toBeVisible();
    await page.getByRole("button", { name: "Edit Which timezone are you in?" }).click();
    await page.getByLabel("Your answer").fill("IST (UTC+5:30)");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(page.getByText("IST (UTC+5:30)")).toBeVisible();

    await page.getByRole("button", { name: "Delete Which timezone are you in?" }).click();
    await page.getByRole("button", { name: "Delete", exact: true }).click();
    await expect(question).toHaveCount(0);
    await expect(page.getByText("Nothing yet.")).toBeVisible();
  });

  test("has no serious accessibility issues, with an editor open", async ({ page }) => {
    const s = await signIn(uniqueEmail("answers-a11y"));
    await seedProfile(s);
    await seedAnswer(s, "Which timezone are you in?", "IST");
    await useSession(page, s);
    await withPreparedApplications(page);

    await page.goto("/profile/answers");
    await expect(page.getByRole("heading", { level: 1, name: "Application answers" })).toBeVisible();
    await page.getByRole("button", { name: "Change Gender" }).click();
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const blocking = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(blocking.map((v) => `${v.id}: ${v.help} at ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
  });
});
