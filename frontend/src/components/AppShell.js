import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Briefcase,
  Building2,
  FileText,
  Home,
  ListChecks,
  LogOut,
  Menu,
  Plus,
  Printer,
  Search,
  Shield,
  ShieldCheck,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";

const NAV = [
  { key: "dashboard", label: "Dashboard", to: "/", icon: Home, end: true },
  { key: "verification", label: "Verification", to: "/verification?field=id_number", icon: AlertTriangle, roles: ["admin", "supervisor"], badgeKey: "verification" },
  { key: "my-households", label: "My Households", to: "/my-households", icon: Briefcase },
  { key: "reassign", label: "Reassign Caseload", to: "/reassign", icon: Users, roles: ["admin", "supervisor"] },
  { key: "print-center", label: "Print Center", to: "/print-center", icon: Printer, roles: ["admin", "supervisor"] },
  { key: "signoffs", label: "Sign-off History", to: "/signoffs", icon: ShieldCheck, roles: ["admin", "supervisor"] },
  { key: "org-settings", label: "Organisation", to: "/settings/organisation", icon: Building2, adminOnly: true },
  { key: "upload", label: "Upload Document", to: "/documents/upload", icon: FileText },
  { key: "audit", label: "Audit Log", to: "/audit", icon: Shield, adminOnly: true },
];

function visibleNav(role) {
  return NAV.filter(
    (n) => (!n.adminOnly || role === "admin") && (!n.roles || n.roles.includes(role))
  );
}

function RoleBadge({ role }) {
  const styles = {
    admin: "bg-slate-900 text-white",
    supervisor: "bg-blue-50 text-blue-900 border border-blue-200",
    "case-worker": "bg-slate-100 text-slate-800 border border-slate-200",
    "data-capturer": "bg-slate-100 text-slate-800 border border-slate-200",
  };
  return (
    <span
      className={cn("rounded-md px-2.5 py-1 text-xs font-medium", styles[role] || "bg-slate-100")}
      data-testid="user-role-badge"
    >
      {ROLE_LABELS[role] || role}
    </span>
  );
}

function NavItems({ role, counts, onNavigate }) {
  return (
    <nav className="flex flex-col gap-1" data-testid="app-sidebar-nav">
      {visibleNav(role).map((n) => {
        const Icon = n.icon;
        const badge = n.badgeKey ? counts?.[n.badgeKey] : 0;
        return (
          <NavLink
            key={n.key}
            to={n.to}
            end={n.end}
            onClick={onNavigate}
            data-testid={`nav-item-${n.key}`}
            className={({ isActive }) =>
              cn(
                "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-base text-slate-700 hover:bg-slate-100",
                isActive &&
                  "bg-slate-100 font-medium text-slate-900 border-l-4 border-[color:var(--sa-green)]"
              )
            }
          >
            <Icon className="h-5 w-5" />
            <span className="flex-1">{n.label}</span>
            {badge > 0 && (
              <span
                className="ml-auto rounded-full bg-amber-500 px-2 py-0.5 text-xs font-semibold text-white tabular-nums"
                data-testid={`nav-badge-${n.key}`}
              >
                {badge}
              </span>
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}

function SidebarContent({ user, counts, onLogout, onNavigate }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-4 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-900 text-white">
          <ShieldCheck className="h-6 w-6" />
        </div>
        <div>
          <p className="text-base font-semibold leading-tight text-slate-900">OVC CaseFile</p>
          <p className="text-xs text-slate-500">Offline case management</p>
        </div>
      </div>
      <div className="flex-1 px-3 py-2">
        <NavItems role={user?.role} counts={counts} onNavigate={onNavigate} />
      </div>
      <div className="border-t border-slate-200 p-4">
        <div className="mb-3">
          <p className="truncate text-sm font-medium text-slate-900">{user?.full_name}</p>
          <div className="mt-1">
            <RoleBadge role={user?.role} />
          </div>
        </div>
        <Button
          variant="outline"
          className="w-full justify-start gap-2"
          onClick={onLogout}
          data-testid="app-logout-button"
        >
          <LogOut className="h-4 w-4" /> Sign out
        </Button>
      </div>
    </div>
  );
}

export function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [counts, setCounts] = useState({ verification: 0 });

  useEffect(() => {
    if (user?.role === "admin" || user?.role === "supervisor") {
      api
        .get("/households/verification_count/")
        .then((r) => setCounts({ verification: r.data.total }))
        .catch(() => {});
    }
  }, [user]);

  const onLogout = async () => {
    await logout();
    navigate("/login");
  };

  const submitSearch = (e) => {
    e.preventDefault();
    navigate(`/?q=${encodeURIComponent(q)}`);
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Desktop sidebar */}
      <aside
        className="hidden w-[280px] shrink-0 border-r border-slate-200 bg-white lg:block"
        data-testid="app-sidebar"
      >
        <div className="sticky top-0 h-screen">
          <SidebarContent user={user} counts={counts} onLogout={onLogout} />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top header */}
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
          <div className="flex items-center gap-3 px-4 py-3 sm:px-6">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" className="lg:hidden" data-testid="mobile-menu-button">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-[280px] p-0">
                <SidebarContent user={user} counts={counts} onLogout={onLogout} onNavigate={() => setMobileOpen(false)} />
              </SheetContent>
            </Sheet>

            <form onSubmit={submitSearch} className="relative max-w-xl flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search surname, ID number, or household number"
                className="h-11 pl-9"
                data-testid="global-search-input"
              />
            </form>

            <div className="ml-auto flex items-center gap-2">
              <Button
                onClick={() => navigate("/households/new")}
                className="gap-2 bg-slate-900 hover:bg-slate-800"
                data-testid="header-new-household-button"
              >
                <Plus className="h-4 w-4" /> <span className="hidden sm:inline">New Household</span>
              </Button>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export { RoleBadge };
