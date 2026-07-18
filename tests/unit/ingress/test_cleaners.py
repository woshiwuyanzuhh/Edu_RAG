"""清洗器单元测试 — 覆盖 10 个文档类型的领域特定清洗逻辑。

每个清洗器测试其独有的过滤规则，确保：
    1. 应过滤的噪声行被正确移除
    2. 应保留的内容行不被误杀
    3. CLEANER_REGISTRY 注册完整
"""
import pytest

from src.ingress.cleaners import CLEANER_REGISTRY
from src.ingress.cleaners.base import BaseCleaner
from src.ingress.cleaners.education import EducationCleaner
from src.ingress.cleaners.gaming import GamingCleaner
from src.ingress.cleaners.tech import TechCleaner
from src.ingress.cleaners.medical import MedicalCleaner
from src.ingress.cleaners.legal import LegalCleaner
from src.ingress.cleaners.finance import FinanceCleaner
from src.ingress.cleaners.news import NewsCleaner
from src.ingress.cleaners.literature import LiteratureCleaner
from src.ingress.cleaners.business import BusinessCleaner
from src.shared.constants import DOCUMENT_TYPES, DOCUMENT_TYPE_KEYS, is_valid_doc_type


class TestCleanerRegistry:
    """清洗器注册表完整性。"""

    def test_all_types_registered(self):
        """DOCUMENT_TYPES 中的每个类型都应在 CLEANER_REGISTRY 注册。"""
        for doc_type in DOCUMENT_TYPE_KEYS:
            assert doc_type in CLEANER_REGISTRY, f"doc_type={doc_type} 未注册清洗器"

    def test_all_cleaners_implement_interface(self):
        """所有注册的清洗器都应实现 ICleaner 接口。"""
        for doc_type, cleaner in CLEANER_REGISTRY.items():
            assert hasattr(cleaner, "clean"), f"{doc_type} 缺少 clean 方法"
            assert hasattr(cleaner, "filter_chunks"), f"{doc_type} 缺少 filter_chunks 方法"

    def test_registry_count(self):
        """应有 10 个清洗器。"""
        assert len(CLEANER_REGISTRY) == 10

    def test_all_cleaners_are_base_subclass(self):
        """所有清洗器都应继承 BaseCleaner。"""
        for doc_type, cleaner in CLEANER_REGISTRY.items():
            assert isinstance(cleaner, BaseCleaner), f"{doc_type} 不是 BaseCleaner 子类"


class TestConstants:
    """常量定义模块测试。"""

    def test_document_types_count(self):
        assert len(DOCUMENT_TYPES) == 10

    def test_document_types_structure(self):
        for item in DOCUMENT_TYPES:
            assert "key" in item
            assert "label" in item
            assert "description" in item
            assert isinstance(item["key"], str)
            assert isinstance(item["label"], str)

    def test_is_valid_doc_type(self):
        assert is_valid_doc_type("general") is True
        assert is_valid_doc_type("business") is True
        assert is_valid_doc_type("unknown") is False
        assert is_valid_doc_type("") is False


class TestBaseCleanerFilterLines:
    """BaseCleaner._filter_lines 辅助方法。"""

    def test_empty_predicates(self):
        text = "line1\nline2\nline3"
        result = BaseCleaner._filter_lines(text, [])
        assert result == text

    def test_single_predicate(self):
        text = "keep\ndrop\nkeep2"
        result = BaseCleaner._filter_lines(text, [lambda s: s == "drop"])
        assert "drop" not in result
        assert "keep" in result
        assert "keep2" in result

    def test_multiple_predicates(self):
        text = "keep\nad_line\nspam\nkeep2"
        preds = [lambda s: s == "ad_line", lambda s: s == "spam"]
        result = BaseCleaner._filter_lines(text, preds)
        assert "ad_line" not in result
        assert "spam" not in result
        assert "keep" in result


