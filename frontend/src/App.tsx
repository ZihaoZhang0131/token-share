import { useEffect, useState } from "react";
import { KeyRound, LogOut } from "lucide-react";
import { api, setSessionSecurity } from "./api";
import AdminConsole from "./AdminConsole";
import { Button, Loading } from "./components";
import { Login, PasswordGate } from "./Login";
import type { Session } from "./types";
import UserConsole from "./UserConsole";

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<Session>("/api/auth/session")
      .then((value) => {
        setSession(value);
        setSessionSecurity(value);
      })
      .catch(() => setSessionSecurity(null))
      .finally(() => setLoading(false));
  }, []);

  function acceptSession(value: Session) {
    setSession(value);
    setSessionSecurity(value);
  }

  async function logout() {
    try {
      await api<void>("/api/auth/logout", { method: "POST" });
    } finally {
      setSession(null);
      setSessionSecurity(null);
    }
  }

  if (loading) return <Loading />;
  if (!session) return <Login onLogin={acceptSession} />;
  if (session.user.must_change_password) return <PasswordGate session={session} onChanged={acceptSession} />;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-brand"><span><KeyRound size={18} /></span><strong>Token Station</strong></div>
        <div className="topbar-user">
          <div><strong>{session.user.display_name}</strong><small>{session.user.role === "admin" ? "管理员" : session.user.email}</small></div>
          <Button variant="ghost" onClick={logout}><LogOut size={16} />退出</Button>
        </div>
      </header>
      {session.user.role === "admin" ? <AdminConsole /> : <UserConsole session={session} />}
    </div>
  );
}
