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
        model="gpt-4o",
        _ephemeral_max_output_tokens=None,
        _ephemeral_reasoning_off=False,
    )
    agent._vprint = lambda *a, **k: None
    agent._buffer_vprint = lambda *a, **k: None
    agent._flush_status_buffer = lambda *a, **k: None
    agent._uniquify_tool_call_ids = lambda calls, taken=None: None
    agent._repair_tool_call = lambda name: None
    agent._cleanup_task_resources = lambda task_id: None
    agent._persist_session = lambda messages, history: None
    return agent


def _trunc_state(agent, retries=0, stub=False):
    from run_agent import AIAgent

    agent._requested_output_cap_from_api_kwargs = AIAgent._requested_output_cap_from_api_kwargs
    st = SimpleNamespace(
        agent=agent, truncated_tool_call_retries=retries, is_stub=stub,
        messages=[], effective_task_id="t", response=SimpleNamespace(),
    )
    st.done = lambda action, result=None: action
    st.end_turn = lambda final, error=None, **kw: "return"
    return st


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
    assert ("_ephemeral_max_output_tokens", None) in _PER_TURN_RESET_STATE


def test_mixed_batch_with_truncated_call_retries_whole_batch():
    agent = _agent()
    mixed_msg = SimpleNamespace(
        content="",
        tool_calls=[
            SimpleNamespace(
                id="call_good", type="function",
                function=SimpleNamespace(name="terminal", arguments='{"command": "echo ok"}'),
            ),
            SimpleNamespace(
                id="call_cut", type="function",
                function=SimpleNamespace(name="terminal", arguments='{"command": "echo cut'),
            ),
        ],
    )
    verdict = validate_tool_calls(
        agent, mixed_msg, "tool_calls",
        messages=[], conversation_history=[], api_call_count=1, effective_task_id="t",
    )
    assert verdict.action == "continue"
    assert agent._truncated_arg_retries == 1


def test_retries_escalate_cap_and_clamp_at_anthropic_model_limit():
    from run_agent import AIAgent

    agent = _agent()
    agent.api_mode = "anthropic_messages"
    agent.model = "claude-sonnet-4"
    agent.max_tokens = 16384
    agent._requested_output_cap_from_api_kwargs = AIAgent._requested_output_cap_from_api_kwargs

    caps = []
    api_kwargs = {"max_tokens": 16384}
    for attempt in range(1, 5):
        verdict = validate_tool_calls(
            agent, _cut_message(), "tool_calls",
            messages=[], conversation_history=[], api_call_count=attempt, effective_task_id="t",
            api_kwargs=api_kwargs,
        )
        assert verdict.action == "continue"
        caps.append(agent._ephemeral_max_output_tokens)
        api_kwargs = {"max_tokens": agent._ephemeral_max_output_tokens}

    assert caps[0] > 16384
    assert all(caps[i] >= caps[i - 1] for i in range(1, len(caps)))
    assert caps[-1] <= 64000


# ── A route that cannot honour a raised cap gets a different request from retry 2 ──
#
# The Antigravity CLI exposes no output-length flag and its client discards max_tokens,
# so a cap-only retry re-sends a byte-identical request into the same ceiling. Thinking
# is spent from that same budget, so the one-shot reasoning-off override is the lever
# that actually changes what such a route sends.


def test_truncated_tool_retry_keeps_reasoning_on_for_the_first_attempt():
    from agent.turn_truncation import _retry_truncated_tool_call

    agent = _agent()
    st = _trunc_state(agent)
    assert _retry_truncated_tool_call(st, {}) == "continue"
    assert st.truncated_tool_call_retries == 1
    assert agent._ephemeral_max_output_tokens > 4096
    assert agent._ephemeral_reasoning_off is False


def test_truncated_tool_retry_drops_reasoning_from_the_second_attempt():
    from agent.turn_truncation import _retry_truncated_tool_call

    agent = _agent()
    st = _trunc_state(agent, retries=1)
    assert _retry_truncated_tool_call(st, {}) == "continue"
    assert st.truncated_tool_call_retries == 2
    assert agent._ephemeral_reasoning_off is True


def test_terminal_truncated_tool_retry_clears_the_reasoning_override():
    from agent.turn_truncation import _retry_truncated_tool_call

    agent = _agent()
    agent._ephemeral_reasoning_off = True
    st = _trunc_state(agent, retries=4)
    assert _retry_truncated_tool_call(st, {}) == "return"
    assert agent._ephemeral_reasoning_off is False


def test_truncated_arg_retry_keeps_reasoning_on_until_the_second_attempt():
    agent = _agent()
    validate_tool_calls(
        agent, _cut_message(), "tool_calls",
        messages=[], conversation_history=[], api_call_count=1, effective_task_id="t",
    )
    assert agent._truncated_arg_retries == 1
    assert agent._ephemeral_reasoning_off is False

    validate_tool_calls(
        agent, _cut_message(), "tool_calls",
        messages=[], conversation_history=[], api_call_count=2, effective_task_id="t",
    )
    assert agent._truncated_arg_retries == 2
    assert agent._ephemeral_reasoning_off is True


def test_terminal_truncated_arg_retry_clears_the_reasoning_override():
    agent = _agent()
    agent._truncated_arg_retries = 4
    agent._ephemeral_reasoning_off = True
    verdict = validate_tool_calls(
        agent, _cut_message(), "tool_calls",
        messages=[], conversation_history=[], api_call_count=2, effective_task_id="t",
    )
    assert verdict.action == "return"
    assert agent._ephemeral_reasoning_off is False


def test_reasoning_override_is_reset_with_the_other_per_turn_state():
    from agent.turn_context import _PER_TURN_RESET_STATE

    assert ("_ephemeral_reasoning_off", False) in _PER_TURN_RESET_STATE


def test_validate_tool_calls_detects_mid_string_cut_ending_in_brace_even_after_invalid_escape():
    for raw in (r'{"a": "\s", "b": "cut }', '{"a": "x\ny", "b": "cut }'):
        agent = _agent()
        tc = SimpleNamespace(id="c1", type="function", function=SimpleNamespace(name="terminal", arguments=raw))
        msg = SimpleNamespace(content="", tool_calls=[tc])
        verdict = validate_tool_calls(
            agent, msg, "tool_calls",
            messages=[], conversation_history=[], api_call_count=1, effective_task_id="t",
        )
        assert verdict.action == "continue"
        assert agent._truncated_arg_retries == 1


def test_validate_tool_calls_does_not_treat_complete_unescaped_quote_as_truncation():
    agent = _agent()
    tc = SimpleNamespace(
        id="c1", type="function",
        function=SimpleNamespace(name="terminal", arguments='{"command": "echo "hi""}'),
    )
    msg = SimpleNamespace(content="", tool_calls=[tc])
    messages = []
    verdict = validate_tool_calls(
        agent, msg, "tool_calls",
        messages=messages, conversation_history=[], api_call_count=1, effective_task_id="t",
    )
    assert verdict.action == "continue"
    assert agent._truncated_arg_retries == 0
    assert agent._invalid_json_retries == 1
