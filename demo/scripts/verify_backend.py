#!/usr/bin/env python3
"""Contract-conformance checker for a HexKit developer backend.

Point it at *your own* running backend URL and it validates the CONTRACT.md §8
checklist the way the HexKit proxy would — assigning a run_id, reading the SSE
stream over a real socket, cancelling mid-run, and inspecting every frame's
shape. Each check prints PASS / FAIL / SKIP; the process exits non-zero if any
required check fails, so it doubles as a CI gate.

Usage:
    python verify_backend.py http://127.0.0.1:8880
    python verify_backend.py http://127.0.0.1:8880 --agent echo

Only dependency is httpx (already in the demo venvs). No proxy, no DB.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import uuid

import httpx

SUPPORTED_FRAMEWORKS = {
    "native",
    "langchain",
    "langgraph",
    "deepagents",
    "openai-agents",
    "google-adk",
}
NATIVE_EVENT_TYPES = {
    "text",
    "reasoning",
    "tool",
    "tool_result",
    "error",
    "done",
}
ROSTER_KEYS = {"id", "name", "role", "main_color", "ui_url"}

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


class Report:
    """Accumulates check outcomes and renders a final summary."""

    def __init__(self) -> None:
        self.failed = 0
        self.passed = 0
        self.skipped = 0

    def ok(self, label: str, detail: str = "") -> None:
        self.passed += 1
        print(f"  {GREEN}PASS{RESET} {label}" + (f" {DIM}— {detail}{RESET}" if detail else ""))

    def fail(self, label: str, detail: str = "") -> None:
        self.failed += 1
        print(f"  {RED}FAIL{RESET} {label}" + (f" {DIM}— {detail}{RESET}" if detail else ""))

    def skip(self, label: str, detail: str = "") -> None:
        self.skipped += 1
        print(f"  {YELLOW}SKIP{RESET} {label}" + (f" {DIM}— {detail}{RESET}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{title}")


async def check_roster(c: httpx.AsyncClient, r: Report) -> list[dict]:
    section("§3  GET /agents — roster")
    try:
        resp = await c.get("/agents")
    except httpx.HTTPError as e:
        r.fail("GET /agents reachable", str(e))
        return []
    if resp.status_code != 200:
        r.fail("GET /agents returns 200", f"got {resp.status_code}")
        return []
    try:
        roster = resp.json()
    except json.JSONDecodeError:
        r.fail("GET /agents returns JSON", "body was not JSON")
        return []
    if not isinstance(roster, list) or not roster:
        r.fail("roster is a non-empty list", repr(roster)[:80])
        return []
    r.ok("GET /agents returns 200 + a non-empty list", f"{len(roster)} agent(s)")

    for entry in roster:
        missing = ROSTER_KEYS - set(entry or {})
        label = f"entry '{(entry or {}).get('id', '?')}' has {sorted(ROSTER_KEYS)}"
        if missing:
            r.fail(label, f"missing {sorted(missing)}")
        else:
            r.ok(label)
        color = (entry or {}).get("main_color", "")
        if not re.fullmatch(r"#[0-9a-fA-F]{3,8}", str(color)):
            r.fail(f"  main_color of '{entry.get('id', '?')}' is a hex color", repr(color))
    return roster


async def check_ui(c: httpx.AsyncClient, r: Report, agent_id: str) -> str:
    section(f"§4  GET /agents/{agent_id}/ui — per-agent UI")
    resp = await c.get(f"/agents/{agent_id}/ui")
    if resp.status_code != 200:
        r.fail("returns 200", f"got {resp.status_code}")
        return ""
    ctype = resp.headers.get("content-type", "")
    if "yaml" in ctype:
        r.ok("Content-Type is text/yaml", ctype)
    else:
        r.fail("Content-Type is text/yaml", f"got {ctype!r}")
    text = resp.text
    if "main_color" in text:
        r.ok("ui.yaml declares page.main_color")
    else:
        r.fail("ui.yaml declares page.main_color")
    if "widgets" in text:
        r.ok("ui.yaml declares widgets")
    else:
        r.fail("ui.yaml declares widgets")

    bogus = f"__nope_{uuid.uuid4().hex[:6]}__"
    resp404 = await c.get(f"/agents/{bogus}/ui")
    if resp404.status_code == 404:
        r.ok("unknown agent id -> 404")
    else:
        r.fail("unknown agent id -> 404", f"got {resp404.status_code}")
    return text


async def check_stream(c: httpx.AsyncClient, r: Report, agent_id: str) -> None:
    section(f"§5  POST /agents/{agent_id}/stream — the run")
    run_id = uuid.uuid4().hex
    body = {
        "run_id": run_id,
        "input": {"messages": [{"role": "user", "content": "ping from verify_backend"}]},
        # Exercise the context the proxy forwards — backend must accept it.
        # Provider keys are NOT part of the context (the backend reads its own
        # from its env); the proxy forwards conversation_id, files, and user.
        "context": {
            "conversation_id": str(uuid.uuid4()),
            "files": [
                {"id": "f1", "name": "note.txt", "mime": "text/plain", "size": 5, "content": "hello"}
            ],
            "user": {"id": str(uuid.uuid4()), "name": "verify_backend", "role": None},
        },
    }
    frames: list[dict] = []
    frameworks: set[str] = set()
    bad_frame = None
    try:
        async with c.stream("POST", f"/agents/{agent_id}/stream", json=body) as resp:
            ctype = resp.headers.get("content-type", "")
            if "text/event-stream" in ctype:
                r.ok("Content-Type is text/event-stream", ctype)
            else:
                r.fail("Content-Type is text/event-stream", f"got {ctype!r}")
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if not payload:
                    continue
                try:
                    frame = json.loads(payload)
                except json.JSONDecodeError:
                    bad_frame = payload[:80]
                    continue
                frames.append(frame)
                if isinstance(frame, dict) and "framework" in frame:
                    frameworks.add(frame["framework"])
    except httpx.HTTPError as e:
        r.fail("stream is readable", str(e))
        return

    if not frames:
        r.fail("stream produced at least one frame")
        return
    r.ok("stream produced frames", f"{len(frames)} frame(s)")

    if bad_frame is not None:
        r.fail("every frame's data: is valid JSON", f"e.g. {bad_frame!r}")
    well_shaped = all(isinstance(f, dict) and "framework" in f and "event" in f for f in frames)
    if well_shaped:
        r.ok("every frame is {framework, event}")
    else:
        sample = next((f for f in frames if not (isinstance(f, dict) and "framework" in f and "event" in f)), None)
        r.fail("every frame is {framework, event}", f"e.g. {json.dumps(sample)[:80]}")

    unsupported = frameworks - SUPPORTED_FRAMEWORKS
    if frameworks and not unsupported:
        r.ok("framework is supported", ", ".join(sorted(frameworks)))
    else:
        r.fail("framework is supported", f"unknown: {sorted(unsupported)}")

    # For native streams, validate the event vocabulary too.
    if "native" in frameworks:
        types = {
            (f["event"] or {}).get("type")
            for f in frames
            if f.get("framework") == "native" and isinstance(f.get("event"), dict)
        }
        unknown = {t for t in types if t not in NATIVE_EVENT_TYPES}
        if not unknown:
            r.ok("native event types are in the vocabulary", ", ".join(sorted(t for t in types if t)))
        else:
            r.fail("native event types are in the vocabulary", f"unknown: {sorted(unknown)}")


async def check_cancel(c: httpx.AsyncClient, r: Report, agent_id: str) -> None:
    section(f"§5  POST /agents/{agent_id}/cancel — cancellation")
    # Unknown run id must report not-found rather than erroring.
    miss = await c.post(f"/agents/{agent_id}/cancel", json={"run_id": "definitely-not-a-run"})
    if miss.status_code == 200 and miss.json().get("cancelled") is False:
        r.ok("unknown run_id -> {cancelled: false}")
    else:
        r.fail("unknown run_id -> {cancelled: false}", f"{miss.status_code} {miss.text[:60]}")

    # Open a real run and cancel it mid-stream using the run_id we assigned.
    run_id = uuid.uuid4().hex
    body = {
        "run_id": run_id,
        "input": {"messages": [{"role": "user", "content": "stream a few words so we can cancel"}]},
        "context": {},
    }
    cancelled_resp: dict | None = None

    async def consume() -> None:
        try:
            async with c.stream("POST", f"/agents/{agent_id}/stream", json=body) as resp:
                async for _ in resp.aiter_lines():
                    pass
        except httpx.HTTPError:
            pass

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.25)  # let the stream open and emit a frame or two
    try:
        resp = await c.post(f"/agents/{agent_id}/cancel", json={"run_id": run_id})
        cancelled_resp = resp.json()
    except httpx.HTTPError as e:
        r.fail("cancel a live run", str(e))
    finally:
        await task

    if cancelled_resp is not None and "cancelled" in cancelled_resp:
        if cancelled_resp["cancelled"] is True:
            r.ok("live run -> {cancelled: true}")
        else:
            # Run may have finished before cancel landed — acceptable shape, note it.
            r.skip("live run -> {cancelled: true}", "run already finished (shape OK)")
    elif cancelled_resp is not None:
        r.fail("cancel returns {cancelled: bool}", json.dumps(cancelled_resp)[:60])


async def check_forget(c: httpx.AsyncClient, r: Report, agent_id: str) -> None:
    section(f"§5  POST /agents/{agent_id}/forget — memory lifecycle")
    resp = await c.post(
        f"/agents/{agent_id}/forget", json={"conversation_id": uuid.uuid4().hex}
    )
    if resp.status_code != 200:
        r.fail("forget an unknown conversation -> 200", f"got {resp.status_code}")
        return
    try:
        data = resp.json()
    except json.JSONDecodeError:
        r.fail("forget returns JSON")
        return
    if isinstance(data, dict) and isinstance(data.get("forgotten"), bool):
        r.ok("forget returns {forgotten: bool}")
    else:
        r.fail("forget returns {forgotten: bool}", json.dumps(data)[:60])


async def check_actions(c: httpx.AsyncClient, r: Report, agent_id: str, ui_text: str) -> None:
    section(f"§5b POST /agents/{agent_id}/actions/{{name}} — widget actions")
    # Strip YAML comments so wiring mentioned in prose doesn't count as real.
    ui_text = re.sub(r"(?m)#.*$", "", ui_text)
    uses_actions = ("data_source" in ui_text) or re.search(r"\baction:\s*\w", ui_text)
    if not uses_actions:
        r.skip("ui.yaml wires no action / data_source", "actions endpoint is optional here")
        return
    # Pull an action name out of the ui.yaml to call it for real.
    m = re.search(r"\baction:\s*([A-Za-z0-9_\-]+)", ui_text)
    name = m.group(1) if m else None
    if not name:
        r.skip("could not extract an action name from ui.yaml")
        return
    resp = await c.post(f"/agents/{agent_id}/actions/{name}", json={"args": {}})
    if resp.status_code != 200:
        r.fail(f"POST actions/{name} returns 200", f"got {resp.status_code}")
        return
    try:
        data = resp.json()
    except json.JSONDecodeError:
        r.fail(f"POST actions/{name} returns JSON")
        return
    if isinstance(data, dict) and "result" in data:
        r.ok(f"action '{name}' returns {{result}}")
    else:
        r.fail(f"action '{name}' returns {{result}}", json.dumps(data)[:60])


async def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a HexKit backend against CONTRACT.md §8.")
    ap.add_argument("base_url", help="Base URL of the running backend, e.g. http://127.0.0.1:8880")
    ap.add_argument("--agent", help="Agent id to exercise (default: first in the roster)")
    ap.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout seconds")
    args = ap.parse_args()

    print(f"HexKit contract conformance — {args.base_url}")
    r = Report()
    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), timeout=args.timeout) as c:
        roster = await check_roster(c, r)
        if not roster:
            print(f"\n{RED}Cannot continue without a roster.{RESET}")
            return 1
        agent_id = args.agent or roster[0]["id"]
        if args.agent and args.agent not in {a.get("id") for a in roster}:
            print(f"\n{RED}Agent '{args.agent}' is not in the roster.{RESET}")
            return 1
        print(f"\n{DIM}Exercising agent: {agent_id}{RESET}")

        ui_text = await check_ui(c, r, agent_id)
        await check_stream(c, r, agent_id)
        await check_cancel(c, r, agent_id)
        await check_forget(c, r, agent_id)
        await check_actions(c, r, agent_id, ui_text)

    print(
        f"\n{'-' * 56}\n"
        f"{GREEN}{r.passed} passed{RESET}, "
        f"{RED}{r.failed} failed{RESET}, "
        f"{YELLOW}{r.skipped} skipped{RESET}"
    )
    if r.failed:
        print(f"{RED}Backend is NOT conformant.{RESET}")
        return 1
    print(f"{GREEN}Backend is conformant.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
