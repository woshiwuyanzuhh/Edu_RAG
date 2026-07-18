"""Backward-compatible exports for LLM providers.

New code should import from src.providers.llm.
"""

__all__ = ["OpenAICompatClient"]


def __getattr__(name: str):
    if name == "OpenAICompatClient":
        from src.providers.llm.client import OpenAICompatClient

        return OpenAICompatClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
