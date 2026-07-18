"""压测数据预灌入脚本 — 创建测试知识库 + 文档。

用法：
    # 灌入默认数据（1 知识库 + 5 文档）
    python scripts/seed_test_data.py

    # 自定义数量
    python scripts/seed_test_data.py --kb-count 3 --docs-per-kb 10

    # 清空旧数据后重建
    python scripts/seed_test_data.py --reset

前置条件：
    - MySQL 已启动（edu_rag 库）
    - Ollama embedding 服务已启动（或 EMBEDDING__PROVIDER=api 指向可用服务）
    - 向量库（Milvus/Chroma）已启动
"""
import argparse
import asyncio
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from src.shared.config import settings  # noqa: E402
from src.shared.database import mysql as mysql_module  # noqa: E402
from src.shared.models.orm import Base, KnowledgeBase, Document  # noqa: E402
from src.ingress.service import IngestionService  # noqa: E402
from src.retrieval.embedder import get_embedder  # noqa: E402
from src.retrieval.vector_store import get_vector_store  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("seed")


@asynccontextmanager
async def get_session() -> AsyncSession:
    """获取独立 DB 会话（脚本用，不走 FastAPI Depends）。"""
    if mysql_module._session_factory is None:
        raise RuntimeError("MySQL 未初始化，请先调用 init_mysql()")
    session = mysql_module._session_factory()
    try:
        yield session
    finally:
        await session.close()


