"use client";
import { useEffect, useState } from "react";
import { API, api } from "@/lib/api";

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState("admin");
  const [pass, setPass] = useState("admin");
  const [msg, setMsg] = useState("");
  const [status, setStatus] = useState<any>(null);

  useEffect(() => { setToken(localStorage.getItem("wc_token")); }, []);

  async function login(e: React.FormEvent) {
    e.preventDefault();
    setMsg("");
    try {
      const body = new URLSearchParams({ username: user, password: pass });
      const res = await fetch(`${API}/api/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      if (!res.ok) throw new Error("bad credentials");
      const d = await res.json();
      localStorage.setItem("wc_token", d.access_token);
      setToken(d.access_token);
    } catch (e: any) { setMsg(e.message); }
  }

  async function loadStatus() {
    try {
      const res = await fetch(`${API}/api/admin/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setStatus(await res.json());
    } catch { setMsg("session expired"); }
  }

  async function retrain() {
    setMsg("Triggering retrain…");
    const res = await fetch(`${API}/api/admin/retrain`, {
      method: "POST", headers: { Authorization: `Bearer ${token}` },
    });
    setMsg(res.ok ? "Retraining started in background." : "Failed.");
  }

  if (!token) return (
    <form onSubmit={login} className="card mx-auto max-w-sm space-y-3">
      <h1 className="text-lg font-bold">Admin Login</h1>
      <input value={user} onChange={(e) => setUser(e.target.value)}
        className="w-full rounded-lg border border-line bg-[#0e1530] px-3 py-2" placeholder="username" />
      <input type="password" value={pass} onChange={(e) => setPass(e.target.value)}
        className="w-full rounded-lg border border-line bg-[#0e1530] px-3 py-2" placeholder="password" />
      <button className="btn w-full">Login</button>
      {msg && <p className="text-danger text-sm">{msg}</p>}
      <p className="text-xs text-muted">Default admin/admin — override via env in prod.</p>
    </form>
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Admin / Data</h1>
        <button onClick={() => { localStorage.removeItem("wc_token"); setToken(null); }}
          className="text-sm text-muted">Logout</button>
      </div>

      <div className="flex flex-wrap gap-3">
        <button className="btn" onClick={retrain}>↻ Trigger Retraining</button>
        <button className="btn" onClick={loadStatus}>Check Status</button>
      </div>
      {msg && <p className="text-sm text-acc">{msg}</p>}

      {status && (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="card">
            <h2 className="h2">Data Freshness</h2>
            <pre className="overflow-auto text-xs text-muted">
              {JSON.stringify(status.freshness, null, 2)}
            </pre>
          </div>
          <div className="card">
            <h2 className="h2">Model Artifacts (KB)</h2>
            {Object.entries(status.artifacts_kb || {}).map(([k, v]: any) => (
              <div key={k} className="flex justify-between border-b border-line py-1 text-sm">
                <span className="text-muted">{k}</span><span className="tabnum">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
