import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { seedJob, seedProfile, signIn, uniqueEmail, useSession } from "../helpers/api";

// Fails on serious or critical WCAG 2.1 AA issues on the main screens.
async function audit(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const blocking = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(blocking.map((v) => `${v.id}: ${v.help} at ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

test.describe("Accessibility", () => {
  test("sign-in page", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
    await audit(page);
  });

  test("signed-in screens", async ({ page }) => {
    const s = await signIn(uniqueEmail("a11y"));
    await seedProfile(s);
    await seedJob(s, { company: "Nimbus Systems", title: "Backend Engineer" });
    await seedJob(s, { company: "Helix Robotics", title: "Platform Engineer", status: "SUBMITTED" });
    await useSession(page, s);

    for (const [path, heading] of [
      ["/", "Today"],
      ["/jobs", "Jobs"],
      ["/applications", "Applied"],
      ["/profile", "Profile"],
      ["/settings", "Settings"],
      ["/plans", "Plans"],
      ["/prep", "Prep"],
    ] as const) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
      await page.waitForLoadState("networkidle");
      await audit(page);
    }
  });
});
