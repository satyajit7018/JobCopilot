const { test, expect } = require('@playwright/test');

test.describe('Login gate', () => {
  test('renders on first load with both sign-in options', async ({ page }) => {
    await page.goto('/');

    const loginView = page.locator('#view-login');
    await expect(loginView).toBeVisible();
    await expect(loginView).toHaveClass(/active/);

    await expect(page.locator('#btn-login-google')).toBeVisible();
    await expect(page.locator('#btn-login-demo')).toBeVisible();
    await expect(page.locator('#login-email-input')).toBeVisible();

    // No cockpit data should be present before authentication.
    await expect(page.locator('.job-card')).toHaveCount(0);
  });

  test('Sign in with Google is blocked with an inline error when email is empty', async ({ page }) => {
    await page.goto('/');

    await page.locator('#login-email-input').fill('');
    await page.locator('#btn-login-google').click();

    const errorEl = page.locator('#login-email-error');
    await expect(errorEl).toBeVisible();
    await expect(errorEl).toContainText('email');

    // Still on the login gate — no auth token was set.
    await expect(page.locator('#view-login')).toHaveClass(/active/);
    const token = await page.evaluate(() => localStorage.getItem('jobcopilot_access_token'));
    expect(token).toBeNull();
  });

  test('"Instant Demo as Alex Mercer" logs in and clears the login gate', async ({ page }) => {
    await page.goto('/');

    await page.locator('#btn-login-demo').click();

    // Demo login issues a real token and routes away from the login view —
    // either straight to the portal-connect step or the pipeline, depending
    // on whether onboarding was already completed for this browser storage.
    await expect(page.locator('#view-login')).not.toHaveClass(/active/, { timeout: 10_000 });

    const token = await page.evaluate(() => localStorage.getItem('jobcopilot_access_token'));
    expect(token).toBeTruthy();

    const displayName = await page.locator('#user-display-name').textContent();
    expect(displayName).toContain('Alex Mercer');
  });
});
