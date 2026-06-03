"""
Per-credentials agent cache, shared by every framework adapter.

The platform backend calls the runtime with `InvokeRequest.context.credentials`
populated from the requesting user's encrypted API keys. The adapter needs a
fresh framework client (`ChatOpenAI`, `OpenAI`, `Gemini`, ...) for those
credentials — but rebuilding it on every call would be wasteful, so we cache
the constructed agent keyed on a hash of the credential values.

How it slots in
---------------

Each adapter previously had:

    self._agent: SomeAgent | None = None    # one cached instance, no creds

Now it has:

    self._agent_cache = CredentialsCache(factory, ...)

and reads:

    agent = await self._agent_cache.get(request.context)

`get(...)` returns one of:
- the legacy single instance (when no credentials AND the factory takes none) —
  identical behavior to today, so existing tests don't change;
- a credentialed instance built per credential-hash key, capped at 8 entries.

Factories opt in by accepting a `credentials` keyword argument. If they don't,
credentials are silently ignored — the agent uses whatever it picks up from
process env vars (today's behavior). That keeps all the existing example
agents working unchanged.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
from collections import OrderedDict
from typing import Any, Awaitable, Callable

from ..protocol import Credentials


_MAX_ENTRIES = 8


def _factory_accepts_credentials(factory: Callable[..., Any]) -> bool:
    """True if `factory` declares a `credentials` parameter (or `**kwargs`)."""
    try:
        sig = inspect.signature(factory)
    except (TypeError, ValueError):
        return False
    for p in sig.parameters.values():
        if p.kind is inspect.Parameter.VAR_KEYWORD:
            return True
        if p.name == "credentials":
            return True
    return False


def _hash_credentials(creds: Credentials) -> str:
    """Stable hex hash of the credential values.

    Sorted by field name so the hash is order-insensitive. We hash the values
    (not the names) so two users with the same OpenAI key share a cache slot —
    a feature, not a leak: nothing about either user is in the cached agent.
    """
    h = hashlib.sha256()
    for name in sorted(type(creds).model_fields):
        value = getattr(creds, name)
        if value is None:
            continue
        h.update(name.encode())
        h.update(b"=")
        h.update(value.encode())
        h.update(b"\n")
    return h.hexdigest()


def _extract_credentials(context: dict[str, Any]) -> Credentials | None:
    raw = context.get("credentials")
    if not raw:
        return None
    if isinstance(raw, Credentials):
        return raw
    if isinstance(raw, dict):
        # Filter out None-valued keys so a fully-empty struct round-trips to None.
        if not any(v for v in raw.values()):
            return None
        return Credentials.model_validate(raw)
    return None


class CredentialsCache:
    """LRU-ish cache of factory results keyed on credentials hash.

    A single `OrderedDict` doubling as a small LRU: every `get` moves its key
    to the end; when we exceed `_MAX_ENTRIES`, we drop the oldest. Sync-safe
    via a single asyncio lock — concurrent first-time callers wait so the
    factory only runs once per key.
    """

    def __init__(
        self,
        factory: Callable[..., Any],
        *,
        validator: Callable[[Any], None] | None = None,
        builder: Callable[[Any], Awaitable[Any]] | None = None,
    ) -> None:
        """`factory` is the user's `build_agent` (sync or async). `validator`
        is called once per built agent to type-check it (raises on bad shape).
        `builder` runs framework-specific post-processing (e.g. ADK wraps the
        agent in a `Runner`). Both validator and builder may be omitted."""
        self._factory = factory
        self._validator = validator
        self._builder = builder
        self._accepts_creds = _factory_accepts_credentials(factory)
        self._entries: OrderedDict[str, Any] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, context: dict[str, Any]) -> Any:
        creds = _extract_credentials(context)
        # Normalize the key up front: a factory that doesn't accept credentials
        # collapses every request to a single slot (today's behavior, env-var
        # based) — so a second user supplying a different key still hits the
        # same cached agent. Done before the lookup so the lookup is correct.
        if creds is None or not self._accepts_creds:
            key = ""
        else:
            key = _hash_credentials(creds)

        async with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key]

            kwargs: dict[str, Any] = {}
            if creds is not None and self._accepts_creds:
                kwargs["credentials"] = creds

            result = self._factory(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            if self._validator is not None:
                self._validator(result)
            if self._builder is not None:
                result = await self._builder(result)

            self._entries[key] = result
            self._entries.move_to_end(key)
            while len(self._entries) > _MAX_ENTRIES:
                self._entries.popitem(last=False)
            return result
