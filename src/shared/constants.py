"""文档类型常量定义 — 全局唯一来源。

所有涉及 doc_type 的模块（API 校验、cleaner 注册表、前端下拉、测试、种子数据）
都应引用此处的常量，避免分散硬编码导致不一致。

设计原则：
    1. 顺序即前端下拉展示顺序
    2. key 为稳定标识符（存入 chunk metadata，不可随意更改）
    3. label 为中文展示名
    4. description 用于前端 tooltip / API 文档
"""
from __future__ import annotations

from typing import Final


class DocumentType:
    """文档类型常量。

    使用类属性而非模块级变量，便于 IDE 自动补全和类型推断。
    """

    # ── 通用兜底 ──
    GENERAL: Final[str] = "general"

    # ── 原有领域 ──
    EDUCATION: Final[str] = "education"
    GAMING: Final[str] = "gaming"

    # ── 新增领域 ──
    TECH: Final[str] = "tech"             # 技术文档（IT/编程/软件手册）
    MEDICAL: Final[str] = "medical"       # 医疗健康
    LEGAL: Final[str] = "legal"           # 法律法规
    FINANCE: Final[str] = "finance"       # 金融财经
    NEWS: Final[str] = "news"             # 新闻资讯
    LITERATURE: Final[str] = "literature"  # 文学作品
    BUSINESS: Final[str] = "business"     # 商业管理


# 文档类型元数据注册表 — 有序，供前端下拉等场景按顺序渲染
# 顺序：通用 → 教育 → 游戏 → 技术 → 医疗 → 法律 → 金融 → 新闻 → 文学 → 商业
DOCUMENT_TYPES: list[dict[str, str]] = [
    {"key": DocumentType.GENERAL,    "label": "通用",     "description": "默认清洗策略，适用于未分类的文档"},
    {"key": DocumentType.EDUCATION,  "label": "教育",     "description": "教材、讲义、试题 — 过滤页码、水印、参考文献"},
    {"key": DocumentType.GAMING,     "label": "游戏攻略",  "description": "论坛攻略、wiki — 过滤签名、广告、纯 emoji"},
    {"key": DocumentType.TECH,       "label": "技术文档",  "description": "IT/编程/软件手册 — 过滤代码行号、shell 提示符、TODO 注释"},
    {"key": DocumentType.MEDICAL,    "label": "医疗健康",  "description": "医学文献、健康科普 — 过滤免责声明、医院信息、广告"},
    {"key": DocumentType.LEGAL,      "label": "法律法规",  "description": "法条、判例、合同 — 过滤页眉页脚、司法解释水印"},
    {"key": DocumentType.FINANCE,    "label": "金融财经",  "description": "研报、财报、理财 — 过滤风险提示、免责声明、股票代码刷屏"},
    {"key": DocumentType.NEWS,       "label": "新闻资讯",  "description": "新闻报道、资讯 — 过滤版权声明、记者署名、编辑信息"},
    {"key": DocumentType.LITERATURE, "label": "文学作品",  "description": "小说、散文、诗歌 — 过滤 OCR 噪声、章节编号噪声，保留对话"},
    {"key": DocumentType.BUSINESS,   "label": "商业管理",  "description": "商业报告、管理文档 — 过滤 PPT 页码、机密水印、页眉页脚"},
]

# 便于 O(1) 查询的 key 集合
DOCUMENT_TYPE_KEYS: frozenset[str] = frozenset(d["key"] for d in DOCUMENT_TYPES)

# key → label 映射
DOCUMENT_TYPE_LABELS: dict[str, str] = {d["key"]: d["label"] for d in DOCUMENT_TYPES}

# key → description 映射
DOCUMENT_TYPE_DESCRIPTIONS: dict[str, str] = {d["key"]: d["description"] for d in DOCUMENT_TYPES}


def is_valid_doc_type(doc_type: str) -> bool:
    """校验 doc_type 是否合法。"""
    return doc_type in DOCUMENT_TYPE_KEYS


def get_doc_type_label(doc_type: str) -> str:
    """获取 doc_type 的中文标签，未知类型返回原值。"""
    return DOCUMENT_TYPE_LABELS.get(doc_type, doc_type)
