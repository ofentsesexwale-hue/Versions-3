import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Plus, Printer, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { printForm } from "@/lib/print";

const FIELDS = [
  ["overview_situation", "Part 3.1 Overview of the situation"],
  ["strengths", "Part 3.2 Strengths and problem solving"],
  ["psychosocial_social", "Part 3.3.1 Social relations & functioning"],
  ["psychosocial_stress", "Part 3.3.2 Sources of stress / behaviour"],
  ["education", "Part 3.4 Education"],
  ["safety", "Part 3.5 Safety and security"],
  ["health_nutrition", "Part 3.6 Health and nutrition"],
  ["economic_legal", "Part 3.7 Economic, basic & legal needs"],
  ["assessment_summary", "Part 3.8 Assessment summary"],
  ["overall_goal", "Part 4 Overall goal"],
  ["client_views", "Part 4 Views of the client(s)"],
];
const EMPTY = FIELDS.reduce((a, [k]) => ({ ...a, [k]: "" }), { problem_codes: "", risk_level: "", due_date_evaluation: "", plan_rows: [] });

export default function AssessmentForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY);
  const [existingId, setExistingId] = useState(null);
  const [risks, setRisks] = useState([]);
  const [saving, setSaving] = useState(false);
  const [versions, setVersions] = useState([]);

  const applyVersion = (a) => {
    setExistingId(a.id);
    setForm({ ...EMPTY, ...a, plan_rows: a.plan_rows || [], due_date_evaluation: a.due_date_evaluation || "" });
  };
  const loadVersions = (selectId) => {
    api.get("/assessments/", { params: { household: id, page_size: 50 } }).then((r) => {
      const list = r.data.results || [];
      setVersions(list);
      const pick = selectId ? list.find((x) => x.id === selectId) : list[0];
      if (pick) applyVersion(pick);
    }).catch(() => {});
  };
  const newVersion = () => { setExistingId(null); setForm(EMPTY); };

  useEffect(() => {
    loadVersions();
    api.get("/choices/").then((r) => setRisks(r.data.risk_level || [])).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const addRow = () => setForm((f) => ({ ...f, plan_rows: [...f.plan_rows, { issue: "", intervention: "", due_date: "", responsibility: "" }] }));
  const setRow = (i, k, v) => setForm((f) => { const rows = [...f.plan_rows]; rows[i] = { ...rows[i], [k]: v }; return { ...f, plan_rows: rows }; });
  const delRow = (i) => setForm((f) => ({ ...f, plan_rows: f.plan_rows.filter((_, x) => x !== i) }));

  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...form, household: Number(id) };
      if (!payload.due_date_evaluation) delete payload.due_date_evaluation;
      let savedId = existingId;
      if (existingId) await api.put(`/assessments/${existingId}/`, payload);
      else { const r = await api.post("/assessments/", payload); savedId = r.data.id; setExistingId(r.data.id); }
      toast.success("Assessment saved");
      loadVersions(savedId);
    } catch (e) {
      toast.error("Could not save assessment");
    } finally { setSaving(false); }
  };

  return (
    <div className="space-y-6" data-testid="assessment-form-page">
      <Button variant="ghost" onClick={() => navigate(`/households/${id}`)} className="gap-2" data-testid="back-button">
        <ArrowLeft className="h-4 w-4" /> Back to household
      </Button>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">CW 09 Assessment, Planning &amp; Contracting</h1>
          <p className="text-sm text-slate-600">Complete the narrative sections; they print onto the official CW 09 form.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {versions.length > 0 && (
            <Select value={existingId ? String(existingId) : "new"} onValueChange={(v) => (v === "new" ? newVersion() : applyVersion(versions.find((x) => String(x.id) === v)))}>
              <SelectTrigger className="w-[220px]" data-testid="assessment-version-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {versions.map((v) => (
                  <SelectItem key={v.id} value={String(v.id)}>
                    v{v.version_number} · {new Date(v.updated_at).toLocaleDateString()} {new Date(v.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}{v.created_by ? ` · ${v.created_by}` : ""}
                  </SelectItem>
                ))}
                <SelectItem value="new">+ New (unsaved)</SelectItem>
              </SelectContent>
            </Select>
          )}
          <Button variant="outline" className="gap-2" onClick={newVersion} data-testid="assessment-new-version-button">New version</Button>
          <Button variant="outline" className="gap-2" onClick={() => printForm("assessment", { householdId: id, assessmentId: existingId })} data-testid="print-assessment-button">
            <Printer className="h-4 w-4" /> Print CW 09
          </Button>
          <Button onClick={save} disabled={saving} className="gap-2 bg-slate-900 hover:bg-slate-800" data-testid="assessment-save-button">
            <Save className="h-4 w-4" /> {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>
      <Card>
        <CardContent className="space-y-4 p-5">
          {FIELDS.map(([k, label]) => (
            <div key={k}>
              <label className="mb-1 block text-xs font-medium text-slate-600">{label}</label>
              <Textarea rows={2} value={form[k]} onChange={set(k)} data-testid={`assessment-${k}`} />
            </div>
          ))}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Problem codes</label>
              <Input value={form.problem_codes} onChange={set("problem_codes")} placeholder="e.g. 1.1, 6.8" data-testid="assessment-problem-codes" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Risk level</label>
              <Select value={form.risk_level} onValueChange={(v) => setForm((f) => ({ ...f, risk_level: v }))}>
                <SelectTrigger data-testid="assessment-risk-level"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>{risks.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Due date for evaluation</label>
              <Input type="date" value={form.due_date_evaluation} onChange={set("due_date_evaluation")} data-testid="assessment-due-date" />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card data-testid="plan-rows-card">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Part 4: Plan of Action</CardTitle>
          <Button variant="outline" size="sm" className="gap-1.5" onClick={addRow} data-testid="add-plan-row-button">
            <Plus className="h-3.5 w-3.5" /> Add row
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {form.plan_rows.length === 0 && (
            <p className="py-2 text-center text-sm text-slate-500" data-testid="plan-rows-empty">No plan rows yet. Add issues, interventions, due dates and responsibilities.</p>
          )}
          {form.plan_rows.map((r, i) => (
            <div key={i} className="grid grid-cols-1 items-start gap-2 rounded-lg border border-slate-200 p-3 sm:grid-cols-[1fr_1fr_130px_150px_auto]" data-testid={`plan-row-${i}`}>
              <Input placeholder="Issue to be addressed" value={r.issue} onChange={(e) => setRow(i, "issue", e.target.value)} data-testid={`plan-issue-${i}`} />
              <Input placeholder="Intervention + codes" value={r.intervention} onChange={(e) => setRow(i, "intervention", e.target.value)} data-testid={`plan-intervention-${i}`} />
              <Input type="date" value={r.due_date} onChange={(e) => setRow(i, "due_date", e.target.value)} data-testid={`plan-due-${i}`} />
              <Input placeholder="Responsibility" value={r.responsibility} onChange={(e) => setRow(i, "responsibility", e.target.value)} data-testid={`plan-responsibility-${i}`} />
              <Button variant="ghost" size="icon" className="text-rose-700" onClick={() => delRow(i)} data-testid={`plan-del-${i}`}><Trash2 className="h-4 w-4" /></Button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
