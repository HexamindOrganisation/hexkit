"""
Adapter registry.

Each framework adapter (LangChain, OpenAI Agents SDK, ...) lives in its own
submodule and registers itself via `@register_adapter("framework_name")`.
The agent registry calls `get_adapter_class(framework)` to look it up.

This pattern keeps adapter selection a one-line table lookup instead of a
chain of `if framework == ...` branches scattered across the codebase.
"""

from __future__ import annotations

from typing import Callable, TypeVar

from ..protocol import UnifiedAgentRuntime


_REGISTRY: dict[str, type[UnifiedAgentRuntime]] = {}

A = TypeVar("A", bound=type[UnifiedAgentRuntime])


def register_adapter(framework: str) -> Callable[[A], A]:
    """Decorator: register an adapter class under a framework name.

    Usage:
        @register_adapter("langchain")
        class LangChainAdapter(UnifiedAgentRuntime):
            ...
    """

    def decorator(cls: A) -> A:
        existing = _REGISTRY.get(framework)
        if existing is not None and existing is not cls:
            raise RuntimeError(
                f"Adapter for framework '{framework}' already registered "
                f"({existing.__name__}); refusing to overwrite with "
                f"{cls.__name__}."
            )
        _REGISTRY[framework] = cls
        return cls

    return decorator


def get_adapter_class(framework: str) -> type[UnifiedAgentRuntime]:
    """Look up the adapter class for a framework, or raise KeyError."""
    try:
        return _REGISTRY[framework]
    except KeyError as e:
        raise KeyError(
            f"No adapter registered for framework '{framework}'. "
            f"Registered: {sorted(_REGISTRY)}"
        ) from e


def registered_frameworks() -> list[str]:
    return sorted(_REGISTRY)
