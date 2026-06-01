"""Mid-stream cancel check against the agent-server (the part TestClient can't
drive concurrently). The agent-server speaks the MINIMAL developer format, so we
parse `data:` JSON `type` fields. Starts a stream, cancels it mid-flight via the
contract's POST /agents/{id}/cancel {run_id}, and asserts the stream stops early
(fewer events than a full run) and cancel returns {cancelled: true}. The proxy
is what synthesizes run_end; here we just prove the dev stream halts."""

import asyncio
import json
import os

import httpx

BASE = os.environ.get("AGENT_URL", "http://127.0.0.1:8080")


async def main():
    async with httpx.AsyncClient(base_url=BASE) as c:
        run_id = "cancel-run-1"
        body = {
            "run_id": run_id,
            "input": {"messages": [{"role": "user",
                                    "content": "one two three four five six seven eight"}]},
            "context": {},
        }
        types = []
        got_text = False
        cancelled_resp = None
        async with c.stream("POST", "/agents/probe/stream", json=body) as resp:
            buf = b""
            async for chunk in resp.aiter_bytes():
                buf += chunk
                while b"\n\n" in buf:
                    frame, buf = buf.split(b"\n\n", 1)
                    data = next((l[len("data:"):].strip()
                                 for l in frame.decode().splitlines()
                                 if l.startswith("data:")), None)
                    if not data:
                        continue
                    packet = json.loads(data)
                    # Wire frame is {"framework": ..., "event": <native event>}.
                    ev = packet.get("event", packet)
                    etype = ev.get("type") if isinstance(ev, dict) else None
                    types.append(etype)
                    if etype == "text":
                        got_text = True
                    # After we've seen some streamed text, fire cancel.
                    if got_text and cancelled_resp is None:
                        cancelled_resp = (await c.post("/agents/probe/cancel",
                                                       json={"run_id": run_id})).json()

    ok_cancel = cancelled_resp == {"cancelled": True}
    # A full run streams 8 words + a tool + tool_result. Cancelling after the
    # first text chunk must stop it well short of that and before the tool runs.
    ok_early = "tool" not in types and len(types) < 8
    print("event types:", types)
    print("cancel response:", cancelled_resp)
    print(("  OK  " if ok_cancel else " FAIL ") + "cancel returned {cancelled: True}")
    print(("  OK  " if ok_early else " FAIL ") + "stream halted early (before tool / full text)")
    if not (ok_cancel and ok_early):
        raise SystemExit(1)
    print("\nCANCEL CHECK PASSED")


asyncio.run(main())
