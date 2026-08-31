import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, CalendarClock, Download, HeartPulse, Home, IdCard, PieChart, TrendingUp, UserSquare2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { digitsOnly, lookupHousehold, uniqueHousehold } from "@/lib/lookup";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { HouseholdRow } from "@/components/HouseholdRow";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";

const CSV_COLUMNS = [
  ["date", "Date"],
  ["household", "Household Number"],
  ["beneficiary", "Beneficiary"],
  ["service_type", "Service Type"],
  ["delivered_by", "Delivered By"],
  ["notes", "Notes"],
];

function KpiCard({ icon: Icon, label, value, testId, accent, onClick }) {
  return (
    <Card
      className={(accent ? "ring-1 ring-amber-400/50 " : "") + (onClick ? "cursor-pointer hover:bg-white/70" : "")}
      data-testid={testId}
      onClick={onClick}
      role={onClick ? "button" : undefined}
    >
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/50 text-foreground">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-[28px] font-semibold leading-none tracking-tight tabular-nums">{value}</p>
          <p className="mt-1 text-sm text-muted-foreground">{label}</p>
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
            <div className="w-full rounded-full bg-foreground/80" style={{ height: `${Math.max(4, (t.count / max) * 52)}px` }} />
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
  const [dobMissing, setDobMissing] = useState([]);
  const [csvCols, setCsvCols] = useState(CSV_COLUMNS.map((c) => c[0]));
  const [csvOpen, setCsvOpen] = useState(false);

  const isSup = user?.role === "supervisor" || user?.role === "admin";

  const exportCsv = async (columns) => {
    try {
      const params = columns && columns.length ? { columns: columns.join(",") } : {};
      const res = await api.get("/services/export/", { responseType: "blob", params });
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
    api.get("/members/missing_dob/").then((r) => setDobMissing(r.data || [])).catch(() => {});
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

  const openUnique = (payload) => {
    const hh = uniqueHousehold(payload);
    if (!hh) return false;
    toast.success(`Opened file for ${payload.matched_label || hh.org_household_number}`);
    navigate(`/households/${hh.id}`);
    return true;
  };

  useEffect(() => {
    if (!q) return;
    let cancelled = false;
    lookupHousehold(api, q)
      .then((payload) => {
        if (!cancelled) openUnique(payload);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const submitSearch = async (e) => {
    e.preventDefault();
    const term = localQ.trim();
    if (!term) {
      setParams({});
      return;
    }
    try {
      const payload = await lookupHousehold(api, term);
      if (openUnique(payload)) return;
    } catch {
      /* fall through to list search */
    }
    setParams({ q: term });
  };

  const unconfirmed = data?.unconfirmed_counts || {};
  const bandLabel = BANDS.find((b) => b.key === band)?.label;
  const list = band ? bandList : q ? data?.search_results || [] : sort === "completeness" ? byCompleteness : data?.recent || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          {user?.is_training ? "Training classroom" : `Welcome, ${user?.full_name?.split(" ")[0] || "there"}`}
        </h1>
        <p className="text-sm text-muted-foreground">
          {user?.is_training
            ? "These TEST households are fictional and used for staff practice."
            : "Live case files for your organisation. Training dummy files are not shown here."}
        </p>
      </div>

      <form onSubmit={submitSearch} className="max-w-2xl">
        <Input value={localQ} onChange={(e) => setLocalQ(e.target.value)} placeholder="Type an ID number to open the household — or search a surname" className="h-12 text-base" data-testid="dashboard-search-input" />
        <p className="mt-2 text-xs text-muted-foreground">Spaces and dashes in ID numbers are ignored. A unique match opens the file immediately.</p>
      </form>

      {!q && !band && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard icon={Home} label="Total households" value={data?.stats?.total_households ?? "\u2014"} testId="kpi-card-total" />
          <KpiCard icon={Home} label="Open cases" value={data?.stats?.open_households ?? "\u2014"} testId="kpi-card-open" onClick={() => navigate("/my-households")} />
          <KpiCard icon={UserSquare2} label="People on file" value={data?.stats?.total_people ?? "\u2014"} testId="kpi-card-people" />
          <KpiCard icon={CalendarClock} label="Overdue visits" value={data?.stats?.overdue_visits ?? 0} testId="kpi-card-overdue-visits" accent onClick={() => navigate("/work-diary")} />
          <KpiCard icon={HeartPulse} label="Open referrals" value={data?.stats?.open_referrals ?? 0} testId="kpi-card-open-referrals" accent onClick={() => navigate("/work-diary")} />
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
                <Dialog open={csvOpen} onOpenChange={setCsvOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm" variant="outline" className="gap-1" data-testid="export-service-csv-button">
                      <Download className="h-3.5 w-3.5" /> CSV
                    </Button>
                  </DialogTrigger>
                  <DialogContent data-testid="csv-column-picker">
                    <DialogHeader><DialogTitle>Export service report (CSV)</DialogTitle></DialogHeader>
                    <p className="text-sm text-slate-600">Choose the columns to include for donor reporting:</p>
                    <div className="space-y-2 py-2">
                      {CSV_COLUMNS.map(([key, label]) => (
                        <label key={key} className="flex items-center gap-2" data-testid={`csv-col-${key}`}>
                          <Checkbox checked={csvCols.includes(key)} onCheckedChange={(v) => setCsvCols((c) => (v ? [...c, key] : c.filter((x) => x !== key)))} />
                          <span className="text-sm text-slate-800">{label}</span>
                        </label>
                      ))}
                    </div>
                    <DialogFooter>
                      <Button onClick={() => { exportCsv(csvCols); setCsvOpen(false); }} disabled={!csvCols.length} className="bg-slate-900 hover:bg-slate-800" data-testid="csv-download-button">
                        Download CSV
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
              {stats?.staff && (
                <ProgressBar label="You have served" served={stats.staff.served} total={stats.staff.total} percent={stats.staff.percent} testId="staff-progress-bar" />
              )}
              {stats?.staff?.goal > 0 && (
                <ProgressBar label="Your monthly goal" served={stats.staff.delivered} total={stats.staff.goal} percent={stats.staff.goal_percent} testId="staff-goal-bar" />
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
                    <div key={r.user_id} className="space-y-1" data-testid={`ranking-row-${r.user_id}`}>
                      <div className="flex items-center gap-2">
                        <span className="w-4 text-xs text-slate-400">{i + 1}.</span>
                        <span className="w-36 truncate text-sm text-slate-700">{r.name}</span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                          <div className={`h-full ${barColor(r.percent)}`} style={{ width: `${Math.min(r.percent, 100)}%` }} />
                        </div>
                        <span className="w-16 text-right text-xs tabular-nums text-slate-600">{r.served}/{r.total}</span>
                      </div>
                      {r.goal > 0 && (
                        <div className="flex items-center gap-2" data-testid={`ranking-goal-${r.user_id}`}>
                          <span className="w-4" />
                          <span className="w-36 text-[10px] text-slate-400">Goal {r.delivered}/{r.goal}</span>
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                            <div className={`h-full ${barColor(r.goal_percent)}`} style={{ width: `${Math.min(r.goal_percent, 100)}%` }} />
                          </div>
                          <span className="w-16 text-right text-[10px] tabular-nums text-slate-500">{r.goal_percent}%</span>
                        </div>
                      )}
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

      {/* Children missing date of birth — nudge staff to capture DOB */}
      {!q && !band && dobMissing.length > 0 && (
        <Card data-testid="dob-missing-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-amber-700">
              <CalendarClock className="h-4 w-4" /> Children missing date of birth ({dobMissing.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-xs text-slate-500">Capture each child's date of birth so beneficiary reminders stay accurate.</p>
            {dobMissing.slice(0, 8).map((m) => (
              <button key={m.id} onClick={() => navigate(`/members/${m.id}/edit`)} className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-left hover:border-slate-400" data-testid={`dob-missing-row-${m.id}`}>
                <span className="text-sm text-slate-800">{m.name} · {m.org_household_number}</span>
                <span className="text-xs font-medium text-amber-700">Add DOB</span>
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
            <div className="p-10 text-center" data-testid="empty-state">
              {band ? (
                <p className="text-muted-foreground">No households in this band.</p>
              ) : q ? (
                <p className="text-muted-foreground">
                  {digitsOnly(q).length >= 6
                    ? "No household file for this ID number. Check the digits, or register a new household."
                    : "No households found — try a different surname or ID number."}
                </p>
              ) : user?.is_training ? (
                <p className="text-muted-foreground">No training households yet. Run seed_data on the server.</p>
              ) : (
                <div className="mx-auto max-w-md space-y-3">
                  <p className="text-lg font-semibold tracking-tight">No live households yet</p>
                  <p className="text-sm text-muted-foreground">
                    Dummy TEST files stay in the training classroom. Register a real household to start the office caseload.
                  </p>
                  <Button onClick={() => navigate("/households/new")} data-testid="empty-new-household-button">
                    Register first household
                  </Button>
                </div>
              )}
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
