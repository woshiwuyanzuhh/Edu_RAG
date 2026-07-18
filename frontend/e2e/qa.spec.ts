import { test, expect } from '@playwright/test'

/**
 * 问答页面 E2E 测试
 *
 * 验证 QA 页面的渲染和交互
 * 注意: 需要前端运行；后端可选（API 失败时页面仍应渲染）
 */
test.describe('问答页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/qa')
    await page.waitForLoadState('networkidle')
  })

  test('页面正确渲染', async ({ page }) => {
    // QA 页面使用 .qa-page 布局（非 PageHeader 组件）
    await expect(page.locator('.qa-page')).toBeVisible({ timeout: 15000 })
  })

  test('有输入框', async ({ page }) => {
    // a-textarea 渲染为 textarea 元素
    const input = page.locator('textarea')
    await expect(input.first()).toBeVisible({ timeout: 10000 })
  })

  test('输入框有占位提示', async ({ page }) => {
    const input = page.locator('textarea').first()
    await expect(input).toBeVisible({ timeout: 10000 })
    await expect(input).toHaveAttribute('placeholder', /输入你的问题/)
  })

  test('输入问题后可以发送', async ({ page }) => {
    const input = page.locator('textarea').first()
    await expect(input).toBeVisible({ timeout: 10000 })

    // 输入文本
    await input.fill('什么是机器学习？')
    await expect(input).toHaveValue('什么是机器学习？')

    // 按下 Enter 发送（QA 页面使用 @keydown.enter.exact.prevent="handleAsk"）
    await input.press('Enter')

    // 验证用户消息出现在对话区域（handleAsk 会清空输入框并添加消息）
    // 使用 .msg-bubble-user 精确匹配用户消息气泡
    await expect(page.locator('.msg-bubble-user')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('.msg-bubble-user')).toContainText('什么是机器学习？')
  })
})
