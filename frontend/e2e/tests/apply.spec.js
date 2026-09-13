const { test, expect } = require('@playwright/test');
const { apiLogin, seedJob, primeAuthenticatedSession } = require('../helpers/api');

test.describe('Apply Now', () => {
  test('optimistically moves the card off Discovered and shows a toast', async ({ page }) => {
    const { access_token, refresh_token } = await apiLogin();
    await seedJob(access_token, { company: 'Helix Robotics', title: 'Platform Engineer (Go)', status: 'DISCOVERED' });

    await primeAuthenticatedSession(page, { accessToken: access_token, refreshToken: refresh_token });
    await page.goto('/');

    const discoveredCards = page.locator('#cards-discovered .job-card');
    await expect(discoveredCards).toHaveCount(1, { timeout: 10_000 });

    const applyBtn = page.locator('#cards-discovered .job-card', { hasText: 'Helix Robotics' })
      .locator('[data-action="applyToJob"]');
    await expect(applyBtn).toBeVisible();
    await applyBtn.click();

    // Optimistic UI update: the app flips the job's local status to SUBMITTED
    // and re-renders synchronously, before the backend /bot/apply call
    // resolves — so the card leaves the Discovered column immediately.
    await expect(page.locator('#cards-discovered .job-card', { hasText: 'Helix Robotics' })).toHaveCount(0, { timeout: 3_000 });

    // A toast is shown once the backend call settles (success keeps the card
    // in Submitted; a failure reverts it and shows an error toast instead —
    // either way the optimistic-update-then-toast contract holds).
    const toast = page.locator('.toast').first();
    await expect(toast).toBeVisible({ timeout: 20_000 });
    await expect(toast).toContainText(/apply|applied/i);
  });
});