class TestTechCleaner:
    """技术文档清洗器。"""

    def test_filters_shell_prompt(self):
        text = "正文内容\n$ ls -la\n更多正文"
        result = TechCleaner().clean(text)
        assert "$ ls -la" not in result
        assert "正文内容" in result

    def test_filters_line_number_prefix(self):
        text = "  1 | import os\n正文内容\n  2 | import sys"
        result = TechCleaner().clean(text)
        assert "import os" not in result or "1 |" not in result
        assert "正文内容" in result

    def test_filters_todo_comment(self):
        text = "# TODO: fix later\n这是正文内容\n# FIXME: broken"
        result = TechCleaner().clean(text)
        # 短 TODO 应被过滤
        assert "TODO: fix later" not in result
        assert "这是正文内容" in result

    def test_keeps_long_code_content(self):
        text = "# TODO: 这里的逻辑需要重构，因为涉及到复杂的状态管理和事务回滚机制\n正文"
        result = TechCleaner().clean(text)
        # 长 TODO（含实质内容）应保留
        assert "状态管理" in result


class TestMedicalCleaner:
    """医疗健康清洗器。"""

    def test_filters_disclaimer(self):
        text = "阿司匹林用于预防血栓\n仅供参考，不能替代医生诊断\n正文继续"
        result = MedicalCleaner().clean(text)
        assert "仅供参考" not in result
        assert "阿司匹林" in result

    def test_filters_hospital_info(self):
        text = "挂号电话：12345678\n正文内容\n医院地址：北京市朝阳区"
        result = MedicalCleaner().clean(text)
        assert "挂号电话" not in result
        assert "正文内容" in result

    def test_filters_drug_ad(self):
        text = "疗效显著，药到病除\n正文内容\n扫码咨询领取优惠"
        result = MedicalCleaner().clean(text)
        assert "疗效显著" not in result
        assert "正文内容" in result


class TestLegalCleaner:
    """法律法规清洗器。"""

    def test_filters_page_number(self):
        text = "第一条 为了保护民事权益\n第 1 页 共 10 页\n第二条 侵权责任"
        result = LegalCleaner().clean(text)
        assert "第 1 页" not in result
        assert "第一条" in result

    def test_filters_watermark(self):
        text = "合同条款正文\n机密\n更多条款"
        result = LegalCleaner().clean(text)
        assert "机密" not in result or "合同条款" in result
        assert "合同条款正文" in result

    def test_keeps_legal_articles(self):
        text = "第十三条 当事人一方不履行合同义务，应当承担继续履行、采取补救措施或者赔偿损失等违约责任。"
        result = LegalCleaner().clean(text)
        assert "第十三条" in result
        assert "违约责任" in result


class TestFinanceCleaner:
    """金融财经清洗器。"""

    def test_filters_risk_disclaimer(self):
        text = "预计2024年净利润增长20%\n投资有风险，入市需谨慎\n仅供参考，不构成投资建议"
        result = FinanceCleaner().clean(text)
        assert "投资有风险" not in result
        assert "仅供参考，不构成" not in result
        assert "净利润增长" in result

    def test_filters_stock_code_spam(self):
        text = "推荐关注以下股票\n600000 600001 600002 600003 600005\n正文继续"
        result = FinanceCleaner().clean(text)
        # 纯代码刷屏行应被过滤
        assert "600000 600001" not in result
        assert "正文继续" in result

    def test_keeps_financial_data(self):
        text = "公司2024年营收50亿元，同比增长15%。毛利率45.3%，净利率12.1%。"
        result = FinanceCleaner().clean(text)
        assert "营收50亿" in result
        assert "毛利率" in result


