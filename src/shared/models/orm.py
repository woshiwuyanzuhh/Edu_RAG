"""
SQLAlchemy ORM 模型 — MySQL 表映射。

变更 (v1.0 → v2.0):
    - datetime.utcnow → func.now() (解决问题 #21)
    - 新增 Session 表 (解决问题 #14 对话历史)
    - ExamRecord 新增维度评分字段 (解决问题 #24)
"""

from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, comment="知识库名称（唯一）")
    description = Column(Text, default="", comment="描述")
    retrieval_config = Column(
        JSON, nullable=True, default=None, comment="知识库级检索策略覆盖：{min_score, fusion_alpha, max_chunks, ...}"
    )
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")
    exam_records = relationship("ExamRecord", back_populates="knowledge_base", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_size = Column(Integer, default=0)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False)
    chunk_count = Column(Integer, default=0)
    status = Column(
        Enum("pending", "processing", "done", "error", name="doc_status"),
        default="pending",
    )
    error_message = Column(Text, nullable=True, comment="处理失败原因")
    created_at = Column(DateTime, server_default=func.now())

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")


class ExamRecord(Base):
    __tablename__ = "exam_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False)
    question_type = Column(
        Enum("choice", "essay", "tf", "mixed", name="question_type"),
        nullable=False,
    )
    question_count = Column(Integer, default=0)
    difficulty = Column(String(20), default="medium")
    questions = Column(JSON, default=lambda: [])
    answers = Column(JSON, default=lambda: [])
    scores = Column(JSON, default=lambda: [])
    dimensions = Column(JSON, default=None, comment="维度评分: {concept, analysis, memory, application}")
    total_score = Column(Float, default=0)
    max_score = Column(Float, default=100)
    status = Column(
        Enum("draft", "answered", "graded", name="exam_status"),
        default="draft",
    )
    created_at = Column(DateTime, server_default=func.now())

    knowledge_base = relationship("KnowledgeBase", back_populates="exam_records")


class ChatSession(Base):
    """对话会话 — 支持多轮对话。#14"""

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_key = Column(String(64), unique=True, nullable=False, index=True, comment="会话唯一标识")
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=True, comment="可选：限定知识库")
    messages = Column(JSON, default=lambda: [], comment="对话历史 [{role, content}]")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Feedback(Base):
    """用户反馈 — QA 答案质量评价。Phase 4 P3-4"""

    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=True, index=True, comment="关联的对话会话")
    question = Column(Text, nullable=False, comment="用户问题")
    answer = Column(Text, nullable=False, comment="系统回答")
    rating = Column(Integer, nullable=False, comment="1=👍 赞, 0=👎 踩")
    comment = Column(Text, nullable=True, comment="可选文字评论")
    created_at = Column(DateTime, server_default=func.now())


class BM25IndexCache(Base):
    """BM25 索引持久化缓存 — 支持多实例共享与崩溃恢复（P0-C3）。

    knowledge_base_id=0 表示 legacy 全局索引（内存中 None 的序列化形式）。
    仅持久化 docs + metadatas，_tokenized 与 _bm25 对象启动时重建。
    """

    __tablename__ = "bm25_index_cache"
    knowledge_base_id = Column(Integer, primary_key=True, comment="知识库 ID；0 表示 legacy 全局索引")
    docs = Column(JSON, nullable=False, default=lambda: [], comment="文档文本列表")
    metadatas = Column(JSON, nullable=False, default=lambda: [], comment="元数据列表")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
