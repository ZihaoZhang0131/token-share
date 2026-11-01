import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { BarChart3, BookOpen, Copy, KeyRound, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { api, formatDate, formatNumber } from "./api";
import { Button, Empty, Field, InlineError, Meter, Modal } from "./components";
import type { AccessKey, ModelRoute, Session, Usage } from "./types";
import Guide from "./IntegrationGuide";

type Tab = "usage" | "keys" | "guide";

export default function UserConsole({
  session,
  onLoginRequired
}: {
  session: Session | null;
  onLoginRequired?: () => void;
}) {
  const [tab, setTab] = useState<Tab>("usage");
  const [usage, setUsage] = useState<Usage | null>(null);
  const [keys, setKeys] = useState<AccessKey[]>([]);
  const [models, setModels] = useState<ModelRoute[]>([]);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [newSecret, setNewSecret] = useState("");
  const isGuest = session === null;

  const load = useCallback(async () => {
    if (!session) {
      setUsage(null);
      setKeys([]);
      setModels([]);
      setError("");
      return;
    }
    setError("");
    try {
      const [nextUsage, nextKeys, nextModels] = await Promise.all([
        api<Usage>("/api/me/usage"), api<AccessKey[]>("/api/me/keys"), api<ModelRoute[]>("/api/me/models")
      ]);
      setUsage(nextUsage); setKeys(nextKeys); setModels(nextModels);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "加载失败"); }
  }, [session]);

  useEffect(() => { void load(); }, [load]);

  async function revoke(key: AccessKey) {
    if (!session) return onLoginRequired?.();
    if (!window.confirm(`确认撤销“${key.name}”？使用它的客户端会立即失效。`)) return;
    await api(`/api/me/keys/${key.id}`, { method: "DELETE" });
    await load();
  }

  return <div className="console-layout">
    <aside className="side-nav"><div><p className="nav-caption">个人控制台</p>
      <button className={tab === "usage" ? "active" : ""} onClick={() => setTab("usage")} aria-current={tab === "usage" ? "page" : undefined}><BarChart3 size={17} />用量</button>
      <button className={tab === "keys" ? "active" : ""} onClick={() => setTab("keys")} aria-current={tab === "keys" ? "page" : undefined}><KeyRound size={17} />访问 Key</button>
      <button className={tab === "guide" ? "active" : ""} onClick={() => setTab("guide")} aria-current={tab === "guide" ? "page" : undefined}><BookOpen size={17} />接入指南</button>
    </div><div className="security-note"><ShieldCheck size={17} /><span><strong>隐私模式</strong><small>不保存提示词和回答正文</small></span></div></aside>
    <main className={`workspace user-workspace user-workspace-${tab}`}><div className="page-head"><div><h1>{tab === "usage" ? "本月用量" : tab === "keys" ? "访问 Key" : "接入指南"}</h1><p className="page-subtitle">{session?.user.email ?? "登录后加载真实额度、模型权限与访问 Key"}</p></div>{tab === "keys" && <Button onClick={session ? () => setCreateOpen(true) : onLoginRequired} disabled={Boolean(session) && keys.filter((key) => key.active).length >= 5}><Plus size={16} />{session ? "创建 Key" : "登录后创建"}</Button>}</div>
      {error && <InlineError message={error} />}
      {tab === "usage" && <UsageView usage={usage} models={models} guest={isGuest} />}
      {tab === "keys" && <KeysView keys={keys} onRevoke={revoke} guest={isGuest} onLoginRequired={onLoginRequired} />}
      {tab === "guide" && <Guide models={models} />}
    </main>
    {session && createOpen && <CreateKey rpmLimit={session.user.rpm_limit} tpmLimit={session.user.tpm_limit} onClose={() => setCreateOpen(false)} onCreated={async (secret) => { setCreateOpen(false); setNewSecret(secret); await load(); }} />}
    {newSecret && <SecretModal secret={newSecret} onClose={() => setNewSecret("")} />}
  </div>;
}

