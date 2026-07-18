"""Generation layer public exports.

The service facade is loaded lazily so utility submodules can be imported
without initializing configuration or provider dependencies.
"""

__all__ = ["GenerationService"]


def __getattr__(name: str):
    if name == "GenerationService":
        from src.generation.service import GenerationService

        return GenerationService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
