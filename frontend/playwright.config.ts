import { defineConfig, devices } from '@playwright/test'
import { existsSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

/**
 * Resolve a usable Chromium executable without forcing `playwright install`:
 * prefer the env override, then any cached ms-playwright chromium build, and
 * fall back to Playwright's own resolution (which errors with a helpful
 * message if nothing is installed).
 */
function resolveChromium(): string | undefined {
  if (process.env.PLAYWRIGHT_CHROMIUM_PATH) return process.env.PLAYWRIGHT_CHROMIUM_PATH
  const root = join(process.env.LOCALAPPDATA ?? '', 'ms-playwright')
  try {
    const dir = readdirSync(root)
      .filter((d) => d.startsWith('chromium-') && !d.includes('headless_shell'))
      .sort()
      .pop()
    if (dir) {
      const exe = join(root, dir, 'chrome-win64', 'chrome.exe')
      if (existsSync(exe)) return exe
    }
  } catch {
    // No cached browsers — let Playwright resolve (or fail) on its own.
  }
  return undefined
}

/**
 * Sentinel AI — Playwright smoke suite.
 *
 * Runs against a real dev server (vite) plus a real backend (FastAPI) so the
 * API-driven pages are exercised end-to-end. If the backend is missing, the
 * app falls back to the labelled demo seed — the smoke tests still pass, but
 * the "api-served" assertion in smoke.spec.ts proves the real integration.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: resolveChromium() ? { executablePath: resolveChromium() } : {},
      },
    },
  ],
  // Start both servers unless they're already listening (then reuse — useful
  // when running against the live dev preview).
  webServer: [
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: process.platform === 'win32'
        ? '.venv311\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000'
        : '.venv311/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
      url: 'http://localhost:8000/health',
      cwd: '../backend',
      reuseExistingServer: true,
      timeout: 90_000,
    },
  ],
})
