"""Endpoint and reasoning policy, applied before quota reservation or upstream I/O."""

from __future__ import annotations

import re

from app.models import ModelRoute

EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
REASONING_LEVELS = ("low", "medium", "high", "xhigh", "max")
OPENAI_MODEL_EFFORTS = {
    "gpt-6-astra": REASONING_LEVELS,
    "gpt-6.1-sol": REASONING_LEVELS,
    "gpt-6.1-terra": ("none", *REASONING_LEVELS),
    "gpt-6-sol": ("none", *REASONING_LEVELS),
    "gpt-6-luna": ("none", *REASONING_LEVELS),
    "gpt-5.6-sol": ("none", *REASONING_LEVELS),
    "gpt-5.6-terra": ("none", *REASONING_LEVELS),
    "gpt-5.6-luna": ("none", *REASONING_LEVELS),
}
DEEPSEEK_MODEL_EFFORTS = {
    "deepseek-flash": ("none", "low", "high", "max"),
    "deepseek-v4-pro": ("none", "low", "high", "max"),
}


def model_family(model: str) -> str | None:
    for family in OPENAI_MODEL_EFFORTS:
        if model == family or re.fullmatch(re.escape(family) + r"-\d{4}-\d{2}-\d{2}", model):
            return family
    return None


def official_output_limit(model: str) -> int | None:
    if model_family(model):
        return 128000
    if model in DEEPSEEK_MODEL_EFFORTS:
        return 393216
    return None


def validate_output_limits(model: str, maximum: int, default: int | None) -> None:
    official = official_output_limit(model)
    if official is not None and maximum > official:
        raise ValueError(f"{model} 官方最大输出为 {official} Token")
    if default is not None and default > maximum:
        raise ValueError("默认输出额度不能超过模型允许上限")


def default_output_budget(route: ModelRoute, payload: dict, protocol: str, effort) -> int:
    """Resolve only omitted request budgets; explicit client budgets always win."""
    if route.default_output_tokens is not None:
        budget = route.default_output_tokens
    elif route.upstream_model in DEEPSEEK_MODEL_EFFORTS:
        disabled = effort == "none"
        if protocol == "chat":
            disabled = (payload.get("thinking") or {}).get("type") == "disabled"
        budget = 8192 if disabled else (131072 if effort == "max" else 65536)
    elif model_family(route.upstream_model):
        intensive = effort in {"high", "xhigh", "max"}
        coding = protocol == "responses" and effort != "none"
        budget = 65536 if intensive or coding else 32768
    else:
        budget = 4096
    return min(budget, route.max_output_tokens)


def validate_route(model: str, effort: str | None) -> None:
    family = model_family(model)
    if family and effort is not None and effort not in OPENAI_MODEL_EFFORTS[family]:
        raise ValueError(f"{family} 仅支持 {' / '.join(OPENAI_MODEL_EFFORTS[family])}")
    if model in DEEPSEEK_MODEL_EFFORTS and effort is not None:
        if effort not in DEEPSEEK_MODEL_EFFORTS[model]:
            raise ValueError("DeepSeek 请使用实际档位 none / low / high / max")


def prepare_deepseek(payload: dict, effort: str | None, protocol: str) -> None:
    choice = payload.get("tool_choice")
    forced_tool = choice is not None and choice not in ("auto", "none")
    if protocol == "responses":
        if "thinking" in payload:
            raise ValueError("DeepSeek Responses 请使用 reasoning.effort，不要使用 thinking")
        for tool in payload.get("tools") or []:
            if tool.get("type") == "function":
                continue
            if tool.get("type") == "custom" and tool.get("name") == "apply_patch":
                continue
            raise ValueError("DeepSeek Responses 仅支持 function 和 apply_patch custom 工具")
        if effort != "none" and forced_tool:
            raise ValueError(
                "DeepSeek 思考模式只支持 tool_choice=auto/none；强制工具请用 none 档位"
            )
        return
    thinking = payload.get("thinking")
    if thinking is not None and (
        not isinstance(thinking, dict)
        or set(thinking) != {"type"}
        or not isinstance(thinking["type"], str)
        or thinking["type"] not in {"enabled", "disabled"}
    ):
        raise ValueError("thinking 必须为包含 type=enabled 或 disabled 的对象")
    if effort is not None:
        expected = "disabled" if effort == "none" else "enabled"
        if thinking is not None and thinking["type"] != expected:
            raise ValueError("thinking 开关与推理强度冲突，不允许覆盖固定档位")
        payload["thinking"] = {"type": expected}
        if effort == "none":
            # Normalize to the explicit toggle, which takes precedence upstream.
            payload.pop("reasoning_effort", None)
    thinking_enabled = (payload.get("thinking") or {}).get("type", "enabled") == "enabled"
    if thinking_enabled and forced_tool:
        raise ValueError("DeepSeek 思考模式只支持 tool_choice=auto/none；强制工具请用 none 档位")


def check_resources(value):
    # Shared upstream credentials must never become a cross-user resource lookup API.
    if isinstance(value, dict):
        if value.get("type") == "additional_tools":
            validate_tools(value.get("tools", []))
        if value.get("type") == "item_reference" or any(
            k in value for k in ("file_id", "vector_store_ids", "container_id")
        ):
            raise ValueError("不支持引用上游私有资源；请由客户端直接提交内容")
        for child in value.values():
            check_resources(child)
    elif isinstance(value, list):
        for child in value:
            check_resources(child)