# ── 测试文档内容（教育领域，多学科）──
TEST_DOCUMENTS = [
    {
        "filename": "biology_photosynthesis.txt",
        "doc_type": "biology",
        "content": """光合作用是植物、藻类和某些细菌利用光能将二氧化碳和水转化为有机物（主要是葡萄糖）并释放氧气的过程。

光合作用的总反应方程式：6CO₂ + 6H₂O + 光能 → C₆H₁₂O₆ + 6O₂

光合作用分为两个阶段：
1. 光反应阶段：发生在类囊体膜上，需要光能。水分子被光解产生氧气、质子和电子。电子通过电子传递链传递，产生 ATP 和 NADPH。
2. 暗反应阶段（卡尔文循环）：发生在基质中，不需要光直接参与。利用光反应产生的 ATP 和 NADPH，将二氧化碳固定并还原为糖类。

影响光合作用速率的因素：
- 光照强度：在一定范围内，光合速率随光照增强而加快
- 二氧化碳浓度：CO₂ 是暗反应的原料
- 温度：影响酶的活性，最适温度通常在 25-35°C
- 水分：水是光反应的原料

光合作用的意义：
- 制造有机物，是生物圈物质和能量的基础
- 维持大气中氧气和二氧化碳的平衡
- 为化石能源的形成提供物质基础
""",
    },
    {
        "filename": "physics_newton_laws.txt",
        "doc_type": "physics",
        "content": """牛顿运动定律是经典力学的基础，由艾萨克·牛顿在 1687 年提出。

牛顿第一定律（惯性定律）：
一切物体在没有受到外力作用时，总保持静止状态或匀速直线运动状态。物体的这种性质叫做惯性。质量是惯性大小的量度。

牛顿第二定律：
物体的加速度与所受合外力成正比，与物体的质量成反比。公式：F = ma，其中 F 是合外力（牛顿），m 是质量（千克），a 是加速度（米/秒²）。

牛顿第二定律的推论：
- 力的单位牛顿的定义：使 1kg 物体产生 1m/s² 加速度的力
- 加速度方向与合外力方向相同
- 合外力为零时，加速度为零（回到第一定律）

牛顿第三定律（作用力与反作用力定律）：
两个物体之间的作用力和反作用力总是大小相等、方向相反，作用在同一条直线上。

牛顿运动定律的适用范围：
- 适用于宏观物体（远大于原子尺度）
- 适用于低速运动（远小于光速）
- 不适用于微观粒子（需量子力学）和高速运动（需相对论）
""",
    },
    {
        "filename": "math_quadratic_functions.txt",
        "doc_type": "math",
        "content": """二次函数是中学数学的重要内容，形式为 f(x) = ax² + bx + c（a ≠ 0）。

二次函数的三种表达式：
1. 一般式：f(x) = ax² + bx + c
2. 顶点式：f(x) = a(x - h)² + k，其中 (h, k) 是顶点坐标
3. 交点式：f(x) = a(x - x₁)(x - x₂)，其中 x₁, x₂ 是与 x 轴交点

顶点公式：
- 顶点横坐标：h = -b / (2a)
- 顶点纵坐标：k = f(h) = c - b² / (4a)

对称轴：x = -b / (2a)

判别式 Δ = b² - 4ac：
- Δ > 0：与 x 轴有两个交点
- Δ = 0：与 x 轴有一个交点（相切）
- Δ < 0：与 x 轴无交点

二次函数的性质：
- a > 0：开口向上，有最小值
- a < 0：开口向下，有最大值
- |a| 越大，开口越窄（变化越快）

求根公式：x = (-b ± √Δ) / (2a)
""",
    },
    {
        "filename": "history_opium_wars.txt",
        "doc_type": "history",
        "content": """鸦片战争（1840-1842）是中国近代史的开端，标志着中国开始沦为半殖民地半封建社会。

背景：
- 19 世纪初，英国完成工业革命，急需开拓市场和掠夺原料
- 中英贸易中，中国出超（顺差），英国入超（逆差）
- 英国向中国走私鸦片，扭转贸易逆差，严重危害中国社会

导火索：1839 年林则徐虎门销烟

第一次鸦片战争（1840-1842）：
- 1840 年 6 月，英军发动侵略
- 1842 年 8 月，清政府被迫签订《南京条约》

《南京条约》主要内容：
1. 割让香港岛给英国
2.赔款 2100 万银元
3. 开放广州、厦门、福州、宁波、上海五处通商口岸
4. 协定关税（中国海关税率须与英国协商）

第二次鸦片战争（1856-1860）：
- 英法联军发动
- 1860 年攻入北京，火烧圆明园
- 签订《天津条约》《北京条约》

鸦片战争的影响：
- 中国主权遭到破坏，开始沦为半殖民地半封建社会
- 自然经济逐渐解体
- 促进了中华民族的觉醒
- 开启了中国近代化的进程
""",
    },
    {
        "filename": "chemistry_redox_reactions.txt",
        "doc_type": "chemistry",
        "content": """氧化还原反应是化学反应中的一大类，其本质是电子的转移。

氧化还原反应的定义：
- 氧化：失去电子（化合价升高）的过程
- 还原：得到电子（化合价降低）的过程
- 氧化还原反应：有电子转移（化合价变化）的化学反应

氧化剂和还原剂：
- 氧化剂：得到电子（被还原）的物质，氧化剂发生还原反应
- 还原剂：失去电子（被氧化）的物质，还原剂发生氧化反应

口诀：升失氧（化合价升高，失去电子，被氧化，是还原剂）
      降得还（化合价降低，得到电子，被还原，是氧化剂）

常见氧化剂：O₂、Cl₂、HNO₃、浓 H₂SO₄、KMnO₄、FeCl₃
常见还原剂：H₂、C、CO、活泼金属（Na、K、Mg）、H₂S、SO₂

氧化还原反应的配平方法：
1. 化合价升降法：使化合价升高总数 = 降低总数
2. 电子得失法：使失电子总数 = 得电子总数

氧化还原反应的应用：
- 金属冶炼（如炼铁：Fe₂O₃ + 3CO → 2Fe + 3CO₂）
- 燃烧反应
- 电池反应（干电池、锂电池）
- 电镀和防腐
""",
    },
]


async def reset_database():
    """清空所有表并重建（仅测试环境用）。"""
    logger.warning("resetting database — dropping and recreating all tables")
    engine = mysql_module._engine
    if engine is None:
        raise RuntimeError("MySQL engine 未初始化")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database reset complete")


