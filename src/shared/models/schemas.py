"""
Pydantic 请求/响应模型。

变更 (v1.0 → v2.0):
    - QARequest 新增 session_id (解决问题 #14)
    - ExamGradeResponse 新增 dimensions (解决问题 #24)
    - 新增 PaginatedResponse 泛型 (解决问题 #8)
"""

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

# ── 通用 ──


class APIResponse(BaseModel):
    """统一 API 响应包装。"""

    success: bool = True
    message: str = ""
    data: Any = None


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """统一分页响应。解决问题 #8。"""

    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    pages: int = 0


# ── 知识库 ──


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="知识库名称")
    description: str = Field(default="", description="描述")
    retrieval_config: dict | None = Field(default=None, description="知识库级检索策略覆盖")


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    retrieval_config: dict | None = None


class KnowledgeBaseResponse(BaseModel):
    id: int
    name: str
    description: str
    retrieval_config: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── 文档 ──


class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    knowledge_base_id: int
    chunk_count: int
    status: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── 问答 ──


class QARequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")
    knowledge_base_id: int | None = Field(default=None, description="限定知识库")
    top_k: int = Field(default=5, ge=1, le=20)
    use_rerank: bool = Field(default=True)
    session_id: str | None = Field(default=None, description="对话会话 ID（多轮）")  # 新增 #14
    history: list[dict] | None = Field(default=None, description="对话历史")  # 新增 #14


class SourceItem(BaseModel):
    doc_id: int
    chunk_index: int
    score: float
    text_preview: str


class QAResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceItem] = Field(default_factory=list)
    session_id: str | None = None  # 新增 #14


# ── 考试 ──


class ExamGenerateRequest(BaseModel):
    knowledge_base_id: int
    question_type: Literal["choice", "essay", "tf", "mixed"] = "mixed"
    question_count: int = Field(default=5, ge=1, le=20)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class QuestionItem(BaseModel):
    number: int
    type: str
    stem: str
    options: list[str] | None = None
    answer: str = ""


class ExamGenerateResponse(BaseModel):
    exam_id: int
    knowledge_base_id: int
    question_type: str
    question_count: int
    questions: list[QuestionItem]


class ExamGradeRequest(BaseModel):
    exam_id: int
    answers: list[dict] = Field(..., description='[{"question_number": 1, "answer": "..."}]')


class GradeDetail(BaseModel):
    question_number: int
    score: float
    max_score: float
    comment: str = ""
    is_correct: bool | None = None


class DimensionScore(BaseModel):
    """维度评分 — 解决问题 #24。"""

    concept: float = Field(default=0, ge=0, le=25, description="概念理解 (0-25)")
    analysis: float = Field(default=0, ge=0, le=25, description="分析能力 (0-25)")
    memory: float = Field(default=0, ge=0, le=25, description="记忆准确性 (0-25)")
    application: float = Field(default=0, ge=0, le=25, description="应用能力 (0-25)")


class ExamGradeResponse(BaseModel):
    exam_id: int
    total_score: float
    max_score: float
    details: list[GradeDetail] = Field(default_factory=list)
    dimensions: DimensionScore | None = None  # 新增 #24
    summary: str = ""


class ExamRecordItem(BaseModel):
    id: int
    knowledge_base_id: int
    question_type: str
    question_count: int
    difficulty: str | None = None
    total_score: float | None = None
    max_score: float | None = None
    status: str
    created_at: datetime | None = None


# ── 用户反馈 (Phase 4 P3-4) ──


class FeedbackCreate(BaseModel):
    session_id: str | None = None
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    rating: int = Field(..., ge=0, le=1, description="1=赞, 0=踩")
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: int
    session_id: str | None = None
    question: str
    answer: str
    rating: int
    comment: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
