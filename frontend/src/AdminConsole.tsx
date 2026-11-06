import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  Activity,
  Boxes,
  CheckCircle2,
  CircleGauge,
  Database,
  FileSearch,
  Plus,
  RefreshCw,
  ScrollText,
  Users
} from "lucide-react";
import { api, formatDate, formatNumber } from "./api";
import { Button, Empty, Field, InlineError, Modal, SelectField } from "./components";
import type { AuditLog, ModelRoute, Provider, UsageLog, User } from "./types";
import { modeLabel } from "./IntegrationGuide";
import { loadAdminSection } from "./loadAdminSection";
import Analytics from "./Analytics";
import { formatTokens } from "./formatTokens";
import { PixelIcon } from "./PixelIcon";

type Tab = "overview" | "providers" | "models" | "users" | "logs" | "audit";

const tabs: { id: Tab; label: string; icon: typeof Activity }[] = [
  { id: "overview", label: "总览", icon: CircleGauge },
  { id: "providers", label: "上游", icon: Database },
  { id: "models", label: "模型", icon: Boxes },
  { id: "users", label: "用户", icon: Users },
  { id: "logs", label: "调用日志", icon: ScrollText },
  { id: "audit", label: "审计日志", icon: FileSearch }
];

export default function AdminConsole() {
  const [tab, setTab] = useState<Tab>("overview");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<ModelRoute[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [logs, setLogs] = useState<UsageLog[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const loadGeneration = useRef(0);
  const [modal, setModal] = useState<"provider" | "model" | "user" | null>(null);
  const [resetUser, setResetUser] = useState<User | null>(null);
  const [editProvider, setEditProvider] = useState<Provider | null>(null);
  const [editModel, setEditModel] = useState<ModelRoute | null>(null);
  const [editUser, setEditUser] = useState<User | null>(null);

  const loadAll = useCallback(async () => {
    const generation = ++loadGeneration.current;
    setLoading(true);
    setError("");
    function loadPart<T>(label: string, path: string, apply: (value: T) => void) {
      return loadAdminSection(label, () => api<T>(path), (value) => {
        if (generation === loadGeneration.current) apply(value);
      });
    }
    const results = await Promise.all([
      loadPart<Provider[]>("上游", "/api/admin/providers", setProviders),
      loadPart<ModelRoute[]>("模型", "/api/admin/models", setModels),
      loadPart<User[]>("用户列表", "/api/admin/users", setUsers),
      loadPart<UsageLog[]>("调用日志", "/api/admin/logs?limit=200", setLogs),
      loadPart<AuditLog[]>("审计日志", "/api/admin/audit?limit=200", setAuditLogs)
    ]);
    if (generation === loadGeneration.current) {
      const failures = results.filter(Boolean);
      setError(failures.length ? `${failures.join("；")}。其他数据已独立加载；失败部分可能仍显示上次数据，请点击刷新重试。` : "");
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
    return () => { loadGeneration.current += 1; };
  }, [loadAll]);

  return (
    <div className="console-layout">
      <nav className="menu-tabs" aria-label="管理控制台">{tabs.map(({ id, label }) => (
        <button className={tab === id ? "active" : ""} key={id} onClick={() => setTab(id)} aria-current={tab === id ? "page" : undefined}><PixelIcon name={id} />{label}</button>
      ))}</nav>
      <main className="workspace">
        <div className="admin-instrument-header">
          <div className="instrument-title"><h1>{tabs.find((item) => item.id === tab)?.label}</h1></div>
          <div className="page-actions"><Button variant="secondary" onClick={() => { setRefreshVersion(v => v + 1); void loadAll(); }} disabled={loading}><RefreshCw size={15} />{loading ? "正在刷新…" : "刷新"}</Button>
            {tab === "overview" && <Button variant="secondary" onClick={() => setTab("logs")}><ScrollText size={15} />查看日志</Button>}
            {tab === "overview" && <Button onClick={() => setModal("provider")}><Plus size={16} />新增上游</Button>}
            {tab === "providers" && <Button onClick={() => setModal("provider")}><Plus size={16} />新增上游</Button>}
            {tab === "models" && <Button onClick={() => setModal("model")} disabled={!providers.length}><Plus size={16} />新增模型</Button>}
            {tab === "users" && <Button onClick={() => setModal("user")}><Plus size={16} />新增用户</Button>}
          </div>
        </div>
        {error && <InlineError message={error} />}
        {tab === "overview" && <Overview refreshVersion={refreshVersion} logs={logs} providers={providers} models={models} users={users} />}
        {tab === "providers" && <Providers providers={providers} onChanged={loadAll} onEdit={setEditProvider} />}
        {tab === "models" && <Models models={models} providers={providers} onChanged={loadAll} onEdit={setEditModel} />}
        {tab === "users" && <UsersView users={users} models={models} onChanged={loadAll} onReset={setResetUser} onEdit={setEditUser} />}
        {tab === "logs" && <Logs logs={logs} users={users} />}
        {tab === "audit" && <AuditLogs logs={auditLogs} users={users} />}
      </main>
      {modal === "provider" && <ProviderForm onClose={() => setModal(null)} onSaved={async () => { setModal(null); await loadAll(); }} />}
      {modal === "model" && <ModelForm providers={providers} onClose={() => setModal(null)} onSaved={async () => { setModal(null); await loadAll(); }} />}
      {modal === "user" && <UserForm models={models} onClose={() => setModal(null)} onSaved={async () => { setModal(null); await loadAll(); }} />}
      {editProvider && <ProviderForm provider={editProvider} onClose={() => setEditProvider(null)} onSaved={async () => { setEditProvider(null); await loadAll(); }} />}
      {editModel && <ModelForm model={editModel} providers={providers} onClose={() => setEditModel(null)} onSaved={async () => { setEditModel(null); await loadAll(); }} />}
      {editUser && <UserEditForm user={editUser} models={models} onClose={() => setEditUser(null)} onSaved={async () => { setEditUser(null); await loadAll(); }} />}
      {resetUser && <ResetPassword user={resetUser} onClose={() => setResetUser(null)} />}
    </div>
  );
}

function Overview({ refreshVersion, logs, providers, models, users }: { refreshVersion: number; logs: UsageLog[]; providers: Provider[]; models: ModelRoute[]; users: User[] }) {
  return <>
    <div className="station-status"><span><i className="status-dot ok" />补给站概况</span><span>{providers.filter(p => p.active).length} 个启用上游</span><span>{models.filter(m => m.active).length} 个可用模型</span><span>{users.filter(u => u.role === "user").length} 位用户</span></div>
    <Analytics admin refreshVersion={refreshVersion} />
    <section className="panel operations-panel">
      <div className="panel-head"><div><h2>上游状态</h2></div><Database size={20} /></div>
      <ProviderLedger providers={providers} logs={logs} models={models} />
    </section>
    <section className="panel">
      <div className="panel-head"><div><h2>最近调用</h2></div><Activity size={20} /></div>
      <LogTable logs={logs.slice(0, 8)} />
    </section>
  </>;
}

function Providers({ providers, onChanged, onEdit }: { providers: Provider[]; onChanged: () => Promise<void>; onEdit: (provider: Provider) => void }) {
  const [testing, setTesting] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  async function test(provider: Provider) {
    setTesting(provider.id); setMessage("");
    try {
      const result = await api<{ ok: boolean; message: string }>(`/api/admin/providers/${provider.id}/test`, { method: "POST" });
      setMessage(`${provider.name}：${result.message}`);
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : "测试失败"); }
    finally { setTesting(null); }
  }
  async function toggle(provider: Provider) {
    await api(`/api/admin/providers/${provider.id}`, { method: "PATCH", body: JSON.stringify({ active: !provider.active }) });
    await onChanged();
  }
  if (!providers.length) return <Empty>还没有上游。新增后，真实 API Key 会立即加密保存。</Empty>;
  return <><div className="card-grid">{providers.map((provider) => <article className="resource-card" key={provider.id}>
    <div className="resource-top"><span className={`status-dot ${provider.active ? "ok" : "off"}`} /><div><h3>{provider.name}</h3><p>{provider.base_url}</p></div></div>
    <dl><div><dt>密钥</dt><dd>•••• {provider.key_last4}</dd></div><div><dt>超时</dt><dd>{provider.timeout_seconds}s</dd></div><div><dt>流式 usage</dt><dd>{provider.supports_stream_usage ? "支持" : "估算"}</dd></div></dl>
    <div className="card-actions"><Button variant="secondary" onClick={() => test(provider)} disabled={testing === provider.id}>{testing === provider.id ? "测试中…" : "测试连接"}</Button><Button variant="ghost" onClick={() => onEdit(provider)}>编辑 / 换 Key</Button><Button variant="ghost" onClick={() => toggle(provider)}>{provider.active ? "停用" : "启用"}</Button></div>
  </article>)}</div>{message && <div className="notice">{message}</div>}</>;
}

function Models({ models, providers, onChanged, onEdit }: { models: ModelRoute[]; providers: Provider[]; onChanged: () => Promise<void>; onEdit: (model: ModelRoute) => void }) {
  const providerName = (id: string) => providers.find((item) => item.id === id)?.name ?? "未知上游";
  async function toggle(model: ModelRoute) {
    await api(`/api/admin/models/${model.id}`, { method: "PATCH", body: JSON.stringify({ active: !model.active }) });
    await onChanged();
  }
  if (!models.length) return <Empty>还没有公开模型映射。先创建上游，再添加模型。</Empty>;
  return <section className="panel table-panel"><table><thead><tr><th>公开模型名</th><th>上游模型</th><th>上游</th><th>接入模式 / 推理</th><th>最大输出</th><th>状态</th><th /></tr></thead><tbody>{models.map((model) => <tr key={model.id}><td><code>{model.public_name}</code></td><td>{model.upstream_model}</td><td>{providerName(model.provider_id)}</td><td>{modeLabel(model.api_mode)}<br /><small>{model.reasoning_effort ? `固定 ${model.reasoning_effort}` : "不固定"}</small></td><td>{formatNumber(model.max_output_tokens)}</td><td><span className={`pill ${model.active ? "pill-ok" : ""}`}>{model.active ? "启用" : "停用"}</span></td><td className="row-actions"><Button variant="ghost" onClick={() => onEdit(model)}>编辑</Button><Button variant="ghost" onClick={() => toggle(model)}>{model.active ? "停用" : "启用"}</Button></td></tr>)}</tbody></table></section>;
}

function UsersView({ users, models, onChanged, onReset, onEdit }: { users: User[]; models: ModelRoute[]; onChanged: () => Promise<void>; onReset: (user: User) => void; onEdit: (user: User) => void }) {
  const ordinary = users.filter((user) => user.role === "user");
  async function toggle(user: User) {
    await api(`/api/admin/users/${user.id}`, { method: "PATCH", body: JSON.stringify({ active: !user.active }) });
    await onChanged();
  }
  if (!ordinary.length) return <Empty>还没有用户账号。用户必须由管理员创建。</Empty>;
  return <section className="panel table-panel"><table><thead><tr><th>用户</th><th>月额度</th><th>速率上限</th><th>模型权限</th><th>状态</th><th /></tr></thead><tbody>{ordinary.map((user) => <tr key={user.id}><td><strong>{user.display_name}</strong><small>{user.email}</small></td><td title={`${user.monthly_token_limit.toLocaleString()} Token`}>{formatTokens(user.monthly_token_limit)}</td><td>{formatNumber(user.rpm_limit)} RPM<small>{formatNumber(user.tpm_limit)} TPM</small></td><td>{user.allowed_models.length ? user.allowed_models.join("、") : "未分配"}<small>{models.length} 个模型可配置</small></td><td><span className={`pill ${user.active ? "pill-ok" : ""}`}>{user.active ? (user.must_change_password ? "待改密" : "正常") : "停用"}</span></td><td className="row-actions"><Button variant="ghost" onClick={() => onEdit(user)}>编辑</Button><Button variant="ghost" onClick={() => onReset(user)}>重置密码</Button><Button variant="ghost" onClick={() => toggle(user)}>{user.active ? "停用" : "启用"}</Button></td></tr>)}</tbody></table></section>;
}

function Logs({ logs, users }: { logs: UsageLog[]; users: User[] }) {
  const [model, setModel] = useState("");
  const [status, setStatus] = useState("");
  const userName = (id: string) => users.find((user) => user.id === id)?.display_name ?? id.slice(0, 8);
  const filtered = logs.filter((log) => (!model || log.model_alias.includes(model)) && (!status || String(log.status_code) === status));
  return <><div className="filters"><Field label="模型" placeholder="筛选公开模型名" value={model} onChange={(e) => setModel(e.target.value)} /><Field label="状态码" placeholder="例如 200" value={status} onChange={(e) => setStatus(e.target.value)} /></div><section className="panel table-panel"><table><thead><tr><th>时间</th><th>请求 ID</th><th>用户</th><th>模型</th><th>消耗 (M)</th><th>耗时</th><th>状态</th></tr></thead><tbody>{filtered.map((log) => <tr key={log.request_id}><td>{formatDate(log.created_at)}</td><td><code>{log.request_id.slice(0, 16)}…</code></td><td>{userName(log.user_id)}</td><td>{log.model_alias}</td><td title={`${log.total_tokens.toLocaleString()} Token`}>{formatTokens(log.total_tokens)}</td><td>{log.latency_ms} ms</td><td><span className={`pill ${log.status_code < 400 ? "pill-ok" : "pill-bad"}`}>{log.status_code}</span></td></tr>)}</tbody></table>{!filtered.length && <Empty>没有符合条件的调用记录</Empty>}</section></>;
}

function LogTable({ logs }: { logs: UsageLog[] }) {
  return <div className="overview-ledger" role="table" aria-label="最近调用元数据">
    <div className="ledger-row ledger-header" role="row"><span>状态</span><span>公开模型</span><span>请求 ID</span><span>消耗 (M)</span><span>耗时</span><span>时间</span></div>
    {logs.length ? logs.map((log) => <div className="ledger-row" role="row" key={log.request_id}><span><i className={`status-dot ${log.status_code < 400 ? "ok" : "bad"}`} />{log.status_code}</span><strong>{log.model_alias}</strong><code>{log.request_id.slice(0, 14)}</code><span title={`${log.total_tokens.toLocaleString()} Token`}>{formatTokens(log.total_tokens)}</span><span>{formatNumber(log.latency_ms)} ms</span><time>{formatDate(log.created_at)}</time></div>) : <div className="ledger-row ledger-empty" role="row"><span><i className="status-dot off" />—</span><strong>尚无调用</strong><code>—</code><span>—</span><span>—</span><time>完成第一次模型调用后显示</time></div>}
  </div>;
}

function ProviderLedger({ providers, logs, models }: { providers: Provider[]; logs: UsageLog[]; models: ModelRoute[] }) {
  return <div className="provider-ledger" role="table" aria-label="上游运行状态">
    <div className="provider-ledger-row provider-ledger-header" role="row"><span>上游</span><span>Base URL</span><span>公开路由</span><span>超时</span><span>Usage</span><span>状态</span></div>
    {providers.length ? providers.map((provider) => {
      const routes = models.filter((model) => model.provider_id === provider.id && model.active).length;
      const hasFault = logs.slice(0, 20).some((log) => log.status_code >= 500 && models.some((model) => model.provider_id === provider.id && model.public_name === log.model_alias));
      return <div className="provider-ledger-row" role="row" key={provider.id}><strong>{provider.name}</strong><code>{provider.base_url}</code><span>{routes}</span><span>{provider.timeout_seconds}s</span><span>{provider.supports_stream_usage ? "上游返回" : "本地估算"}</span><span><i className={`status-dot ${hasFault ? "bad" : provider.active ? "ok" : "off"}`} />{hasFault ? "近期故障" : provider.active ? "启用" : "停用"}</span></div>;
    }) : <div className="provider-ledger-row provider-ledger-empty" role="row"><strong>尚无上游</strong><code>—</code><span>0</span><span>—</span><span>—</span><span><i className="status-dot off" />待配置</span></div>}
  </div>;
}

function AuditLogs({ logs, users }: { logs: AuditLog[]; users: User[] }) {
  const actorName = (id: string) => users.find((user) => user.id === id)?.display_name ?? id.slice(0, 8);
  return <section className="panel table-panel"><table><thead><tr><th>时间</th><th>操作者</th><th>动作</th><th>对象类型</th><th>对象 ID</th><th>元数据</th></tr></thead><tbody>{logs.map((log) => <tr key={log.id}><td>{formatDate(log.created_at)}</td><td>{actorName(log.actor_user_id)}</td><td><code>{log.action}</code></td><td>{log.target_type}</td><td><code>{log.target_id.slice(0, 16)}</code></td><td><code>{Object.keys(log.metadata_json).join("、") || "—"}</code></td></tr>)}</tbody></table>{!logs.length && <Empty>尚无审计记录</Empty>}</section>;
}

function ProviderForm({ provider, onClose, onSaved }: { provider?: Provider; onClose: () => void; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState({ name: provider?.name ?? "", base_url: provider?.base_url ?? "", api_key: "", timeout_seconds: provider?.timeout_seconds ?? 120, supports_stream_usage: provider?.supports_stream_usage ?? false });
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); setError(""); try { const body: Record<string, unknown> = { ...form }; if (provider && !form.api_key) delete body.api_key; await api(provider ? `/api/admin/providers/${provider.id}` : "/api/admin/providers", { method: provider ? "PATCH" : "POST", body: JSON.stringify(body) }); await onSaved(); } catch (reason) { setError(reason instanceof Error ? reason.message : "保存失败"); } finally { setBusy(false); } }
  return <Modal title={provider ? "编辑上游" : "新增上游"} onClose={onClose}><form className="modal-form" onSubmit={submit}><Field label="名称" placeholder="例如：阿里云百炼" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /><Field label="Base URL" placeholder="https://example.com/v1" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} required hint="仅允许解析到公网地址的 HTTPS URL" /><Field label={provider ? "替换真实 API Key（可选）" : "真实 API Key"} type="password" autoComplete="off" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} required={!provider} hint={provider ? `留空则继续使用末四位 ${provider.key_last4} 的已加密 Key` : "保存后不可读取，只能替换"} /><Field label="超时秒数" type="number" min={10} max={600} value={form.timeout_seconds} onChange={(e) => setForm({ ...form, timeout_seconds: Number(e.target.value) })} /><label className="check-field"><input type="checkbox" checked={form.supports_stream_usage} onChange={(e) => setForm({ ...form, supports_stream_usage: e.target.checked })} /><span>上游支持流式 usage 统计</span></label>{error && <InlineError message={error} />}<div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>取消</Button><Button type="submit" disabled={busy}>{busy ? "正在保存…" : provider ? "保存修改" : "加密并保存"}</Button></div></form></Modal>;
}

