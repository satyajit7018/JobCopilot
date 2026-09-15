const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const { apiLogin, seedJob, primeAuthenticatedSession } = require('../helpers/api');

/**
 * Formats critical/serious axe-core violations into an actionable human-readable report.
 */
function formatViolations(violations) {
  return violations
    .map((v, i) => {
      const targets = v.nodes.map((n) => n.target.join(' ')).join('\n      - ');
      return `  ${i + 1}. [${v.impact ? v.impact.toUpperCase() : 'UNKNOWN'}] ${v.id}: ${v.help}\n     Help URL: ${v.helpUrl}\n     Targets:\n      - ${targets}`;
    })
    .join('\n\n');
}

/**
 * Filters violations to critical/serious impacts and asserts that none exist.
 */
function assertNoCriticalOrSeriousViolations(results, stateName) {
  const criticalOrSerious = results.violations.filter(
    (v) => v.impact === 'critical' || v.impact === 'serious'
  );

  if (criticalOrSerious.length > 0) {
    const summary = formatViolations(criticalOrSerious);
    console.error(`\n[A11Y AUDIT FAILURE] ${criticalOrSerious.length} critical/serious violation(s) in "${stateName}":\n${summary}\n`);
  }

  expect(
    criticalOrSerious,
    `Expected 0 critical/serious a11y violations in "${stateName}", but found ${criticalOrSerious.length}:\n${formatViolations(criticalOrSerious)}`
  ).toEqual([]);
}

test.describe('Accessibility (axe-core WCAG 2 A/AA)', () => {
  test('Login gate meets WCAG 2 A/AA critical/serious standards', async ({ page }) => {
    await page.goto('/');

    const loginView = page.locator('#view-login');
    await expect(loginView).toBeVisible();
    await expect(loginView).toHaveClass(/active/);

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();

    assertNoCriticalOrSeriousViolations(results, 'Login gate');
  });

  test('Onboarding portals view meets WCAG 2 A/AA critical/serious standards', async ({ page }) => {
    const { access_token } = await apiLogin();

    // Log in via real token but keep portals unconfigured so onboarding view renders
    await page.addInitScript((token) => {
      localStorage.setItem('jobcopilot_access_token', token);
    }, access_token);

    await page.goto('/');

    const portalsView = page.locator('#view-connect-portals');
    await expect(portalsView).toBeVisible();
    await expect(portalsView).toHaveClass(/active/);
    await expect(page.locator('#btn-continue-cockpit-text')).toBeVisible();

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();

    assertNoCriticalOrSeriousViolations(results, 'Onboarding portals view');
  });

  test('Authenticated pipeline view meets WCAG 2 A/AA critical/serious standards', async ({ page }) => {
    const { access_token, refresh_token } = await apiLogin();
    await seedJob(access_token, {
      company: 'Helix Robotics',
      title: 'Platform Engineer (Go)',
      status: 'DISCOVERED',
    });

    await primeAuthenticatedSession(page, { accessToken: access_token, refreshToken: refresh_token });
    await page.goto('/');

    const cardsDiscovered = page.locator('#cards-discovered');
    await expect(cardsDiscovered).toBeVisible();
    await expect(page.locator('#cards-discovered .job-card')).toHaveCount(1, { timeout: 10_000 });

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();

    assertNoCriticalOrSeriousViolations(results, 'Authenticated pipeline view');
  });
});
