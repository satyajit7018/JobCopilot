const { test, expect } = require('@playwright/test');
const { apiLogin, seedJob, primeAuthenticatedSession } = require('../helpers/api');

test.describe('Pipeline', () => {
  test('renders job cards, opens job details on click, and Escape closes the modal', async ({ page }) => {
    const { access_token, refresh_token } = await apiLogin();
    await seedJob(access_token, { company: 'Nimbus Systems', title: 'Senior Backend Engineer (Python)', status: 'DISCOVERED' });
    await seedJob(access_token, { company: 'Vertex Labs', title: 'Frontend Engineer (React)', status: 'DISCOVERED' });

    await primeAuthenticatedSession(page, { accessToken: access_token, refreshToken: refresh_token });
    await page.goto('/');

    await expect(page.locator('#view-pipeline')).toHaveClass(/active/);

    const cards = page.locator('#cards-discovered .job-card');
    await expect(cards).toHaveCount(2, { timeout: 10_000 });

    const nimbusCard = page.locator('#cards-discovered .job-card', { hasText: 'Nimbus Systems' });
    await expect(nimbusCard).toBeVisible();

    // Clicking the card body (not an inner action button) opens the details modal.
    await nimbusCard.click();

    const modal = page.locator('#modal-job-details');
    await expect(modal).toHaveClass(/active/);
    await expect(page.locator('#title-job-details')).toHaveText('Senior Backend Engineer (Python)');
    await expect(page.locator('#details-company-name')).toHaveText('Nimbus Systems');

    await page.keyboard.press('Escape');
    await expect(modal).not.toHaveClass(/active/);
  });

  test('search filters cards by skill/title', async ({ page }) => {
    const { access_token, refresh_token } = await apiLogin();
    await seedJob(access_token, { company: 'Nimbus Systems', title: 'Senior Backend Engineer (Python)', status: 'DISCOVERED' });
    await seedJob(access_token, { company: 'Vertex Labs', title: 'Frontend Engineer (React)', status: 'DISCOVERED' });

    await primeAuthenticatedSession(page, { accessToken: access_token, refreshToken: refresh_token });
    await page.goto('/');

    const cards = page.locator('#cards-discovered .job-card');
    await expect(cards).toHaveCount(2, { timeout: 10_000 });

    await page.locator('#pipeline-search-input').fill('react');

    await expect(cards).toHaveCount(1, { timeout: 5_000 });
    await expect(cards.first()).toContainText('Vertex Labs');

    await page.locator('#pipeline-search-input').fill('');
    await expect(cards).toHaveCount(2);
  });
});
