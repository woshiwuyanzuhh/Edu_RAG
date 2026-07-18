"""Locust 压测脚本（P2-C9）。

分层压测策略：
    L1 接入层：mock LLM，压鉴权/路由/限流（QA 端点，快速返回）
    L2 检索层：mock LLM，压 Milvus+BM25+MySQL+Redis（QA 端点，真实检索）
    L3 全链路：真实 LLM，采样验证端到端（少量并发）

mock LLM：启动 tests/load/mock_llm_server.py，设 LLM__BASE_URL=http://localhost:8090/v1

用法：
    # Web UI 模式
    locust -f tests/load/locustfile.py --host http://localhost:8000

    # 无头模式（CI/自动化）— 1000 并发，每秒新增 50，跑 10 分钟
    locust -f tests/load/locustfile.py --headless -u 1000 -r 50 --run-time 10m --host http://localhost:8000

    # 100 万总请求目标：调高 -u 和 --run-time，观察 QPS 和 P99
"""
import os
import random

from locust import HttpUser, between, task


# 教育领域测试问题集
QUERIES = [
    "什么是光合作用？",
    "解释牛顿第二定律",
    "二次函数的顶点公式是什么",
    "细胞呼吸分为哪几个阶段",
    "抗日战争的起止时间",
    "化合价的定义",
    "三角函数的基本关系",
    "DNA 的双螺旋结构",
    "鸦片战争的影响",
    "氧化还原反应的本质",
]


class EduRagUser(HttpUser):
    """模拟教育 RAG 用户：QA 提问（主） + 浏览文档/知识库（辅）。"""
    wait_time = between(0.5, 2.0)
    host = os.environ.get("TARGET_HOST", "http://localhost:8000")

    def on_start(self):
        api_key = os.environ.get("APP_API_KEY", "")
        if api_key:
            self.client.headers.update({"X-API-Key": api_key})

    @task(7)
    def qa_ask(self):
        """QA 提问 — 主压测目标（检索 + 生成）。"""
        self.client.post(
            "/api/qa/ask",
            json={
                "question": random.choice(QUERIES),
                "knowledge_base_id": int(os.environ.get("KB_ID", "1")),
            },
            name="/api/qa/ask",
        )

    @task(2)
    def list_documents(self):
        """文档列表 — 压 MySQL 分页。"""
        self.client.get(
            "/api/documents?knowledge_base_id=1&page=1&page_size=20",
            name="/api/documents",
        )

    @task(1)
    def list_knowledge_bases(self):
        """知识库列表。"""
        self.client.get("/api/knowledge", name="/api/knowledge")
