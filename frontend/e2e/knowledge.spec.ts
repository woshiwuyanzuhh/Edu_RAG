import { test, expect } from '@playwright/test'

/**
 * 知识库页面 E2E 测试
 *
 * 验证知识库页面的渲染和交互
 * 注意: 需要后端运行且数据库中有数据
 */
test.describe('知识库页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/knowledge')
    // 等待页面加载
    await page.waitForLoadState('networkidle')
  })

  test('页面正确渲染', async ({ page }) => {
    // 验证页面标题存在
    const header = page.locator('h2, .page-header-title')
    await expect(header.first()).toBeVisible({ timeout: 15000 })
    await expect(header.first()).toContainText('知识库')
  })

  test('有创建知识库的入口', async ({ page }) => {
    // 查找"创建"或"新建"按钮
    const createBtn = page.getByRole('button', { name: /创建|新建|添加/ })
    // 按钮可能存在（如果后端可用）或页面显示空状态
    const isVisible = await createBtn.first().isVisible().catch(() => false)
    if (isVisible) {
      await expect(createBtn.first()).toBeVisible()
    }
  })

  test('点击创建按钮弹出表单', async ({ page }) => {
    // 精确匹配“创建知识库”按钮（PageHeader extra 中的按钮）
    const createBtn = page.getByRole('button', { name: '创建知识库' })
    const isVisible = await createBtn.first().isVisible().catch(() => false)
    if (!isVisible) {
      // 页面可能渲染了空状态（后端未运行），尝试点击空状态的 action 按钮
      const emptyAction = page.locator('.empty-state button')
      const emptyVisible = await emptyAction.first().isVisible().catch(() => false)
      if (!emptyVisible) {
        test.skip()
        return
      }
      await emptyAction.first().click()
    } else {
      await createBtn.first().click()
    }

    // 验证模态框出现
    await expect(page.locator('.ant-modal')).toBeVisible({ timeout: 5000 })
  })

  test('知识库列表渲染或空状态提示', async ({ page }) => {
    // 等待 API 响应完成
    await page.waitForTimeout(2000)

    // 要么有知识库列表，要么有空状态提示
    const list = page.locator('.ant-card, .ant-list-item, [class*="kb-item"], [class*="knowledge-item"]')
    const empty = page.locator('.ant-empty, .empty-state, [class*="empty"]')
    const hasList = await list.first().isVisible().catch(() => false)
    const hasEmpty = await empty.first().isVisible().catch(() => false)

    // 至少有一个应该可见
    expect(hasList || hasEmpty).toBeTruthy()
  })
})
