import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
    isActive ? "bg-white/15 text-white" : "text-slate-300 hover:bg-white/10 hover:text-white"
  }`;

export default function Header() {
  const { user, logout, isRole } = useAuth();
  const admin = isRole("admin");
  return (
    <header className="bg-navy text-white shadow">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-amber focus:px-3 focus:py-1 focus:text-navy">
        Skip to content
      </a>
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5">
        <NavLink to="/" className="flex items-center gap-2" aria-label="STARE home">
          <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
            <rect width="32" height="32" rx="6" fill="#14305a" />
            <path d="M9 21c2 2 12 2 12-2s-12-2-12-6 9-4 13-2" fill="none" stroke="#f5a623" strokeWidth="3" strokeLinecap="round" />
          </svg>
          <span className="text-lg font-extrabold tracking-[0.18em]">ST<span className="text-amber">A</span>RE</span>
        </NavLink>
        <nav aria-label="Main" className="flex flex-wrap items-center gap-1">
          <NavLink to="/" end className={link}>Matters</NavLink>
          <NavLink to="/firewall" className={link}>Check a draft</NavLink>
          {admin && <NavLink to="/audit" className={link}>Audit log</NavLink>}
          {admin && <NavLink to="/users" className={link}>Users</NavLink>}
          {admin && <NavLink to="/settings" className={link}>Settings</NavLink>}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-sm">
          <span className="text-slate-200">
            {user?.name} <span className="ml-1 rounded-full bg-amber px-2 py-0.5 text-xs font-bold capitalize text-navy">{user?.role}</span>
          </span>
          <button className="rounded-md border border-white/30 px-3 py-1 text-sm hover:bg-white/10" onClick={logout}>Log out</button>
        </div>
      </div>
    </header>
  );
}