async def seed_knowledge_base(name: str, description: str) -> KnowledgeBase:
    """创建知识库。"""
    async with get_session() as db:
        result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.name == name))
        existing = result.scalar_one_or_none()
        if existing:
            logger.info(f"knowledge_base_exists id={existing.id} name={name}")
            return existing

        kb = KnowledgeBase(name=name, description=description)
        db.add(kb)
        await db.commit()
        await db.refresh(kb)
        logger.info(f"knowledge_base_created id={kb.id} name={name}")
        return kb


async def seed_document(
    kb_id: int,
    filename: str,
    doc_type: str,
    content: str,
    ingestion_service: IngestionService,
) -> int:
    """创建文档记录并执行入库管线。"""
    upload_dir = Path(settings.app.get_upload_dir())
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{uuid.uuid4().hex[:8]}_{filename}"
    file_path.write_text(content, encoding="utf-8")

    async with get_session() as db:
        doc = Document(
            filename=filename,
            file_path=str(file_path),
            file_type=filename.rsplit(".", 1)[-1],
            file_size=len(content.encode("utf-8")),
            knowledge_base_id=kb_id,
            status="processing",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        doc_id = doc.id

    # 执行入库管线
    try:
        result = await ingestion_service.ingest(
            file_path=str(file_path),
            doc_id=doc_id,
            kb_id=kb_id,
            doc_type=doc_type,
        )
        async with get_session() as db:
            doc_db = await db.get(Document, doc_id)
            if doc_db:
                doc_db.status = "done"
                doc_db.chunk_count = result.chunk_count
                await db.commit()

        logger.info(f"document_ingested doc_id={doc_id} chunks={result.chunk_count} file={filename}")
        return result.chunk_count
    except Exception as e:
        logger.error(f"document_ingest_failed doc_id={doc_id} error={e}")
        async with get_session() as db:
            doc_db = await db.get(Document, doc_id)
            if doc_db:
                doc_db.status = "error"
                doc_db.error_message = str(e)
                await db.commit()
        raise


async def main(kb_count: int, docs_per_kb: int, reset: bool):
    """主入口。"""
    await mysql_module.init_mysql()

    if reset:
        await reset_database()

    embedder = get_embedder()
    vector_store = get_vector_store()
    ingestion_service = IngestionService(embedder=embedder, vector_store=vector_store)

    total_chunks = 0
    total_docs = 0

    for kb_idx in range(kb_count):
        kb_name = f"压测知识库-{kb_idx + 1}" if kb_count > 1 else "压测知识库"
        kb_desc = f"压力测试用知识库（{kb_idx + 1}/{kb_count}），包含多学科教育内容"
        kb = await seed_knowledge_base(kb_name, kb_desc)

        for doc_idx in range(docs_per_kb):
            template = TEST_DOCUMENTS[doc_idx % len(TEST_DOCUMENTS)]
            filename = f"{kb_idx + 1}_{doc_idx + 1}_{template['filename']}"
            chunks = await seed_document(
                kb_id=kb.id,
                filename=filename,
                doc_type=template["doc_type"],
                content=template["content"],
                ingestion_service=ingestion_service,
            )
            total_chunks += chunks
            total_docs += 1

    logger.info(f"seed_complete kb_count={kb_count} total_docs={total_docs} total_chunks={total_chunks}")
    await mysql_module.close_mysql()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="压测数据预灌入")
    parser.add_argument("--kb-count", type=int, default=1, help="知识库数量（默认 1）")
    parser.add_argument("--docs-per-kb", type=int, default=5, help="每个知识库文档数（默认 5）")
    parser.add_argument("--reset", action="store_true", help="清空数据库后重建（慎用）")
    args = parser.parse_args()

    asyncio.run(main(args.kb_count, args.docs_per_kb, args.reset))
