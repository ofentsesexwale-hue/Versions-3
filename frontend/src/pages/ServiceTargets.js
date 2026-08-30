import { useEffect, useState } from "react";
import { Target, Save } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function ServiceTargets() {
  const { user } = useAuth();
  const [rows, setRows] = useState([]);
  const [savingId, setSavingId] = useState(null);

  useEffect(() => {
    api.get("/service-targets/").then((r) => setRows(r.data)).catch(() => {});
  }, []);

  const isSup = user?.role === "supervisor" || user?.role === "admin";
  if (user && !isSup) {
    return <div className="p-8 text-center text-slate-600" data-testid="targets-forbidden">Only supervisors and administrators can set service targets.</div>;
  }

  const setGoal = (uid, val) =>
    setRows((rs) => rs.map((r) => (r.user_id === uid ? { ...r, monthly_goal: val } : r)));

  const save = async (row) => {
    setSavingId(row.user_id);
    try {
      await api.put("/service-targets/", { user_id: row.user_id, monthly_goal: Number(row.monthly_goal) || 0 });
      toast.success(`Target saved for ${row.name}`);
    } catch (e) {
      toast.error("Could not save target");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="space-y-6" data-testid="service-targets-page">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900"><Target className="h-6 w-6" /> Monthly service targets</h1>
        <p className="text-sm text-slate-600">Set each case worker's monthly service-delivery goal. Progress against the goal shows on the dashboard ranking.</p>
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">Case workers ({rows.length})</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {rows.length === 0 && <p className="text-sm text-slate-500">No case workers found.</p>}
          {rows.map((row) => (
            <div key={row.user_id} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3" data-testid={`target-row-${row.user_id}`}>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-900">{row.name}</p>
                <p className="text-xs text-slate-500">{row.username}</p>
              </div>
              <Input
                type="number"
                min={0}
                value={row.monthly_goal}
                onChange={(e) => setGoal(row.user_id, e.target.value)}
                className="w-28"
                data-testid={`target-input-${row.user_id}`}
              />
              <span className="text-xs text-slate-500">/ month</span>
              <Button size="sm" className="gap-1 bg-slate-900 hover:bg-slate-800" onClick={() => save(row)} disabled={savingId === row.user_id} data-testid={`target-save-${row.user_id}`}>
                <Save className="h-3.5 w-3.5" /> Save
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
