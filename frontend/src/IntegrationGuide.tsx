import { useEffect, useState, type ReactNode } from "react";
import { Copy } from "lucide-react";
import { Button, Empty, InlineError, SelectField } from "./components";
import { buildGuideSnippets, guideModels, type GuidePath } from "./guideSnippets";
import type { ModelRoute } from "./types";

export function modeLabel(mode: ModelRoute["api_mode"]) {
  return mode === "both" ? "聊天 + 编码" : mode === "responses" ? "编码 · Responses" : "聊天 · Chat";
}

const paths: { id: GuidePath; label: string; detail: string }[] = [
  { id: "chat", label: "聊天 API", detail: "Python / curl" },
  { id: "responses", label: "编码 API", detail: "工具循环 / 流式" },
  { id: "codex", label: "CC Switch + Codex", detail: "终端 / 桌面端" },
];

export default function IntegrationGuide({ models }: { models: ModelRoute[] }) {
  const [path, setPath] = useState<GuidePath>("chat");
  const [selected, setSelected] = useState("");
  const available = guideModels(models, path);
  const route = available.find((model) => model.public_name === selected) ?? available[0];
  const snippets = buildGuideSnippets(window.location.origin, route);

  return <div className="guide-stack">
    <section className="panel guide-intro">
      <StepTitle number="01" title="创建并保存访问 Key" />
      <p>在「访问 Key」创建中转 Key。明文仅显示一次，请安全保存。</p>
      <div className="guide-path-tabs" role="group" aria-label="接入方式">
        {paths.map((item) => <button key={item.id} type="button" className={path === item.id ? "active" : ""} aria-pressed={path === item.id} onClick={() => setPath(item.id)}><strong>{item.label}</strong><small>{item.detail}</small></button>)}
      </div>
    </section>

    <section className="panel">
      <StepTitle number="02" title="选择模型与连接地址" />
      <SelectField label="已授权的公开模型" value={route?.public_name ?? ""} onChange={(event) => setSelected(event.target.value)} disabled={!available.length}>
        {available.length ? available.map((model) => <option value={model.public_name} key={model.id}>{model.public_name}</option>) : <option value="">暂无可用模型</option>}
      </SelectField>
      {route && snippets ? <>
        <div className="connection-fields"><CopyField label="Base URL" value={snippets.base} /><CopyField label="模型名" value={route.public_name} /></div>
        <p className="notice">{route.reasoning_effort ? <>此模型固定使用 <strong>{route.reasoning_effort}</strong> 推理档位，客户端设置须一致。</> : "此模型未固定推理档位，请按上游支持情况选择。"} 当前接口：{path === "chat" ? "Chat Completions" : "Responses"}。</p>
      </> : <Empty>请登录并获取{path === "chat" ? "聊天" : "编码 / Responses"}模型授权。</Empty>}
    </section>

    {route && snippets && <>
      {path === "codex" ? <CodexSteps route={route} snippets={snippets} /> : <>
        <section className="panel">
          <StepTitle number="03" title="配置本地环境" />
          <p>运行 <code>python -m pip install openai</code>，在同一终端设置中转 Key：</p>
          <EnvironmentSetup />
        </section>
        <section className="panel">
          <StepTitle number="04" title={path === "chat" ? "发出第一条聊天请求" : "先验证，再接入工具"} />
          <p>把示例保存为 <code>example.py</code>，执行 <code>python example.py</code>。请求成功后，在「用量」查看新增消耗。</p>
          {path === "chat" ? <Snippet title="Python · 第一条消息" code={snippets.chat} /> : <Snippet title="Python · Responses 连通验证" code={snippets.verify} />}
          <details className="guide-details"><summary>{path === "chat" ? "查看 curl 示例（macOS / Linux）" : "查看客户端工具循环与流式输出"}</summary>
            {path === "chat" ? <Snippet title="curl · 聊天" code={snippets.curl} /> : <><Snippet title="Python · 编码工具循环" code={snippets.coding} /><Snippet title="Python · 流式输出" code={snippets.stream} /></>}
          </details>
        </section>
      </>}
      {path !== "chat" && <details className="panel guide-details">
        <summary>编码模式的接入范围</summary>
        <p>仅支持无状态 HTTP / SSE：每轮传回完整 input 和工具结果，并使用 <code>store=false</code>。保留 reasoning / encrypted_content 等输出项；不使用 <code>previous_response_id</code>。</p>
        <p className="muted">支持客户端 function/custom 工具及 namespace；具体工具仍受上游模型规则限制。不开放托管工具、上游文件 ID、后台任务、WebSocket 或远程 /responses/compact。工具在你的电脑执行。</p>
      </details>}
    </>}

    <section className="panel">
      <StepTitle number="05" title="遇到问题，从这里排查" />
      <details className="guide-details"><summary>常见错误与解决方法</summary>
      <dl className="guide-faq">
        <dt>401 · Key 无效</dt><dd>检查是否复制完整、是否已撤销，以及环境变量是否在当前终端生效。不要使用上游 Key 或网页登录密码。</dd>
        <dt>403 / 404 · 权限或模型不匹配</dt><dd>检查账号状态、公开模型名和模型授权。Base URL 应以 /v1 结尾，不要再添加 /responses，也不要重复 /v1。</dd>
        <dt>422 · 参数不兼容</dt><dd>核对聊天 / 编码模式和固定推理档位；编码请求使用 store=false，并移除托管工具、previous_response_id 等不支持的字段。</dd>
        <dt>429 · 配额或速率限制</dt><dd>查看「用量」和 Key 的 RPM / TPM。每次调用会先预留输入与最大输出 Token；必要时降低最大输出或等待限流窗口刷新。</dd>
        <dt>Codex 模型没有出现 / 配置未生效</dt><dd>确认 CC Switch 已启用正确供应商、模型映射使用本站公开模型名，且管理的是客户端实际读取的配置目录。完全退出后重启 Codex，并新建会话。</dd>
      </dl></details>
      <p className="muted">核对日期：2026-11-06 · 兼容性以客户端版本为准</p>
      <p><a href="https://github.com/farion1231/cc-switch/blob/main/docs/user-manual/zh/2-providers/2.1-add.md" target="_blank" rel="noreferrer">CC Switch 官方手册 ↗</a> · <a href="https://learn.chatgpt.com/docs/config-file/config-reference" target="_blank" rel="noreferrer">Codex 配置参考 ↗</a></p>
    </section>
  </div>;
}

