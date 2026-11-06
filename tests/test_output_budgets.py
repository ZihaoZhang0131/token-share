import pytest

from app.model_policy import prepare_payload, validate_output_limits
from app.models import ModelRoute


@pytest.mark.parametrize("model,protocol,extra,expected", [
    ("gpt-6.1-sol", "chat", {}, 32768),
    ("gpt-6.1-sol", "chat", {"reasoning_effort": "high"}, 65536),
    ("gpt-6.1-sol", "responses", {}, 65536),
    ("gpt-6.1-sol", "responses", {"reasoning": {"effort": "max"}}, 65536),
    ("gpt-6.1-terra", "responses", {"reasoning": {"effort": "none"}}, 32768),
    ("deepseek-flash", "chat", {}, 65536),
    ("deepseek-flash", "chat", {"thinking": {"type": "disabled"}}, 8192),
    ("deepseek-v4-pro", "chat", {"reasoning_effort": "none"}, 8192),
    ("deepseek-v4-pro", "chat", {"reasoning_effort": "max"}, 131072),
    ("deepseek-v4-pro", "responses", {"reasoning": {"effort": "max"}}, 131072),
    ("deepseek-flash", "responses", {"reasoning": {"effort": "none"}}, 8192),
    ("custom-model", "chat", {}, 4096),
])
def test_automatic_budgets_and_client_override(model, protocol, extra, expected):
    maximum = 393216 if model.startswith("deepseek") else 128000
    route = ModelRoute(upstream_model=model, api_mode="both", max_output_tokens=maximum)
    field = "max_output_tokens" if protocol == "responses" else (
        "max_completion_tokens" if model.startswith("gpt") else "max_tokens"
    )
    assert prepare_payload(route, extra.copy(), protocol)[field] == expected
    # The full ceiling remains available even when defaults are much smaller.
    assert prepare_payload(route, {**extra, field: maximum}, protocol)[field] == maximum
    assert prepare_payload(route, {**extra, field: 512}, protocol)[field] == 512
    with pytest.raises(ValueError, match="不能超过"):
        prepare_payload(route, {**extra, field: maximum + 1}, protocol)
    route.default_output_tokens = 20000
    assert prepare_payload(route, extra.copy(), protocol)[field] == 20000
    route.default_output_tokens = None
    route.max_output_tokens = 1024
    assert prepare_payload(route, extra.copy(), protocol)[field] == 1024


def test_pinned_effort_and_legacy_conversion():
    route = ModelRoute(upstream_model="deepseek-flash", api_mode="both",
                       max_output_tokens=393216, reasoning_effort="max")
    assert prepare_payload(route, {}, "chat")["max_tokens"] == 131072
    assert prepare_payload(route, {"max_completion_tokens": 200000}, "chat")["max_tokens"] == 200000
    route.upstream_model = "gpt-6.1-sol"
    route.max_output_tokens = 128000
    route.reasoning_effort = "high"
    assert prepare_payload(route, {"max_tokens": 100000}, "chat")["max_completion_tokens"] == 100000


def test_configuration_bounds():
    validate_output_limits("deepseek-flash", 393216, 131072)
    validate_output_limits("gpt-6.1-sol", 128000, None)
    with pytest.raises(ValueError, match="官方最大"):
        validate_output_limits("gpt-6.1-sol", 131072, None)
    with pytest.raises(ValueError, match="默认输出额度"):
        validate_output_limits("deepseek-flash", 8192, 65536)
