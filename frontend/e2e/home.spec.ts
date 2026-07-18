import { test, expect } from '@playwright/test'

/**
 * 首页 E2E 测试
 *
 * 验证首页渲染、导航功能、路由跳转
 */
test.describe('首页', () => {
  test('正确渲染首页内容', async ({ page }) => {
    await page.goto('/')

    // 验证标题
    await expect(page.locator('h1')).toContainText('edu_rag')
    await expect(page.locator('h1')).toContainText('智能题库系统')

    // 验证架构评分徽章
    await expect(page.locator('.hero-badge')).toContainText('4.8/5')

    // 验证功能卡片存在
    const featureCards = page.locator('.feature-card, [class*="feature"]')
    await expect(featureCards.first()).toBeVisible({ timeout: 15000 })
  })

  test('显示功能特性卡片', async ({ page }) => {
    await page.goto('/')

    // 验证功能卡片存在（使用 .feature-card 类精确匹配）
    const cards = page.locator('.feature-card')
    await expect(cards.first()).toBeVisible({ timeout: 15000 })
    await expect(cards).toHaveCount(4)

    // 验证四个功能卡片文本
    await expect(page.locator('.feature-title', { hasText: '知识库管理' })).toBeVisible()
    await expect(page.locator('.feature-title', { hasText: '文档上传' })).toBeVisible()
    await expect(page.locator('.feature-title', { hasText: '智能问答' })).toBeVisible()
    await expect(page.locator('.feature-title', { hasText: '智能题库' })).toBeVisible()
  })

  test('显示统计数据', async ({ page }) => {
    await page.goto('/')

    // 验证统计区域
    await expect(page.getByText('知识库').first()).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('文档').first()).toBeVisible()
    await expect(page.getByText('问答').first()).toBeVisible()
    await expect(page.getByText('考试').first()).toBeVisible()
  })

  test('显示使用步骤', async ({ page }) => {
    await page.goto('/')

    // 验证步骤区域
    await expect(page.getByText('创建知识库').first()).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('上传文档').first()).toBeVisible()
    await expect(page.getByText('智能问答').first()).toBeVisible()
    await expect(page.getByText('生成题目').first()).toBeVisible()
  })
})