function ModelForm({ model, providers, onClose, onSaved }: { model?: ModelRoute; providers: Provider[]; onClose: () => void; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState({ public_name: model?.public_name ?? "", upstream_model: model?.upstream_model ?? "", provider_id: model?.provider_id ?? providers[0]?.id ?? "", max_output_tokens: model?.max_output_tokens ?? 16384, tokenizer: model?.tokenizer ?? "cl100k_base", api_mode: model?.api_mode ?? "chat", reasoning_effort: model?.reasoning_effort ?? "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      await api(model ? `/api/admin/models/${model.id}` : "/api/admin/models", {
        method: model ? "PATCH" : "POST",
        body: JSON.stringify({ ...form, reasoning_effort: form.reasoning_effort || null })
      });
      await onSaved();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "保存失败"); }
    finally { setBusy(false); }
  }
  return <Modal title={model ? "编辑模型映射" : "新增模型映射"} onClose={onClose}>
    <form className="modal-form" onSubmit={submit}>
      <Field label="公开模型名" placeholder="gpt-6.1-sol-high" value={form.public_name} onChange={(e) => setForm({ ...form, public_name: e.target.value })} required hint="用户选择的别名；不同推理档位使用不同别名" />
      <Field label="上游真实模型名" placeholder="gpt-6.1-sol" value={form.upstream_model} onChange={(e) => setForm({ ...form, upstream_model: e.target.value })} required />
      <SelectField label="上游" value={form.provider_id} onChange={(e) => setForm({ ...form, provider_id: e.target.value })}>{providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}</SelectField>
      <div className="form-grid">
        <SelectField label="接入模式" value={form.api_mode} onChange={(e) => setForm({ ...form, api_mode: e.target.value as ModelRoute["api_mode"] })}>
          <option value="chat">聊天 · Chat Completions</option><option value="responses">编码 · Responses</option><option value="both">聊天 + 编码</option>
        </SelectField>
        <SelectField label="固定推理强度" value={form.reasoning_effort} onChange={(e) => setForm({ ...form, reasoning_effort: e.target.value })}>
          <option value="">不固定 · 客户端 / 上游默认</option>
          {["low", "medium", "high", "xhigh", "max", "none", "minimal"].map((effort) => <option key={effort} value={effort}>{effort}</option>)}
        </SelectField>
      </div>
      <p className="notice">固定档位不可覆盖；工具调用需开启编码模式。</p>
      <Field label="最大输出 Token" type="number" min={1} max={262144} value={form.max_output_tokens} onChange={(e) => setForm({ ...form, max_output_tokens: Number(e.target.value) })} hint={`${formatTokens(form.max_output_tokens)} · 包含推理与回答；不是输入上限，需小于用户及 Key 可用 TPM。`} />
      <Field label="Tokenizer" value={form.tokenizer} onChange={(e) => setForm({ ...form, tokenizer: e.target.value })} />
      {error && <InlineError message={error} />}
      <div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>取消</Button><Button type="submit" disabled={busy}>{busy ? "正在保存…" : "保存映射"}</Button></div>
    </form>
  </Modal>;
}

