import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Briefcase,
  Building2,
  CalendarClock,
  FileText,
  HeartHandshake,
  Home,
  Landmark,
  LogOut,
  Menu,
  Plus,
  Printer,
  ScanLine,
  Search,
  Shield,
  ShieldCheck,
  Target,
  UserCog,
  Users,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { toast } from "sonner";
import api from "@/lib/api";
import { lookupHousehold, uniqueHousehold } from "@/lib/lookup";
import { playChime } from "@/lib/chimes";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";

const NAV = [
  { key: "dashboard", label: "Dashboard", to: "/", icon: Home, end: true },
  { key: "verification", label: "Verification", to: "/verification?field=id_number", icon: AlertTriangle, roles: ["admin", "supervisor"], badgeKey: "verification" },
  { key: "my-households", label: "My Households", to: "/my-households", icon: Briefcase },
  { key: "work-diary", label: "Work diary", to: "/work-diary", icon: CalendarClock, badgeKey: "diary", hideFor: ["caregiver"] },
  { key: "services", label: "Daily Service Log", to: "/services", icon: HeartHandshake, hideFor: ["caregiver"] },
  { key: "partners", label: "Partner directory", to: "/partners", icon: Landmark, hideFor: ["caregiver"] },
  { key: "reassign", label: "Reassign Caseload", to: "/reassign", icon: Users, roles: ["admin", "supervisor"] },
  { key: "print-center", label: "Print Center", to: "/print-center", icon: Printer, roles: ["admin", "supervisor"] },
  { key: "signoffs", label: "Sign-off History", to: "/signoffs", icon: ShieldCheck, roles: ["admin", "supervisor"] },
  { key: "targets", label: "Service Targets", to: "/settings/targets", icon: Target, roles: ["admin", "supervisor"] },
  { key: "org-settings", label: "Organisation", to: "/settings/organisation", icon: Building2, adminOnly: true },
  { key: "staff", label: "Staff accounts", to: "/settings/staff", icon: UserCog, adminOnly: true },
  { key: "password", label: "Change password", to: "/settings/password", icon: Shield },
  { key: "upload", label: "Upload Document", to: "/documents/upload", icon: FileText, hideFor: ["caregiver"] },
  { key: "scan", label: "Scan Intake", to: "/scan-intake", icon: ScanLine, hideFor: ["caregiver"] },
  { key: "audit", label: "Audit Log", to: "/audit", icon: Shield, adminOnly: true },
];

function visibleNav(role) {
  return NAV.filter(
    (n) =>
      (!n.adminOnly || role === "admin") &&
      (!n.roles || n.roles.includes(role)) &&
      (!n.hideFor || !n.hideFor.includes(role)),
  );
}

function RoleBadge({ role, isSystemBuilder }) {
  const label = isSystemBuilder
    ? "Administrator"
    : (ROLE_LABELS[role] || role);
  return (
    <span
      className="rounded-full bg-white/50 px-2.5 py-0.5 text-[11px] font-medium tracking-wide text-foreground/80"
      data-testid="user-role-badge"
    >
      {label}
    </span>
  );
}

