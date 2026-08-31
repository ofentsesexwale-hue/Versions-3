import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DateField } from "@/components/DateField";
import { ConfirmableField } from "@/components/ConfirmableField";
import { ChoiceSelect, usePersonForm } from "@/components/PersonFormKit";
import { IdCheckHint } from "@/components/IdCheckHint";

export default function MemberForm() {
  const { id } = useParams();
  const location = useLocation();
  const isEdit = location.pathname.endsWith("/edit");
  const navigate = useNavigate();
  const [choices, setChoices] = useState(null);
  const [householdId, setHouseholdId] = useState(isEdit ? null : Number(id));
  const [memberId, setMemberId] = useState(isEdit ? Number(id) : null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const pf = usePersonForm({ id_type: "SA ID Number", nationality: "South African" });

  useEffect(() => {
    const tasks = [api.get("/choices/")];
    if (isEdit) tasks.push(api.get(`/members/${id}/`));
    Promise.all(tasks).then((res) => {
      setChoices(res[0].data);
      if (isEdit) {
        const m = res[1].data;
        setHouseholdId(m.household);
        pf.setForm(m);
        pf.setConfirmed({ surname: m.surname_confirmed, id_number: m.id_number_confirmed, date_of_birth: m.date_of_birth_confirmed });
        pf.setMeta({
          surname: { by: m.surname_confirmed_by, at: m.surname_confirmed_at },
          id_number: { by: m.id_number_confirmed_by, at: m.id_number_confirmed_at },
          date_of_birth: { by: m.date_of_birth_confirmed_by, at: m.date_of_birth_confirmed_at },
        });
      }
      setLoading(false);
    });
  }, [id]);

  const submit = async () => {
    setSaving(true);
    const payload = {
      ...pf.form,
      household: householdId,
      surname_confirmed: pf.confirmed.surname,
      id_number_confirmed: pf.confirmed.id_number,
      date_of_birth_confirmed: pf.confirmed.date_of_birth,
    };
    try {
      if (isEdit) await api.patch(`/members/${memberId}/`, payload);
      else await api.post("/members/", payload);
      toast.success("Member saved");
      navigate(`/households/${householdId}`);
    } catch (e) {
      const data = e?.response?.data;
      toast.error(typeof data === "object" ? Object.values(data)[0] : "Could not save member");
    } finally {
      setSaving(false);
    }
  };

  if (loading || !choices) return <div data-testid="loading-state">Loading...</div>;
  const f = pf.form;

  return (
    <div className="mx-auto max-w-3xl space-y-6 pb-24">
      <Button variant="ghost" onClick={() => navigate(`/households/${householdId}`)} className="gap-2" data-testid="back-button">
        <ArrowLeft className="h-4 w-4" /> Back to household
      </Button>
      <h1 className="text-2xl font-semibold text-slate-900">{isEdit ? "Edit member" : "Add household member"}</h1>

      <Card>
        <CardHeader><CardTitle className="text-base">Verification-required fields</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <ConfirmableField fieldKey="surname" label="Surname" hasValue={pf.hasVal("surname")} confirmed={pf.confirmed.surname} confirmedBy={pf.meta.surname?.by} confirmedAt={pf.meta.surname?.at} onConfirm={() => pf.setConfirmed((c) => ({ ...c, surname: true }))}>
            <Input value={f.surname || ""} onChange={(e) => pf.setConfirmable("surname", e.target.value)} className="h-11" data-testid="member-surname-input" />
          </ConfirmableField>
          <ConfirmableField fieldKey="id_number" label="ID / Passport number" hasValue={pf.hasVal("id_number")} confirmed={pf.confirmed.id_number} confirmedBy={pf.meta.id_number?.by} confirmedAt={pf.meta.id_number?.at} onConfirm={() => pf.setConfirmed((c) => ({ ...c, id_number: true }))}>
            <Input value={f.id_number || ""} onChange={(e) => pf.setConfirmable("id_number", e.target.value)} className="h-11" data-testid="member-id_number-input" />
          </ConfirmableField>
          <IdCheckHint
            idNumber={f.id_number}
            idType={f.id_type}
            excludeMember={memberId}
            currentDob={f.date_of_birth}
            currentSex={f.sex}
            onApplyDob={(v) => pf.setConfirmable("date_of_birth", v)}
            onApplySex={(v) => pf.set("sex", v)}
          />
          <ConfirmableField fieldKey="date_of_birth" label="Date of birth" hasValue={pf.hasVal("date_of_birth")} confirmed={pf.confirmed.date_of_birth} confirmedBy={pf.meta.date_of_birth?.by} confirmedAt={pf.meta.date_of_birth?.at} onConfirm={() => pf.setConfirmed((c) => ({ ...c, date_of_birth: true }))}>
            <DateField value={f.date_of_birth} onChange={(v) => pf.setConfirmable("date_of_birth", v)} testId="date-picker-member-dob" />
          </ConfirmableField>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Personal details</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div className="space-y-1.5"><Label>First name</Label><Input value={f.name || ""} onChange={(e) => pf.set("name", e.target.value)} className="h-11" data-testid="member-name-input" /></div>
          <div className="space-y-1.5"><Label>Known as</Label><Input value={f.known_as || ""} onChange={(e) => pf.set("known_as", e.target.value)} className="h-11" /></div>
          <div className="space-y-1.5"><Label>Relationship to head</Label><Input value={f.relationship_to_head || ""} onChange={(e) => pf.set("relationship_to_head", e.target.value)} className="h-11" data-testid="member-relationship-input" /></div>
          <ChoiceSelect label="ID type" value={f.id_type} onChange={(v) => pf.set("id_type", v)} options={choices.id_type} testId="member-id_type-select" />
          <div className="space-y-1.5"><Label>Nationality</Label><Input value={f.nationality || ""} onChange={(e) => pf.set("nationality", e.target.value)} className="h-11" /></div>
          <ChoiceSelect label="Sex" value={f.sex} onChange={(v) => pf.set("sex", v)} options={choices.sex} testId="member-sex-select" />
          <ChoiceSelect label="Race" value={f.race} onChange={(v) => pf.set("race", v)} options={choices.race} testId="member-race-select" />
          <div className="space-y-1.5"><Label>Date joined</Label><DateField value={f.date_joined} onChange={(v) => pf.set("date_joined", v)} testId="date-picker-member-joined" /></div>
          <div className="flex items-center gap-3 pt-6"><Checkbox checked={!!f.disability} onCheckedChange={(v) => pf.set("disability", !!v)} data-testid="member-disability-checkbox" /><Label>Has a disability</Label></div>
          {f.disability && (
            <div className="space-y-1.5 sm:col-span-2"><Label>Disability description</Label><Textarea value={f.disability_description || ""} onChange={(e) => pf.set("disability_description", e.target.value)} /></div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">School and grants</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div className="flex items-center gap-3 pt-2 sm:col-span-2">
            <Checkbox checked={!!f.enrolled_in_school} onCheckedChange={(v) => pf.set("enrolled_in_school", !!v)} data-testid="member-enrolled-checkbox" />
            <Label>Currently enrolled in school</Label>
          </div>
          <div className="space-y-1.5"><Label>School name</Label><Input value={f.school_name || ""} onChange={(e) => pf.set("school_name", e.target.value)} className="h-11" data-testid="member-school-input" /></div>
          <div className="space-y-1.5"><Label>Grade</Label><Input value={f.grade || ""} onChange={(e) => pf.set("grade", e.target.value)} className="h-11" data-testid="member-grade-input" /></div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Grant types</Label>
            <div className="flex flex-wrap gap-3 pt-1">
              {(choices.grant_types || []).map((g) => {
                const val = g.value || g;
                const label = g.label || g;
                const selected = (f.grant_types || []).includes(val);
                return (
                  <label key={val} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={selected}
                      onCheckedChange={(v) => {
                        const cur = f.grant_types || [];
                        pf.set("grant_types", v ? [...cur, val] : cur.filter((x) => x !== val));
                      }}
                    />
                    {label}
                  </label>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">HIVSTAT (need-to-know)</CardTitle>
          <p className="text-sm text-muted-foreground">Store HIV status, ART and viral load on the child&apos;s record so HIV risk printouts are filled. Share only with staff who need this to deliver services.</p>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <ChoiceSelect
            label="HIV status"
            value={f.hiv_status || "unknown"}
            onChange={(v) => pf.set("hiv_status", v)}
            options={(choices.hiv_status || []).map((x) => x.value)}
            testId="member-hiv-status-select"
          />
          <ChoiceSelect
            label="On ART"
            value={f.on_art || "na"}
            onChange={(v) => pf.set("on_art", v)}
            options={(choices.on_art || []).map((x) => x.value)}
            testId="member-on-art-select"
          />
          <div className="space-y-1.5"><Label>Last viral load</Label><Input value={f.last_viral_load || ""} onChange={(e) => pf.set("last_viral_load", e.target.value)} className="h-11" /></div>
          <div className="space-y-1.5"><Label>Viral load date</Label><DateField value={f.last_viral_load_date} onChange={(v) => pf.set("last_viral_load_date", v)} /></div>
          <div className="space-y-1.5"><Label>Last HIV test date</Label><DateField value={f.hiv_test_date} onChange={(v) => pf.set("hiv_test_date", v)} /></div>
          <ChoiceSelect
            label="HIV test required"
            value={f.hiv_test_required === true ? "yes" : f.hiv_test_required === false ? "no" : "unknown"}
            onChange={(v) => pf.set("hiv_test_required", v === "yes" ? true : v === "no" ? false : null)}
            options={["unknown", "yes", "no"]}
            testId="member-hiv-test-required-select"
          />
          <div className="space-y-1.5 sm:col-span-2"><Label>HIV notes</Label><Textarea value={f.hiv_risk_notes || ""} onChange={(e) => pf.set("hiv_risk_notes", e.target.value)} /></div>
        </CardContent>
      </Card>

      <div className="sticky bottom-0 flex items-center justify-between border-t border-slate-200 bg-white/95 p-3 backdrop-blur">
        <p className={pf.blocked ? "text-sm text-amber-800" : "text-sm text-emerald-800"} data-testid="save-blocked-unconfirmed-message">
          {pf.blocked ? "Confirm the highlighted fields before saving." : "All required confirmations complete."}
        </p>
        <Button onClick={submit} disabled={saving || pf.blocked} className="gap-2 bg-slate-900 hover:bg-slate-800" data-testid="member-save-button">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save member
        </Button>
      </div>
    </div>
  );
}
