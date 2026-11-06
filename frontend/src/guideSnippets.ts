import type { ModelRoute } from "./types";

export type GuidePath = "chat" | "responses" | "codex";

export function guideModels(models: ModelRoute[], path: GuidePath): ModelRoute[] {
  const protocol = path === "chat" ? "chat" : "responses";
  return models.filter((model) => model.active && (model.api_mode === protocol || model.api_mode === "both"));
}

function shellQuote(value: string): string {
  return `'${value.replaceAll("'", `'"'"'`)}'`;
}

/** Templates never contain a user's secret; callers must supply an authorized route. */
export function buildGuideSnippets(origin: string, route?: ModelRoute) {
  if (!route) return null;
  const base = `${origin.replace(/\/+$/, "")}/v1`;
  const model = route.public_name;
  const budget = Math.min(4096, route.max_output_tokens);
  const quotedModel = JSON.stringify(model);
  const setup = `import os\nfrom openai import OpenAI\n\nclient = OpenAI(\n    api_key=os.environ["TOKEN_STATION_KEY"],\n    base_url=${JSON.stringify(base)},\n    max_retries=0,\n)`;
  const config = (provider: "token_station" | "custom", credential: string) => `model_provider = "${provider}"\nmodel = ${quotedModel}\n${route.reasoning_effort ? `model_reasoning_effort = ${JSON.stringify(route.reasoning_effort)}\n` : ""}web_search = "disabled"\n\n[model_providers.${provider}]\nname = "Token Station"\nbase_url = ${JSON.stringify(base)}\n${credential}\nwire_api = "responses"\nrequires_openai_auth = false\nsupports_websockets = false\nrequest_max_retries = 0\nstream_max_retries = 0\n\n[model_providers.${provider}.capabilities]\nremote_compaction = "unsupported"`;
  return {
    base,
    model,
    budget,
    chat: `${setup}\n\nresponse = client.chat.completions.create(\n    model=${quotedModel},\n    messages=[{"role": "user", "content": "你好"}],\n    max_completion_tokens=${budget},\n)\nprint(response.choices[0].message.content)`,
    curl: `curl ${shellQuote(`${base}/chat/completions`)} \\\n  -H "Authorization: Bearer $TOKEN_STATION_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d ${shellQuote(JSON.stringify({ model, messages: [{ role: "user", content: "你好" }], max_completion_tokens: budget }))}`,
    coding: `${setup}\n\n# 仅运行本地白名单工具，不执行模型返回的任意命令。\ntools = [{\n    "type": "function", "name": "read_project_file",\n    "description": "读取示例项目文件",\n    "parameters": {"type": "object", "properties": {},\n                   "required": [], "additionalProperties": False},\n    "strict": True,\n}]\nhistory = [{"role": "user", "content": "读取项目文件，解释它的功能"}]\nfor _ in range(4):\n    response = client.responses.create(\n        model=${quotedModel}, input=history, tools=tools,\n        store=False, max_output_tokens=${budget},\n    )\n    # 保留所有输出项，包括 reasoning / encrypted_content。\n    history.extend(response.output)\n    calls = [x for x in response.output if x.type == "function_call"]\n    if not calls:\n        print(response.output_text)\n        break\n    for call in calls:\n        result = "def add(a, b): return a + b" if call.name == "read_project_file" else "不允许的工具"\n        history.append({"type": "function_call_output",\n                        "call_id": call.call_id, "output": result})`,
    stream: `${setup}\n\nwith client.responses.stream(\n    model=${quotedModel}, input="写一个 Python 二分查找函数",\n    store=False, max_output_tokens=${budget},\n) as stream:\n    for event in stream:\n        if event.type == "response.output_text.delta":\n            print(event.delta, end="", flush=True)`,
    verify: `${setup}\n\nresponse = client.responses.create(\n    model=${quotedModel}, input="请只回复：连接成功",\n    store=False, max_output_tokens=${budget},\n)\nprint(response.output_text)`,
    codex: config("token_station", 'env_key = "TOKEN_STATION_KEY"'),
    ccSwitch: config("custom", 'experimental_bearer_token = "替换为你的中转 Key"'),
  };
}
