import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { Role, User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox } from "../components/Spinner";
import { errMsg, fmtDate } from "../util";

export default function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[] | null>(null);
  const [err, setErr] = useState("");
  const [f, setF] = useState({ name: "", email: "", password: "", role: "paralegal" as Role });
  const [busy, setBusy] = useState(false);

  const load = () => api.users().then(setUsers).catch((e) => setErr(errMsg(e)));
  useEffect(() => { load(); }, []);

  async function patch(id: number, p: Parameters<typeof api.patchUser>[1]) {
    setErr("");
    try { await api.patchUser(id, p); await load(); } catch (e) { setErr(errMsg(e)); }
  }
  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try { await api.createUser(f); setF({ name: "", email: "", password: "", role: "paralegal" }); await load(); } catch (x) { setErr(errMsg(x)); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-navy">Users</h1>
      {err && <ErrorBox message={err} />}
      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead><tr><th className="th">Name</th><th className="th">Email</th><th className="th">Role</th><th className="th">Status</th><th className="th">Created</th><th className="th">Actions</th></tr></thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id}>
                <td className="td font-medium">{u.name}{u.id === me?.id && <span className="chip chip-grey ml-2">you</span>}</td>
                <td className="td">{u.email}</td>
                <td className="td">
                  <select aria-label={`Role for ${u.name}`} className="input !w-32 !py-1" value={u.role} disabled={u.id === me?.id} onChange={(e) => patch(u.id, { role: e.target.value as Role })}>
                    <option value="attorney">attorney</option><option value="paralegal">paralegal</option><option value="admin">admin</option>
                  </select>
                </td>
                <td className="td"><span className={`chip ${u.active ? "chip-ok" : "chip-grey"}`}>{u.active ? "Active" : "Deactivated"}</span></td>
                <td className="td text-muted">{fmtDate(u.created_at)}</td>
                <td className="td">
                  <button className={`btn btn-sm ${u.active ? "btn-danger" : ""}`} disabled={u.id === me?.id} onClick={() => patch(u.id, { active: !u.active })}>{u.active ? "Deactivate" : "Reactivate"}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!users && !err && <p className="p-4 text-muted" role="status">Loading...</p>}
      </div>
      <form onSubmit={create} className="card card-b grid gap-3 md:grid-cols-5" aria-label="Create user">
        <div><label className="label" htmlFor="nu-n">Name</label><input id="nu-n" className="input" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
        <div><label className="label" htmlFor="nu-e">Email</label><input id="nu-e" className="input" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
        <div><label className="label" htmlFor="nu-p">Password (8+ chars)</label><input id="nu-p" className="input" type="password" minLength={8} required autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></div>
        <div><label className="label" htmlFor="nu-r">Role</label>
          <select id="nu-r" className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value as Role })}>
            <option value="attorney">attorney</option><option value="paralegal">paralegal</option><option value="admin">admin</option>
          </select></div>
        <div className="flex items-end"><button className="btn btn-primary w-full" disabled={busy}>{busy ? "Creating..." : "Create user"}</button></div>
      </form>
    </div>
  );
}
