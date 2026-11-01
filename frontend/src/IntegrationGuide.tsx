import { useState } from "react";
import { Copy } from "lucide-react";
import { Button, Empty, InlineError, SelectField } from "./components";
import type { ModelRoute } from "./types";

export function modeLabel(mode: ModelRoute["api_mode"]) {
  return mode === "both" ? "聊天 + 编码" : mode === "responses" ? "编码 · Responses" : "聊天 · Chat";
}

export default function IntegrationGuide({ models }: { models: ModelRoute[] }) {
  const [mode, setMode] = useState<"chat" | "responses">("chat");
  const [selected, setSelected] = useState("");
  const available = models.filter((m) => m.api_mode === mode || m.api_mode === "both");
  const route = available.find((m) => m.public_name === selected) ?? available[0];
  const model = route?.public_name ?? "替换为已授权的公开模型名";
  const base = `${window.location.origin}/v1`;
  const budget = Math.min(4096, route?.max_output_tokens ?? 4096);
  const setup = `import os\nfrom openai import OpenAI\n\nclient = OpenAI(\n    api_key=os.environ["TOKEN_STATION_KEY"],\n    base_url="${base}",\n    max_retries=0,\n)\n`;
  const chat = `${setup}\nresponse = client.chat.completions.create(\n    model="${model}",\n    messages=[{"role": "user", "content": "你好"}],\n    max_completion_tokens=${budget},\n)\nprint(response.choices[0].message.content)`;
  const coding = `${setup}\n# 客户端执行受限工具；勿直接执行模型返回的任意命令\ntools = [{\n    "type": "function", "name": "read_project_file",\n    "description": "读取示例项目文件",\n    "parameters": {"type": "object", "properties": {},\n                   "required": [], "additionalProperties": False},\n    "strict": True,\n}]\nhistory = [{"role": "user", "content": "读取项目文件，解释它的功能"}]\nfor _ in range(4):\n    response = client.responses.create(\n        model="${model}", input=history, tools=tools,\n        store=False, max_output_tokens=${budget},\n    )\n    # 保留所有输出项，包括 reasoning / encrypted_content\n    history.extend(response.output)\n    calls = [x for x in response.output if x.type == "function_call"]\n    if not calls:\n        print(response.output_text)\n        break\n    for call in calls:\n        result = "def add(a, b): return a + b" if call.name == "read_project_file" else "不允许的工具"\n        history.append({"type": "function_call_output",\n                        "call_id": call.call_id, "output": result})`;
  const stream = `${setup}\nwith client.responses.stream(\n    model="${model}", input="写一个 Python 二分查找函数",\n    store=False, max_output_tokens=${budget},\n) as stream:\n    for event in stream:\n        if event.type == "response.output_text.delta":\n            print(event.delta, end="", flush=True)`;
  const codex = `model_provider = "token_station"\nmodel = "${model}"\nmodel_reasoning_effort = "${route?.reasoning_effort ?? "medium"}"\nweb_search = "disabled"\n\n[model_providers.token_station]\nname = "Token Station"\nbase_url = "${base}"\nenv_key = "TOKEN_STATION_KEY"\nwire_api = "responses"\nrequires_openai_auth = false\nsupports_websockets = false\nrequest_max_retries = 0\nstream_max_retries = 0`;
  const curl = `curl ${base}/chat/completions \\\n  -H "Authorization: Bearer $TOKEN_STATION_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify({ model, messages: [{ role: "user", content: "你好" }], max_completion_tokens: budget })}'`;
  return <div className="guide-stack">
    <section className="panel guide-intro"><h2>选择接入方式</h2>
      <div className="form-grid"><SelectField label="接入方式" value={mode} onChange={(e) => setMode(e.target.value as "chat" | "responses")}><option value="chat">聊天 · Chat Completions</option><option value="responses">编码 · Responses</option></SelectField>
        <SelectField label="公开模型" value={route?.public_name ?? ""} onChange={(e) => setSelected(e.target.value)} disabled={!available.length}>{available.length ? available.map((m) => <option value={m.public_name} key={m.id}>{m.public_name}</option>) : <option value="">暂无已授权模型</option>}</SelectField></div>
      <p>Base URL：<code>{base}</code></p>
      <p>凭证使用你的中转站 Key，通过环境变量 TOKEN_STATION_KEY 加载。固定推理强度：{route?.reasoning_effort ?? "由客户端或上游决定"}。</p>
      {!route && <Empty>登录并由管理员分配对应模式的模型后，再使用以下模板。</Empty>}
    </section>
    {mode === "chat" ? <><Snippet title="Python · 聊天" code={chat} /><Snippet title="curl · 聊天" code={curl} /></> : <>
      <p className="notice">仅支持无状态 HTTP / SSE。每轮传回完整 input 和工具结果，不使用 previous_response_id。支持 function/custom 及其 namespace；不开放托管工具、文件 ID、后台任务、WebSocket 或 /responses/compact。</p>
      <Snippet title="Python · 编码工具循环" code={coding} /><Snippet title="Python · 流式输出" code={stream} /><Snippet title="Codex · config.toml 配置片段" code={codex} />
      <p className="notice">Codex 的推理设置必须与固定档位一致。将片段合并到客户端配置，勿覆盖原配置；不同客户端版本可能发送额外接口或工具，需按此兼容边界配置。</p>
    </>}
  </div>;
}

function Snippet({ title, code }: { title: string; code: string }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  async function copy() {
    try { await navigator.clipboard.writeText(code); setCopied(true); setError(""); }
    catch { setError("复制失败，请手动选择下方代码复制。"); }
  }
  return <section className="code-card"><div><strong>{title}</strong><Button variant="ghost" onClick={copy}><Copy size={15} />{copied ? "已复制" : "复制"}</Button></div>{error && <InlineError message={error} />}<pre><code>{code}</code></pre></section>;
}
