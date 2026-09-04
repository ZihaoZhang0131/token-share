import { useState, type FormEvent } from "react";
import { KeyRound, LogIn, ShieldCheck } from "lucide-react";
import { api } from "./api";
import { Button, Field, InlineError, Modal } from "./components";
import type { Session } from "./types";
import UserConsole from "./UserConsole";

export function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);

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

  const openLogin = () => {
    setError("");
    setLoginOpen(true);
  };

  return (
    <div className="app-shell guest-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <span><KeyRound size={18} /></span>
          <div><strong>Token Station</strong><small>安全访问控制面</small></div>
        </div>
        <div className="topbar-user">
          <div><strong>访客</strong><small>未登录</small></div>
          <Button variant="ghost" onClick={openLogin}><LogIn size={16} />登录</Button>
        </div>
      </header>

      <UserConsole session={null} onLoginRequired={openLogin} />

      {loginOpen && (
        <Modal title="登录控制台" onClose={() => setLoginOpen(false)}>
          <form className="modal-form guest-login-form" onSubmit={submit}>
            <p className="guest-login-intro">账号由管理员创建，不开放公开注册。</p>
            <Field label="邮箱" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required />
            <Field label="密码" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
            {error && <InlineError message={error} />}
            <div className="login-boundary"><ShieldCheck size={16} />登录后加载你的真实额度、模型权限与访问 Key。</div>
            <div className="modal-actions">
              <Button type="button" variant="secondary" onClick={() => setLoginOpen(false)}>取消</Button>
              <Button type="submit" disabled={busy}>{busy ? "正在验证…" : "登录"}</Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
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