function UserForm({ models, onClose, onSaved }: { models: ModelRoute[]; onClose: () => void; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState({ email: "", display_name: "", temporary_password: "", monthly_token_limit: 1000000, rpm_limit: 60, tpm_limit: 100000, allowed_models: [] as string[] });
  const [error, setError] = useState("");
  function toggleModel(name: string) { setForm({ ...form, allowed_models: form.allowed_models.includes(name) ? form.allowed_models.filter((item) => item !== name) : [...form.allowed_models, name] }); }
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); try { await api("/api/admin/users", { method: "POST", body: JSON.stringify(form) }); await onSaved(); } catch (reason) { setError(reason instanceof Error ? reason.message : "创建失败"); } }
  return <Modal title="新增用户" onClose={onClose}><form className="modal-form" onSubmit={submit}><Field label="显示名称" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} required /><Field label="邮箱" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /><Field label="临时密码" type="password" value={form.temporary_password} onChange={(e) => setForm({ ...form, temporary_password: e.target.value })} required hint="至少 12 位；用户首次登录必须修改" /><Field label="每月 Token 额度" type="number" min={1} value={form.monthly_token_limit} hint={formatTokens(form.monthly_token_limit)} onChange={(e) => setForm({ ...form, monthly_token_limit: Number(e.target.value) })} /><div className="form-grid"><Field label="每把 Key 的 RPM 上限" type="number" min={1} max={10000} value={form.rpm_limit} onChange={(e) => setForm({ ...form, rpm_limit: Number(e.target.value) })} /><Field label="每把 Key 的 TPM 上限" type="number" min={100} value={form.tpm_limit} hint={formatTokens(form.tpm_limit)} onChange={(e) => setForm({ ...form, tpm_limit: Number(e.target.value) })} /></div><fieldset className="model-picker"><legend>允许使用的模型</legend>{models.filter((model) => model.active).map((model) => <label key={model.id}><input type="checkbox" checked={form.allowed_models.includes(model.public_name)} onChange={() => toggleModel(model.public_name)} />{model.public_name}</label>)}{!models.length && <small>暂无可分配模型</small>}</fieldset>{error && <InlineError message={error} />}<div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>取消</Button><Button type="submit">创建用户</Button></div></form></Modal>;
}

