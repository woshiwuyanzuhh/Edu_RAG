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

环境变量：
    TARGET_HOST   — 目标地址（默认 http://localhost:8000）
    APP_API_KEY   — API 密钥（如启用鉴权）
    KB_ID         — 压测知识库 ID（默认 1）
    QA_RATIO      — QA 请求占比（默认 70）
"""
import os
import random

from locust import HttpUser, between, task


# 教育领域测试问题集（与 seed_test_data.py 内容匹配）
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
    "光合作用的暗反应是什么",
    "牛顿第三定律的内容",
    "判别式的作用是什么",
    "虎门销烟是哪一年",
    "常见的氧化剂有哪些",
]

QA_RATIO = int(os.environ.get("QA_RATIO", "70"))


class EduRagUser(HttpUser):
    """模拟教育 RAG 用户：QA 提问（主） + 浏览文档/知识库（辅）。"""
    wait_time = between(0.5, 2.0)
    host = os.environ.get("TARGET_HOST", "http://localhost:8000")

    def on_start(self):
        api_key = os.environ.get("APP_API_KEY", "")
        if api_key:
            self.client.headers.update({"X-API-Key": api_key})

    @task(QA_RATIO)
    def qa_ask(self):
        """QA 提问（非流式）— 主压测目标（检索 + 生成）。"""
        kb_id = int(os.environ.get("KB_ID", "1"))
        self.client.post(
            "/api/qa",
            json={
                "question": random.choice(QUERIES),
                "knowledge_base_id": kb_id,
                "top_k": 5,
                "use_rerank": True,
            },
            name="/api/qa",
        )

    @task(10)
    def qa_stream(self):
        """QA 提问（SSE 流式）— 压流式端点。"""
        kb_id = int(os.environ.get("KB_ID", "1"))
        with self.client.post(
            "/api/qa/stream",
            json={
                "question": random.choice(QUERIES),
                "knowledge_base_id": kb_id,
                "top_k": 5,
            },
            name="/api/qa/stream",
            stream=True,
            catch_response=True,
        ) as resp:
            # 消费 SSE 流，否则连接不会释放
            for line in resp.iter_lines():
                pass
            resp.success()

    @task(10)
    def list_documents(self):
        """文档列表 — 压 MySQL 分页。"""
        kb_id = int(os.environ.get("KB_ID", "1"))
        self.client.get(
            f"/api/documents?knowledge_base_id={kb_id}&page=1&page_size=20",
            name="/api/documents",
        )

    @task(5)
    def list_knowledge_bases(self):
        """知识库列表。"""
        self.client.get("/api/knowledge", name="/api/knowledge")

    @task(5)
    def exam_generate(self):
        """考试出题 — 压 LLM 生成。"""
        kb_id = int(os.environ.get("KB_ID", "1"))
        self.client.post(
            "/api/exam/generate",
            json={
                "knowledge_base_id": kb_id,
                "question_type": "choice",
                "question_count": 5,
                "difficulty": "medium",
            },
            name="/api/exam/generate",
        )
