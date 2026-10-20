import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { errMsg } from "../util";

const DEMO = ["attorney@stare.local", "paralegal@stare.local", "admin@stare.local"];

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("attorney@stare.local");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try { await login(email.trim(), password); } catch (x) { setErr(errMsg(x)); } finally { setBusy(false); }
  }

  return (
    <main className="flex min-h-[calc(100vh-40px)] items-center justify-center bg-navy px-4 pb-12">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center text-white">
          <div className="text-4xl font-extrabold tracking-[0.25em]">ST<span className="text-amber">A</span>RE</div>
          <p className="mt-2 text-sm text-slate-300">Verified federal employment-discrimination research</p>
        </div>
        <form onSubmit={submit} className="card card-b space-y-4" aria-label="Sign in">
          <h1 className="text-lg font-bold text-navy">Sign in</h1>
          {err && <div className="alert alert-bad" role="alert">{err}</div>}
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" className="input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="pw">Password</label>
            <input id="pw" className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <button className="btn btn-primary w-full" disabled={busy}>{busy ? "Signing in..." : "Sign in"}</button>
          <div className="alert alert-info text-xs">
            <strong>Demo users</strong> (password <code>stare-demo</code>):
            <div className="mt-1 flex flex-wrap gap-1">
              {DEMO.map((d) => (
                <button type="button" key={d} className="chip chip-navy cursor-pointer" onClick={() => { setEmail(d); setPassword("stare-demo"); }}>{d}</button>
              ))}
            </div>
          </div>
        </form>
      </div>
    </main>
  );
}