function UsageView({ usage, models, guest = false }: { usage: Usage | null; models: ModelRoute[]; guest?: boolean }) {
  const maxDay = useMemo(() => Math.max(1, ...(usage?.daily.map((item) => item.tokens) ?? [1])), [usage]);
  const usedPercent = usage && usage.monthly_token_limit > 0 ? (usage.used_tokens / usage.monthly_token_limit) * 100 : 0;
  if (guest) return <>
    <section className="usage-hero guest-usage"><div><span>本月已使用</span><strong>—</strong><small>剩余额度 —</small></div><div className="usage-meter"><Meter value={0} max={1} label="登录后显示用量比例" /><span>— / —</span></div></section>
    <section className="stats-grid three"><article className="stat-card"><span>请求数</span><strong>—</strong><small>登录后显示</small></article><article className="stat-card"><span>输入 Token</span><strong>—</strong><small>登录后显示</small></article><article className="stat-card"><span>输出 Token</span><strong>—</strong><small>登录后显示</small></article></section>
    <section className="panel"><div className="panel-head"><div><h2>每日 Token</h2><p>按北京时间统计</p></div></div><Empty>登录后显示每日用量</Empty></section>
    <section className="panel"><div className="panel-head"><div><h2>允许使用的模型</h2><p>模型权限由管理员分配</p></div></div><Empty>登录后显示可用模型</Empty></section>
  </>;
  if (!usage) return <div className="skeleton-grid"><div /><div /><div /></div>;
  return <>
    <section className="usage-hero"><div><span>{usage.month} 已使用</span><strong>{formatNumber(usage.used_tokens)}</strong><small>剩余 {formatNumber(usage.remaining_tokens)} Token</small></div><div className="usage-meter"><Meter value={usage.used_tokens} max={usage.monthly_token_limit} /><span>{usedPercent.toFixed(1)}% / {formatNumber(usage.monthly_token_limit)}</span></div></section>
    <section className="stats-grid three"><article className="stat-card"><span>请求数</span><strong>{formatNumber(usage.request_count)}</strong><small>本自然月</small></article><article className="stat-card"><span>输入 Token</span><strong>{formatNumber(usage.input_tokens)}</strong><small>提示词及上下文</small></article><article className="stat-card"><span>输出 Token</span><strong>{formatNumber(usage.output_tokens)}</strong><small>模型生成内容</small></article></section>
    <section className="panel"><div className="panel-head"><div><h2>每日 Token</h2><p>按北京时间统计</p></div></div><div className="bar-chart">{usage.daily.map((item, index) => <div className="bar-slot" key={item.date} title={`${item.date}: ${item.tokens}`}><span style={{ height: `${Math.max(item.tokens ? 6 : 1, (item.tokens / maxDay) * 100)}%` }} /><small>{index % 5 === 0 || index === usage.daily.length - 1 ? item.date : ""}</small></div>)}</div></section>
    <section className="panel"><div className="panel-head"><div><h2>允许使用的模型</h2><p>模型权限由管理员分配</p></div></div><div className="model-chips">{models.map((model) => <code key={model.id}>{model.public_name}</code>)}{!models.length && <Empty>尚未分配模型</Empty>}</div></section>
  </>;
}

function KeysView({ keys, onRevoke, guest = false, onLoginRequired }: { keys: AccessKey[]; onRevoke: (key: AccessKey) => void; guest?: boolean; onLoginRequired?: () => void }) {
  if (!keys.length) return <Empty>{guest ? <div className="guest-empty"><strong>尚未加载访问 Key</strong><span>登录后可查看、创建或撤销你的 Key。</span><Button onClick={onLoginRequired}>登录查看</Button></div> : "还没有访问 Key。创建后，明文只会显示一次。"}</Empty>;
  return <div className="key-list">{keys.map((key) => <article className={`key-row ${key.active ? "" : "disabled"}`} key={key.id}><div className="key-icon"><KeyRound size={19} /></div><div className="key-main"><div><strong>{key.name}</strong><span className={`pill ${key.active ? "pill-ok" : ""}`}>{key.active ? "有效" : "已撤销"}</span></div><code>ts_sk_{key.prefix}_••••{key.last4}</code><small>创建 {formatDate(key.created_at)} · 最近使用 {formatDate(key.last_used_at)}</small></div><dl><div><dt>RPM</dt><dd>{formatNumber(key.rpm_limit)}</dd></div><div><dt>TPM</dt><dd>{formatNumber(key.tpm_limit)}</dd></div></dl>{key.active && <Button variant="ghost" onClick={() => onRevoke(key)} aria-label={`撤销 ${key.name}`}><Trash2 size={16} />撤销</Button>}</article>)}</div>;
}


function CreateKey({ rpmLimit, tpmLimit, onClose, onCreated }: { rpmLimit: number; tpmLimit: number; onClose: () => void; onCreated: (secret: string) => Promise<void> }) {
  const [form, setForm] = useState({ name: "", rpm_limit: Math.min(10, rpmLimit), tpm_limit: Math.min(50000, tpmLimit) }); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); setError(""); try { const result = await api<{ plaintext: string }>("/api/me/keys", { method: "POST", body: JSON.stringify(form) }); await onCreated(result.plaintext); } catch (reason) { setError(reason instanceof Error ? reason.message : "创建失败"); } finally { setBusy(false); } }
  return <Modal title="创建访问 Key" onClose={onClose}><form className="modal-form" onSubmit={submit}><Field label="名称" placeholder="例如：我的电脑" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /><div className="form-grid"><Field label="每分钟请求数（RPM）" type="number" min={1} max={rpmLimit} value={form.rpm_limit} onChange={(e) => setForm({ ...form, rpm_limit: Number(e.target.value) })} hint={`账号上限 ${formatNumber(rpmLimit)}`} /><Field label="每分钟 Token（TPM）" type="number" min={100} max={tpmLimit} value={form.tpm_limit} onChange={(e) => setForm({ ...form, tpm_limit: Number(e.target.value) })} hint={`账号上限 ${formatNumber(tpmLimit)}`} /></div>{error && <InlineError message={error} />}<div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>取消</Button><Button type="submit" disabled={busy}>{busy ? "正在生成…" : "生成 Key"}</Button></div></form></Modal>;
}

function SecretModal({ secret, onClose }: { secret: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  async function copy() { await navigator.clipboard.writeText(secret); setCopied(true); }
  return <Modal title="保存你的新 Key" onClose={onClose}><div className="secret-state"><div className="warning-icon"><KeyRound size={28} /></div><h3>明文只显示这一次</h3><p>关闭窗口后无法再次查看。如果丢失，请撤销后重新创建。</p><div className="secret-box"><code>{secret}</code><Button variant="secondary" onClick={copy}><Copy size={15} />{copied ? "已复制" : "复制"}</Button></div><Button onClick={onClose}>我已安全保存</Button></div></Modal>;
}
