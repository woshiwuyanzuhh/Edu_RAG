# edu_rag v2.0 Makefile — 前后端分离
# 一键启动:  make start    (后端 + 前端)
# 一键关闭:  make stop     (杀死 8000 / 5173 端口进程)

.PHONY: help start stop restart run dev test lint clean dev-frontend build-frontend docker docker-down

help:
	@echo "edu_rag v2.0 — 可用命令:"
	@echo "  make start          一键启动 (后端 + 前端)"
	@echo "  make stop           一键关闭 (后端 + 前端)"
	@echo "  make restart        重启 (stop + start)"
	@echo ""
	@echo "  make run            仅启动后端 (prod)"
	@echo "  make dev            仅启动后端 (reload)"
	@echo "  make dev-frontend   仅启动前端 (Vite dev)"
	@echo "  make build-frontend 构建前端 (生产)"
	@echo ""
	@echo "  make test           运行测试"
	@echo "  make lint           代码检查 (Ruff + MyPy)"
	@echo "  make clean          清理临时文件"
	@echo "  make docker         启动全栈 Docker"

# ── 一键启动 / 关闭 ──────────────────────────

start:
	@echo "=== edu_rag v2.0 — 启动 ==="
	@echo "后端 (port 8000) + 前端 (port 5173)"
	@echo "请确保 MySQL / Redis / Ollama 已运行"
	@echo ""
	@echo "[1/2] 启动后端..."
	@start "edu_rag Backend" cmd /c "cd /d $(CURDIR) && uvicorn src.orchestration.app:app --reload --host 0.0.0.0 --port 8000"
	@sleep 2
	@echo "[2/2] 启动前端..."
	@start "edu_rag Frontend" cmd /c "cd /d $(CURDIR)\frontend && npm run dev"
	@echo ""
	@echo "Backend  : http://localhost:8000"
	@echo "Frontend : http://localhost:5173"
	@echo "关闭服务: make stop"

stop:
	@echo "=== edu_rag v2.0 — 关闭 ==="
	@echo "停止 port 8000 (backend) 和 port 5173 (frontend)..."
	@for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
	@for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5173" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
	@taskkill /FI "WINDOWTITLE eq edu_rag Backend*"  >nul 2>&1
	@taskkill /FI "WINDOWTITLE eq edu_rag Frontend*" >nul 2>&1
	@echo "Done."

restart: stop start
	@echo "Restarted."

# ── 单服务 ────────────────────────────────────

run:
	uvicorn src.orchestration.app:app --host 0.0.0.0 --port 8000

dev:
	uvicorn src.orchestration.app:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

build-frontend:
	cd frontend && npm ci && npm run build
	@echo "前端构建完成: frontend/dist/"

# ── 测试 & 质量 ──────────────────────────────

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	ruff check src/
	mypy src/ --ignore-missing-imports

# ── 数据库 ────────────────────────────────────

migrate:
	alembic upgrade head

migrate-new:
	@read -p "Migration message: " msg; alembic revision --autogenerate -m "$$msg"

# ── 清理 ─────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf frontend/dist frontend/node_modules/.vite

# ── Docker ────────────────────────────────────

docker:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down
