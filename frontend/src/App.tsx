import { useEffect, useState } from "react";
import { api, setSessionSecurity } from "./api";
import AdminConsole from "./AdminConsole";
import { Loading } from "./components";
import { Login, PasswordGate } from "./Login";
import type { Session } from "./types";
import UserConsole from "./UserConsole";
import GameFrame from "./GameFrame";

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
    <GameFrame name={session.user.display_name} role={session.user.role === "admin" ? "管理员" : "用户"} action="退出" onAction={logout}>
      {session.user.role === "admin" ? <AdminConsole /> : <UserConsole session={session} />}
    </GameFrame>
  );
}
