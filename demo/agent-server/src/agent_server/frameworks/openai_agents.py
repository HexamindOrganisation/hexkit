"""Project OpenAI Agents SDK stream events into HexKit native events.

Reusable for any ``agents.Agent``: ``to_native_event`` maps one
``stream_events()`` item to the native JSON event the proxy's
``OpenAIAgentsTranslator`` reads; ``agent_input`` shapes HexKit input for the SDK.
"""

from __future__ import annotations

from typing import Any

from .. import protocol


def agent_input(input: dict[str, Any]) -> Any:
    """HexKit ``{"messages": [...]}`` → SDK input (full transcript, or last user text)."""
    messages = (input or {}).get("messages")
    if isinstance(messages, list) and messages:
        return messages
    return protocol.last_user_text(input)


def to_native_event(sdk_event: Any, tool_names_by_id: dict[str, str]) -> dict | None:
    """One SDK ``stream_events()`` item → the native JSON event the proxy reads
    (``None`` to drop it).

    Besides serializing the SDK objects, this renames the SDK's event types
    (``*_event``) to the ones the translator matches (``raw_response`` /
    ``run_item``). ``tool_names_by_id`` lets the tool-output event recover its
    name, which the SDK's output item omits.
    """
    event_type = getattr(sdk_event, "type", None)

    # Streamed assistant text.
    if event_type == "raw_response_event":
        data = getattr(sdk_event, "data", None)
        if getattr(data, "type", None) == "response.output_text.delta":
            delta = getattr(data, "delta", "") or ""
            if delta:
                return {
                    "type": "raw_response",
                    "data": {"type": "response.output_text.delta", "delta": delta},
                }
        return None

    # Tool calls + the message-finalized marker.
    if event_type == "run_item_stream_event":
        item_name = getattr(sdk_event, "name", None)
        item = getattr(sdk_event, "item", None)
        raw_item = getattr(item, "raw_item", None)

        if item_name == "tool_called":
            call_id = getattr(raw_item, "call_id", None) or getattr(raw_item, "id", "") or ""
            tool_name = getattr(raw_item, "name", "tool") or "tool"
            arguments = getattr(raw_item, "arguments", "") or "{}"  # JSON string; proxy parses
            tool_names_by_id[call_id] = tool_name
            return {
                "type": "run_item",
                "name": "tool_called",
                "item": {
                    "raw_item": {
                        "call_id": call_id,
                        "name": tool_name,
                        "arguments": arguments,
                    }
                },
            }

        if item_name == "tool_output":
            # output item's raw_item is a dict (function_call_output), not a model
            call_id = (
                raw_item.get("call_id", "")
                if isinstance(raw_item, dict)
                else getattr(raw_item, "call_id", "")
            )
            return {
                "type": "run_item",
                "name": "tool_output",
                "item": {
                    "raw_item": {
                        "call_id": call_id,
                        "name": tool_names_by_id.get(call_id, "tool"),
                    },
                    "output": getattr(item, "output", None),
                },
            }

        if item_name == "message_output_created":
            # Closes the open text block; content already streamed as deltas.
            return {
                "type": "run_item",
                "name": "message_output_created",
                "item": {"raw_item": {"content": []}},
            }

    # Everything else (agent_updated, handoffs, …) is dropped, like the translator.
    return None
