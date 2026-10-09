import { expect, test } from "@playwright/test";
import { seedJob, seedProfile, signIn, uniqueEmail, useSession } from "../helpers/api";

test.describe("Applications", () => {
  test("shows the board, opens an application, and updates its status", async ({ page }) => {
    const s = await signIn(uniqueEmail("apps"));
    await seedProfile(s);
    await seedJob(s, { company: "Helix Robotics", title: "Platform Engineer (Go)", status: "SUBMITTED" });
    await seedJob(s, { company: "Orbit Pay", title: "Staff Engineer", status: "OFFER" });
    await useSession(page, s);

    await page.goto("/applications");
    await expect(page.getByRole("region", { name: "Applied" }).getByText("Platform Engineer (Go)")).toBeVisible();
    await expect(page.getByRole("region", { name: "Offer" }).getByText("Staff Engineer")).toBeVisible();

    await page.getByRole("link", { name: "Platform Engineer (Go)" }).click();
    await expect(page).toHaveURL(/\/applications\/.+/);
    await expect(page.getByRole("heading", { name: "Follow up" })).toBeVisible();

    await page.getByLabel("Status").selectOption("INTERVIEW");
    await expect(page.getByText("Updated")).toBeVisible();

    const nextYear = new Date().getFullYear() + 1;
    await page.getByLabel("Interview date").fill(`${nextYear}-01-15T10:30`);
    await page.getByRole("button", { name: "Save date" }).click();
    await expect(page.getByText("Date saved")).toBeVisible();
    await expect(page.getByText("Jan 15", { exact: false }).first()).toBeVisible();
    await page.reload();
    await expect(page.getByLabel("Interview date")).toHaveValue(`${nextYear}-01-15T10:30`);
    await page.getByRole("button", { name: "Clear" }).click();
    await expect(page.getByText("Date cleared")).toBeVisible();
    await expect(page.getByLabel("Interview date")).toHaveValue("");

    await page.goto("/applications");
    await expect(page.getByRole("region", { name: "Interviewing" }).getByText("Platform Engineer (Go)")).toBeVisible();
  });

  test("checks an offer against the salary ranges", async ({ page }) => {
    const s = await signIn(uniqueEmail("offer"));
    await seedProfile(s);
    const id = await seedJob(s, { company: "Orbit Pay", title: "Senior Software Engineer", status: "OFFER" });
    await useSession(page, s);

    await page.goto(`/applications/${id}`);
    await page.getByLabel("Base salary").fill("32");
    await page.getByRole("button", { name: "Check this offer" }).click();
    await expect(page.getByText("32 LPA", { exact: true })).toBeVisible();
    await expect(page.getByLabel("What you'd like", { exact: true })).not.toHaveValue("");
  });
});
