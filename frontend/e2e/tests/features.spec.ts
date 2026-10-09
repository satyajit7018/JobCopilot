import { expect, test } from "@playwright/test";
import { seedJob, seedProfile, signIn, uniqueEmail, useSession } from "../helpers/api";

test.describe("Retention features", () => {
  test("save a job for later, filter to saved, and unsave", async ({ page }) => {
    const s = await signIn(uniqueEmail("save"));
    await seedProfile(s);
    await seedJob(s, { company: "Nimbus Systems", title: "Backend Engineer" });
    await seedJob(s, { company: "Vertex Labs", title: "Frontend Engineer" });
    await useSession(page, s);

    await page.goto("/jobs");
    const rows = page.getByRole("link", { name: /^Review / });
    await expect(rows).toHaveCount(2);
    await page.getByRole("button", { name: "Save Backend Engineer at Nimbus Systems" }).click();
    await page.getByRole("button", { name: /^Saved \(1\)$/ }).click();
    await expect(rows).toHaveCount(1);
    await expect(page.getByText("Nimbus Systems", { exact: true })).toBeVisible();

    // Saved survives a reload, and can be undone from the review page.
    await page.reload();
    await page.getByRole("link", { name: "Review Backend Engineer at Nimbus Systems" }).click();
    await page.getByRole("button", { name: "Saved", exact: true }).click();
    await expect(page.getByRole("button", { name: "Save", exact: true })).toBeVisible();
  });

  test("Find new jobs reports what it found", async ({ page }) => {
    const s = await signIn(uniqueEmail("find"));
    await seedProfile(s);
    await seedJob(s, { company: "Nimbus Systems", title: "Backend Engineer" });
    await useSession(page, s);
    // The real search calls dozens of live job sites; the result is stubbed here.
    await page.route("**/api/discovery/run", (r) => r.fulfill({ json: { status: "success", matched_and_saved: 3, total_sourced: 2400 } }));

    await page.goto("/jobs");
    await page.getByRole("button", { name: "Find new jobs" }).click();
    await expect(page.getByText("Found 3 new matches. They're marked New.")).toBeVisible();

    await page.route("**/api/discovery/run", (r) =>
      r.fulfill({ status: 429, json: { detail: "You just searched. We also check for new jobs every hour; try again in 14 min." } }),
    );
    await page.getByRole("button", { name: "Find new jobs" }).click();
    await expect(page.getByText(/try again in 14 min/)).toBeVisible();
  });

  test("send feedback from the account menu", async ({ page }) => {
    const s = await signIn(uniqueEmail("feedback"));
    await seedProfile(s);
    await useSession(page, s);

    await page.goto("/");
    await page.getByRole("button", { name: /E2E Tester/ }).first().click();
    await page.getByRole("menuitem", { name: "Send feedback" }).click();
    await page.getByLabel("What's working, what isn't, or what you'd like to see?").fill("Please add saved searches.");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByText("Thanks, we got it.")).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await expect(page.getByRole("dialog")).toBeHidden();
  });

  test("getting-started checklist tracks progress and can be hidden", async ({ page }) => {
    const s = await signIn(uniqueEmail("checklist"));
    await seedProfile(s);
    const job = await seedJob(s, { company: "Nimbus Systems", title: "Backend Engineer" });
    await useSession(page, s);

    await page.goto("/");
    const checklist = page.getByRole("region", { name: /Getting started/ });
    await expect(checklist.getByText("1 of 6 done")).toBeVisible();
    await page.goto(`/jobs/${job}`);
    await expect(page.getByRole("heading", { name: "Backend Engineer" })).toBeVisible();
    await page.goto("/");
    await expect(checklist.getByText("2 of 6 done")).toBeVisible();
    await checklist.getByRole("button", { name: "Hide" }).click();
    await expect(checklist).toBeHidden();
  });
});
