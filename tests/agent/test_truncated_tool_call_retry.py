"""A cut tool-call must be retried, not end the turn on the first hit.

Ending here is what left an unattended session idle until a person typed continue.
"""
from types import SimpleNamespace

from agent.turn_tool_validation import validate_tool_calls


def _agent():
    agent = SimpleNamespace(
        valid_tool_names={"terminal"},
        log_prefix="",
        _invalid_tool_retries=0,
        _invalid_json_retries=0,
        _truncated_arg_retries=0,
        max_tokens=4096,
        api_mode="chat_completions",
        model="gemini-4-neon",
        _ephemeral_max_output_tokens=None,
    )
    agent._vprint = lambda *a, **k: None
    agent._uniquify_tool_call_ids = lambda calls, taken=None: None
    agent._repair_tool_call = lambda name: None
    agent._cleanup_task_resources = lambda task_id: None
    agent._persist_session = lambda messages, history: None
    return agent


def _cut_message():
    tc = SimpleNamespace(
        id="call_1",
        type="function",
        function=SimpleNamespace(name="terminal", arguments='{"command": "echo hi"'),
    )
    return SimpleNamespace(content="", tool_calls=[tc])


def test_first_cut_retries_instead_of_ending():
    agent = _agent()
    verdict = validate_tool_calls(
        agent, _cut_message(), "tool_calls",
        messages=[], conversation_history=[], api_call_count=1, effective_task_id="t",
    )
    assert verdict.action == "continue"
    assert agent._truncated_arg_retries == 1
    assert agent._ephemeral_max_output_tokens > 4096


def test_fifth_cut_still_refuses_to_execute():
    agent = _agent()
    agent._truncated_arg_retries = 4
    verdict = validate_tool_calls(
        agent, _cut_message(), "length",
        messages=[], conversation_history=[], api_call_count=2, effective_task_id="t",
    )
    assert verdict.action == "return"
    assert "output length limit" in (verdict.result or {}).get("final_response", "")