function NavItems({ role, counts, onNavigate }) {
  return (
    <nav className="flex flex-col gap-0.5" data-testid="app-sidebar-nav">
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
                "flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-[15px] text-foreground/70 transition-colors hover:bg-white/40",
                isActive && "bg-white/70 font-semibold text-foreground shadow-sm",
              )
            }
          >
            <Icon className="h-[18px] w-[18px] opacity-80" />
            <span className="flex-1">{n.label}</span>
            {badge > 0 && (
              <span
                className="ml-auto rounded-full bg-foreground px-2 py-0.5 text-[11px] font-semibold text-white tabular-nums"
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

function SidebarContent({ user, counts, onLogout, onNavigate, logoUrl, orgName }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 px-4 py-6">
        {logoUrl ? (
          <img src={logoUrl} alt="Sebueng Itumeleng" className="h-10 w-10 rounded-2xl object-cover" data-testid="sidebar-org-logo" />
        ) : (
          <img src="/emblem.jpg" alt="Sebueng Itumeleng" className="h-10 w-10 rounded-2xl object-cover" data-testid="sidebar-org-logo" />
        )}
        <div>
          <p className="text-[15px] font-semibold tracking-tight">{orgName && orgName !== "OVC Organisation" ? orgName : "Sebueng Itumeleng"}</p>
          <p className="text-[11px] text-muted-foreground">{user?.is_training ? "Training workspace" : "Live office files"}</p>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-1">
        <NavItems role={user?.role} counts={counts} onNavigate={onNavigate} />
      </div>
      <div className="mx-3 mb-4 rounded-2xl bg-white/40 p-3">
        {user?.is_training && (
          <p className="mb-2 rounded-xl bg-amber-100/80 px-2.5 py-1.5 text-[11px] font-medium text-amber-900">
            Training classroom — fictional TEST files only
          </p>
        )}
        <p className="truncate text-sm font-medium">{user?.full_name}</p>
        <div className="mt-1.5">
          <RoleBadge role={user?.role} isSystemBuilder={user?.is_system_builder} />
        </div>
        <Button
          variant="ghost"
          className="mt-3 w-full justify-start gap-2 text-foreground/70"
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
  const [counts, setCounts] = useState({ verification: 0, diary: 0 });
  const [muted, setMuted] = useState(() => localStorage.getItem("ovc_mute_sounds") === "1");
  const [org, setOrg] = useState(null);

  useEffect(() => {
    api.get("/organisation/").then((r) => setOrg(r.data)).catch(() => {});
  }, []);

  const logoUrl = org?.logo
    ? (org.logo.startsWith("http") ? org.logo : `${process.env.REACT_APP_BACKEND_URL || ""}${org.logo}`)
    : "/emblem.jpg";

  useEffect(() => {
    api.get("/work-diary/").then((r) => {
      const c = r.data.counts || {};
      setCounts((prev) => ({ ...prev, diary: (c.overdue_visits || 0) + (c.overdue_referrals || 0) }));
    }).catch(() => {});
    if (user?.role === "admin" || user?.role === "supervisor") {
      api
        .get("/households/verification_count/")
        .then((r) => setCounts((prev) => ({ ...prev, verification: r.data.total })))
        .catch(() => {});
    }
  }, [user]);

  const onLogout = async () => {
    playChime("logout");
    await logout();
    navigate("/login");
  };

  const submitSearch = async (e) => {
    e.preventDefault();
    const term = q.trim();
    if (!term) return;
    try {
      const payload = await lookupHousehold(api, term);
      const hh = uniqueHousehold(payload);
      if (hh) {
        playChime("open");
        toast.success(`Opened file for ${payload.matched_label || hh.org_household_number}`, { silent: true });
        setQ("");
        navigate(`/households/${hh.id}`);
        return;
      }
    } catch {
      /* fall through */
    }
    navigate(`/?q=${encodeURIComponent(term)}`);
  };

  return (
    <div className="flex min-h-screen">
      <aside
        className="glass-tint hidden w-[272px] shrink-0 lg:block"
        data-testid="app-sidebar"
        style={{ background: "rgba(255,255,255,0.38)" }}
      >
        <div className="sticky top-0 h-screen">
          <SidebarContent user={user} counts={counts} onLogout={onLogout} logoUrl={logoUrl} orgName={org?.name} />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass sticky top-0 z-20 mx-3 mt-3 rounded-[1.5rem] sm:mx-4">
          <div className="flex items-center gap-3 px-3 py-2.5 sm:px-4">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="lg:hidden" data-testid="mobile-menu-button">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="glass w-[280px] border-white/40 p-0">
                <SidebarContent user={user} counts={counts} onLogout={onLogout} logoUrl={logoUrl} orgName={org?.name} onNavigate={() => setMobileOpen(false)} />
              </SheetContent>
            </Sheet>

            <form onSubmit={submitSearch} className="relative max-w-xl flex-1">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="ID number, surname, or office file number"
                className="h-11 pl-10"
                data-testid="global-search-input"
              />
            </form>

            <div className="ml-auto flex items-center gap-2">
              {logoUrl && <img src={logoUrl} alt="logo" className="hidden h-8 max-w-[120px] object-contain sm:block" data-testid="header-org-logo" />}
              <Button
                variant="ghost"
                size="icon"
                title={muted ? "Unmute office chimes" : "Mute office chimes"}
                data-testid="mute-chimes-button"
                onClick={() => {
                  const next = !muted;
                  setMuted(next);
                  localStorage.setItem("ovc_mute_sounds", next ? "1" : "0");
                }}
              >
                {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
              </Button>
              <Button
                onClick={() => navigate("/households/new")}
                className="gap-2"
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
