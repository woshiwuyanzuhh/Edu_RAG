# edu_rag v2.0 Makefile — 前后端分离

.PHONY: help run dev test lint clean dev-frontend build-frontend docker docker-down

help:
	@echo "edu_rag v2.0 — 可用命令:"
	@echo "  make run            启动后端 (prod)"
	@echo "  make dev            启动后端 (reload)"
	@echo "  make dev-frontend   启动前端 (Vite dev server)"
	@echo "  make build-frontend 构建前端 (生产)"
	@echo "  make test           运行测试"
	@echo "  make lint           代码检查"
	@echo "  make clean          清理临时文件"
	@echo "  make docker         启动全栈 Docker"

run:
	uvicorn src.orchestration.app:app --host 0.0.0.0 --port 8000

dev:
	uvicorn src.orchestration.app:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

build-frontend:
	cd frontend && npm ci && npm run build
	@echo "前端构建完成: frontend/dist/"

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	ruff check src/
	mypy src/ --ignore-missing-imports

migrate:
	alembic upgrade head
migrate-new:
	@read -p "Migration message: " msg; alembic revision --autogenerate -m "$$msg"
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf frontend/dist frontend/node_modules/.vite

docker:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down
