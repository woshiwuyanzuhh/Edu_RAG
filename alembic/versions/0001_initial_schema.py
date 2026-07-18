"""initial schema — 创建全部 6 张表。

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-18 00:00:00.000000

本迁移基于 src/shared/models/orm.py 的 ORM 模型手动编写，
等价于 alembic revision --autogenerate 的输出。

包含表:
    - knowledge_bases
    - documents
    - exam_records
    - chat_sessions
    - feedback
    - bm25_index_cache
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建全部表。"""
    # ── knowledge_bases ──
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False, comment="知识库名称（唯一）"),
        sa.Column("description", sa.Text(), nullable=True, comment="描述"),
        sa.Column(
            "retrieval_config",
            sa.JSON(),
            nullable=True,
            comment="知识库级检索策略覆盖：{min_score, fusion_alpha, max_chunks, ...}",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        comment="知识库",
    )

    # ── documents ──
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "done", "error", name="doc_status"),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True, comment="处理失败原因"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="文档",
    )

    # ── exam_records ──
    op.create_table(
        "exam_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column(
            "question_type",
            sa.Enum("choice", "essay", "tf", "mixed", name="question_type"),
            nullable=False,
        ),
        sa.Column("question_count", sa.Integer(), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("questions", sa.JSON(), nullable=True),
        sa.Column("answers", sa.JSON(), nullable=True),
        sa.Column("scores", sa.JSON(), nullable=True),
        sa.Column(
            "dimensions",
            sa.JSON(),
            nullable=True,
            comment="维度评分: {concept, analysis, memory, application}",
        ),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "answered", "graded", name="exam_status"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="考试记录",
    )

    # ── chat_sessions ──
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "session_key",
            sa.String(length=64),
            nullable=False,
            comment="会话唯一标识",
        ),
        sa.Column(
            "knowledge_base_id",
            sa.Integer(),
            nullable=True,
            comment="可选：限定知识库",
        ),
        sa.Column(
            "messages",
            sa.JSON(),
            nullable=True,
            comment="对话历史 [{role, content}]",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_key"),
        comment="对话会话 — 支持多轮对话",
    )
    op.create_index(
        "ix_chat_sessions_session_key",
        "chat_sessions",
        ["session_key"],
        unique=False,
    )

    # ── feedback ──
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True, comment="关联的对话会话"),
        sa.Column("question", sa.Text(), nullable=False, comment="用户问题"),
        sa.Column("answer", sa.Text(), nullable=False, comment="系统回答"),
        sa.Column("rating", sa.Integer(), nullable=False, comment="1=赞, 0=踩"),
        sa.Column("comment", sa.Text(), nullable=True, comment="可选文字评论"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="用户反馈 — QA 答案质量评价",
    )
    op.create_index(
        "ix_feedback_session_id",
        "feedback",
        ["session_id"],
        unique=False,
    )

    # ── bm25_index_cache ──
    op.create_table(
        "bm25_index_cache",
        sa.Column(
            "knowledge_base_id",
            sa.Integer(),
            nullable=False,
            comment="知识库 ID；0 表示 legacy 全局索引",
        ),
        sa.Column("docs", sa.JSON(), nullable=False, comment="文档文本列表"),
        sa.Column("metadatas", sa.JSON(), nullable=False, comment="元数据列表"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("knowledge_base_id"),
        comment="BM25 索引持久化缓存 — 支持多实例共享与崩溃恢复",
    )


def downgrade() -> None:
    """按逆序删除全部表。"""
    op.drop_table("bm25_index_cache")
    op.drop_index("ix_feedback_session_id", table_name="feedback")
    op.drop_table("feedback")
    op.drop_index("ix_chat_sessions_session_key", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_table("exam_records")
    op.drop_table("documents")
    op.drop_table("knowledge_bases")
