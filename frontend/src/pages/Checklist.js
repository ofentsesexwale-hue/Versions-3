import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, BadgeCheck, Lock, Printer, PenLine } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { printForm } from "@/lib/print";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CATEGORY_LABELS, CATEGORY_ORDER, formatDateTime } from "@/lib/constants";

export default function Checklist() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const canEdit = user?.permissions?.can_edit_checklist_evidence;
  const [signOpen, setSignOpen] = useState(false);
  const [sacssp, setSacssp] = useState("");
  const [items, setItems] = useState([]);
  const [household, setHousehold] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    Promise.all([
      api.get("/checklist/", { params: { household: id, page_size: 200 } }),
      api.get(`/households/${id}/`),
    ]).then(([c, h]) => {
      setItems(c.data.results || c.data);
      setHousehold(h.data);
      setLoading(false);
    });
  };
  useEffect(() => { load(); }, [id]);

  const signOff = async () => {
    try {
      const res = await api.post(`/households/${id}/sign_checklist/`, { sacssp });
      setHousehold(res.data);
      toast.success("Checklist signed off");
      setSignOpen(false);
    } catch (e) {
      toast.error("Only supervisors can sign off the checklist");
    }
  };

  const patchItem = async (item, changes) => {
    try {
      const res = await api.patch(`/checklist/${item.id}/`, changes);
      setItems((its) => its.map((x) => (x.id === item.id ? res.data : x)));
      toast.success("Checklist updated");
    } catch (e) {
      toast.error("Only supervisors can sign off checklist items");
    }
  };

  if (loading) return <div data-testid="loading-state">Loading...</div>;

  const grouped = CATEGORY_ORDER.map((cat) => ({
    cat,
    items: items.filter((i) => i.category === cat),
  })).filter((g) => g.items.length > 0);

  const total = items.length;
  const yes = items.filter((i) => i.has_evidence === "Yes").length;
  const percent = total ? Math.round((yes * 100) / total) : 0;

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate(`/households/${id}`)} className="gap-2" data-testid="back-button">
        <ArrowLeft className="h-4 w-4" /> Back to household
      </Button>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Case file checklist</h1>
          <p className="text-sm text-slate-600">{household?.org_household_number}</p>
          {!canEdit && (
            <p className="mt-2 inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">
              <Lock className="h-3 w-3" /> View only - supervisors sign off items
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {canEdit && (
            <Dialog open={signOpen} onOpenChange={setSignOpen}>
              <DialogTrigger asChild>
                <Button className="gap-2 bg-slate-900 hover:bg-slate-800" data-testid="signoff-checklist-button">
                  <PenLine className="h-4 w-4" /> Sign off checklist
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>Sign off case-file checklist</DialogTitle></DialogHeader>
                <p className="text-sm text-slate-600">Your name and today's date will be stamped on the printed DSD checklist.</p>
                <div>
                  <label className="text-xs font-medium text-slate-600">SACSSP Number (optional)</label>
                  <Input value={sacssp} onChange={(e) => setSacssp(e.target.value)} placeholder="e.g. 10-12345" data-testid="signoff-sacssp-input" />
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setSignOpen(false)}>Cancel</Button>
                  <Button className="bg-slate-900 hover:bg-slate-800" onClick={signOff} data-testid="signoff-confirm-button">Sign off</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
          <Button
            variant="outline"
            className="gap-2"
            onClick={() => printForm("checklist", { householdId: id })}
            data-testid="print-checklist-button"
          >
            <Printer className="h-4 w-4" /> Print DSD Checklist
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-5">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-medium text-slate-800">Case file completeness</span>
            <span className="tabular-nums text-slate-600" data-testid="checklist-progress-label">{yes} of {total} items evidenced ({percent}%)</span>
          </div>
          <Progress value={percent} className="h-3" data-testid="checklist-progress" />
        </CardContent>
      </Card>

      {grouped.map((g) => (
        <Card key={g.cat}>
          <CardHeader><CardTitle className="text-base">{CATEGORY_LABELS[g.cat]}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {g.items.map((item) => (
              <div key={item.id} className="grid grid-cols-1 gap-3 border-b border-slate-100 pb-3 last:border-0 sm:grid-cols-12 sm:items-center" data-testid={`checklist-row-${item.id}`}>
                <div className="sm:col-span-4">
                  <p className="text-sm font-medium text-slate-900">{item.sub_item}</p>
                  {item.checked_by && (
                    <p className="mt-0.5 inline-flex items-center gap-1 text-xs text-emerald-700">
                      <BadgeCheck className="h-3 w-3" /> {item.checked_by} · {formatDateTime(item.checked_at)}
                    </p>
                  )}
                </div>
                <div className="sm:col-span-3">
                  <Select
                    value={item.has_evidence === "" ? "blank" : item.has_evidence}
                    onValueChange={(v) => patchItem(item, { has_evidence: v === "blank" ? "" : v })}
                    disabled={!canEdit}
                  >
                    <SelectTrigger className="h-10" data-testid={`checklist-evidence-${item.id}`}><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Yes">Yes</SelectItem>
                      <SelectItem value="No">No</SelectItem>
                      <SelectItem value="blank">Unknown</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="sm:col-span-5">
                  <Input
                    defaultValue={item.comments}
                    placeholder="Comments"
                    disabled={!canEdit}
                    onBlur={(e) => { if (e.target.value !== item.comments) patchItem(item, { comments: e.target.value }); }}
                    className="h-10"
                    data-testid={`checklist-comments-${item.id}`}
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
