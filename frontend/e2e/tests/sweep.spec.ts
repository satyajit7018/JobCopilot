import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { makePremium, seedJob, seedProfile, signIn, uniqueEmail, useSession, type Session } from "../helpers/api";

// Quality sweep: every screen, as Free and Premium, at desktop and phone width.
// Fails on console errors, failed API calls (a 402 means a Free screen called a
// Premium API), sideways scrolling on phones, and serious accessibility issues.

const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "phone", width: 390, height: 844 },
] as const;

interface Problems {
  console: string[];
  requests: string[];
}

function watch(page: Page): Problems {
  const problems: Problems = { console: [], requests: [] };
  page.on("console", (m) => {
    if (m.type() === "error") problems.console.push(m.text());
  });
  page.on("pageerror", (e) => problems.console.push(`pageerror: ${e.message}`));
  page.on("response", (r) => {
    const url = new URL(r.url());
    if (url.pathname.startsWith("/api/") && r.status() >= 400) problems.requests.push(`${r.status()} ${r.request().method()} ${url.pathname}`);
  });
  return problems;
}

async function seed(s: Session) {
  await seedProfile(s);
  const match = await seedJob(s, { company: "Nimbus Systems", title: "Senior Backend Engineer (Python)" });
  await seedJob(s, { company: "Vertex Labs", title: "Frontend Engineer (React)", status: "SAVED" });
  const applied = await seedJob(s, { company: "Helix Robotics", title: "Platform Engineer (Go)", status: "SUBMITTED" });
  await seedJob(s, { company: "Orbit Pay", title: "Staff Engineer", status: "OFFER" });
  return { match, applied };
}

async function checkPage(page: Page, path: string, viewport: string) {
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  await page.waitForLoadState("networkidle");
  if (viewport === "phone") {
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${path} scrolls sideways on a phone`).toBeLessThanOrEqual(1);
  } else {
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const blocking = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(blocking.map((v) => `${path} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
  }
}

for (const plan of ["free", "premium"] as const) {
  for (const vp of VIEWPORTS) {
    test(`every screen works — ${plan}, ${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      const s = await signIn(uniqueEmail(`sweep-${plan}-${vp.name}`));
      if (plan === "premium") makePremium(s);
      const { match, applied } = await seed(s);
      await useSession(page, s);
      const problems = watch(page);

      for (const path of [
        "/",
        "/jobs",
        `/jobs/${match}`,
        "/applications",
        `/applications/${applied}`,
        "/prep",
        "/profile",
        "/settings",
        "/plans",
        "/help",
        "/privacy",
        "/terms",
      ]) {
        await checkPage(page, path, vp.name);
      }

      expect(problems.requests, "failed API calls").toEqual([]);
      expect(problems.console, "console errors").toEqual([]);
    });
  }
}

test("dark mode keeps text readable on every screen", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.setViewportSize({ width: 1280, height: 800 });
  const s = await signIn(uniqueEmail("sweep-dark"));
  const { match, applied } = await seed(s);
  await useSession(page, s);
  const problems = watch(page);
  for (const path of ["/", "/jobs", `/jobs/${match}`, "/applications", `/applications/${applied}`, "/prep", "/profile", "/settings", "/plans", "/help"]) {
    await checkPage(page, path, "desktop");
  }
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(0, 0, 0)");
  expect(problems.console, "console errors").toEqual([]);
});

test("public pages work signed out", async ({ page }) => {
  const problems = watch(page);
  for (const path of ["/login", "/help", "/privacy", "/terms"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  }
  await expect(page).toHaveURL(/\/terms$/);
  expect(problems.console).toEqual([]);
});

test("an unknown address shows Home, and a broken page shows a friendly error", async ({ page }) => {
  const s = await signIn(uniqueEmail("sweep-errors"));
  await seedProfile(s);
  await useSession(page, s);
  await page.goto("/no-such-page");
  await expect(page).toHaveURL(/\/$/);
  // A page file that can't load (after reload too) ends on the friendly error screen.
  await page.route("**/assets/PrepPage-*.js", (r) => r.abort());
  await page.goto("/");
  await page.getByRole("link", { name: "Prep" }).first().click();
  await expect(page.getByRole("heading", { name: "Something went wrong" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Reload" })).toBeVisible();
});
