import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import type { Role } from "./api/types";
import Header from "./components/Header";
import Footer from "./components/Footer";
import Login from "./pages/Login";
import Matters from "./pages/Matters";
import MatterPage from "./pages/MatterPage";
import RunWorkspace from "./pages/RunWorkspace";
import CheckDraft from "./pages/CheckDraft";
import AuditLog from "./pages/AuditLog";
import Users from "./pages/Users";
import Settings from "./pages/Settings";

function Shell({ roles }: { roles?: Role[] }) {
  const { user } = useAuth();
  const loc = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  const denied = roles && !roles.includes(user.role);
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main id="main" className="mx-auto w-full max-w-[1600px] flex-1 px-4 pb-20 pt-5">
        {denied ? (
          <div className="alert alert-warn">Your role ({user.role}) does not have access to this page.</div>
        ) : (
          <Outlet />
        )}
      </main>
      <Footer />
    </div>
  );
}

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <><Login /><Footer /></>} />
      <Route element={<Shell />}>
        <Route path="/" element={<Matters />} />
        <Route path="/matters/:id" element={<MatterPage />} />
        <Route path="/runs/:id" element={<RunWorkspace />} />
        <Route path="/firewall" element={<CheckDraft />} />
      </Route>
      <Route element={<Shell roles={["admin"]} />}>
        <Route path="/audit" element={<AuditLog />} />
        <Route path="/users" element={<Users />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
