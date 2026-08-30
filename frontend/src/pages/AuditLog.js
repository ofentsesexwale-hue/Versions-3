import { useEffect, useState } from "react";
import { Download, Shield } from "lucide-react";
import { toast } from "sonner";
import api, { API, TOKEN_KEY } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DateField } from "@/components/DateField";
import { formatDateTime } from "@/lib/constants";

const ACTIONS = ["viewed", "created", "edited", "deleted", "downloaded", "printed", "confirmed", "suggested"];

export default function AuditLog() {
  const [users, setUsers] = useState([]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ user: "", action: "", date_from: "", date_to: "" });

  useEffect(() => {
    api.get("/users/").then((r) => setUsers(r.data));
  }, []);

  const buildParams = () => {
    const p = { page };
    if (filters.user) p.user = filters.user;
    if (filters.action) p.action = filters.action;
    if (filters.date_from) p.date_from = filters.date_from;
    if (filters.date_to) p.date_to = filters.date_to;
    return p;
  };

  useEffect(() => {
    setLoading(true);
    api.get("/audit/", { params: buildParams() }).then((r) => setData(r.data)).finally(() => setLoading(false));
  }, [page, filters]);

  const setF = (k, v) => { setPage(1); setFilters((f) => ({ ...f, [k]: v })); };

  const exportCsv = async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    const qs = new URLSearchParams();
    Object.entries(buildParams()).forEach(([k, v]) => { if (v && k !== "page") qs.append(k, v); });
    const res = await fetch(`${API}/audit/export/?${qs.toString()}`, { headers: { Authorization: `Token ${token}` } });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "audit_log.csv"; a.click();
    URL.revokeObjectURL(url);
    toast.success("Audit log exported");
  };

  const rows = data?.results || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900"><Shield className="h-6 w-6" /> Audit log</h1>
          <p className="text-sm text-slate-600">POPIA compliance - every view, edit, download and print is recorded.</p>
        </div>
        <Button variant="outline" className="gap-2" onClick={exportCsv} data-testid="audit-export-button">
          <Download className="h-4 w-4" /> Export CSV
        </Button>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Filters</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <div>
            <p className="mb-1 text-sm text-slate-700">User</p>
            <Select value={filters.user || "all"} onValueChange={(v) => setF("user", v === "all" ? "" : v)}>
              <SelectTrigger className="h-10" data-testid="audit-filter-user"><SelectValue placeholder="All users" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All users</SelectItem>
                {users.map((u) => <SelectItem key={u.id} value={String(u.id)}>{u.full_name} ({u.username})</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <p className="mb-1 text-sm text-slate-700">Action</p>
            <Select value={filters.action || "all"} onValueChange={(v) => setF("action", v === "all" ? "" : v)}>
              <SelectTrigger className="h-10" data-testid="audit-filter-action"><SelectValue placeholder="All actions" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All actions</SelectItem>
                {ACTIONS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <p className="mb-1 text-sm text-slate-700">From date</p>
            <DateField value={filters.date_from} onChange={(v) => setF("date_from", v)} testId="audit-filter-from" placeholder="Any" />
          </div>
          <div>
            <p className="mb-1 text-sm text-slate-700">To date</p>
            <DateField value={filters.date_to} onChange={(v) => setF("date_to", v)} testId="audit-filter-to" placeholder="Any" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4" data-testid="loading-state">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
          ) : rows.length === 0 ? (
            <div className="p-8 text-center text-slate-600" data-testid="empty-state">No audit entries match these filters.</div>
          ) : (
            <Table data-testid="audit-log-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Target</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="tabular-nums text-sm text-slate-600">{formatDateTime(r.timestamp)}</TableCell>
                    <TableCell className="text-sm">{r.user}</TableCell>
                    <TableCell><Badge variant="secondary">{r.action}</Badge></TableCell>
                    <TableCell className="text-sm text-slate-700">{r.target_description}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">{data?.count || 0} entries</p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={!data?.previous} onClick={() => setPage((p) => Math.max(1, p - 1))} data-testid="audit-prev-page">Previous</Button>
          <Button variant="outline" size="sm" disabled={!data?.next} onClick={() => setPage((p) => p + 1)} data-testid="audit-next-page">Next</Button>
        </div>
      </div>
    </div>
  );
}