function CodexSteps({ route, snippets }: { route: ModelRoute; snippets: NonNullable<ReturnType<typeof buildGuideSnippets>> }) {
  return <>
    <section className="panel">
      <StepTitle number="03" title="在 CC Switch 添加本站" />
      <ol className="guide-steps">
        <li>从 <a href="https://github.com/farion1231/cc-switch/releases" target="_blank" rel="noreferrer">官方发布页</a>安装 CC Switch，并先安装你要使用的 Codex CLI 或桌面端。</li>
        <li>在 CC Switch 选择 <strong>Codex → 直连 → 添加供应商 → 自定义配置</strong>，名称填写 <strong>Token Station</strong>。</li>
        <li>请求地址填入上面的 Base URL；在 CC Switch 的 API Key 栏填写你的中转 Key。上游格式选择 <strong>Responses（原生）</strong>，无需开启协议转换或本地路由。</li>
        <li>在模型映射中添加 <code>{route.public_name}</code>，菜单显示名与实际请求模型均可填写这个公开别名，并将它设为默认模型。{route.reasoning_effort ? <>思考等级仅配置 <strong>{route.reasoning_effort}</strong>，与本站固定档位一致。</> : "推理等级按此上游支持情况填写；不确定时联系管理员。"} 不自行放大上下文窗口。</li>
        <li>确认关闭 WebSocket、托管搜索，并将远程压缩能力设为 unsupported。高级配置片段见下方；合并时保留已有 MCP、项目和其他个人设置。</li>
        <li>保存并<strong>启用</strong>供应商；完全退出后重启 Codex，新建会话使模型列表与配置生效。</li>
      </ol>
      <details className="guide-details"><summary>查看 CC Switch 高级配置示例</summary>
        <p className="muted">在 CC Switch 内填写真实 Key；合并此片段，不要覆盖原配置或分享密钥。</p>
        <Snippet title="CC Switch · config.toml 合并片段" code={snippets.ccSwitch} />
      </details>
    </section>
    <section className="panel">
      <StepTitle number="04" title="启动 Codex，确认请求到达本站" />
      <div className="guide-platforms">
        <div><h3>终端 CLI</h3><p>切换后重新启动 <code>codex</code>。在模型菜单确认公开模型和推理档位，然后发送「请只回复：连接成功，不调用任何工具」。</p></div>
        <div><h3>Codex 桌面端</h3><p>完全退出应用后重新打开，新建会话并检查模型。若仍要求官方登录，在 CC Switch「设置 → 应用配置」检查「非接管切换时保留官方登录」，不要手动删除现有登录文件。</p></div>
      </div>
      <p className="notice">收到回复后刷新本站「用量」，确认调用已入账。</p>
      <details className="guide-details"><summary>配置目录与手动 CLI 接入</summary>
        <p>macOS / Linux：<code>~/.codex/config.toml</code>；Windows：<code>%USERPROFILE%\.codex\config.toml</code>。若使用自定义 CODEX_HOME 或 WSL，CC Switch 和客户端必须指向同一配置目录。</p>
        <p>不使用 CC Switch 时，可备份并合并下面的配置。该方式通过当前终端环境变量读取 Key；从桌面图标启动的应用不一定继承此变量，因此桌面端优先使用 CC Switch 管理凭证。</p>
        <EnvironmentSetup />
        <Snippet title="Codex CLI · 手动合并配置" code={snippets.codex} />
      </details>
    </section>
  </>;
}

function EnvironmentSetup() {
  return <div className="guide-platforms">
    <Snippet title="macOS / Linux · 当前终端" code={'export TOKEN_STATION_KEY="替换为你的中转 Key"'} />
    <Snippet title="Windows PowerShell · 当前终端" code={'$env:TOKEN_STATION_KEY = "替换为你的中转 Key"'} />
  </div>;
}

function StepTitle({ number, title }: { number: string; title: string }) {
  return <div className="guide-step-heading"><span className="guide-step-number" aria-hidden="true">{number}</span><h2>{title}</h2></div>;
}

function CopyField({ label, value }: { label: string; value: string }) {
  return <div className="copy-field"><small>{label}</small><code>{value}</code><CopyButton value={value} label={`复制${label}`} /></div>;
}

function CopyButton({ value, label = "复制" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setCopied(false); setError(""); }, [value]);
  async function copy() {
    try { await navigator.clipboard.writeText(value); setCopied(true); setError(""); }
    catch { setError("复制失败，请手动选择内容复制。"); }
  }
  return <><Button type="button" variant="ghost" onClick={copy} aria-label={label}><Copy size={15} />{copied ? "已复制" : "复制"}</Button>{error && <InlineError message={error} />}</>;
}

function Snippet({ title, code, children }: { title: string; code: string; children?: ReactNode }) {
  return <section className="code-card"><div><strong>{title}</strong><CopyButton value={code} label={`复制${title}`} /></div>{children}<pre><code>{code}</code></pre></section>;
}
