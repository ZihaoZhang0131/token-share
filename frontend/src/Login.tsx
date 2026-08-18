import { useState, type FormEvent } from "react";
import { KeyRound, ShieldCheck } from "lucide-react";
import { api } from "./api";
import { Button, Field, InlineError } from "./components";
import type { Session } from "./types";

export function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const session = await api<Session>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      onLogin(session);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "登录失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-brand">
        <div className="brand-mark"><KeyRound size={28} /></div>
        <div>
          <h1>Token Station</h1>
          <p>真实上游密钥只留在服务端。为每位用户分配独立凭证、额度和模型权限。</p>
        </div>
        <div className="login-schematic" aria-label="安全访问链路">
          <span>上游凭证</span><i /><span>模型权限</span><i /><span>中转 Key</span>
        </div>
        <div className="trust-line"><ShieldCheck size={17} /> AES-256-GCM · 服务端 Session · 不记录对话正文</div>
      </section>
      <form className="login-card" onSubmit={submit}>
        <div>
          <h2>登录控制台</h2>
          <p className="muted">账号由管理员创建，不开放公开注册。</p>
        </div>
        <Field label="邮箱" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <Field label="密码" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <InlineError message={error} />}
        <Button type="submit" disabled={busy}>{busy ? "正在验证…" : "登录"}</Button>
      </form>
    </main>
  );
}

export function PasswordGate({ session, onChanged }: { session: Session; onChanged: (session: Session) => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (next !== confirm) return setError("两次输入的新密码不一致");
    setBusy(true);
    setError("");
    try {
      const updated = await api<Session>("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next })
      });
      onChanged(updated);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "修改失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="center-shell">
      <form className="password-card" onSubmit={submit}>
        <div className="brand-mark"><ShieldCheck size={26} /></div>
        <h1>请先设置新密码</h1>
        <p className="muted">你好，{session.user.display_name}。新密码至少 12 位，并包含三类字符。</p>
        <Field label="当前临时密码" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
        <Field label="新密码" type="password" value={next} onChange={(e) => setNext(e.target.value)} required />
        <Field label="确认新密码" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
        {error && <InlineError message={error} />}
        <Button type="submit" disabled={busy}>{busy ? "正在保存…" : "保存并进入控制台"}</Button>
      </form>
    </main>
  );
}
