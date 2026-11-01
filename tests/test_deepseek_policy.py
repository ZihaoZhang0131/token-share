import pytest

from app.model_policy import DEEPSEEK_MODEL_EFFORTS, prepare_payload, validate_route
from app.models import ModelRoute


def route(model, effort=None):
    return ModelRoute(
        public_name="public",
        upstream_model=model,
        api_mode="both",
        max_output_tokens=16384,
        reasoning_effort=effort,
    )


@pytest.mark.parametrize("model", DEEPSEEK_MODEL_EFFORTS)
@pytest.mark.parametrize("effort", ["none", "low", "high", "max"])
def test_deepseek_effort_translation(model, effort):
    chat = prepare_payload(route(model, effort), {"max_completion_tokens": 128}, "chat")
    assert chat["max_tokens"] == 128 and "max_completion_tokens" not in chat
    assert chat["thinking"] == {"type": "disabled" if effort == "none" else "enabled"}
    assert chat.get("reasoning_effort") == (None if effort == "none" else effort)
    response = prepare_payload(route(model, effort), {}, "responses")
    assert response["reasoning"] == {"effort": effort}
    assert response["max_output_tokens"] == 16384
    assert chat["store"] is False and response["store"] is False


@pytest.mark.parametrize("model", DEEPSEEK_MODEL_EFFORTS)
def test_deepseek_conflicts_and_defaults(model):
    for effort in ["minimal", "medium", "xhigh", "ultra"]:
        with pytest.raises(ValueError):
            validate_route(model, effort)
    for effort, toggle in [("none", "enabled"), ("high", "disabled")]:
        with pytest.raises(ValueError, match="冲突"):
            prepare_payload(route(model, effort), {"thinking": {"type": toggle}}, "chat")
    with pytest.raises(ValueError, match="不允许覆盖"):
        prepare_payload(route(model, "low"), {"reasoning_effort": "high"}, "chat")
    with pytest.raises(ValueError, match="不允许覆盖"):
        prepare_payload(route(model, "none"), {"reasoning": {"effort": "max"}}, "responses")
    default = prepare_payload(route(model), {}, "chat")
    assert "thinking" not in default and "reasoning_effort" not in default
    assert prepare_payload(route(model), {"thinking": {"type": "disabled"}}, "chat")
    with pytest.raises(ValueError):
        prepare_payload(route(model), {"thinking": "disabled"}, "chat")
    with pytest.raises(ValueError):
        prepare_payload(route(model), {"thinking": {"type": []}}, "chat")
    with pytest.raises(ValueError):
        prepare_payload(route(model), {"max_tokens": 32, "max_completion_tokens": 32}, "chat")


def test_deepseek_responses_tools_and_schema():
    r = route("deepseek-flash", "low")
    for tool in [{"type": "function", "name": "ping"}, {"type": "custom", "name": "apply_patch"}]:
        assert prepare_payload(r, {"tools": [tool]}, "responses")
    for tool in [
        {"type": "custom", "name": "other"},
        {"type": "namespace", "tools": []},
        {"type": "web_search"},
    ]:
        with pytest.raises(ValueError):
            prepare_payload(r, {"tools": [tool]}, "responses")
    with pytest.raises(ValueError):
        prepare_payload(r, {"thinking": {"type": "disabled"}}, "responses")


@pytest.mark.parametrize("protocol", ["chat", "responses"])
def test_deepseek_forced_tools_require_non_thinking(protocol):
    for choice in ["required", {"type": "function", "function": {"name": "ping"}}]:
        with pytest.raises(ValueError, match="强制工具"):
            prepare_payload(route("deepseek-flash", "low"), {"tool_choice": choice}, protocol)
        assert prepare_payload(route("deepseek-flash", "none"), {"tool_choice": choice}, protocol)
    assert prepare_payload(route("deepseek-flash", "low"), {"tool_choice": "auto"}, protocol)