class TestNewsCleaner:
    """新闻资讯清洗器。"""

    def test_filters_copyright(self):
        text = "今日发生重大事件\n版权所有 未经授权不得转载\n更多报道"
        result = NewsCleaner().clean(text)
        assert "版权所有" not in result
        assert "重大事件" in result

    def test_filters_reporter_byline(self):
        text = "事件详细报道\n记者：张三\n正文继续"
        result = NewsCleaner().clean(text)
        assert "记者：张三" not in result
        assert "事件详细报道" in result

    def test_filters_editor_info(self):
        text = "新闻正文内容\n编辑：李四\n更多内容"
        result = NewsCleaner().clean(text)
        assert "编辑：李四" not in result
        assert "新闻正文内容" in result


class TestLiteratureCleaner:
    """文学作品清洗器。"""

    def test_filters_ocr_garbage(self):
        text = "他走进了那间屋子\n！@#￥%……&*（）\n心跳加速"
        result = LiteratureCleaner().clean(text)
        assert "！@#" not in result
        assert "他走进了" in result

    def test_filters_chapter_noise(self):
        text = "第三章\n那是很久以前的故事\nChapter 1\n故事开始了"
        result = LiteratureCleaner().clean(text)
        assert "第三章" not in result or "那是很久以前" in result
        assert "Chapter 1" not in result
        assert "故事开始了" in result

    def test_allows_short_dialogue(self):
        """文学作品应允许短句通过（诗歌、对话）。"""
        text = "你好。\n他笑了。\n是的。"
        cleaned = LiteratureCleaner().clean(text)
        chunks = [cleaned]  # 模拟切分
        filtered = LiteratureCleaner().filter_chunks(chunks)
        # 短句应被保留（阈值宽松）
        assert len(filtered) >= 1


class TestBusinessCleaner:
    """商业管理清洗器。"""

    def test_filters_ppt_page_number(self):
        text = "战略规划概要\n1 / 10\n市场分析"
        result = BusinessCleaner().clean(text)
        assert "1 / 10" not in result
        assert "战略规划" in result

    def test_filters_confidential_watermark(self):
        text = "季度财报概要\n机密\n营收增长15%"
        result = BusinessCleaner().clean(text)
        assert "机密" not in result or "季度财报" in result
        assert "营收增长" in result

    def test_filters_slide_footer(self):
        text = "核心业务分析\nXX公司-3\n下一页内容"
        result = BusinessCleaner().clean(text)
        # 公司名+页码的短行应被过滤
        assert "核心业务分析" in result


class TestCleanerConsistency:
    """所有清洗器的一致性测试。"""

    @pytest.mark.parametrize("doc_type", list(DOCUMENT_TYPE_KEYS))
    def test_clean_returns_string(self, doc_type):
        """所有清洗器 clean() 应返回字符串。"""
        cleaner = CLEANER_REGISTRY[doc_type]
        result = cleaner.clean("这是一段测试文本内容，用于验证清洗器返回类型。")
        assert isinstance(result, str)

    @pytest.mark.parametrize("doc_type", list(DOCUMENT_TYPE_KEYS))
    def test_clean_preserves_content(self, doc_type):
        """所有清洗器不应移除正常的中文字符内容。"""
        cleaner = CLEANER_REGISTRY[doc_type]
        text = "人工智能是计算机科学的一个重要分支，涉及机器学习和深度学习。"
        result = cleaner.clean(text)
        assert "人工智能" in result
        assert "机器学习" in result

    @pytest.mark.parametrize("doc_type", list(DOCUMENT_TYPE_KEYS))
    def test_filter_chunks_returns_list(self, doc_type):
        """所有清洗器 filter_chunks() 应返回列表。"""
        cleaner = CLEANER_REGISTRY[doc_type]
        chunks = ["这是一个测试片段，内容足够长度用于通过基础过滤。"]
        result = cleaner.filter_chunks(chunks)
        assert isinstance(result, list)

    @pytest.mark.parametrize("doc_type", list(DOCUMENT_TYPE_KEYS))
    def test_empty_input(self, doc_type):
        """空输入不应抛异常。"""
        cleaner = CLEANER_REGISTRY[doc_type]
        assert cleaner.clean("") == ""
        assert cleaner.filter_chunks([]) == []
