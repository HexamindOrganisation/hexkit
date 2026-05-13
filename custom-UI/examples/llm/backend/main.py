"""Minimalist FastAPI backend for the agent-ui minimal example.

Endpoints:
  - GET    /conversations           → list of summaries
  - POST   /conversations           → create a new empty conversation
  - GET    /conversations/{id}      → messages for one conversation
  - POST   /chat                    → stream OpenAI completion; persists if conversation_id given
  - GET    /metrics                 → cumulative LLM metrics for this server process
"""

from __future__ import annotations

import os
import time
import uuid
from typing import AsyncIterator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

app = FastAPI(title="agent-ui minimal backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def now_ms() -> int:
    return int(time.time() * 1000)


# ----- Metrics tracking -------------------------------------------------------
# Approximate per-1M-token USD pricing. Override via env if you care about
# precision; this is good enough for an example dashboard.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini":  (0.15,  0.60),
    "gpt-4o":       (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4":       (30.00, 60.00),
}

METRICS: dict[str, float] = {
    "requests": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "cost_usd": 0.0,
    "last_latency_ms": 0,
    "last_prompt_tokens": 0,
    "last_completion_tokens": 0,
    "last_total_tokens": 0,
}


def _record_usage(usage: dict, latency_ms: int) -> None:
    pt = int(usage.get("prompt_tokens") or 0)
    ct = int(usage.get("completion_tokens") or 0)
    tt = pt + ct
    in_rate, out_rate = PRICING.get(MODEL, PRICING["gpt-4o-mini"])
    cost = (pt * in_rate + ct * out_rate) / 1_000_000
    METRICS["requests"] = int(METRICS["requests"]) + 1
    METRICS["prompt_tokens"] = int(METRICS["prompt_tokens"]) + pt
    METRICS["completion_tokens"] = int(METRICS["completion_tokens"]) + ct
    METRICS["total_tokens"] = int(METRICS["total_tokens"]) + tt
    METRICS["cost_usd"] = float(METRICS["cost_usd"]) + cost
    METRICS["last_latency_ms"] = latency_ms
    METRICS["last_prompt_tokens"] = pt
    METRICS["last_completion_tokens"] = ct
    METRICS["last_total_tokens"] = tt


CONVERSATIONS: dict[str, dict] = {
    "c1": {
        "summary": {
            "id": "c1",
            "title": "Quarterly report review",
            "preview": "Walk me through the Q3 numbers…",
            "timestamp": now_ms() - 1000 * 60 * 60 * 24,
        },
        "messages": [
            {"id": "c1-1", "role": "user", "content": "Walk me through the Q3 numbers."},
            {"id": "c1-2", "role": "assistant", "content": "Revenue was $4.2M, up 18% YoY."},
        ],
    },
    "c2": {
        "summary": {
            "id": "c2",
            "title": "Refactor the billing module",
            "preview": "Here's the plan for splitting out invoices.",
            "timestamp": now_ms() - 1000 * 60 * 60 * 4,
        },
        "messages": [
            {"id": "c2-1", "role": "user", "content": "Here's the plan for splitting out invoices."},
            {"id": "c2-2", "role": "assistant", "content": "Looks good. Let's stage the migration."},
        ],
    },
}


@app.get("/conversations")
def list_conversations() -> list[dict]:
    items = [c["summary"] for c in CONVERSATIONS.values()]
    items.sort(key=lambda s: s.get("timestamp", 0), reverse=True)
    return items


@app.post("/conversations")
def create_conversation() -> dict:
    cid = uuid.uuid4().hex[:8]
    summary = {
        "id": cid,
        "title": "New chat",
        "preview": "",
        "timestamp": now_ms(),
    }
    CONVERSATIONS[cid] = {"summary": summary, "messages": []}
    return summary


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> list[dict]:
    convo = CONVERSATIONS.get(conversation_id)
    if convo is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return convo["messages"]


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    conversation_id: Optional[str] = None


@app.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    convo = CONVERSATIONS.get(req.conversation_id) if req.conversation_id else None

    if convo is not None and req.messages:
        last = req.messages[-1]
        if last.role == "user":
            convo["messages"].append(
                {
                    "id": f"{req.conversation_id}-{len(convo['messages'])}",
                    "role": "user",
                    "content": last.content,
                }
            )
            summary = convo["summary"]
            summary["preview"] = last.content[:80]
            summary["timestamp"] = now_ms()
            if summary["title"] == "New chat":
                summary["title"] = last.content[:48] or "New chat"

    async def stream() -> AsyncIterator[str]:
        started = time.perf_counter()
        completion = await client.chat.completions.create(
            model=MODEL,
            messages=[m.model_dump() for m in req.messages],
            stream=True,
            stream_options={"include_usage": True},
        )
        full = ""
        usage: dict = {}
        async for chunk in completion:
            # The terminal chunk from `include_usage` carries empty `choices`
            # and a populated `usage` field.
            if getattr(chunk, "usage", None) is not None:
                usage = chunk.usage.model_dump()
            if chunk.choices:
                delta = chunk.choices[0].delta.content
                if delta:
                    full += delta
                    yield delta
        latency_ms = int((time.perf_counter() - started) * 1000)
        if usage:
            _record_usage(usage, latency_ms)
        if convo is not None:
            convo["messages"].append(
                {
                    "id": f"{req.conversation_id}-{len(convo['messages'])}",
                    "role": "assistant",
                    "content": full,
                }
            )

    return StreamingResponse(stream(), media_type="text/plain")


@app.get("/metrics")
def get_metrics() -> dict:
    """Cumulative LLM metrics. Each cell can be a primitive or
    `{ value, delta?, hint? }` — see the agent-ui `metrics` widget docs."""
    last_tt = int(METRICS["last_total_tokens"])
    last_lat = int(METRICS["last_latency_ms"])
    return {
        "requests": int(METRICS["requests"]),
        "total_tokens": (
            {
                "value": int(METRICS["total_tokens"]),
                "delta": last_tt or None,
                "hint": "last request" if last_tt else "no requests yet",
            }
        ),
        "cost": {
            "value": round(float(METRICS["cost_usd"]), 6),
            "hint": f"USD · {MODEL}",
        },
        "latency": (
            {"value": last_lat, "hint": "last request"}
            if last_lat
            else {"value": 0, "hint": "no requests yet"}
        ),
    }
