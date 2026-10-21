import { expect, test } from "@playwright/test";
import { makePremium, seedJob, seedProfile, signIn, uniqueEmail, useSession } from "../helpers/api";

test.describe("Jobs and review", () => {
  test("lists matches, filters them, and opens a review; with sending off, Premium applies on the site", async ({ page }) => {
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
    await expect(page.getByRole("link", { name: /at Vertex Labs/ })).toBeVisible();
    await page.getByLabel("Search jobs").fill("");
    await expect(rows).toHaveCount(2);

    // "Not interested" hides a job; Undo brings it back.
    await page.getByRole("button", { name: "Not interested in Frontend Engineer (React) at Vertex Labs" }).click();
    await expect(rows).toHaveCount(1);
    await page.getByRole("button", { name: "Undo" }).click();
    await expect(rows).toHaveCount(2);

    await page.getByRole("link", { name: "Review Senior Backend Engineer (Python) at Nimbus Systems" }).click();
    await expect(page.getByRole("heading", { name: "Senior Backend Engineer (Python)" })).toBeVisible();
    // Sending for real is switched off on the server (the default), so nothing offers it:
    // Premium applies on the employer's site like everyone else, with its tailored materials.
    await expect(page.getByRole("link", { name: /Open the application/ })).toBeVisible();
    await expect(page.getByText("Your tailored resume and cover letter are under “Your application”.", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Start practice run" })).toHaveCount(0);
    await expect(page.getByText("Submit for real")).toHaveCount(0);
    await expect(page.getByText("Let JobCopilot write your application")).toHaveCount(0);
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
    await expect(page.getByText("Let JobCopilot write your application")).toBeVisible();
    await expect(page.getByText("Let JobCopilot apply for you")).toHaveCount(0);

    await page.getByRole("button", { name: "I've applied" }).click();
    await expect(page.getByText("Added to your applications")).toBeVisible();
    await page.goto("/applications");
    await expect(page.getByRole("region", { name: "Applied" }).getByText("Senior Backend Engineer (Python)")).toBeVisible();

    await page.goto("/plans");
    await expect(page.getByRole("heading", { name: "Premium" })).toBeVisible();
    // Not promised while the server doesn't send applications.
    await expect(page.getByText("Automatic applying, with your approval for each one")).toHaveCount(0);
  });
});
