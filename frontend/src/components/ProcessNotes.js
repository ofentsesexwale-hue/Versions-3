import { useEffect, useState } from "react";
import { NotebookPen, Plus, Printer, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { formatDate } from "@/lib/constants";
import { printForm } from "@/lib/print";

const ENGAGEMENTS = ["Office", "Home", "School", "Court", "Telephone", "Other"];
const EMPTY = {
  person_engaged_name: "", person_engaged_contact: "", problem_code: "",
  intervention_code: "", type_of_engagement: "Home",
  purpose_and_what_transpired: "", outcome_and_follow_up: "",
  evaluation_reflection: "", date_of_next_follow_up: "",
};

// CW 11 structured process notes for a household: list, add and print.
export function ProcessNotes({ householdId }) {
  const [notes, setNotes] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [codes, setCodes] = useState({ problem_codes: [], intervention_codes: [] });

  const load = () => {
    api.get("/process-notes/", { params: { household: householdId, page_size: 100 } })
      .then((r) => setNotes(r.data.results || r.data))
      .catch(() => {});
  };
  useEffect(() => { load(); }, [householdId]);

  useEffect(() => {
    api.get("/choices/")
      .then((r) => setCodes({ problem_codes: r.data.problem_codes || [], intervention_codes: r.data.intervention_codes || [] }))
      .catch(() => {});
  }, []);

  const save = async () => {
    if (!form.purpose_and_what_transpired.trim()) {
      toast.error("Please describe what transpired");
      return;
    }
    setSaving(true);
    try {
      const payload = { ...form, household: householdId };
      if (!payload.date_of_next_follow_up) delete payload.date_of_next_follow_up;
      await api.post("/process-notes/", payload);
      toast.success("Process note added");
      setForm(EMPTY);
      setOpen(false);
      load();
    } catch (e) {
      toast.error("Could not save process note");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (noteId) => {
    await api.delete(`/process-notes/${noteId}/`);
    toast.success("Process note removed");
    load();
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <Card data-testid="process-notes-card">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2 text-base">
          <NotebookPen className="h-4 w-4" /> Process notes (CW 11) ({notes.length})
        </CardTitle>
        <div className="flex gap-2">
          {notes.length > 0 && (
            <Button variant="outline" size="sm" className="gap-1.5"
              onClick={() => printForm("process_note", { householdId })}
              data-testid="print-process-notes-button">
              <Printer className="h-3.5 w-3.5" /> Print all
            </Button>
          )}
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm" className="gap-1.5 bg-slate-900 hover:bg-slate-800" data-testid="add-process-note-button">
                <Plus className="h-3.5 w-3.5" /> Add note
              </Button>
            </DialogTrigger>
            <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
              <DialogHeader><DialogTitle>New CW 11 Process Note</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <label className="text-xs font-medium text-slate-600">Person(s) engaged</label>
                    <Input value={form.person_engaged_name} onChange={set("person_engaged_name")} data-testid="pn-person-name" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">Contact details</label>
                    <Input value={form.person_engaged_contact} onChange={set("person_engaged_contact")} data-testid="pn-person-contact" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">Problem code (CW 06)</label>
                    <Select value={form.problem_code} onValueChange={(v) => setForm((f) => ({ ...f, problem_code: v }))}>
                      <SelectTrigger data-testid="pn-problem-code"><SelectValue placeholder="Select code" /></SelectTrigger>
                      <SelectContent className="max-h-72">
                        {codes.problem_codes.map((c) => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">Intervention code (CW 10)</label>
                    <Select value={form.intervention_code} onValueChange={(v) => setForm((f) => ({ ...f, intervention_code: v }))}>
                      <SelectTrigger data-testid="pn-intervention-code"><SelectValue placeholder="Select code" /></SelectTrigger>
                      <SelectContent className="max-h-72">
                        {codes.intervention_codes.map((c) => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">Type of engagement</label>
                    <Select value={form.type_of_engagement} onValueChange={(v) => setForm((f) => ({ ...f, type_of_engagement: v }))}>
                      <SelectTrigger data-testid="pn-engagement-type"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {ENGAGEMENTS.map((e) => <SelectItem key={e} value={e}>{e}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">Date of next follow-up</label>
                    <Input type="date" value={form.date_of_next_follow_up} onChange={set("date_of_next_follow_up")} data-testid="pn-next-followup" />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600">Purpose of engagement and what transpired</label>
                  <Textarea rows={3} value={form.purpose_and_what_transpired} onChange={set("purpose_and_what_transpired")} data-testid="pn-purpose" />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600">Outcome and follow-up</label>
                  <Textarea rows={2} value={form.outcome_and_follow_up} onChange={set("outcome_and_follow_up")} data-testid="pn-outcome" />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600">Evaluation / reflection</label>
                  <Textarea rows={2} value={form.evaluation_reflection} onChange={set("evaluation_reflection")} data-testid="pn-evaluation" />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                <Button onClick={save} disabled={saving} className="bg-slate-900 hover:bg-slate-800" data-testid="pn-save-button">
                  {saving ? "Saving..." : "Save note"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {notes.length === 0 ? (
          <p className="py-4 text-center text-sm text-slate-600" data-testid="process-notes-empty">
            No process notes yet. Add a CW 11 note to record an engagement.
          </p>
        ) : (
          notes.map((n) => (
            <div key={n.id} className="rounded-lg border border-slate-200 p-3" data-testid={`process-note-${n.id}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{n.type_of_engagement_display || n.type_of_engagement}</Badge>
                    <span className="text-xs text-slate-500">{formatDate(n.created_at)} · {n.created_by}</span>
                  </div>
                  <p className="mt-1.5 text-sm text-slate-800">{n.purpose_and_what_transpired}</p>
                  {n.outcome_and_follow_up && (
                    <p className="mt-1 text-xs text-slate-600"><span className="font-medium">Outcome:</span> {n.outcome_and_follow_up}</p>
                  )}
                </div>
                <Button variant="ghost" size="icon" className="text-rose-700" onClick={() => remove(n.id)} data-testid={`delete-process-note-${n.id}`}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