function UserEditForm({ user, models, onClose, onSaved }: { user: User; models: ModelRoute[]; onClose: () => void; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState({ display_name: user.display_name, monthly_token_limit: user.monthly_token_limit, rpm_limit: user.rpm_limit, tpm_limit: user.tpm_limit, allowed_models: [...user.allowed_models] });
  const [error, setError] = useState("");
  function toggleModel(name: string) { setForm({ ...form, allowed_models: form.allowed_models.includes(name) ? form.allowed_models.filter((item) => item !== name) : [...form.allowed_models, name] }); }
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); try { await api(`/api/admin/users/${user.id}`, { method: "PATCH", body: JSON.stringify(form) }); await onSaved(); } catch (reason) { setError(reason instanceof Error ? reason.message : "保存失败"); } }
  return <Modal title={`编辑用户 · ${user.display_name}`} onClose={onClose}><form className="modal-form" onSubmit={submit}><Field label="显示名称" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} required /><Field label="每月 Token 额度" type="number" min={1} value={form.monthly_token_limit} hint={formatTokens(form.monthly_token_limit)} onChange={(e) => setForm({ ...form, monthly_token_limit: Number(e.target.value) })} /><div className="form-grid"><Field label="每把 Key 的 RPM 上限" type="number" min={1} max={10000} value={form.rpm_limit} onChange={(e) => setForm({ ...form, rpm_limit: Number(e.target.value) })} /><Field label="每把 Key 的 TPM 上限" type="number" min={100} value={form.tpm_limit} hint={formatTokens(form.tpm_limit)} onChange={(e) => setForm({ ...form, tpm_limit: Number(e.target.value) })} /></div><fieldset className="model-picker"><legend>允许使用的模型</legend>{models.filter((model) => model.active || form.allowed_models.includes(model.public_name)).map((model) => <label key={model.id}><input type="checkbox" checked={form.allowed_models.includes(model.public_name)} onChange={() => toggleModel(model.public_name)} />{model.public_name}</label>)}</fieldset>{error && <InlineError message={error} />}<div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>取消</Button><Button type="submit">保存修改</Button></div></form></Modal>;
}

function ResetPassword({ user, onClose }: { user: User; onClose: () => void }) {
  const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [done, setDone] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); try { await api(`/api/admin/users/${user.id}/reset-password`, { method: "POST", body: JSON.stringify({ temporary_password: password }) }); setDone(true); } catch (reason) { setError(reason instanceof Error ? reason.message : "重置失败"); } }
  return <Modal title="重置临时密码" onClose={onClose}>{done ? <div className="success-state"><CheckCircle2 size={32} /><h3>密码已重置</h3><p>该用户的其他登录会话已失效，下次登录必须修改密码。</p><Button onClick={onClose}>完成</Button></div> : <form className="modal-form" onSubmit={submit}><p className="muted">为 {user.display_name} 设置新的临时密码。</p><Field label="临时密码" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />{error && <InlineError message={error} />}<div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>取消</Button><Button type="submit">确认重置</Button></div></form>}</Modal>;
}
