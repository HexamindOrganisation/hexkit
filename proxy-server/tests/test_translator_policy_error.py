"""hexgate >= 0.3 returns a blocked call as an ordinary tool result prefixed
``[policy_denied]`` / ``[approval_required]``. The translators must surface that
as the step's ``error`` so the tool-calls widget renders a blocked step."""

from hexa_events import RunEmitter
from platform_backend.translators.base import policy_error
from platform_backend.translators.google_adk import GoogleADKTranslator

DENIED = (
    "[policy_denied] Tool 'restart_service' is denied by the agent policy: "
    'Policy denied tool "restart_service": (args.env in ["dev", "staging"]). '
    "The tool was not executed."
)
APPROVAL = "[approval_required] Tool 'delete_resource' requires human approval"


def test_policy_error_detects_markers_in_adk_dict_and_bare_string():
    assert policy_error({"result": DENIED}) == DENIED
    assert policy_error(APPROVAL) == APPROVAL
    assert policy_error({"error": "  " + DENIED}) == "  " + DENIED


def test_policy_error_ignores_ordinary_results():
    assert policy_error({"result": "(stub) restarted payments@prod"}) is None
    assert policy_error("ok") is None
    assert policy_error(None) is None
    assert policy_error({"result": 42}) is None
    assert policy_error("mentions [policy_denied] later") is None


def test_google_adk_tool_end_carries_policy_error():
    emitter = RunEmitter("r1")
    translator = GoogleADKTranslator()
    translator.handle(
        emitter,
        {
            "content": {
                "parts": [{"function_call": {"id": "c1", "name": "restart_service", "args": {}}}]
            }
        },
    )
    events = translator.handle(
        emitter,
        {
            "content": {
                "parts": [
                    {
                        "function_response": {
                            "id": "c1",
                            "name": "restart_service",
                            "response": {"result": DENIED},
                        }
                    }
                ]
            }
        },
    )
    tool_end = [e for e in events if e.event_type == "tool_end"][0]
    assert tool_end.state == "failed"
    assert tool_end.output_summary == DENIED
    assert tool_end.output == {"result": DENIED}
