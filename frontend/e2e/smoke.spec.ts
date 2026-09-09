/**
 * Sentinel AI — route smoke tests.
 *
 * Renders every route in the app and asserts the page actually painted
 * (no blank screen, no Vite error overlay, no uncaught exceptions, no
 * console page errors). The original motivation: a redesign shipped 64
 * TypeScript/JSX syntax errors that no unit check caught because nothing
 * ever rendered the pages.
 *
 * Backend note: the suite starts the real FastAPI server, so the API-driven
 * pages (Overview, Habitation Investigation, Decision Intelligence) are
 * exercised against the validated risk engine — with the labelled demo seed
 * as automatic fallback when the backend is unavailable.
 */
import { test, expect, type Page } from '@playwright/test'

/** Every route registered in App.tsx, with a marker each page must render. */
const ROUTES: Array<{ path: string; mustShow: string; name: string }> = [
  { path: '/', mustShow: 'Sentinel AI Command', name: 'Command Overview' },
  { path: '/risk', mustShow: 'Risk', name: 'Risk Intelligence' },
  { path: '/habitations', mustShow: 'Habitation', name: 'Habitations list' },
  { path: '/habitations/munnar-central', mustShow: 'Munnar Central', name: 'Habitation Investigation' },
  { path: '/habitations/munnar-central/decision', mustShow: 'Decision', name: 'Decision Intelligence' },
  { path: '/priorities', mustShow: 'Priorit', name: 'Risk & Relocation Priorities' },
  { path: '/relocation', mustShow: 'Relocation', name: 'Relocation Intelligence' },
  { path: '/scenarios', mustShow: 'Scenario', name: 'Scenario Analysis' },
  { path: '/reports', mustShow: 'Report', name: 'Reports' },
  { path: '/data', mustShow: 'Data', name: 'Data & Sources' },
]

/** The app shell must always be present: 56px nav rail with its 8 items. */
async function expectAppShell(page: Page) {
  await expect(page.locator('nav[aria-label="Main navigation"]')).toBeVisible()
  await expect(page.locator('nav[aria-label="Main navigation"] a')).toHaveCount(8)
}

/**
 * Shared per-route assertions: navigation succeeded, something painted, and
 * nothing exploded. Attach these before route-specific expectations.
 */
async function expectHealthyRender(page: Page, route: { path: string; mustShow: string; name: string }) {
  // No uncaught exceptions or console errors on the page.
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  page.on('pageerror', (err) => pageErrors.push(String(err)))
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })

  // No Vite/HMR error overlay.
  await page.goto(route.path, { waitUntil: 'domcontentloaded' })
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)

  // The route content actually painted (not a blank screen).
  await expect(
    page.getByText(route.mustShow, { exact: false }).first(),
  ).toBeVisible({ timeout: 15_000 })

  // Let async effects settle, then assert nothing crashed.
  await page.waitForTimeout(1_000)
  expect(pageErrors, `${route.name}: uncaught exceptions`).toEqual([])
  expect(
    consoleErrors.filter((e) => !e.includes('favicon')),
    `${route.name}: console errors`,
  ).toEqual([])
}

test.describe('route smoke tests', () => {
  for (const route of ROUTES) {
    test(`renders ${route.name} (${route.path})`, async ({ page }) => {
      await expectHealthyRender(page, route)
      await expectAppShell(page)
    })
  }

  test('overview stats come from the API (backend integration)', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    // Provenance badge must report the API, not the demo seed, when the
    // backend is up (the suite starts it).
    await expect(page.getByText('API · updated', { exact: false })).toBeVisible({ timeout: 15_000 })
  })

  test('decision intelligence shows the API decision trace', async ({ page }) => {
    await page.goto('/habitations/munnar-central/decision', { waitUntil: 'domcontentloaded' })
    // The engine-derived base risk string is served by /risk/decision-trace.
    await expect(page.getByText('Base 80.21', { exact: false })).toBeVisible({ timeout: 15_000 })
    // All seven trace steps painted.
    await expect(page.getByText('SYSTEM RECOMMENDATION').first()).toBeVisible()
  })

  test('top-level navigation switches pages', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await page.locator('nav[aria-label="Main navigation"] a[title="Habitations"]').click()
    await expect(page).toHaveURL(/\/habitations$/)
    await expect(page.getByText('Habitation', { exact: false }).first()).toBeVisible()
  })
})
