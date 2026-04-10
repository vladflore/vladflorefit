import { expect, test } from '@playwright/test';

async function waitForLibrary(page) {
  await page.goto('/index.html');
  await expect(page.locator('#container')).toBeVisible();
  await expect(page.locator('#loading')).not.toBeVisible();
  await expect(page.locator('#exercises-row [data-exercise-id]').first()).toBeVisible();
}

test.describe('Flexary UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('https://www.googletagmanager.com/**', route => route.abort());
    await page.goto('/index.html');
    await page.evaluate(() => {
      localStorage.clear();
    });
  });

  test('renders the main library with exercise cards', async ({ page }) => {
    await waitForLibrary(page);

    await expect(page.getByRole('heading', { name: 'Welcome to Flexary' })).toBeVisible();
    await expect(page.locator('#exercise-stats')).toContainText('exercises');
    expect(await page.locator('#exercises-row [data-exercise-id]').count()).toBeGreaterThan(20);
    await expect(page.locator('#empty-state')).toBeHidden();
  });

  test('search filters the exercise list', async ({ page }) => {
    await waitForLibrary(page);

    await page.locator('#search-input').fill('squat');
    expect(await page.locator('#exercises-row [data-exercise-id]').count()).toBeGreaterThanOrEqual(2);
    await expect(page.locator('#exercises-row')).toContainText('Body Weight Squat');
    await expect(page.locator('#exercises-row')).toContainText('Goblet Squat');
  });

  test('language switch reloads translated UI', async ({ page }) => {
    await waitForLibrary(page);

    await page.locator('#lang-select').selectOption('es');
    await expect(page.getByRole('heading', { name: 'Bienvenido a Flexary' })).toBeVisible();
    await expect(page.locator('#search-input')).toHaveAttribute('placeholder', 'Busca por nombre, categoría o parte del cuerpo');
  });

  test('detail page renders exercise information', async ({ page }) => {
    await page.goto('/detail.html?exercise_id=1');

    await expect(page.locator('#container')).toBeVisible();
    await expect(page.locator('#exercise-name')).toHaveText('Body Weight Squat');
    await expect(page.locator('#exercise-instructions')).toContainText('Stand with feet shoulder-width apart');
    await expect(page.locator('#key-cues-container')).toContainText('Keep knees tracking over toes');
  });

  test('detail page prefers custom_video_id over the library video', async ({ page }) => {
    await page.route('**/src/js/auth.js', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/javascript',
        body: '',
      });
    });
    await page.addInitScript(() => {
      window.flexaryAuth = {
        ready: Promise.resolve(),
        state: {
          session: { access_token: 'test-token' },
          user: { email: 'tester@example.com' },
        },
        getCurrentUser: async () => ({ email: 'tester@example.com' }),
      };
      localStorage.setItem('flexary_auth_session', JSON.stringify({ access_token: 'test-token' }));
    });
    await page.goto('/detail.html?exercise_id=1&custom_video_id=0EpP3pYUYTk');

    await expect(page.locator('#container')).toBeVisible();
    await expect(page.locator('#exercise-video')).toHaveAttribute('src', /0EpP3pYUYTk/);
    await expect(page.locator('#exercise-video')).not.toHaveAttribute('src', /l83R5PblSMA/);
  });

  test('detail page ignores custom_video_id for guests', async ({ page }) => {
    await page.goto('/detail.html?exercise_id=1&custom_video_id=0EpP3pYUYTk');

    await expect(page.locator('#container')).toBeVisible();
    await expect(page.locator('#exercise-video')).toHaveAttribute('src', /l83R5PblSMA/);
    await expect(page.locator('#exercise-video')).not.toHaveAttribute('src', /0EpP3pYUYTk/);
  });

  test('adding an exercise creates a workout entry', async ({ page }) => {
    await waitForLibrary(page);

    const firstCard = page.locator('#exercises-row [data-exercise-id]').first();
    const exerciseName = (await firstCard.getAttribute('data-exercise-name')) ?? '';
    await firstCard.locator('#add-ex-to-workout').click();

    await expect(page.locator('.exercise-overlay')).toBeVisible();
    await page.locator('.exercise-overlay button').filter({ hasText: 'Add' }).click();

    await expect(page.locator('#toggle-workout-sidebar .workout-count-badge')).toHaveText('1');
    await page.locator('#toggle-workout-sidebar').click();
    await expect(page.locator('#workout-list-container')).toContainText(exerciseName);
  });

  test('creating a custom exercise adds a custom card and persists after reload', async ({ page }) => {
    await waitForLibrary(page);

    const customName = 'Playwright Custom Row';

    await page.locator('#add-custom-exercise').click();
    await expect(page.locator('.cm-overlay')).toBeVisible();

    const modal = page.locator('.cm-overlay');
    await modal.getByPlaceholder('e.g. Resistance Band Row').fill(customName);
    await modal.locator('select').selectOption('Strength');
    await modal.getByPlaceholder('e.g. Legs, Core').fill('Back, Arms');
    await modal.getByRole('button', { name: 'Next →' }).click();

    await expect(modal).toContainText('Step 2 of 2');
    await modal.getByPlaceholder('Step-by-step instructions...').fill('Pull the band toward your torso.');
    await modal.getByRole('button', { name: 'Add' }).click();

    const customCard = page.locator(`#exercises-row [data-exercise-name="${customName}"]`);
    await expect(customCard).toBeVisible();
    await expect(customCard.locator('.exercise-card')).toHaveClass(/exercise-card--custom/);

    await page.reload();
    await expect(page.locator('#container')).toBeVisible();
    await expect(page.locator(`#exercises-row [data-exercise-name="${customName}"]`)).toBeVisible();
  });

  test('guests do not see stored custom workout video traces', async ({ page }) => {
    await page.evaluate(() => {
      localStorage.setItem('workouts', JSON.stringify([
        {
          id: '11111111-1111-1111-1111-111111111111',
          execution_date: '2026-04-11',
          name: 'Guest Workout',
          superset_rounds: {},
          breaks: {},
          exercises: [
            {
              id: 1,
              internal_id: '22222222-2222-2222-2222-222222222222',
              name: 'Body Weight Squat',
              sets: 1,
              reps: '10',
              time: '',
              distance: '',
              notes: '',
              superset_id: '',
              rest_between_sets: 0,
              custom_video_id: '0EpP3pYUYTk',
            },
          ],
        },
      ]));
    });

    await page.goto('/index.html');
    await expect(page.locator('#container')).toBeVisible();
    await expect(page.locator('#toggle-workout-sidebar .workout-count-badge')).toHaveText('1');
    await page.locator('#toggle-workout-sidebar').click();
    await expect(page.locator('#workout-list-container')).toContainText('Body Weight Squat');
    await expect(page.locator('.exercise-item-video-link')).toHaveCount(0);

    await page.locator('#workout-list-container #workout-item-edit').first().click();
    await expect(page.getByPlaceholder('YouTube URL or video ID')).toHaveCount(0);
  });
});

