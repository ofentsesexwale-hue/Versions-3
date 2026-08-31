import { useEffect, useState } from "react";
import { Plus, Printer, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { formatDate } from "@/lib/constants";
import { printForm } from "@/lib/print";

function results(data) {
  return data?.results || data || [];
}

function Choice({ label, value, onChange, options, testId }) {
  return (
    <div className="space-y-1">
      {label && <Label>{label}</Label>}
      <Select value={value || undefined} onValueChange={onChange}>
        <SelectTrigger className="h-11" data-testid={testId}>
          <SelectValue placeholder="Select..." />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function RecordList({ title, testId, printKey, householdId, items, empty, onRemove, children, addLabel, dialog, extra }) {
  return (
    <Card data-testid={testId}>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="text-base">{title}</CardTitle>
        <div className="flex gap-2">
          {printKey && (
            <Button variant="outline" size="sm" className="gap-1" onClick={() => printForm(printKey, { householdId })}>
              <Printer className="h-3.5 w-3.5" /> Print
            </Button>
          )}
          {dialog}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {extra}
        {items.length === 0 && <p className="py-4 text-center text-sm text-muted-foreground">{empty}</p>}
        {items.map((item) => (
          <div key={item.id} className="rounded-2xl border border-white/50 bg-white/40 p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">{children(item)}</div>
              {onRemove && (
                <Button variant="ghost" size="icon" className="text-rose-700" onClick={() => onRemove(item.id)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function CaseRecords({ householdId, household, members = [], caregiver }) {
  const [choices, setChoices] = useState(null);
  const [consents, setConsents] = useState([]);
  const [plans, setPlans] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [cow1, setCow1] = useState([]);
  const [evals, setEvals] = useState([]);
  const [groups, setGroups] = useState([]);

  const reload = () => {
    const p = { household: householdId, page_size: 100 };
    Promise.all([
      api.get("/consents/", { params: p }),
      api.get("/care-plans/", { params: p }),
      api.get("/protection-incidents/", { params: p }),
      api.get("/cow1/", { params: p }),
      api.get("/evaluations/", { params: p }),
      api.get("/group-sessions/", { params: p }),
    ]).then(([a, b, c, d, e, f]) => {
      setConsents(results(a.data));
      setPlans(results(b.data));
      setIncidents(results(c.data));
      setCow1(results(d.data));
      setEvals(results(e.data));
      setGroups(results(f.data));
    }).catch(() => {});
  };

  useEffect(() => {
    api.get("/choices/").then((r) => setChoices(r.data)).catch(() => {});
    reload();
  }, [householdId]);

  if (!choices) return null;

  const people = [
    caregiver ? { name: `${caregiver.name || ""} ${caregiver.surname || ""}`.trim() } : null,
    ...members.map((m) => ({ name: `${m.name || ""} ${m.surname || ""}`.trim(), id: m.id })),
  ].filter(Boolean);

  return (
    <div className="space-y-6">
      <ConsentPanel householdId={householdId} caregiver={caregiver} members={members} consents={consents} choices={choices} reload={reload} />
      <CarePlanPanel householdId={householdId} household={household} people={people} plans={plans} reload={reload} />
      <IncidentPanel householdId={householdId} members={members} incidents={incidents} choices={choices} reload={reload} />
      <Cow1Panel householdId={householdId} items={cow1} reload={reload} />
      <EvalPanel householdId={householdId} items={evals} choices={choices} reload={reload} />
      <GroupPanel householdId={householdId} items={groups} reload={reload} />
    </div>
  );
}

function ConsentPanel({ householdId, caregiver, members, consents, choices, reload }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    consent_type: "services",
    caregiver_name: `${caregiver?.name || ""} ${caregiver?.surname || ""}`.trim(),
    caregiver_signed: true,
    caregiver_signed_date: new Date().toISOString().slice(0, 10),
    child_name: "",
    child_assent: false,
    child_assent_date: "",
    notes: "",
  });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...form, household: Number(householdId) };
      if (!payload.child_assent_date) payload.child_assent_date = null;
      await api.post("/consents/", payload);
      toast.success("Consent recorded");
      setOpen(false);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save consent");
    } finally {
      setSaving(false);
    }
  };

  return (
    <RecordList
      title="Consent (dated records)"
      testId="consent-card"
      printKey="consent"
      householdId={householdId}
      items={consents}
      empty="No dated consent yet. Record services, information-sharing, and photo consent here — not only as a checklist tick."
      onRemove={async (id) => { await api.delete(`/consents/${id}/`); toast.success("Consent removed"); reload(); }}
      dialog={(
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm" className="gap-1" data-testid="add-consent-button"><Plus className="h-3.5 w-3.5" /> Record consent</Button>
          </DialogTrigger>
          <DialogContent className="max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle>Dated consent</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <Choice label="Type" value={form.consent_type} onChange={(v) => set("consent_type", v)} options={choices.consent_types} />
              <div className="space-y-1"><Label>Caregiver name</Label><Input value={form.caregiver_name} onChange={(e) => set("caregiver_name", e.target.value)} /></div>
              <label className="flex items-center gap-2"><Checkbox checked={form.caregiver_signed} onCheckedChange={(v) => set("caregiver_signed", !!v)} /><span className="text-sm">Caregiver signed</span></label>
              <div className="space-y-1"><Label>Caregiver signed date</Label><Input type="date" value={form.caregiver_signed_date} onChange={(e) => set("caregiver_signed_date", e.target.value)} /></div>
              <div className="space-y-1"><Label>Child (for assent)</Label>
                <Input value={form.child_name} onChange={(e) => set("child_name", e.target.value)} placeholder="Name" list="consent-children" />
                <datalist id="consent-children">{members.map((m) => <option key={m.id} value={`${m.name} ${m.surname}`.trim()} />)}</datalist>
              </div>
              <label className="flex items-center gap-2"><Checkbox checked={form.child_assent} onCheckedChange={(v) => set("child_assent", !!v)} /><span className="text-sm">Child assent given</span></label>
              <div className="space-y-1"><Label>Assent date</Label><Input type="date" value={form.child_assent_date} onChange={(e) => set("child_assent_date", e.target.value)} /></div>
              <div className="space-y-1"><Label>Notes</Label><Textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} /></div>
            </div>
            <DialogFooter>
              <Button onClick={save} disabled={saving} data-testid="save-consent-button">Save consent</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    >
      {(c) => (
        <>
          <p className="font-medium">{c.consent_type_display}</p>
          <p className="text-sm text-muted-foreground">
            {c.caregiver_signed ? `Caregiver signed ${formatDate(c.caregiver_signed_date)}` : "Caregiver not signed"}
            {c.child_name ? ` · Child: ${c.child_name}${c.child_assent ? ` (assent ${formatDate(c.child_assent_date)})` : ""}` : ""}
          </p>
        </>
      )}
    </RecordList>
  );
}

function emptyRow(name = "") {
  return { member_name: name, need: "", action: "", by_whom: "", month: "", progress: "" };
}

function CarePlanPanel({ householdId, household, people, plans, reload }) {
  const current = plans[0];
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [goal, setGoal] = useState("");
  const [review, setReview] = useState("");
  const [ssp, setSsp] = useState("");
  const [sign, setSign] = useState("");
  const [rows, setRows] = useState([emptyRow()]);

  useEffect(() => {
    if (current) {
      setGoal(current.overall_goal || "");
      setReview(current.review_date || "");
      setSsp(current.ssp_name || "");
      setSign(current.caregiver_sign_name || "");
      setRows(current.rows?.length ? current.rows : [emptyRow()]);
    } else if (people.length) {
      setRows(people.map((p) => emptyRow(p.name)));
    }
  }, [current, people.length]);

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        household: Number(householdId),
        overall_goal: goal,
        review_date: review || null,
        ssp_name: ssp,
        caregiver_sign_name: sign,
        rows: rows.filter((r) => r.member_name || r.need || r.action),
      };
      if (current) await api.patch(`/care-plans/${current.id}/`, payload);
      else await api.post("/care-plans/", payload);
      toast.success("Family care plan saved");
      setOpen(false);
      reload();
    } catch (e) {
      toast.error("Could not save care plan");
    } finally {
      setSaving(false);
    }
  };

  const setRow = (i, k, v) => setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, [k]: v } : r)));

  return (
    <RecordList
      title="Family Care Plan"
      testId="care-plan-card"
      printKey="family_care_plan"
      householdId={householdId}
      items={plans}
      empty="No care plan saved yet. Capture needs and actions so the printed form is filled, not blank."
      dialog={(
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm" className="gap-1" data-testid="edit-care-plan-button"><Plus className="h-3.5 w-3.5" /> {current ? "Update plan" : "Create plan"}</Button>
          </DialogTrigger>
          <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
            <DialogHeader><DialogTitle>Family care plan</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1"><Label>Overall goal</Label><Textarea value={goal} onChange={(e) => setGoal(e.target.value)} /></div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="space-y-1"><Label>Review date</Label><Input type="date" value={review} onChange={(e) => setReview(e.target.value)} /></div>
                <div className="space-y-1"><Label>SSP name</Label><Input value={ssp} onChange={(e) => setSsp(e.target.value)} /></div>
                <div className="space-y-1"><Label>Caregiver sign name</Label><Input value={sign} onChange={(e) => setSign(e.target.value)} /></div>
              </div>
              {rows.map((row, i) => (
                <div key={i} className="grid grid-cols-1 gap-2 rounded-xl border border-white/50 p-3 sm:grid-cols-2">
                  <Input placeholder="Family member" value={row.member_name} onChange={(e) => setRow(i, "member_name", e.target.value)} />
                  <Input placeholder="Identified need" value={row.need} onChange={(e) => setRow(i, "need", e.target.value)} />
                  <Input placeholder="Action to be taken" value={row.action} onChange={(e) => setRow(i, "action", e.target.value)} />
                  <Input placeholder="By whom" value={row.by_whom} onChange={(e) => setRow(i, "by_whom", e.target.value)} />
                  <Input placeholder="Month" value={row.month} onChange={(e) => setRow(i, "month", e.target.value)} />
                  <Input placeholder="Progress" value={row.progress} onChange={(e) => setRow(i, "progress", e.target.value)} />
                </div>
              ))}
              <Button variant="outline" size="sm" onClick={() => setRows((r) => [...r, emptyRow()])}>Add row</Button>
            </div>
            <DialogFooter>
              <Button onClick={save} disabled={saving} data-testid="save-care-plan-button">Save plan</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    >
      {(p) => (
        <>
          <p className="font-medium">Updated {formatDate(p.updated_at)}</p>
          <p className="text-sm text-muted-foreground">{p.overall_goal || `${p.rows?.length || 0} need/action rows`}</p>
        </>
      )}
    </RecordList>
  );
}

function IncidentPanel({ householdId, members, incidents, choices, reload }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    incident_date: new Date().toISOString().slice(0, 10),
    incident_type: "neglect",
    member: "",
    alleged_perpetrator: "",
    location: "",
    description: "",
    reported_to: "",
    action_taken: "",
    status: "open",
  });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...form, household: Number(householdId), member: form.member || null };
      await api.post("/protection-incidents/", payload);
      toast.success("Protection incident recorded");
      setOpen(false);
      reload();
    } catch (e) {
      toast.error("Could not save incident");
    } finally {
      setSaving(false);
    }
  };
  return (
    <RecordList
      title="Form 22 — Protection incidents"
      testId="form22-card"
      printKey="form22"
      householdId={householdId}
      items={incidents}
      empty="No protection incidents on this file."
      onRemove={async (id) => { await api.delete(`/protection-incidents/${id}/`); reload(); }}
      dialog={(
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button size="sm" className="gap-1"><Plus className="h-3.5 w-3.5" /> Record incident</Button></DialogTrigger>
          <DialogContent className="max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle>Protection incident</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1"><Label>Date</Label><Input type="date" value={form.incident_date} onChange={(e) => set("incident_date", e.target.value)} /></div>
              <Choice label="Type" value={form.incident_type} onChange={(v) => set("incident_type", v)} options={choices.protection_types} />
              <Choice label="Child involved" value={form.member ? String(form.member) : "none"} onChange={(v) => set("member", v === "none" ? "" : Number(v))} options={[{ value: "none", label: "Not specified" }, ...members.map((m) => ({ value: String(m.id), label: `${m.name} ${m.surname}` }))]} />
              <Input placeholder="Alleged perpetrator" value={form.alleged_perpetrator} onChange={(e) => set("alleged_perpetrator", e.target.value)} />
              <Input placeholder="Location" value={form.location} onChange={(e) => set("location", e.target.value)} />
              <Textarea placeholder="Description" value={form.description} onChange={(e) => set("description", e.target.value)} />
              <Input placeholder="Reported to" value={form.reported_to} onChange={(e) => set("reported_to", e.target.value)} />
              <Textarea placeholder="Action taken" value={form.action_taken} onChange={(e) => set("action_taken", e.target.value)} />
              <Choice label="Status" value={form.status} onChange={(v) => set("status", v)} options={choices.incident_status} />
            </div>
            <DialogFooter><Button onClick={save} disabled={saving}>Save incident</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    >
      {(i) => (
        <>
          <p className="font-medium">{i.incident_type_display} · {formatDate(i.incident_date)}</p>
          <p className="text-sm text-muted-foreground">{i.member_name || "Household"} · {i.status}</p>
        </>
      )}
    </RecordList>
  );
}

function Cow1Panel({ householdId, items, reload }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    plan_date: new Date().toISOString().slice(0, 10),
    community_issue: "", planned_activities: "", stakeholders: "", expected_outcome: "", ssp_name: "",
  });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const save = async () => {
    setSaving(true);
    try {
      await api.post("/cow1/", { ...form, household: Number(householdId) });
      toast.success("COW 1 plan saved");
      setOpen(false);
      reload();
    } catch (e) {
      toast.error("Could not save COW 1");
    } finally { setSaving(false); }
  };
  return (
    <RecordList
      title="COW 1 Community work plan"
      testId="cow1-card"
      printKey="cow1"
      householdId={householdId}
      items={items}
      empty="No COW 1 community plan on this file."
      onRemove={async (id) => { await api.delete(`/cow1/${id}/`); reload(); }}
      dialog={(
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button size="sm" className="gap-1"><Plus className="h-3.5 w-3.5" /> Add COW 1</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>COW 1 plan</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <Input type="date" value={form.plan_date} onChange={set("plan_date")} />
              <Textarea placeholder="Community issue" value={form.community_issue} onChange={set("community_issue")} />
              <Textarea placeholder="Planned activities" value={form.planned_activities} onChange={set("planned_activities")} />
              <Input placeholder="Stakeholders" value={form.stakeholders} onChange={set("stakeholders")} />
              <Textarea placeholder="Expected outcome" value={form.expected_outcome} onChange={set("expected_outcome")} />
              <Input placeholder="SSP name" value={form.ssp_name} onChange={set("ssp_name")} />
            </div>
            <DialogFooter><Button onClick={save} disabled={saving}>Save</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    >
      {(p) => (
        <>
          <p className="font-medium">{formatDate(p.plan_date)}</p>
          <p className="text-sm text-muted-foreground line-clamp-2">{p.community_issue || p.planned_activities}</p>
        </>
      )}
    </RecordList>
  );
}

function EvalPanel({ householdId, items, choices, reload }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    evaluation_date: new Date().toISOString().slice(0, 10),
    period_from: "", period_to: "", progress_against_plan: "", remaining_needs: "", recommendation: "continue", ssp_name: "",
  });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...form, household: Number(householdId) };
      if (!payload.period_from) payload.period_from = null;
      if (!payload.period_to) payload.period_to = null;
      await api.post("/evaluations/", payload);
      toast.success("CW 12 evaluation saved");
      setOpen(false);
      reload();
    } catch (e) {
      toast.error("Could not save evaluation");
    } finally { setSaving(false); }
  };
  return (
    <RecordList
      title="CW 12 Evaluation"
      testId="evaluation-card"
      printKey="evaluation"
      householdId={householdId}
      items={items}
      empty="No CW 12 evaluation yet. Record progress against the care plan here."
      onRemove={async (id) => { await api.delete(`/evaluations/${id}/`); reload(); }}
      dialog={(
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button size="sm" className="gap-1"><Plus className="h-3.5 w-3.5" /> Add evaluation</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>CW 12 evaluation</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <Input type="date" value={form.evaluation_date} onChange={(e) => set("evaluation_date", e.target.value)} />
              <div className="grid grid-cols-2 gap-2">
                <Input type="date" value={form.period_from} onChange={(e) => set("period_from", e.target.value)} />
                <Input type="date" value={form.period_to} onChange={(e) => set("period_to", e.target.value)} />
              </div>
              <Textarea placeholder="Progress against plan" value={form.progress_against_plan} onChange={(e) => set("progress_against_plan", e.target.value)} />
              <Textarea placeholder="Remaining needs" value={form.remaining_needs} onChange={(e) => set("remaining_needs", e.target.value)} />
              <Choice label="Recommendation" value={form.recommendation} onChange={(v) => set("recommendation", v)} options={choices.evaluation_recommendation} />
              <Input placeholder="SSP name" value={form.ssp_name} onChange={(e) => set("ssp_name", e.target.value)} />
            </div>
            <DialogFooter><Button onClick={save} disabled={saving}>Save</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    >
      {(p) => (
        <>
          <p className="font-medium">{formatDate(p.evaluation_date)} · {p.recommendation_display || p.recommendation}</p>
          <p className="text-sm text-muted-foreground line-clamp-2">{p.progress_against_plan}</p>
        </>
      )}
    </RecordList>
  );
}

function GroupPanel({ householdId, items, reload }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    session_date: new Date().toISOString().slice(0, 10),
    group_name: "", topic: "", attendees_count: 0, attendees_notes: "", session_notes: "", outcomes: "",
  });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const save = async () => {
    setSaving(true);
    try {
      await api.post("/group-sessions/", { ...form, household: Number(householdId), attendees_count: Number(form.attendees_count) || 0 });
      toast.success("Group session saved");
      setOpen(false);
      reload();
    } catch (e) {
      toast.error("Could not save session");
    } finally { setSaving(false); }
  };
  return (
    <RecordList
      title="GRW Group work"
      testId="group-work-card"
      printKey="group_work"
      householdId={householdId}
      items={items}
      empty="No group-work sessions linked to this file."
      onRemove={async (id) => { await api.delete(`/group-sessions/${id}/`); reload(); }}
      dialog={(
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button size="sm" className="gap-1"><Plus className="h-3.5 w-3.5" /> Add session</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>GRW session</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <Input type="date" value={form.session_date} onChange={set("session_date")} />
              <Input placeholder="Group name" value={form.group_name} onChange={set("group_name")} />
              <Input placeholder="Topic" value={form.topic} onChange={set("topic")} />
              <Input type="number" min="0" placeholder="Attendees" value={form.attendees_count} onChange={set("attendees_count")} />
              <Textarea placeholder="Who attended" value={form.attendees_notes} onChange={set("attendees_notes")} />
              <Textarea placeholder="Session notes" value={form.session_notes} onChange={set("session_notes")} />
              <Textarea placeholder="Outcomes" value={form.outcomes} onChange={set("outcomes")} />
            </div>
            <DialogFooter><Button onClick={save} disabled={saving}>Save</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    >
      {(p) => (
        <>
          <p className="font-medium">{formatDate(p.session_date)} · {p.group_name || "Group"}</p>
          <p className="text-sm text-muted-foreground">{p.topic} · {p.attendees_count} attendees</p>
        </>
      )}
    </RecordList>
  );
}
