import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CalendarClock, Home, IdCard, UserSquare2 } from "lucide-react";
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

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";
  const [localQ, setLocalQ] = useState(q);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState("recent");
  const [byCompleteness, setByCompleteness] = useState([]);

  useEffect(() => {
    setLoading(true);
    api
      .get("/dashboard/", { params: q ? { q } : {} })
      .then((res) => setData(res.data))
      .finally(() => setLoading(false));
  }, [q]);

  useEffect(() => setLocalQ(q), [q]);

  useEffect(() => {
    if (q || sort !== "completeness") return;
    api
      .get("/households/", { params: { ordering: "completeness", page_size: 15 } })
      .then((r) => setByCompleteness(r.data.results || []))
      .catch(() => {});
  }, [q, sort]);

  const submitSearch = (e) => {
    e.preventDefault();
    setParams(localQ ? { q: localQ } : {});
  };

  const isSup = user?.role === "supervisor" || user?.role === "admin";
  const unconfirmed = data?.unconfirmed_counts || {};
  const list = q
    ? data?.search_results || []
    : sort === "completeness"
    ? byCompleteness
    : data?.recent || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          Welcome, {user?.full_name?.split(" ")[0] || "there"}
        </h1>
        <p className="text-sm text-slate-600">Case management dashboard</p>
      </div>

      <form onSubmit={submitSearch} className="max-w-2xl">
        <Input
          value={localQ}
          onChange={(e) => setLocalQ(e.target.value)}
          placeholder="Search by surname, ID number, or household number"
          className="h-12 text-base"
          data-testid="dashboard-search-input"
        />
      </form>

      {!q && (
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

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle className="text-base">
            {q ? `Search results for "${q}"` : sort === "completeness" ? "Least-ready case files" : "Recent households"}
          </CardTitle>
          {!q && (
            <div className="flex gap-1 rounded-lg border border-slate-200 p-0.5" data-testid="dashboard-sort-toggle">
              <Button size="sm" variant="ghost" className={sort === "recent" ? "h-8 bg-slate-900 text-white hover:bg-slate-800 hover:text-white" : "h-8"} onClick={() => setSort("recent")} data-testid="sort-recent">Recent</Button>
              <Button size="sm" variant="ghost" className={sort === "completeness" ? "h-8 bg-slate-900 text-white hover:bg-slate-800 hover:text-white" : "h-8"} onClick={() => setSort("completeness")} data-testid="sort-completeness">Least complete</Button>
            </div>
          )}
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-3 p-4" data-testid="loading-state">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : list.length === 0 ? (
            <div className="p-8 text-center text-slate-600" data-testid="empty-state">
              {q ? "No households found - try a different surname or ID number." : "No households yet."}
            </div>
          ) : (
            <div>
              {list.map((hh) => (
                <HouseholdRow key={hh.id} hh={hh} onClick={() => navigate(`/households/${hh.id}`)} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
