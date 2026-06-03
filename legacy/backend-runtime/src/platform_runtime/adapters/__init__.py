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


def register_adapter(
    framework: str, *aliases: str
) -> Callable[[A], A]:
    """Decorator: register an adapter class under a framework name and any
    number of aliases.

    Aliases all dispatch to the same adapter class. Use them when several
    framework names share an underlying runtime (e.g. `langchain`,
    `langgraph`, and `deepagents` all produce LangChain `Runnable`s and
    share one adapter implementation).

    Usage:
        @register_adapter("langchain", "langgraph", "deepagents")
        class LangChainAdapter(UnifiedAgentRuntime):
            ...
    """

    def decorator(cls: A) -> A:
        for name in (framework, *aliases):
            existing = _REGISTRY.get(name)
            if existing is not None and existing is not cls:
                raise RuntimeError(
                    f"Adapter for framework '{name}' already registered "
                    f"({existing.__name__}); refusing to overwrite with "
                    f"{cls.__name__}."
                )
            _REGISTRY[name] = cls
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
