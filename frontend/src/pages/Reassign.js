import { useEffect, useState } from "react";
import { ArrowRight, Loader2, Users } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

export default function Reassign() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [fromUser, setFromUser] = useState("");
  const [toUser, setToUser] = useState("");
  const [households, setHouseholds] = useState([]);
  const [selected, setSelected] = useState({});
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get("/users/").then((r) => setUsers(r.data)).catch(() => {});
  }, []);

  const loadCaseload = (uid) => {
    if (!uid) { setHouseholds([]); setSelected({}); return; }
    setLoading(true);
    api.get("/households/", { params: { assigned_to: uid, page_size: 200 } })
      .then((r) => {
        const rows = r.data.results || [];
        setHouseholds(rows);
        const sel = {};
        rows.forEach((h) => (sel[h.id] = true));
        setSelected(sel);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadCaseload(fromUser); }, [fromUser]);

  if (user && user.role !== "admin" && user.role !== "supervisor") {
    return (
      <div className="p-8 text-center text-slate-600" data-testid="reassign-forbidden">
        Only supervisors and administrators can reassign caseloads.
      </div>
    );
  }

  const workers = users.filter((u) => u.role === "case-worker");
  const selectedIds = households.filter((h) => selected[h.id]).map((h) => h.id);
  const allChecked = households.length > 0 && selectedIds.length === households.length;

  const toggleAll = () => {
    const val = !allChecked;
    const sel = {};
    households.forEach((h) => (sel[h.id] = val));
    setSelected(sel);
  };

  const submit = async () => {
    if (!toUser) { toast.error("Choose a case worker to move households to"); return; }
    if (selectedIds.length === 0) { toast.error("Select at least one household"); return; }
    if (String(toUser) === String(fromUser)) { toast.error("Source and target case workers are the same"); return; }
    setSubmitting(true);
    try {
      const res = await api.post("/households/bulk_reassign/", {
        from_user: fromUser || undefined,
        to_user: toUser,
        household_ids: selectedIds,
      });
      toast.success(`Reassigned ${res.data.reassigned} household(s) to ${res.data.to_user}`);
      loadCaseload(fromUser);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Reassignment failed");
    } finally {
      setSubmitting(false);
    }
  };

  const nameOf = (u) => `${u.full_name || u.username}`;

  return (
    <div className="space-y-6" data-testid="reassign-page">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900">
          <Users className="h-6 w-6" /> Reassign caseload
        </h1>
        <p className="text-sm text-slate-600">Move a batch of households from one case worker to another.</p>
      </div>

      <Card>
        <CardContent className="grid grid-cols-1 items-end gap-4 p-5 sm:grid-cols-[1fr_auto_1fr]">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">From case worker</label>
            <Select value={fromUser} onValueChange={setFromUser}>
              <SelectTrigger data-testid="reassign-from-select"><SelectValue placeholder="Select a case worker" /></SelectTrigger>
              <SelectContent>
                {workers.map((u) => (
                  <SelectItem key={u.id} value={String(u.id)}>{nameOf(u)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="hidden justify-center pb-2 sm:flex"><ArrowRight className="h-5 w-5 text-slate-400" /></div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">To case worker</label>
            <Select value={toUser} onValueChange={setToUser}>
              <SelectTrigger data-testid="reassign-to-select"><SelectValue placeholder="Select a case worker" /></SelectTrigger>
              <SelectContent>
                {workers.map((u) => (
                  <SelectItem key={u.id} value={String(u.id)}>{nameOf(u)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">
            {fromUser ? `Households to move (${selectedIds.length}/${households.length})` : "Select a source case worker"}
          </CardTitle>
          {households.length > 0 && (
            <Button variant="outline" size="sm" onClick={toggleAll} data-testid="reassign-select-all">
              {allChecked ? "Clear all" : "Select all"}
            </Button>
          )}
        </CardHeader>
        <CardContent className="p-0">
          {!fromUser ? (
            <div className="p-8 text-center text-slate-600" data-testid="reassign-empty">
              Choose a "from" case worker to list their assigned households.
            </div>
          ) : loading ? (
            <div className="space-y-3 p-4" data-testid="loading-state">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : households.length === 0 ? (
            <div className="p-8 text-center text-slate-600" data-testid="reassign-no-households">
              This case worker has no assigned households.
            </div>
          ) : (
            households.map((h) => (
              <label
                key={h.id}
                className="flex cursor-pointer items-center gap-3 border-b border-slate-100 px-4 py-3 last:border-0 hover:bg-slate-50"
                data-testid={`reassign-row-${h.id}`}
              >
                <Checkbox
                  checked={!!selected[h.id]}
                  onCheckedChange={(v) => setSelected((s) => ({ ...s, [h.id]: !!v }))}
                  data-testid={`reassign-checkbox-${h.id}`}
                />
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900">{h.org_household_number}</p>
                  <p className="truncate text-sm text-slate-600">{h.caregiver_name || "No caregiver"} · {h.town || "\u2014"}</p>
                </div>
                <span className="shrink-0 text-xs tabular-nums text-slate-500">{h.checklist_progress?.percent ?? 0}% file</span>
              </label>
            ))
          )}
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button
          onClick={submit}
          disabled={submitting || !toUser || selectedIds.length === 0}
          className="gap-2 bg-slate-900 hover:bg-slate-800"
          data-testid="reassign-submit-button"
        >
          {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
          Reassign {selectedIds.length > 0 ? `${selectedIds.length} ` : ""}household(s)
        </Button>
      </div>
    </div>
  );
}
