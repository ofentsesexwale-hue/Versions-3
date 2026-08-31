import { useEffect, useState } from "react";
import { Plus, Check, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { formatDate } from "@/lib/constants";

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

export function CaseworkPanels({ householdId, members = [], caregiver }) {
  const [choices, setChoices] = useState(null);
  const [partners, setPartners] = useState([]);
  const [referrals, setReferrals] = useState([]);
  const [visits, setVisits] = useState([]);

  const reload = () => {
    const p = { household: householdId, page_size: 100 };
    Promise.all([
      api.get("/referrals/", { params: p }),
      api.get("/visits/", { params: p }),
      api.get("/partners/", { params: { page_size: 200 } }),
    ]).then(([a, b, c]) => {
      setReferrals(results(a.data));
      setVisits(results(b.data));
      setPartners(results(c.data));
    }).catch(() => {});
  };

  useEffect(() => {
    api.get("/choices/").then((r) => setChoices(r.data)).catch(() => {});
    reload();
  }, [householdId]);

  if (!choices) return null;
  const people = [
    caregiver ? `${caregiver.name || ""} ${caregiver.surname || ""}`.trim() : "",
    ...members.map((m) => `${m.name || ""} ${m.surname || ""}`.trim()),
  ].filter(Boolean);

  return (
    <div className="space-y-6">
      <VisitPanel householdId={householdId} visits={visits} choices={choices} reload={reload} />
      <ReferralPanel
        householdId={householdId}
        referrals={referrals}
        partners={partners}
        members={members}
        people={people}
        choices={choices}
        reload={reload}
      />
    </div>
  );
}

function VisitPanel({ householdId, visits, choices, reload }) {
  const [open, setOpen] = useState(false);
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ visit_date: today, visit_type: "home", purpose: "", notes: "" });

  const save = async () => {
    try {
      await api.post("/visits/", { ...form, household: Number(householdId), status: "planned" });
      toast.success("Visit planned");
      setOpen(false);
      reload();
    } catch {
      toast.error("Could not save visit");
    }
  };

  const mark = async (id, action) => {
    await api.post(`/visits/${id}/${action}/`);
    toast.success(action === "mark_done" ? "Visit completed" : "Marked missed");
    reload();
  };

  return (
    <Card data-testid="planned-visits-card">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">Planned visits</CardTitle>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm" className="gap-1" data-testid="add-visit-button"><Plus className="h-3.5 w-3.5" /> Plan visit</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Plan a visit</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1"><Label>Date</Label><Input type="date" value={form.visit_date} onChange={(e) => setForm((f) => ({ ...f, visit_date: e.target.value }))} data-testid="visit-date-input" /></div>
              <Choice label="Type" value={form.visit_type} onChange={(v) => setForm((f) => ({ ...f, visit_type: v }))} options={choices.visit_types} testId="visit-type-select" />
              <div className="space-y-1"><Label>Purpose</Label><Input value={form.purpose} onChange={(e) => setForm((f) => ({ ...f, purpose: e.target.value }))} data-testid="visit-purpose-input" /></div>
              <div className="space-y-1"><Label>Notes</Label><Textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></div>
            </div>
            <DialogFooter>
              <Button onClick={save} data-testid="visit-save-button">Save</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardHeader>
      <CardContent className="space-y-2">
        {visits.length === 0 && <p className="py-4 text-center text-sm text-muted-foreground">No visits planned. Gold-standard OVC files keep a diary of the next home visit.</p>}
        {visits.map((v) => (
          <div key={v.id} className="flex items-start justify-between gap-2 rounded-2xl border border-white/50 bg-white/40 p-3" data-testid={`visit-row-${v.id}`}>
            <div>
              <p className="text-sm font-medium">{formatDate(v.visit_date)} · {v.visit_type_display}</p>
              <p className="text-xs text-muted-foreground">{v.purpose || "—"} · {v.status_display}</p>
            </div>
            <div className="flex gap-1">
              {v.status === "planned" && (
                <>
                  <Button size="sm" variant="outline" className="gap-1" onClick={() => mark(v.id, "mark_done")} data-testid={`visit-done-${v.id}`}><Check className="h-3.5 w-3.5" /> Done</Button>
                  <Button size="sm" variant="ghost" onClick={() => mark(v.id, "mark_missed")}>Missed</Button>
                </>
              )}
              <Button size="icon" variant="ghost" className="text-rose-700" onClick={async () => { await api.delete(`/visits/${v.id}/`); reload(); }}><Trash2 className="h-4 w-4" /></Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function ReferralPanel({ householdId, referrals, partners, members, people, choices, reload }) {
  const [open, setOpen] = useState(false);
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    client_name: people[0] || "",
    partner: "",
    agency_name: "",
    reason: "grant",
    details: "",
    referred_on: today,
    follow_up_date: "",
    status: "sent",
  });

  const save = async () => {
    try {
      const payload = {
        ...form,
        household: Number(householdId),
        partner: form.partner ? Number(form.partner) : null,
        follow_up_date: form.follow_up_date || null,
        member: form.member ? Number(form.member) : null,
      };
      delete payload.member;
      if (form.member) payload.member = Number(form.member);
      await api.post("/referrals/", payload);
      toast.success("Referral recorded");
      setOpen(false);
      reload();
    } catch {
      toast.error("Could not save referral");
    }
  };

  const setStatus = async (id, status) => {
    await api.patch(`/referrals/${id}/`, { status });
    reload();
  };

  return (
    <Card data-testid="referrals-card">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">External referrals</CardTitle>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm" className="gap-1" data-testid="add-referral-button"><Plus className="h-3.5 w-3.5" /> Refer out</Button>
          </DialogTrigger>
          <DialogContent className="max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle>Refer to a partner</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1"><Label>Client name</Label><Input value={form.client_name} onChange={(e) => setForm((f) => ({ ...f, client_name: e.target.value }))} data-testid="referral-client-input" /></div>
              <div className="space-y-1">
                <Label>Partner from directory</Label>
                <Select value={form.partner || "none"} onValueChange={(v) => setForm((f) => ({ ...f, partner: v === "none" ? "" : v }))}>
                  <SelectTrigger className="h-11" data-testid="referral-partner-select"><SelectValue placeholder="Choose or type below" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Type a name instead</SelectItem>
                    {partners.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>{p.name} ({p.kind_display})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {!form.partner && (
                <div className="space-y-1"><Label>Agency name</Label><Input value={form.agency_name} onChange={(e) => setForm((f) => ({ ...f, agency_name: e.target.value }))} /></div>
              )}
              <Choice label="Reason" value={form.reason} onChange={(v) => setForm((f) => ({ ...f, reason: v }))} options={choices.referral_reasons} testId="referral-reason-select" />
              <div className="space-y-1"><Label>Details</Label><Textarea value={form.details} onChange={(e) => setForm((f) => ({ ...f, details: e.target.value }))} /></div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1"><Label>Referred on</Label><Input type="date" value={form.referred_on} onChange={(e) => setForm((f) => ({ ...f, referred_on: e.target.value }))} /></div>
                <div className="space-y-1"><Label>Follow up by</Label><Input type="date" value={form.follow_up_date} onChange={(e) => setForm((f) => ({ ...f, follow_up_date: e.target.value }))} /></div>
              </div>
            </div>
            <DialogFooter>
              <Button onClick={save} data-testid="referral-save-button">Save referral</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardHeader>
      <CardContent className="space-y-2">
        {referrals.length === 0 && <p className="py-4 text-center text-sm text-muted-foreground">No referrals yet. Track SASSA, clinic, school and SAPS referrals here until they close.</p>}
        {referrals.map((r) => (
          <div key={r.id} className="rounded-2xl border border-white/50 bg-white/40 p-3" data-testid={`referral-row-${r.id}`}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-sm font-medium">{r.partner_name} · {r.reason_display}</p>
                <p className="text-xs text-muted-foreground">{r.member_name || r.client_name} · {r.status_display} · {formatDate(r.referred_on)}</p>
              </div>
              <Button size="icon" variant="ghost" className="text-rose-700" onClick={async () => { await api.delete(`/referrals/${r.id}/`); reload(); }}><Trash2 className="h-4 w-4" /></Button>
            </div>
            {r.status !== "completed" && r.status !== "declined" && (
              <div className="mt-2 flex flex-wrap gap-1">
                {["accepted", "completed", "declined", "no_show"].map((s) => (
                  <Button key={s} size="sm" variant="outline" onClick={() => setStatus(r.id, s)}>{s.replace("_", " ")}</Button>
                ))}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