def validate_tools(tools):
    if not isinstance(tools, list):
        raise ValueError("tools 必须是数组")
    for tool in tools:
        if not isinstance(tool, dict):
            raise ValueError("工具格式错误")
        if tool.get("type") == "namespace":
            validate_tools(tool.get("tools", []))
        elif tool.get("type") not in {"function", "custom"}:
            raise ValueError("仅支持客户端 function/custom 工具及 namespace，不支持托管工具")


def prepare_payload(route: ModelRoute, payload: dict, protocol: str) -> dict:
    family = model_family(route.upstream_model)
    deepseek = route.upstream_model in DEEPSEEK_MODEL_EFFORTS
    if route.api_mode not in {protocol, "both"}:
        raise ValueError("此模型未启用当前接口，请选择匹配的聊天或编码模型")
    if protocol == "responses":
        if any(
            payload.get(k) is not None for k in ("previous_response_id", "conversation", "prompt")
        ):
            raise ValueError("仅支持无状态 Responses；请在 input 中传回历史和工具结果")
        if payload.get("background") or payload.get("store"):
            raise ValueError("编码模式不支持后台任务或存储；请设置 store=false")
        validate_tools(payload.get("tools") or [])
        if (
            "reasoning_effort" in payload
            or "max_tokens" in payload
            or "max_completion_tokens" in payload
        ):
            raise ValueError("Responses 请使用 reasoning.effort 和 max_output_tokens")
        reasoning = payload.get("reasoning") or {}
        if not isinstance(reasoning, dict):
            raise ValueError("reasoning 必须为对象")
        effort = reasoning.get("effort")
        output_field = "max_output_tokens"
    else:
        if payload.get("stream_options") is not None and not isinstance(
            payload["stream_options"], dict
        ):
            raise ValueError("stream_options 必须为对象")
        if "reasoning" in payload or "max_output_tokens" in payload:
            raise ValueError("Chat 请使用 reasoning_effort 和 max_completion_tokens")
        if (
            payload.get("max_tokens") is not None
            and payload.get("max_completion_tokens") is not None
        ):
            raise ValueError("max_tokens 和 max_completion_tokens 不能同时设置")
        effort = payload.get("reasoning_effort")
        if deepseek and "max_completion_tokens" in payload:
            payload["max_tokens"] = payload.pop("max_completion_tokens")
        output_field = (
            "max_completion_tokens"
            if ("max_completion_tokens" in payload or family is not None)
            else "max_tokens"
        )
        if payload.get("n", 1) != 1:
            raise ValueError("为保证配额准确，仅支持 n=1")
        if output_field == "max_completion_tokens" and "max_tokens" in payload:
            payload[output_field] = payload.pop("max_tokens")
    if effort is not None and (not isinstance(effort, str) or effort not in EFFORTS):
        raise ValueError("不支持的推理强度")
    if route.reasoning_effort is not None:
        if effort is not None and effort != route.reasoning_effort:
            raise ValueError(f"此公开模型固定使用 {route.reasoning_effort} 推理强度，不允许覆盖")
        effort = route.reasoning_effort
    validate_route(route.upstream_model, effort)
    # Confirmed against all eight production upstream models on 2026-11-01:
    # max is accepted by Responses, but rejected by Chat Completions.
    if family and protocol == "chat" and effort == "max":
        raise ValueError("max 推理强度请使用 /v1/responses 编码接口")
    if protocol == "chat" and (payload.get("tools") or payload.get("functions")):
        responses_only = family in {"gpt-6-astra", "gpt-6.1-sol", "gpt-6.1-terra"}
        reasoning_tools = family in {"gpt-6-sol", "gpt-6-luna"} and effort != "none"
        if responses_only or reasoning_tools:
            raise ValueError(f"{family} 当前档位的工具调用请使用 /v1/responses 编码接口")
    if effort is not None:
        if protocol == "responses":
            payload["reasoning"] = {**reasoning, "effort": effort}
        else:
            payload["reasoning_effort"] = effort
    if deepseek:
        prepare_deepseek(payload, effort, protocol)
    if family and family.startswith("gpt-6") and effort != "none":
        if any(
            payload.get(k) is not None for k in ("temperature", "top_p", "logprobs", "top_logprobs")
        ):
            raise ValueError(f"{family} 推理模式请移除 temperature/top_p/logprobs 参数")
        if protocol == "responses" and "message.output_text.logprobs" in (
            payload.get("include") or []
        ):
            raise ValueError(f"{family} 推理模式不支持输出 logprobs")
    check_resources(payload)
    requested = payload.get(output_field)
    if requested is None:
        requested = default_output_budget(route, payload, protocol, effort)
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        raise ValueError("最大输出 Token 必须为正整数")
    if requested > route.max_output_tokens:
        raise ValueError(f"最大输出 Token 不能超过 {route.max_output_tokens}")
    # The same bound is sent upstream, not just reserved locally.
    payload[output_field] = requested
    payload["store"] = False
    payload["model"] = route.upstream_model
    return payload
