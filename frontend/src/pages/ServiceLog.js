import { useEffect, useMemo, useState } from "react";
import { CalendarCheck, CheckCircle2, HeartHandshake } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export default function ServiceLog() {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [serviceType, setServiceType] = useState("Home Visit");
  const [notes, setNotes] = useState("");
  const [types, setTypes] = useState([]);
  const [households, setHouseholds] = useState([]);
  const [selected, setSelected] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/choices/").then((r) => setTypes(r.data.service_types || [])).catch(() => {});
    setLoading(true);
    api.get("/households/", { params: { page_size: 500 } })
      .then((r) => setHouseholds(r.data.results || r.data))
      .finally(() => setLoading(false));
  }, []);

  const selectedIds = useMemo(
    () => Object.keys(selected).filter((k) => selected[k]).map(Number),
    [selected]
  );

  const toggle = (id) => setSelected((s) => ({ ...s, [id]: !s[id] }));

  const bulkLog = async (ids) => {
    if (!ids.length) return toast.error("Select at least one household");
    if (!serviceType) return toast.error("Select a service type");
    setSaving(true);
    try {
      const r = await api.post("/services/bulk_log/", {
        household_ids: ids, service_type: serviceType, service_date: date, notes,
      });
      toast.success(`${r.data.logged} household(s) logged as served`);
      setSelected({});
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not log services");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="service-log-page">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900">
          <HeartHandshake className="h-6 w-6" /> Daily Service Log
        </h1>
        <p className="text-sm text-slate-600">Record which households received a service today.</p>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Service details</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Date</label>
            <Input type="date" max={today} value={date} onChange={(e) => setDate(e.target.value)} data-testid="log-date-input" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Service type</label>
            <Select value={serviceType} onValueChange={setServiceType}>
              <SelectTrigger data-testid="log-type-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {types.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Notes (optional)</label>
            <Input value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="log-notes-input" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-base">Households ({households.length})</CardTitle>
          <div className="flex gap-2">
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="sm" className="gap-1" data-testid="mark-all-button">
                  <CheckCircle2 className="h-4 w-4" /> Mark all served today
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Mark all households as served?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This logs a "{serviceType}" service on {date} for all {households.length} household(s) shown.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={() => bulkLog(households.map((h) => h.id))} className="bg-slate-900 hover:bg-slate-800" data-testid="confirm-mark-all-button">Confirm</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            <Button size="sm" className="gap-1 bg-slate-900 hover:bg-slate-800" onClick={() => bulkLog(selectedIds)} disabled={saving} data-testid="log-selected-button">
              <CalendarCheck className="h-4 w-4" /> Log selected ({selectedIds.length})
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <p className="p-6 text-center text-sm text-slate-500" data-testid="loading-state">Loading...</p>
          ) : households.length === 0 ? (
            <p className="p-6 text-center text-sm text-slate-600" data-testid="empty-state">No households available.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {households.map((hh) => (
                <label key={hh.id} className="flex cursor-pointer items-center gap-3 px-4 py-3 hover:bg-slate-50" data-testid={`log-household-${hh.id}`}>
                  <Checkbox checked={!!selected[hh.id]} onCheckedChange={() => toggle(hh.id)} data-testid={`log-check-${hh.id}`} />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">{hh.org_household_number}</p>
                    <p className="text-xs text-slate-500">{hh.caregiver_name || "No caregiver"} · {hh.town || "—"}</p>
                  </div>
                </label>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
