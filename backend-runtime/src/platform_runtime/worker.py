"""
Per-agent worker entrypoint.

Run as:

    python -m platform_runtime.worker <agent_dir>

The worker hosts EXACTLY ONE agent inside its own process. It uses the same
in-process `LangChainAdapter` we already had, but lives behind the IPC wire
protocol defined in `platform_runtime.ipc`.

The main loop:

  1. Load the agent (manifest + entrypoint) via the existing AgentRegistry.
     If loading fails before the IPC handshake, emit a `fatal` frame and
     exit non-zero — the parent will see EOF on stdout and surface the
     error.
  2. Emit `{"ready": true}` so the parent knows we're up.
  3. Read JSON-lines requests from stdin in a loop. Dispatch each request
     concurrently to a handler coroutine (multiple streams can interleave).
  4. Each handler writes its result / events / end frames back on stdout,
     tagged with the request's `id`.
  5. A `close` request, or stdin EOF, ends the loop cleanly.

stdout is the wire — never write to it directly anywhere else. Use logging
(which goes to stderr) for diagnostics.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import traceback
from typing import Any

# Activate built-in adapters. The decorator registration is what makes
# `framework: langchain` etc. resolvable inside this child process.
from .adapters import langchain_adapter  # noqa: F401

# Optional adapters (extras must be installed). Silent on absence — the
# worker only needs the adapter for THIS agent's framework anyway, and
# the registry will fail with a clear error if it's missing.
try:  # pragma: no cover
    from .adapters import openai_agents_adapter  # noqa: F401
except ImportError:
    pass
from .ipc import (
    WorkerRequest,
    connect_stdin_reader,
    frame_end,
    frame_error,
    frame_event,
    frame_fatal,
    frame_ready,
    frame_result,
    write_frame_sync,
)
from .protocol import InvokeRequest, UnifiedAgentRuntime
from .registry import AgentRegistry


logger = logging.getLogger("platform_runtime.worker")


# stdout writes from concurrent handlers must not interleave. POSIX guarantees
# atomicity only for writes ≤ PIPE_BUF (4096 bytes on Linux); a long event
# payload could split. A single lock serializes all frame writes.
_stdout_lock: asyncio.Lock | None = None


async def _emit(frame: dict[str, Any]) -> None:
    assert _stdout_lock is not None
    async with _stdout_lock:
        # The actual byte write is synchronous (sys.stdout is a regular file
        # object). Holding the lock around it is enough; no need to push the
        # work off-thread for the small frames we exchange.
        write_frame_sync(sys.stdout.buffer, frame)


# ---------------------------------------------------------------------------
# Per-request handlers
# ---------------------------------------------------------------------------

async def _handle(req: WorkerRequest, runtime: UnifiedAgentRuntime) -> None:
    """Dispatch one request and emit the appropriate response frame(s).

    All exceptions from inside this function become `error` frames tagged
    with the request id. This guarantees the parent always gets a terminal
    frame for every request id it sent (either result, end, or error).
    """
    try:
        if req.method == "metadata":
            md = await runtime.metadata()
            await _emit(frame_result(req.id, md.model_dump(mode="json")))

        elif req.method == "tools":
            tools = await runtime.tools()
            await _emit(
                frame_result(
                    req.id,
                    [t.model_dump(mode="json") for t in tools],
                )
            )

        elif req.method == "health":
            h = await runtime.health()
            await _emit(frame_result(req.id, h.model_dump(mode="json")))

        elif req.method == "invoke":
            ir = InvokeRequest.model_validate(req.params)
            r = await runtime.invoke(ir)
            await _emit(frame_result(req.id, r.model_dump(mode="json")))

        elif req.method == "stream":
            ir = InvokeRequest.model_validate(req.params)
            async for event in runtime.stream(ir):
                await _emit(frame_event(req.id, event.model_dump(mode="json")))
            await _emit(frame_end(req.id))

        else:
            # Shouldn't happen — Pydantic Literal validation catches unknown
            # methods on the way in. Defensive only.
            await _emit(
                frame_error(
                    req.id,
                    f"Unknown method '{req.method}'",
                    "ValueError",
                )
            )

    except Exception as e:  # noqa: BLE001 — boundary; we MUST not raise
        logger.exception("Handler failed for request %s", req.id)
        await _emit(frame_error(req.id, str(e), type(e).__name__))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def _main(agent_dir: str) -> int:
    global _stdout_lock
    _stdout_lock = asyncio.Lock()

    # Step 1: load the agent. Anything failing here is fatal — the worker
    # can't host an agent it couldn't construct.
    registry = AgentRegistry()
    try:
        loaded = registry.load(agent_dir)
    except Exception as e:
        logger.exception("Failed to load agent at %s", agent_dir)
        write_frame_sync(sys.stdout.buffer, frame_fatal(f"{type(e).__name__}: {e}"))
        return 2

    runtime = loaded.runtime
    logger.info(
        "Worker ready: agent_id=%s framework=%s",
        loaded.manifest.agent_id,
        loaded.manifest.framework,
    )

    # Step 2: handshake.
    await _emit(frame_ready())

    # Step 3: request loop.
    reader = await connect_stdin_reader()
    inflight: set[asyncio.Task[Any]] = set()
    close_requested = False

    while True:
        line = await reader.readline()
        if not line:
            # Parent closed our stdin → graceful shutdown.
            break

        try:
            raw = json.loads(line)
            req = WorkerRequest.model_validate(raw)
        except Exception as e:  # noqa: BLE001
            # Malformed frame: there is no correlation id to attach to, so
            # we can only log. The parent should never send these.
            logger.error("Discarding malformed frame: %s (%s)", e, line[:200])
            continue

        if req.method == "close":
            # Confirm + exit. We do not start new handlers after this.
            await _emit(frame_result(req.id, {"closed": True}))
            close_requested = True
            break

        # Dispatch concurrently. Multiple in-flight streams are fine — the
        # `id` tag is what keeps their frames separable on the wire.
        task = asyncio.create_task(_handle(req, runtime))
        inflight.add(task)
        task.add_done_callback(inflight.discard)

    # Step 4: drain in-flight handlers before exiting. They each emit their
    # terminal frame so the parent's pending requests resolve.
    if inflight:
        logger.info("Draining %d in-flight handler(s)", len(inflight))
        await asyncio.gather(*inflight, return_exceptions=True)

    try:
        await runtime.aclose()
    except Exception:  # noqa: BLE001
        logger.exception("runtime.aclose() failed")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="platform_runtime.worker")
    parser.add_argument("agent_dir", help="Directory containing agent.yaml")
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python log level for the worker's own logs (stderr).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        stream=sys.stderr,
        level=args.log_level.upper(),
        format="[worker] %(levelname)s %(name)s: %(message)s",
    )

    try:
        code = asyncio.run(_main(args.agent_dir))
    except KeyboardInterrupt:
        code = 130
    except Exception:
        # Last-chance dump to stderr; the parent will pick this up.
        traceback.print_exc(file=sys.stderr)
        code = 1

    sys.exit(code)


if __name__ == "__main__":
    main()
