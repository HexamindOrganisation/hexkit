"""Framework translator registry.

Each developer backend tags its stream frames with a `framework`; the proxy
selects the matching translator, which normalizes that framework's native
events into the rich internal schema. `native` is the escape hatch for custom
loops / unsupported frameworks (already-normalized minimal events).
"""

from __future__ import annotations

from .base import BaseTranslator
from .fortify import FortifyTranslator
from .google_adk import GoogleADKTranslator
from .langchain import LangChainTranslator
from .native import NativeTranslator
from .openai_agents import OpenAIAgentsTranslator

_REGISTRY: dict[str, type[BaseTranslator]] = {
    "native": NativeTranslator,
    "langchain": LangChainTranslator,
    "langgraph": LangChainTranslator,
    "deepagents": LangChainTranslator,
    "openai-agents": OpenAIAgentsTranslator,
    "google-adk": GoogleADKTranslator,
    "fortify": FortifyTranslator,
}

SUPPORTED_FRAMEWORKS = tuple(_REGISTRY)


def get_translator(framework: str | None) -> BaseTranslator | None:
    """Return a fresh translator for `framework`, or None if unsupported."""
    cls = _REGISTRY.get((framework or "").lower())
    return cls() if cls is not None else None


__all__ = ["BaseTranslator", "get_translator", "SUPPORTED_FRAMEWORKS"]
