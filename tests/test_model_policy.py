import pytest

from app.model_policy import OPENAI_MODEL_EFFORTS, prepare_payload, validate_route
from app.models import ModelRoute


def route(model, effort=None):
    return ModelRoute(
        public_name="public",
        upstream_model=model,
        api_mode="both",
        max_output_tokens=16384,
        reasoning_effort=effort,
    )


@pytest.mark.parametrize("model", OPENAI_MODEL_EFFORTS)
@pytest.mark.parametrize("protocol", ["chat", "responses"])
def test_family_efforts_and_token_bound(model, protocol):
    for effort in OPENAI_MODEL_EFFORTS[model]:
        if protocol == "chat" and effort == "max":
            with pytest.raises(ValueError, match="/v1/responses"):
                prepare_payload(route(model, effort), {}, protocol)
            continue
        data = prepare_payload(route(model, effort), {}, protocol)
        assert data["model"] == model
        assert data["store"] is False
        if protocol == "chat":
            assert data["max_completion_tokens"] == 16384
            assert "max_tokens" not in data
            assert data["reasoning_effort"] == effort
        else:
            assert data["max_output_tokens"] == 16384
            assert data["reasoning"]["effort"] == effort
    with pytest.raises(ValueError):
        validate_route(model, "minimal")
    with pytest.raises(ValueError):
        prepare_payload(
            route(model, "low"),
            {"reasoning_effort": "high"}
            if protocol == "chat"
            else {"reasoning": {"effort": "high"}},
            protocol,
        )


@pytest.mark.parametrize("model", ["gpt-6-astra", "gpt-6.1-sol"])
def test_no_none_and_snapshots(model):
    with pytest.raises(ValueError):
        validate_route(model + "-2026-10-01", "none")


@pytest.mark.parametrize("model", ["gpt-6-astra", "gpt-6.1-sol", "gpt-6.1-terra"])
def test_responses_only_tools(model):
    with pytest.raises(ValueError, match="/v1/responses"):
        prepare_payload(route(model, "low"), {"tools": [{"type": "function"}]}, "chat")


@pytest.mark.parametrize("model", ["gpt-6-sol", "gpt-6-luna"])
def test_chat_tools_require_none(model):
    data = {"tools": [{"type": "function"}], "max_tokens": 32}
    assert prepare_payload(route(model, "none"), data.copy(), "chat")["max_completion_tokens"] == 32
    with pytest.raises(ValueError):
        prepare_payload(route(model, "high"), data.copy(), "chat")


def test_sampling_policy_and_other_providers():
    with pytest.raises(ValueError):
        prepare_payload(route("gpt-6-astra", "low"), {"temperature": 0.2}, "chat")
    with pytest.raises(ValueError):
        prepare_payload(
            route("gpt-6-luna", "high"), {"include": ["message.output_text.logprobs"]}, "responses"
        )
    assert prepare_payload(route("gpt-6-luna", "none"), {"temperature": 0.2}, "chat")
    assert prepare_payload(route("deepseek-v4-pro"), {}, "chat")["max_tokens"] == 16384
