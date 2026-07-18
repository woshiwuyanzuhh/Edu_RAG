# edu_rag E2E 测试

> 基于 Playwright 的端到端测试

## 测试文件

| 文件 | 覆盖范围 | 测试数 |
|------|---------|--------|
| `home.spec.ts` | 首页渲染、功能卡片、统计数据、使用步骤 | 4 |
| `navigation.spec.ts` | SPA 路由跳转、后退前进、直接访问路由 | 6 |
| `knowledge.spec.ts` | 知识库页面渲染、创建入口、列表/空状态 | 4 |
| `qa.spec.ts` | 问答页面渲染、输入框、发送消息 | 4 |
| **合计** | | **18** |

## 运行方式

### 前提条件

1. **前端运行**：`cd frontend && npm run dev` → http://localhost:5173
2. **后端可选**：后端运行时可测试完整流程；未运行时部分测试会 skip

### 运行测试

```bash
# 从 frontend 目录运行
cd frontend

# 运行所有 E2E 测试（无头模式）
npm run e2e

# 交互式 UI 模式（推荐开发时使用）
npm run e2e:ui

# 有头模式（显示浏览器窗口）
npm run e2e:headed
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `E2E_BASE_URL` | `http://localhost:5173` | 前端地址（也可用 `http://localhost:8000` 测试 SPA fallback） |

### CI 环境

在 CI 中使用 `E2E_BASE_URL=http://localhost:8000` 可测试后端 SPA fallback 模式（无需单独启动前端 dev server）。
CI 配置见 `.github/workflows/e2e.yml`。

## 首次安装

```bash
cd frontend
npm install -D @playwright/test
npx playwright install chromium
```

## 测试报告

- HTML 报告：`frontend/playwright-report/`
- 测试截图/视频：`frontend/test-results/`（仅失败时保留）
