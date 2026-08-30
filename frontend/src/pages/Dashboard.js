import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, CalendarClock, Download, HeartPulse, Home, IdCard, PieChart, TrendingUp, UserSquare2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { HouseholdRow } from "@/components/HouseholdRow";

function KpiCard({ icon: Icon, label, value, testId, accent, onClick }) {
  return (
    <Card
      className={(accent ? "border-l-4 border-amber-400 " : "") + (onClick ? "cursor-pointer transition-colors hover:border-slate-400" : "")}
      data-testid={testId}
      onClick={onClick}
      role={onClick ? "button" : undefined}
    >
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
          <Icon className="h-6 w-6" />
        </div>
        <div>
          <p className="text-2xl font-semibold tabular-nums text-slate-900">{value}</p>
          <p className="text-sm text-slate-600">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

const barColor = (pct) => (pct >= 100 ? "bg-emerald-500" : pct >= 75 ? "bg-amber-500" : "bg-rose-500");

function TrendChart({ trend }) {
  const max = Math.max(1, ...trend.map((t) => t.count));
  return (
    <div className="border-t border-slate-100 pt-3" data-testid="service-trend-chart">
      <p className="mb-2 flex items-center gap-1 text-xs font-medium text-slate-600">
        <TrendingUp className="h-3.5 w-3.5" /> Services delivered — last 4 weeks
      </p>
      <div className="flex items-end justify-between gap-3" style={{ height: "72px" }}>
        {trend.map((t) => (
          <div key={t.label} className="flex flex-1 flex-col items-center justify-end gap-1" data-testid={`trend-week-${t.label}`}>
            <span className="text-xs font-medium tabular-nums text-slate-700">{t.count}</span>
            <div className="w-full rounded-t bg-[color:var(--sa-green,#007a4d)]" style={{ height: `${Math.max(4, (t.count / max) * 52)}px` }} />
            <span className="text-[10px] text-slate-400">{t.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ProgressBar({ label, served, total, percent, testId }) {
  return (
    <div data-testid={testId}>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-slate-700">{label}</span>
        <span className="tabular-nums font-medium text-slate-900">{served}/{total} ({percent}%)</span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full transition-all ${barColor(percent)}`} style={{ width: `${Math.min(percent, 100)}%` }} />
      </div>
    </div>
  );
}

const BANDS = [
  { key: "ready", label: "Ready for inspection (\u226590%)", color: "bg-emerald-500" },
  { key: "in_progress", label: "In progress (50\u201389%)", color: "bg-amber-500" },
  { key: "needs_attention", label: "Needs attention (<50%)", color: "bg-rose-500" },
];

function CompletenessChart({ bands, onSelect }) {
  const total = (bands.ready || 0) + (bands.in_progress || 0) + (bands.needs_attention || 0) || 1;
  return (
    <Card data-testid="completeness-chart">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base"><PieChart className="h-4 w-4" /> Case file completeness</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {BANDS.map((b) => {
          const count = bands[b.key] || 0;
          const pct = Math.round((count / total) * 100);
          return (
            <button key={b.key} onClick={() => onSelect(b.key)} className="block w-full text-left" data-testid={`completeness-band-${b.key}`}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="text-slate-700">{b.label}</span>
                <span className="tabular-nums font-medium text-slate-900">{count}</span>
              </div>
              <div className="h-4 w-full overflow-hidden rounded bg-slate-100">
                <div className={`h-full ${b.color} transition-all`} style={{ width: `${pct}%` }} />
              </div>
            </button>
          );
        })}
        <p className="text-xs text-slate-500">Click a band to view those households.</p>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";
  const band = params.get("band") || "";
  const [localQ, setLocalQ] = useState(q);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState("recent");
  const [byCompleteness, setByCompleteness] = useState([]);
  const [bandList, setBandList] = useState([]);
  const [stats, setStats] = useState(null);
  const [missed, setMissed] = useState([]);
  const [reminders, setReminders] = useState([]);

  const isSup = user?.role === "supervisor" || user?.role === "admin";

  const exportCsv = async () => {
    try {
      const res = await api.get("/services/export/", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `service_report_${stats?.month || "month"}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Service report exported");
    } catch (e) {
      toast.error("Could not export report");
    }
  };

  useEffect(() => {
    setLoading(true);
    api.get("/dashboard/", { params: q ? { q } : {} }).then((res) => setData(res.data)).finally(() => setLoading(false));
  }, [q]);

  useEffect(() => setLocalQ(q), [q]);

  useEffect(() => {
    api.get("/services/stats/").then((r) => setStats(r.data)).catch(() => {});
    api.get("/services/monthly_detail/").then((r) => setMissed(r.data.missed || [])).catch(() => {});
    api.get("/services/beneficiary_reminders/").then((r) => setReminders(r.data || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (q || sort !== "completeness") return;
    api.get("/households/", { params: { ordering: "completeness", page_size: 15 } })
      .then((r) => setByCompleteness(r.data.results || [])).catch(() => {});
  }, [q, sort]);

  useEffect(() => {
    if (!band) return;
    api.get("/households/", { params: { band, page_size: 100 } })
      .then((r) => setBandList(r.data.results || [])).catch(() => {});
  }, [band]);

  const submitSearch = (e) => {
    e.preventDefault();
    setParams(localQ ? { q: localQ } : {});
  };

  const unconfirmed = data?.unconfirmed_counts || {};
  const bandLabel = BANDS.find((b) => b.key === band)?.label;
  const list = band ? bandList : q ? data?.search_results || [] : sort === "completeness" ? byCompleteness : data?.recent || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Welcome, {user?.full_name?.split(" ")[0] || "there"}</h1>
        <p className="text-sm text-slate-600">Case management dashboard</p>
      </div>

      <form onSubmit={submitSearch} className="max-w-2xl">
        <Input value={localQ} onChange={(e) => setLocalQ(e.target.value)} placeholder="Search by surname, ID number, or household number" className="h-12 text-base" data-testid="dashboard-search-input" />
      </form>

      {!q && !band && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard icon={Home} label="Total households" value={data?.stats?.total_households ?? "\u2014"} testId="kpi-card-total" />
          {isSup && (
            <>
              <KpiCard icon={IdCard} label="With unconfirmed ID numbers" value={unconfirmed.id_number ?? 0} testId="kpi-card-unconfirmed-id" accent onClick={() => navigate("/verification?field=id_number")} />
              <KpiCard icon={UserSquare2} label="With unconfirmed surnames" value={unconfirmed.surname ?? 0} testId="kpi-card-unconfirmed-surname" accent onClick={() => navigate("/verification?field=surname")} />
              <KpiCard icon={CalendarClock} label="With unconfirmed dates of birth" value={unconfirmed.date_of_birth ?? 0} testId="kpi-card-unconfirmed-dob" accent onClick={() => navigate("/verification?field=date_of_birth")} />
            </>
          )}
        </div>
      )}

      {/* Services progress + completeness chart */}
      {!q && !band && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card data-testid="service-progress-card">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Monthly service delivery{stats?.month ? ` \u00b7 ${stats.month}` : ""}</CardTitle>
              {isSup && (
                <Button size="sm" variant="outline" className="gap-1" onClick={exportCsv} data-testid="export-service-csv-button">
                  <Download className="h-3.5 w-3.5" /> CSV
                </Button>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
              {stats?.staff && (
                <ProgressBar label="You have served" served={stats.staff.served} total={stats.staff.total} percent={stats.staff.percent} testId="staff-progress-bar" />
              )}
              {isSup && stats?.org && (
                <ProgressBar label="Organisation has served" served={stats.org.served} total={stats.org.total} percent={stats.org.percent} testId="org-progress-bar" />
              )}
              {stats?.staff?.by_type && Object.keys(stats.staff.by_type).length > 0 && (
                <p className="text-xs text-slate-500" data-testid="staff-by-type">
                  {Object.entries(stats.staff.by_type).map(([t, c]) => `${t}: ${c}`).join(" \u00b7 ")}
                </p>
              )}
              {isSup && stats?.ranking?.length > 0 && (
                <div className="space-y-2 border-t border-slate-100 pt-3" data-testid="staff-ranking">
                  <p className="text-xs font-medium text-slate-600">Staff performance</p>
                  {stats.ranking.map((r, i) => (
                    <div key={r.user_id} className="flex items-center gap-2" data-testid={`ranking-row-${r.user_id}`}>
                      <span className="w-4 text-xs text-slate-400">{i + 1}.</span>
                      <span className="w-36 truncate text-sm text-slate-700">{r.name}</span>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                        <div className={`h-full ${barColor(r.percent)}`} style={{ width: `${Math.min(r.percent, 100)}%` }} />
                      </div>
                      <span className="w-16 text-right text-xs tabular-nums text-slate-600">{r.served}/{r.total}</span>
                    </div>
                  ))}
                </div>
              )}
              {stats?.trend?.length > 0 && <TrendChart trend={stats.trend} />}
            </CardContent>
          </Card>

          {isSup && data?.completeness_bands && (
            <CompletenessChart bands={data.completeness_bands} onSelect={(b) => setParams({ band: b })} />
          )}
        </div>
      )}

      {/* Beneficiary reminders: individual children overdue for HIV testing / counselling */}
      {!q && !band && isSup && reminders.length > 0 && (
        <Card data-testid="beneficiary-reminders-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-rose-700">
              <HeartPulse className="h-4 w-4" /> Children overdue for HIV testing / counselling ({reminders.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {reminders.slice(0, 8).map((r, i) => (
              <button key={`${r.member_id}-${r.service_type}`} onClick={() => navigate(`/households/${r.household_id}`)} className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-left hover:border-slate-400" data-testid={`reminder-row-${i}`}>
                <span className="flex items-center gap-2 text-sm text-slate-800">
                  {r.name} · {r.org_household_number}
                  {r.dob_missing && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800" data-testid={`reminder-dob-missing-${i}`}>DOB missing</span>}
                </span>
                <span className="text-xs text-slate-500">{r.service_type} — {r.last_service_date ? `last ${r.last_service_date}` : "never"}</span>
              </button>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Missed households (supervisor/admin) */}
      {!q && !band && isSup && missed.length > 0 && (
        <Card data-testid="missed-households-card">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-base text-rose-700">
              <AlertTriangle className="h-4 w-4" /> Not served in 30+ days ({missed.length})
            </CardTitle>
            <Button size="sm" variant="outline" onClick={() => navigate("/services")} data-testid="log-service-today-button">Log service today</Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {missed.slice(0, 8).map((m) => (
              <button key={m.id} onClick={() => navigate(`/households/${m.id}`)} className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-left hover:border-slate-400" data-testid={`missed-row-${m.id}`}>
                <span className="text-sm text-slate-800">{m.org_household_number} · {m.caregiver_name || "—"}</span>
                <span className="text-xs text-slate-500">Last: {m.last_service_date || "Never"}</span>
              </button>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle className="text-base">
            {band ? bandLabel : q ? `Search results for "${q}"` : sort === "completeness" ? "Least-ready case files" : "Recent households"}
          </CardTitle>
          {band ? (
            <Button size="sm" variant="ghost" onClick={() => setParams({})} data-testid="clear-band-filter">Clear filter</Button>
          ) : !q ? (
            <div className="flex gap-1 rounded-lg border border-slate-200 p-0.5" data-testid="dashboard-sort-toggle">
              <Button size="sm" variant="ghost" className={sort === "recent" ? "h-8 bg-slate-900 text-white hover:bg-slate-800 hover:text-white" : "h-8"} onClick={() => setSort("recent")} data-testid="sort-recent">Recent</Button>
              <Button size="sm" variant="ghost" className={sort === "completeness" ? "h-8 bg-slate-900 text-white hover:bg-slate-800 hover:text-white" : "h-8"} onClick={() => setSort("completeness")} data-testid="sort-completeness">Least complete</Button>
            </div>
          ) : null}
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-3 p-4" data-testid="loading-state">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
            </div>
          ) : list.length === 0 ? (
            <div className="p-8 text-center text-slate-600" data-testid="empty-state">
              {band ? "No households in this band." : q ? "No households found - try a different surname or ID number." : "No households yet."}
            </div>
          ) : (
            <div>
              {list.map((hh) => <HouseholdRow key={hh.id} hh={hh} onClick={() => navigate(`/households/${hh.id}`)} />)}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
