const { test, expect } = require('@playwright/test');

test.describe('Session expiry', () => {
  test('an invalid stored token lands the user back on the login gate with no job cards', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('jobcopilot_access_token', 'this-is-not-a-real-jwt');
      localStorage.setItem('jobcopilot_portals_configured', 'true');
    });

    await page.goto('/');

    // The app boots as "authenticated" (token present) and immediately fetches
    // /jobs, which 401s; authFetch's forceReauth() then clears storage and
    // routes back to the login gate.
    await expect(page.locator('#view-login')).toHaveClass(/active/, { timeout: 10_000 });
    await expect(page.locator('.job-card')).toHaveCount(0);

    const token = await page.evaluate(() => localStorage.getItem('jobcopilot_access_token'));
    expect(token).toBeNull();
  });
});
