import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E 测试配置
 *
 * 运行方式:
 *   npx playwright test          # 运行所有 E2E 测试
 *   npx playwright test --ui     # 交互式 UI 模式
 *   npx playwright test --headed # 有头模式（显示浏览器窗口）
 *
 * 前提条件:
 *   - 后端运行在 http://localhost:8000
 *   - 前端运行在 http://localhost:5173（或使用后端 SPA fallback http://localhost:8000）
 */
export default defineConfig({
  testDir: '.',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : 'html',
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    // 前端开发服务器地址（vite dev server）
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // 可选：自动启动前端开发服务器
  // webServer: {
  //   command: 'npm run dev',
  //   url: 'http://localhost:5173',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 30_000,
  // },
})
