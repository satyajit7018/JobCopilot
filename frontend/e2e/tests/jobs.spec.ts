import { expect, test } from "@playwright/test";
import { makePremium, seedJob, seedProfile, signIn, uniqueEmail, useSession } from "../helpers/api";

test.describe("Jobs and review", () => {
  test("lists matches, filters them, and opens a review that never applies without approval", async ({ page }) => {
    const s = await signIn(uniqueEmail("jobs"));
    makePremium(s);
    await seedProfile(s);
    await seedJob(s, { company: "Nimbus Systems", title: "Senior Backend Engineer (Python)" });
    await seedJob(s, { company: "Vertex Labs", title: "Frontend Engineer (React)" });
    await useSession(page, s);

    await page.goto("/jobs");
    const rows = page.getByRole("link", { name: /^Review / });
    await expect(rows).toHaveCount(2);

    await page.getByLabel("Search jobs").fill("react");
    await expect(rows).toHaveCount(1);
    await expect(page.getByText("Vertex Labs", { exact: true })).toBeVisible();
    await page.getByLabel("Search jobs").fill("");
    await expect(rows).toHaveCount(2);

    await page.getByRole("link", { name: "Review Senior Backend Engineer (Python) at Nimbus Systems" }).click();
    await expect(page.getByRole("heading", { name: "Senior Backend Engineer (Python)" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Start practice run" })).toBeVisible();

    // Real submission stays locked until materials are prepared and both boxes are checked.
    await page.getByText("Submit for real").click();
    await expect(page.getByRole("button", { name: "Approve and submit" })).toBeDisabled();
    await expect(page.getByText("Prepare your application first so you can read it.")).toBeVisible();
  });

  test("on Free, review offers applying yourself and tracks it", async ({ page }) => {
    const s = await signIn(uniqueEmail("free"));
    await seedProfile(s);
    await seedJob(s, { company: "Nimbus Systems", title: "Senior Backend Engineer (Python)" });
    await useSession(page, s);

    await page.goto("/jobs");
    await page.getByRole("link", { name: "Review Senior Backend Engineer (Python) at Nimbus Systems" }).click();
    await expect(page.getByRole("link", { name: /Open the application/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "Start practice run" })).toHaveCount(0);
    await expect(page.getByText("Let JobCopilot apply for you")).toBeVisible();

    await page.getByRole("button", { name: "I've applied" }).click();
    await expect(page.getByText("Added to your applications")).toBeVisible();
    await page.goto("/applications");
    await expect(page.getByRole("region", { name: "Applied" }).getByText("Senior Backend Engineer (Python)")).toBeVisible();

    await page.goto("/plans");
    await expect(page.getByRole("heading", { name: "Premium" })).toBeVisible();
  });
});
