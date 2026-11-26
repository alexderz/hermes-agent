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
    assert agent._truncated_arg_retries == 0
    assert "output length limit" in (verdict.result or {}).get("final_response", "")


def test_fifth_cut_with_tool_calls_finish_reason_uses_unreported_copy():
    agent = _agent()
    agent._truncated_arg_retries = 4
    verdict = validate_tool_calls(
        agent, _cut_message(), "tool_calls",
        messages=[], conversation_history=[], api_call_count=2, effective_task_id="t",
    )
    assert verdict.action == "return"
    assert agent._truncated_arg_retries == 0
    final = (verdict.result or {}).get("final_response", "")
    assert "output length limit" not in final
    assert "transport" in final or "router" in final


def test_retry_boosts_above_api_kwargs_cap_when_agent_max_tokens_is_none():
    from run_agent import AIAgent

    agent = _agent()
    agent.max_tokens = None
    agent._requested_output_cap_from_api_kwargs = AIAgent._requested_output_cap_from_api_kwargs
    verdict = validate_tool_calls(
        agent, _cut_message(), "tool_calls",
        messages=[], conversation_history=[], api_call_count=1, effective_task_id="t",
        api_kwargs={"max_tokens": 32768},
    )
    assert verdict.action == "continue"
    assert agent._ephemeral_max_output_tokens > 32768


def test_run_tool_round_forwards_api_kwargs_to_truncated_retry():
    from agent.turn_tool_round import run_tool_round
    from run_agent import AIAgent

    agent = _agent()
    agent.max_tokens = None
    agent.quiet_mode = True
    agent.verbose_logging = False
    agent._requested_output_cap_from_api_kwargs = AIAgent._requested_output_cap_from_api_kwargs
    verdict = run_tool_round(
        agent, assistant_message=_cut_message(), finish_reason="tool_calls",
        messages=[], conversation_history=[], api_call_count=1, effective_task_id="t",
        user_message="go", system_message=None, active_system_prompt="",
        compression_attempts=0, max_compression_attempts=3, final_response=None,
        failed=False, _turn_exit_reason="unknown", truncated_tool_call_retries=0,
        current_turn_user_idx=0, api_kwargs={"max_completion_tokens": 16384},
    )
    assert verdict.action == "continue"
    assert agent._truncated_arg_retries == 1
    assert agent._ephemeral_max_output_tokens > 16384


def test_valid_json_and_turn_reset_clear_truncated_arg_retries():
    from agent.turn_context import _PER_TURN_RESET_STATE

    agent = _agent()
    agent._truncated_arg_retries = 2
    ok_msg = SimpleNamespace(
        content="",
        tool_calls=[SimpleNamespace(
            id="call_ok", type="function",
            function=SimpleNamespace(name="terminal", arguments='{"command": "echo ok"}'),
        )],
    )
    verdict = validate_tool_calls(
        agent, ok_msg, "tool_calls",
        messages=[], conversation_history=[], api_call_count=2, effective_task_id="t",
    )
    assert verdict.action == "ok"
    assert agent._truncated_arg_retries == 0
    assert ("_truncated_arg_retries", 0) in _PER_TURN_RESET_STATE
