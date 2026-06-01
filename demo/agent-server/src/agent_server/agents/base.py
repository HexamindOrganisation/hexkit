"""The agent interface a developer implements.

An agent declares the `framework` whose native events it emits, and its `run`
is an async generator yielding those native events (already JSON-able). The
server route wraps each as `{"framework": ..., "event": ...}` and frames it to
SSE; the HexaUI proxy selects the matching translator and normalizes the stream.

`framework="native"` means the agent emits the minimal already-normalized events
(see `agent_server.protocol`) — the zero-translation escape hatch.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Protocol


class Agent(Protocol):
    """A streaming agent. One `run` per request, yielding native events."""

    framework: str

    def run(
        self,
        *,
        input: dict[str, Any],
        context: dict[str, Any],
    ) -> AsyncIterator[dict]:
        ...
