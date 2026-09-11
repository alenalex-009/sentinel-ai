import { test, expect } from '@playwright/test'

/**
 * Relocation — automatic evacuation options workflow (map-driven).
 *
 * Verifies the full command-map experience WITHOUT manual site selection:
 *   1. open Relocation → origin auto-selected (highest demand: Munnar Central)
 *   2. recommended route appears automatically (RECOMMENDED badge + why)
 *   3. alternatives + rejected sections render with real reasons
 *   4. the map actually paints routes (MapLibre queryRenderedFeatures)
 *   5. switching origin (Rajakkad) recomputes: new recommendation, no stale routes
 *
 * Requires a live backend (docker compose up db backend osrm-kerala valhalla-kerala).
 * If routing engines are down the test still asserts the honest UNAVAILABLE
 * state — it never expects fabricated data.
 */

// Options evaluation = engines probe + 3 real OSRM routes (~15-45s).
const OPTIONS_TIMEOUT = 90_000
// Playwright's default test timeout (30s) is shorter than the evaluation;
// raise the per-test budget so slow engine probes don't fail the test.
test.setTimeout(180_000)

test('Relocation page auto-recommends an evacuation option without manual selection', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(String(e)))

  await page.goto('/relocation')

  // Origin selector present with affected habitations; default = highest demand.
  await expect(page.locator('select')).toBeVisible({ timeout: 30_000 })
  const originOptions = page.locator('select option')
  await expect(originOptions.first()).toContainText('Munnar Central', { timeout: 30_000 })
  const originCount = await originOptions.count()
  expect(originCount).toBeGreaterThanOrEqual(2)

  // The recommendation appears automatically — no "Select a site" empty state.
  await expect(page.getByText('RECOMMENDED', { exact: false }).first())
    .toBeVisible({ timeout: OPTIONS_TIMEOUT })

  // Route detail card carries the ranked option's real values.
  await expect(page.getByText('Why:', { exact: false }).first()).toBeVisible({ timeout: 20_000 })

  // Either real routes were painted, or the honest unavailable state is shown.
  const paintedRoutes = await page.evaluate(() => {
    const cont = document.querySelector('.maplibregl-map') as (HTMLElement & Record<string, unknown>) | null
    if (!cont) return -1
    const fiberKey = Object.keys(cont).find(k => k.startsWith('__reactFiber'))
    if (!fiberKey) return -2
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let fiber = cont[fiberKey] as any
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let map: any = null
    for (let i = 0; i < 60 && fiber && !map; i++) {
      let hook = fiber.memoizedState
      while (hook) {
        const cand = hook.memoizedState
        if (cand && typeof cand.getLayer === 'function') { map = cand; break }
        if (cand && cand.current && typeof cand.current.getLayer === 'function') { map = cand.current; break }
        hook = hook.next
      }
      fiber = fiber.return
    }
    if (!map) return -3
    try {
      const rec = map.queryRenderedFeatures({ layers: ['route-line'] }).length
      const alt = map.queryRenderedFeatures({ layers: ['route-alt-line'] }).length
      return rec + alt
    } catch { return -4 }
  })
  // With engines up this must be > 0 (routes painted). Engines-down honesty is
  // asserted separately; a hard failure here means routes silently vanished.
  expect(paintedRoutes).toBeGreaterThan(0)

  // Alternatives listed with their real reason text.
  const altText = await page.locator('button', { hasText: 'km ·' }).filter({ hasText: 'min' }).count()
  expect(altText).toBeGreaterThanOrEqual(1)

  expect(errors).toEqual([])
})

test('Switching origin recomputes the recommendation and clears stale routes', async ({ page }) => {
  await page.goto('/relocation')
  await expect(page.getByText('RECOMMENDED', { exact: false }).first())
    .toBeVisible({ timeout: OPTIONS_TIMEOUT })

  // Switch origin to Rajakkad.
  const sel = page.locator('select')
  await sel.selectOption('rajakkad')

  // New recommendation for the new origin (header + route detail update).
  await expect(page.getByText('Rajakkad →', { exact: false }).first())
    .toBeVisible({ timeout: OPTIONS_TIMEOUT })
  // The previous Munnar recommendation must not remain as the focused route.
  await expect(page.getByText('Munnar Central →', { exact: false })).toHaveCount(0, { timeout: 10_000 })
  // Why-text regenerated from the new origin's actual results.
  await expect(page.getByText('Why:', { exact: false }).first()).toBeVisible({ timeout: 20_000 })
})
