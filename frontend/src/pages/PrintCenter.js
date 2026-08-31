import { useEffect, useMemo, useState } from "react";
import { Printer } from "lucide-react";
import { toast } from "sonner";
import { isFieldWorker } from "@/lib/constants";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { DSD_FORMS, printForm } from "@/lib/print";

export default function PrintCenter() {
  const { user } = useAuth();
  const [households, setHouseholds] = useState([]);
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState("checklist");
  const [scope, setScope] = useState("all");
  const [worker, setWorker] = useState("");
  const [district, setDistrict] = useState("");

  useEffect(() => {
    api.get("/households/", { params: { page_size: 500 } }).then((r) => setHouseholds(r.data.results || [])).catch(() => {});
    api.get("/users/").then((r) => setUsers(r.data)).catch(() => {});
  }, []);

  const districts = useMemo(
    () => [...new Set(households.map((h) => h.district).filter(Boolean))].sort(),
    [households]
  );
  const workers = users.filter((u) => isFieldWorker(u.role));

  const matchedIds = useMemo(() => {
    if (scope === "all") return households.map((h) => h.id);
    if (scope === "worker") return households.filter((h) => (h.assigned_to_ids || []).includes(Number(worker))).map((h) => h.id);
    if (scope === "district") return households.filter((h) => h.district === district).map((h) => h.id);
    return [];
  }, [scope, worker, district, households]);

  if (user && user.role !== "admin" && user.role !== "supervisor") {
    return <div className="p-8 text-center text-slate-600" data-testid="printcenter-forbidden">Only supervisors and administrators can use the Print Center.</div>;
  }

  const run = () => {
    if (matchedIds.length === 0) { toast.error("No households match this scope"); return; }
    if (matchedIds.length > 60) { toast.error("Too many households (max 60). Narrow the scope."); return; }
    printForm(form, { householdIds: matchedIds });
  };

  return (
    <div className="space-y-6" data-testid="print-center-page">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900"><Printer className="h-6 w-6" /> Print Center</h1>
        <p className="text-sm text-slate-600">Batch-print an official DSD form across a case worker's caseload or a district.</p>
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">Batch print</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Form</label>
            <Select value={form} onValueChange={setForm}>
              <SelectTrigger data-testid="printcenter-form-select"><SelectValue /></SelectTrigger>
              <SelectContent className="max-h-72">
                {DSD_FORMS.map((f) => <SelectItem key={f.key} value={f.key}>{f.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Scope</label>
            <Select value={scope} onValueChange={setScope}>
              <SelectTrigger data-testid="printcenter-scope-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All households</SelectItem>
                <SelectItem value="worker">By case worker</SelectItem>
                <SelectItem value="district">By district</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {scope === "worker" && (
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Case worker</label>
              <Select value={worker} onValueChange={setWorker}>
                <SelectTrigger data-testid="printcenter-worker-select"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>{workers.map((u) => <SelectItem key={u.id} value={String(u.id)}>{u.full_name || u.username}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          )}
          {scope === "district" && (
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">District</label>
              <Select value={district} onValueChange={setDistrict}>
                <SelectTrigger data-testid="printcenter-district-select"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent className="max-h-72">{districts.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          )}
          <div className="flex items-center justify-between border-t border-slate-100 pt-4">
            <p className="text-sm text-slate-600" data-testid="printcenter-count">{matchedIds.length} household(s) selected</p>
            <Button onClick={run} className="gap-2 bg-slate-900 hover:bg-slate-800" data-testid="printcenter-run-button">
              <Printer className="h-4 w-4" /> Print
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
