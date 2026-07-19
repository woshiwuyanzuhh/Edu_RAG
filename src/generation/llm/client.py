"""Backward-compatible import path for the OpenAI-compatible LLM client.

New code should import from src.providers.llm.client.
"""

from src.providers.llm.client import OpenAICompatClient

__all__ = ["OpenAICompatClient"]
