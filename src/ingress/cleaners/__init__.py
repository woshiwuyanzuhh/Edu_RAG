"""文本清洗器 — 多领域策略。

按文档类型（doc_type）选择对应的清洗器：
    general     → BaseCleaner        通用基础清洗
    education   → EducationCleaner   教育（页码/水印/参考文献）
    gaming      → GamingCleaner      游戏攻略（签名/广告/emoji）
    tech        → TechCleaner        技术文档（行号/shell/TODO）
    medical     → MedicalCleaner     医疗健康（免责声明/广告）
    legal       → LegalCleaner       法律法规（水印/页眉脚）
    finance     → FinanceCleaner     金融财经（风险提示/代码刷屏）
    news        → NewsCleaner        新闻资讯（版权/署名/来源）
    literature  → LiteratureCleaner  文学作品（OCR噪声/章节噪声，保留对话）
    business    → BusinessCleaner    商业管理（PPT页码/机密水印）

新增类型步骤：
    1. 在 src/shared/constants.py 的 DOCUMENT_TYPES 添加条目
    2. 在本文件 import + 注册
    3. 实现清洗器类（继承 BaseCleaner）
    4. 在前端 UploadPage.vue / upload.html 添加下拉选项（如需）
"""

from src.ingress.cleaners.base import BaseCleaner
from src.ingress.cleaners.business import BusinessCleaner
from src.ingress.cleaners.education import EducationCleaner
from src.ingress.cleaners.finance import FinanceCleaner
from src.ingress.cleaners.gaming import GamingCleaner
from src.ingress.cleaners.legal import LegalCleaner
from src.ingress.cleaners.literature import LiteratureCleaner
from src.ingress.cleaners.medical import MedicalCleaner
from src.ingress.cleaners.news import NewsCleaner
from src.ingress.cleaners.tech import TechCleaner
from src.interfaces.cleaner import ICleaner
from src.shared.constants import DocumentType

# 清洗器注册表: doc_type → ICleaner
# 顺序与 DOCUMENT_TYPES 保持一致
CLEANER_REGISTRY: dict[str, ICleaner] = {
    DocumentType.GENERAL: BaseCleaner(),
    DocumentType.EDUCATION: EducationCleaner(),
    DocumentType.GAMING: GamingCleaner(),
    DocumentType.TECH: TechCleaner(),
    DocumentType.MEDICAL: MedicalCleaner(),
    DocumentType.LEGAL: LegalCleaner(),
    DocumentType.FINANCE: FinanceCleaner(),
    DocumentType.NEWS: NewsCleaner(),
    DocumentType.LITERATURE: LiteratureCleaner(),
    DocumentType.BUSINESS: BusinessCleaner(),
}

__all__ = [
    "BaseCleaner",
    "EducationCleaner",
    "GamingCleaner",
    "TechCleaner",
    "MedicalCleaner",
    "LegalCleaner",
    "FinanceCleaner",
    "NewsCleaner",
    "LiteratureCleaner",
    "BusinessCleaner",
    "CLEANER_REGISTRY",
]
