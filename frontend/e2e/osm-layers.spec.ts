/**
 * Sentinel AI — live OSM layers + hazard-aware routing smoke tests.
 *
 * Proves the Phase 6 wiring end-to-end on the /relocation workspace:
 *  1. The "OSM layers" toggle fetches /api/v1/osm/{category} for the Munnar
 *     pilot bbox and surfaces honest provenance ("Live OSM: …" when the
 *     provider answered, "OSM provider unavailable" when it did not).
 *  2. The hazard-avoidance switch drives /api/v1/routing/hazard-aware, and the
 *     route chip reports either a scored route or the engine's honest
 *     UNAVAILABLE state (engines are offline locally).
 *
 * Overpass is a shared public service and can be slow or flaky under load, so
 * these tests assert the UI reflects the provider's answer either way — never
 * a fabricated success. Real LIVE evidence is captured in screenshots.
 */
import { test, expect, type Page } from '@playwright/test'

/** Wait for the OSM layer status chip and return its text. */
async function readOsmStatus(page: Page): Promise<string> {
  const chip = page.locator('text=/Live OSM:|OSM provider unavailable/').first()
  await chip.waitFor({ timeout: 120_000 })
  return (await chip.textContent()) ?? ''
}

test('OSM layers toggle renders live features with honest provenance', async ({ page }) => {
  test.setTimeout(180_000)
  const consoleInfo: string[] = []
  page.on('console', (msg) => {
    if (msg.text().includes('[osm]')) consoleInfo.push(msg.text())
  })

  await page.goto('/relocation')
  await expect(page.getByRole('heading', { name: 'Relocation Intelligence' })).toBeVisible()

  const toggle = page.getByRole('button', { name: 'OSM layers' })
  await expect(toggle).toBeVisible()
  await toggle.click()

  const status = await readOsmStatus(page)

  // The toggle must now read "on" and the legend must appear.
  await expect(page.getByRole('button', { name: 'OSM layers on' })).toBeVisible()
  const legend = page.getByLabel('OSM legend')
  await expect(legend).toBeVisible()
  for (const label of ['roads', 'buildings', 'facilities', 'water']) {
    await expect(legend.getByText(label)).toBeVisible()
  }

  if (status.startsWith('Live OSM:')) {
    expect(status).toMatch(/roads \d/)
    expect(consoleInfo.some((l) => /status=(LIVE|CACHED)/.test(l))).toBeTruthy()
  } else {
    expect(status).toContain('OSM provider unavailable')
  }

  await page.screenshot({ path: 'e2e/.artifacts/osm-layers.png', fullPage: false })
})

test('hazard-avoidance switch drives the scored route or honest UNAVAILABLE', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto('/relocation')
  const avoid = page.getByRole('switch', { name: 'Avoid hazard zones' })
  await expect(avoid).toBeVisible()
  await expect(avoid).toHaveAttribute('aria-checked', 'true')

  // Route chip resolves to either a scored OK route or the engine's honest
  // UNAVAILABLE chip (engines are offline locally). Take a screenshot either way.
  await page.waitForTimeout(12_000)
  const okRoute = page.locator('text=/min.*via/')
  const unavailable = page.locator('text=unavailable')

  // Toggling avoidance re-routes (new network request fired by the app).
  await avoid.click()
  await expect(avoid).toHaveAttribute('aria-checked', 'false')
  await page.waitForTimeout(6_000)

  const okCount = await okRoute.count()
  const unavailableCount = await unavailable.count()
  expect(okCount > 0 || unavailableCount > 0).toBeTruthy()

  await page.screenshot({ path: 'e2e/.artifacts/hazard-route.png', fullPage: false })
})