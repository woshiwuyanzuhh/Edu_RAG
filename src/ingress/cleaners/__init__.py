"""文本清洗器 — 多领域策略。"""
from src.ingress.cleaners.base import BaseCleaner
from src.ingress.cleaners.education import EducationCleaner
from src.ingress.cleaners.gaming import GamingCleaner
from src.interfaces.cleaner import ICleaner

CLEANER_REGISTRY: dict[str, ICleaner] = {
    "general": BaseCleaner(),
    "education": EducationCleaner(),
    "gaming": GamingCleaner(),
}

__all__ = ["BaseCleaner", "EducationCleaner", "GamingCleaner", "CLEANER_REGISTRY"]
