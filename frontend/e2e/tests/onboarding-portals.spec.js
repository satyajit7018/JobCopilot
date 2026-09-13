const { test, expect } = require('@playwright/test');
const { apiLogin } = require('../helpers/api');

test.describe('Portal onboarding', () => {
  test('connecting a portal updates the CTA reactively and Continue lands on pipeline', async ({ page }) => {
    const { access_token } = await apiLogin();

    // Log in via the real token but deliberately leave portals "not configured"
    // so the app boots straight into the connect-portals onboarding step,
    // exactly like a first-time user after Google SSO.
    await page.addInitScript((token) => {
      localStorage.setItem('jobcopilot_access_token', token);
    }, access_token);

    await page.goto('/');

    const portalsView = page.locator('#view-connect-portals');
    await expect(portalsView).toHaveClass(/active/);

    const ctaText = page.locator('#btn-continue-cockpit-text');
    await expect(ctaText).toHaveText('Continue to Main Cockpit ➔');

    // Connect one portal (LinkedIn) and verify the CTA copy reacts immediately.
    const linkedinCard = page.locator('[data-portal-id="linkedin"]');
    await linkedinCard.click();
    await expect(linkedinCard).toHaveClass(/connected/);
    await expect(ctaText).toHaveText('Continue with 1 Connected Portal ➔');

    // Connect a second portal — CTA copy updates again reactively.
    const naukriCard = page.locator('[data-portal-id="naukri"]');
    await naukriCard.click();
    await expect(ctaText).toHaveText('Continue with 2 Connected Portals ➔');

    await page.locator('#btn-continue-cockpit').click();

    await expect(page.locator('#view-pipeline')).toHaveClass(/active/);
    await expect(portalsView).not.toHaveClass(/active/);
  });
});
