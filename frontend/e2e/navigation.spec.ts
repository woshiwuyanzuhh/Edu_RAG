import { test, expect } from '@playwright/test'

/**
 * 路由导航 E2E 测试
 *
 * 验证 SPA 路由跳转功能
 */
test.describe('路由导航', () => {
  test('从首页导航到知识库页面', async ({ page }) => {
    await page.goto('/')

    // 点击功能卡片中的“进入管理”按钮
    const kbBtn = page.locator('.feature-btn', { hasText: '进入管理' })
    await kbBtn.first().click({ timeout: 15000 })

    await expect(page).toHaveURL(/\/knowledge/, { timeout: 10000 })
  })

  test('从首页导航到文档上传页面', async ({ page }) => {
    await page.goto('/')

    const uploadBtn = page.locator('.feature-btn', { hasText: '上传文档' })
    await uploadBtn.first().click({ timeout: 15000 })

    await expect(page).toHaveURL(/\/upload/, { timeout: 10000 })
  })

  test('从首页导航到问答页面', async ({ page }) => {
    await page.goto('/')

    const qaBtn = page.locator('.feature-btn', { hasText: '开始提问' })
    await qaBtn.first().click({ timeout: 15000 })

    await expect(page).toHaveURL(/\/qa/, { timeout: 10000 })
  })

  test('从首页导航到考试页面', async ({ page }) => {
    await page.goto('/')

    // 点击功能卡片中的“生成题目”按钮
    const examBtn = page.locator('.feature-btn', { hasText: '生成题目' })
    await examBtn.first().click({ timeout: 15000 })

    await expect(page).toHaveURL(/\/exam/, { timeout: 10000 })
  })

  test('直接访问各路由页面', async ({ page }) => {
    // 知识库
    await page.goto('/knowledge')
    await expect(page).toHaveURL(/\/knowledge/)

    // 上传
    await page.goto('/upload')
    await expect(page).toHaveURL(/\/upload/)

    // 问答
    await page.goto('/qa')
    await expect(page).toHaveURL(/\/qa/)

    // 考试
    await page.goto('/exam')
    await expect(page).toHaveURL(/\/exam/)
  })

  test('浏览器后退前进功能正常', async ({ page }) => {
    await page.goto('/')
    await page.goto('/knowledge')
    await page.goto('/qa')

    // 后退
    await page.goBack()
    await expect(page).toHaveURL(/\/knowledge/)

    // 再后退
    await page.goBack()
    await expect(page).toHaveURL(/\/$/)
  })
})
