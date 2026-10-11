import { expect, test } from "@playwright/test";
import { makePremium, seedJob, seedProfile, signIn, uniqueEmail, useSession } from "../helpers/api";

test.describe("Guided job search", () => {
  test("Applications is a list with stage filters on phones", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const s = await signIn(uniqueEmail("phone-apps"));
    await seedProfile(s);
    await seedJob(s, { company: "Nimbus Systems", title: "Backend Engineer", status: "SUBMITTED" });
    await seedJob(s, { company: "Helix Robotics", title: "Platform Engineer", status: "INTERVIEW" });
    await useSession(page, s);

    await page.goto("/applications");
    const stages = page.getByRole("group", { name: "Filter by stage" });
    const all = page.getByRole("list", { name: "All applications" });
    await expect(all.getByText(/Nimbus Systems/)).toBeVisible();
    await expect(all.getByText(/Helix Robotics/)).toBeVisible();
    await stages.getByRole("button", { name: "Interviewing 1" }).click();
    const interviewing = page.getByRole("list", { name: "Interviewing" });
    await expect(interviewing.getByText(/Helix Robotics/)).toBeVisible();
    await expect(interviewing.getByText(/Nimbus Systems/)).toBeHidden();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("a reason for hiding a job becomes a rule you can remove in Profile", async ({ page }) => {
    const s = await signIn(uniqueEmail("hide-why"));
    await seedProfile(s);
    await seedJob(s, { company: "Nimbus Systems", title: "Backend Engineer" });
    await seedJob(s, { company: "Vertex Labs", title: "Frontend Engineer" });
    await useSession(page, s);

    await page.goto("/jobs");
    await page.getByRole("button", { name: "Not interested in Backend Engineer at Nimbus Systems" }).click();
    await page.getByRole("group", { name: "Why not? (optional)" }).getByRole("button", { name: "Not this company" }).click();
    await expect(page.getByText("New searches will skip jobs at Nimbus Systems.")).toBeVisible();

    await page.getByRole("link", { name: "Profile" }).first().click();
    const section = page.getByRole("region", { name: "Skipped in new searches" });
    await expect(section.getByRole("listitem")).toHaveText(/^Jobs at Nimbus Systems/);
    await section.getByRole("button", { name: "Remove Jobs at Nimbus Systems" }).click();
    await expect(section).toBeHidden();
  });

  test("filters and scroll position survive opening a job and coming back", async ({ page }) => {
    const s = await signIn(uniqueEmail("keep-place"));
    await seedProfile(s);
    await seedJob(s, { company: "Nimbus Systems", title: "Backend Engineer" });
    await seedJob(s, { company: "Vertex Labs", title: "Frontend Engineer", status: "SAVED" });
    await useSession(page, s);

    await page.goto("/jobs");
    await page.getByRole("button", { name: /^Saved \(/ }).click();
    await expect(page).toHaveURL(/saved=true/);
    await page.getByRole("link", { name: "Review Frontend Engineer at Vertex Labs" }).click();
    await expect(page.getByRole("heading", { name: "Frontend Engineer" })).toBeVisible();
    await page.goBack();
    await expect(page.getByRole("button", { name: /^Saved \(/ })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("link", { name: /^Review / })).toHaveCount(1);
  });

  test("score and upload explain themselves", async ({ page }) => {
    const s = await signIn(uniqueEmail("trust"));
    await seedProfile(s);
    const job = await seedJob(s, { company: "Nimbus Systems", title: "Backend Engineer" });
    await useSession(page, s);
    await page.goto(`/jobs/${job}`);
    await expect(page.getByText("It isn't your chance of getting an interview.")).toBeVisible();
    await page.goto("/profile");
    await page.getByRole("button", { name: /Replace/ }).first().click();
    await expect(page.getByText(/Only you can see your resume/)).toBeVisible();
  });

  test("Premium: AI rewording is shown next to your own words, and you choose", async ({ page }) => {
    const s = await signIn(uniqueEmail("wording"));
    makePremium(s);
    await seedProfile(s);
    const job = await seedJob(s, { company: "Nimbus Systems", title: "Backend Engineer" });
    await useSession(page, s);
    // Tailoring calls the AI and renders a PDF; the result is stubbed here.
    await page.route("**/api/jobs/*/tailor", (r) =>
      r.fulfill({
        json: {
          cover_letter: "Dear Nimbus team,",
          pdf_hash: "x",
          resume_wording: "ai",
          resume_changes: [{ role: "Senior Software Engineer", company: "Example Payments", before: "Built payment APIs", after: "Built payment APIs in Python serving 2M requests a day" }],
        },
      }),
    );
    let chosen = "";
    await page.route("**/api/jobs/*/resume-wording", async (r) => {
      chosen = (r.request().postDataJSON() as { choice: string }).choice;
      await r.fulfill({ json: { status: "success", resume_wording: chosen } });
    });

    await page.goto(`/jobs/${job}`);
    await page.getByRole("button", { name: "Prepare my application" }).click();
    await expect(page.getByText("Built payment APIs", { exact: true })).toBeVisible();
    await expect(page.getByText("Built payment APIs in Python serving 2M requests a day")).toBeVisible();
    await page.getByText("My own words", { exact: true }).click();
    await expect.poll(() => chosen).toBe("original");
  });

  test("Next match walks the list, and Not interested works from the job page", async ({ page }) => {
    const s = await signIn(uniqueEmail("next"));
    await seedProfile(s);
    const first = await seedJob(s, { company: "Nimbus Systems", title: "Backend Engineer" });
    await seedJob(s, { company: "Vertex Labs", title: "Frontend Engineer" });
    await useSession(page, s);

    await page.goto(`/jobs/${first}`);
    await expect(page).toHaveTitle("Backend Engineer at Nimbus Systems · JobCopilot");
    await page.getByRole("button", { name: "Not interested" }).click();
    await expect(page.getByText(/hidden from your matches/)).toBeVisible();
    await page.getByRole("link", { name: /^Next match/ }).click();
    await expect(page.getByRole("heading", { name: "Frontend Engineer" })).toBeVisible();
    // The only other match is hidden now, so there's nowhere further to go.
    await expect(page.getByRole("link", { name: /^Next match/ })).toHaveCount(0);
  });

  test("notes on an application are saved", async ({ page }) => {
    const s = await signIn(uniqueEmail("notes"));
    await seedProfile(s);
    const job = await seedJob(s, { company: "Helix Robotics", title: "Platform Engineer", status: "SUBMITTED" });
    await useSession(page, s);

    await page.goto(`/applications/${job}`);
    await expect(page).toHaveTitle("Platform Engineer at Helix Robotics · JobCopilot");
    await page.getByLabel("Notes", { exact: true }).fill("Spoke to Priya. Follow up Friday.");
    await page.getByRole("button", { name: "Save notes" }).click();
    await expect(page.getByText("Notes saved")).toBeVisible();
    await page.reload();
    await expect(page.getByLabel("Notes", { exact: true })).toHaveValue("Spoke to Priya. Follow up Friday.");
  });

  test("Profile asks before leaving with unsaved changes", async ({ page }) => {
    const s = await signIn(uniqueEmail("unsaved"));
    await seedProfile(s);
    await useSession(page, s);

    await page.goto("/profile");
    await expect(page).toHaveTitle("Profile · JobCopilot");
    await page.getByLabel("Phone").fill("+91 90000 00000");
    await page.getByRole("link", { name: "Today" }).first().click();
    const dialog = page.getByRole("dialog", { name: "Leave without saving?" });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Keep editing" }).click();
    await expect(page).toHaveURL(/\/profile$/);

    await page.getByRole("link", { name: "Today" }).first().click();
    await dialog.getByRole("button", { name: "Save and leave" }).click();
    await expect(page).toHaveURL(/\/$/);
    await page.goto("/profile");
    await expect(page.getByLabel("Phone")).toHaveValue("+91 90000 00000");
  });
});
