"""
Parent-side process supervisor for a single per-agent worker.

Responsibilities
----------------
- Spawn the worker subprocess (`python -m platform_runtime.worker <dir>`).
- Own its stdin / stdout / stderr pipes.
- Demultiplex JSON-lines frames coming from stdout by request `id`:
    * single-shot responses (`result`/`error`)  → fulfill a Future
    * stream frames (`event`/`end`/`error`)     → push onto a Queue
- Drain stderr to the parent's logger so the worker's diagnostics are visible.
- Detect crashes (EOF on stdout) and fail all in-flight calls cleanly.
- Expose `rpc(method, params)` for unary calls and `stream_rpc(...)` for
  the streaming `stream` method.

The supervisor does NOT enforce a restart policy. It exposes `start`, `stop`,
`restart`, and `is_alive`. Higher layers (the registry / RemoteAdapter)
decide when to revive a dead worker. Implicit restart hides bugs during
development; explicit revival keeps behavior debuggable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, AsyncIterator
from uuid import uuid4


logger = logging.getLogger("platform_runtime.supervisor")


class WorkerCrashed(Exception):
    """The worker process is unavailable or died with an in-flight call."""


class WorkerSupervisor:
    """Owns one subprocess and the pipes to talk to it."""

    READY_TIMEOUT_S = 30.0
    STOP_GRACE_S = 5.0
    TERMINATE_GRACE_S = 2.0

    def __init__(
        self,
        agent_dir: str,
        *,
        python_executable: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._agent_dir = agent_dir
        self._python = python_executable or sys.executable
        self._env = env  # None ⇒ inherit parent env
        self._proc: asyncio.subprocess.Process | None = None

        # Demux state. Both maps are keyed by the wire correlation id.
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._streams: dict[str, asyncio.Queue[tuple[str, Any]]] = {}

        # Background tasks for stdout/stderr.
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None

        # Serializes writes to stdin so concurrent senders don't interleave.
        self._write_lock = asyncio.Lock()

        # Handshake state.
        self._ready = asyncio.Event()
        self._fatal: str | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Spawn the worker and wait for its `ready` handshake."""
        if self.is_alive():
            return

        # Reset state in case this is a restart.
        self._pending.clear()
        self._streams.clear()
        self._ready = asyncio.Event()
        self._fatal = None

        self._proc = await asyncio.create_subprocess_exec(
            self._python,
            "-m",
            "platform_runtime.worker",
            self._agent_dir,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )
        logger.info(
            "Worker spawned: pid=%s dir=%s",
            self._proc.pid,
            self._agent_dir,
        )

        self._reader_task = asyncio.create_task(self._read_stdout())
        self._stderr_task = asyncio.create_task(self._read_stderr())

        try:
            await asyncio.wait_for(self._ready.wait(), self.READY_TIMEOUT_S)
        except asyncio.TimeoutError as e:
            await self.stop()
            raise WorkerCrashed(
                f"Worker did not become ready within {self.READY_TIMEOUT_S}s"
            ) from e

        if self._fatal is not None:
            msg = self._fatal
            await self.stop()
            raise WorkerCrashed(f"Worker reported fatal: {msg}")

    async def stop(self) -> None:
        """Shut the worker down: send `close`, then escalate to signals."""
        proc = self._proc
        if proc is None:
            return

        if proc.returncode is None:
            try:
                # Politely ask it to close. We don't await a response — if
                # stdin is broken, just escalate.
                await self._send_raw(
                    {"id": uuid4().hex, "method": "close", "params": {}}
                )
            except Exception:  # noqa: BLE001
                pass

            try:
                await asyncio.wait_for(proc.wait(), self.STOP_GRACE_S)
            except asyncio.TimeoutError:
                logger.warning("Worker did not exit cleanly; SIGTERM")
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), self.TERMINATE_GRACE_S)
                except asyncio.TimeoutError:
                    logger.warning("Worker ignored SIGTERM; SIGKILL")
                    proc.kill()
                    await proc.wait()

        # Drain the background tasks. The read loops exit on EOF, which
        # happens once the child closes.
        for task in (self._reader_task, self._stderr_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass

        self._reader_task = None
        self._stderr_task = None
        self._proc = None

        self._fail_all("Worker stopped")

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    # ------------------------------------------------------------------
    # RPC surface
    # ------------------------------------------------------------------

    async def rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """One-shot request/response. Awaits the matching `result` or
        raises `WorkerCrashed` on `error` / crash."""
        if not self.is_alive():
            raise WorkerCrashed("Worker is not running")

        corr_id = uuid4().hex
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._pending[corr_id] = fut

        try:
            await self._send_raw(
                {"id": corr_id, "method": method, "params": params or {}}
            )
            return await fut
        finally:
            # In normal success/failure the dispatcher already popped it.
            # Pop again on cancellation paths so the map stays clean.
            self._pending.pop(corr_id, None)

    async def stream_rpc(
        self, method: str, params: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """Streaming RPC. Yields each `event` payload dict; returns on `end`;
        raises on `error` or worker crash.

        If the caller breaks out early, the queue is removed from the demux
        map so further frames for this id are silently dropped. The worker
        keeps producing them until its handler finishes — that's accepted
        waste; the alternative (a cancel frame) is on the roadmap."""
        if not self.is_alive():
            raise WorkerCrashed("Worker is not running")

        corr_id = uuid4().hex
        q: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        self._streams[corr_id] = q

        try:
            await self._send_raw(
                {"id": corr_id, "method": method, "params": params}
            )
            while True:
                kind, payload = await q.get()
                if kind == "event":
                    yield payload
                elif kind == "end":
                    return
                elif kind == "error":
                    # `payload` is a WorkerCrashed instance.
                    raise payload
        finally:
            self._streams.pop(corr_id, None)

    # ------------------------------------------------------------------
    # Internals: write side
    # ------------------------------------------------------------------

    async def _send_raw(self, frame: dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdin.is_closing():
            raise WorkerCrashed("Worker stdin is not writable")

        line = (json.dumps(frame, separators=(",", ":")) + "\n").encode("utf-8")
        async with self._write_lock:
            proc.stdin.write(line)
            await proc.stdin.drain()

    # ------------------------------------------------------------------
    # Internals: read side
    # ------------------------------------------------------------------

    async def _read_stdout(self) -> None:
        """Background loop: parse every JSON-lines frame and dispatch."""
        proc = self._proc
        assert proc is not None and proc.stdout is not None
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break  # Child closed → EOF
                try:
                    frame = json.loads(line)
                except json.JSONDecodeError:
                    logger.error("Discarding malformed frame: %r", line[:200])
                    continue
                self._dispatch(frame)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("stdout reader crashed")
        finally:
            # The child is gone (or we are tearing down). Anyone awaiting
            # a response gets a clear error.
            self._fail_all("Worker process exited")

    async def _read_stderr(self) -> None:
        """Forward the worker's stderr to our own logger, line by line."""
        proc = self._proc
        assert proc is not None and proc.stderr is not None
        try:
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                logger.warning(
                    "worker[%s]: %s",
                    self._agent_dir,
                    line.decode("utf-8", errors="replace").rstrip(),
                )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("stderr reader crashed")

    def _dispatch(self, frame: dict[str, Any]) -> None:
        """Route one parsed frame to the right consumer."""
        if frame.get("ready") is True:
            self._ready.set()
            return

        if "fatal" in frame:
            fatal = frame["fatal"]
            self._fatal = fatal.get("message", "unknown fatal")
            self._ready.set()  # Unblock start() so it can raise.
            self._fail_all(f"Worker fatal: {self._fatal}")
            return

        corr_id = frame.get("id")
        if not isinstance(corr_id, str):
            logger.error("Frame without correlation id: %r", frame)
            return

        if "result" in frame:
            fut = self._pending.pop(corr_id, None)
            if fut is not None and not fut.done():
                fut.set_result(frame["result"])
            return

        if "error" in frame:
            err = frame["error"]
            exc = WorkerCrashed(
                f"{err.get('type', 'Error')}: {err.get('message', '')}"
            )
            fut = self._pending.pop(corr_id, None)
            if fut is not None and not fut.done():
                fut.set_exception(exc)
                return
            q = self._streams.get(corr_id)
            if q is not None:
                # Stream-side error terminates the stream.
                q.put_nowait(("error", exc))
            return

        if "event" in frame:
            q = self._streams.get(corr_id)
            if q is not None:
                q.put_nowait(("event", frame["event"]))
            # else: stream was cancelled on our side — silently drop.
            return

        if frame.get("end") is True:
            q = self._streams.get(corr_id)
            if q is not None:
                q.put_nowait(("end", None))
            return

        logger.error("Unknown frame shape: %r", frame)

    def _fail_all(self, reason: str) -> None:
        """Fail every pending request and stream. Called on crash / shutdown."""
        exc = WorkerCrashed(reason)
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()
        for q in self._streams.values():
            q.put_nowait(("error", exc))
        self._streams.clear()