test.describe('Stretching category', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('https://www.googletagmanager.com/**', route => route.abort());
    await page.goto('/index.html');
    await page.evaluate(() => localStorage.clear());
    await waitForLibrary(page);
  });

  test('Stretching badge appears in the filter panel with bg-primary class', async ({ page }) => {
    const badge = page.locator('[data-category="Stretching"]');
    await expect(badge).toBeVisible();
    await expect(badge).toHaveClass(/bg-primary/);
    await expect(badge).toContainText('Stretching');
  });

  test('filtering by Stretching shows only Stretching exercises', async ({ page }) => {
    await page.locator('[data-category="Stretching"]').click();

    const cards = page.locator('#exercises-row [data-exercise-id]');
    await expect(cards.first()).toBeVisible();
    const count = await cards.count();
    expect(count).toBeGreaterThanOrEqual(1);

    for (let i = 0; i < count; i++) {
      await expect(cards.nth(i).locator('#category-badge')).toContainText('Stretching');
    }
  });

  test('Stretching exercise card shows bg-primary badge', async ({ page }) => {
    await page.locator('#search-input').fill('Quadriceps Stretch');
    const card = page.locator('#exercises-row [data-exercise-id]').first();
    await expect(card).toBeVisible();
    await expect(card.locator('#category-badge')).toContainText('Stretching');
    await expect(card.locator('#category-badge')).toHaveClass(/bg-primary/);
  });

  test('detail page shows Stretching badge for stretching exercise', async ({ page }) => {
    await page.goto('/detail.html?exercise_id=66');
    await expect(page.locator('#container')).toBeVisible();
    await expect(page.locator('#exercise-name')).toHaveText('Quadriceps Stretch');
    await expect(page.locator('#category-badge')).toContainText('Stretching');
    await expect(page.locator('#category-badge')).toHaveClass(/bg-primary/);
  });

  test('selecting multiple category filters including Stretching does not error', async ({ page }) => {
    await page.locator('[data-category="Strength"]').click();
    await page.locator('[data-category="Stretching"]').click();

    await expect(page.locator('#exercises-row [data-exercise-id]').first()).toBeVisible();
    await expect(page.locator('#exercise-stats')).toBeVisible();
  });

  test('custom exercise with Stretching category shows bg-primary badge', async ({ page }) => {
    const customName = 'Playwright Stretching Test';

    await page.locator('#add-custom-exercise').click();
    await expect(page.locator('.cm-overlay')).toBeVisible();

    const modal = page.locator('.cm-overlay');
    await modal.getByPlaceholder('e.g. Resistance Band Row').fill(customName);
    await modal.locator('select').selectOption('Stretching');
    await modal.getByPlaceholder('e.g. Legs, Core').fill('Full Body');
    await modal.getByRole('button', { name: 'Next →' }).click();

    await expect(modal).toContainText('Step 2 of 2');
    await modal.getByRole('button', { name: 'Add' }).click();

    const customCard = page.locator(`#exercises-row [data-exercise-name="${customName}"]`);
    await expect(customCard).toBeVisible();
    await expect(customCard.locator('#category-badge')).toContainText('Stretching');
    await expect(customCard.locator('#category-badge')).toHaveClass(/bg-primary/);
  });
});
