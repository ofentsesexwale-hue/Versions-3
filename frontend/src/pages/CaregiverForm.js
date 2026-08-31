import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
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

export default function CaregiverForm() {
  const { id } = useParams(); // household id
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [choices, setChoices] = useState(null);
  const [cgId, setCgId] = useState(null);
  const [hasLogin, setHasLogin] = useState(false);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [savingLogin, setSavingLogin] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const pf = usePersonForm({ id_type: "SA ID Number", nationality: "South African" });

  useEffect(() => {
    Promise.all([api.get("/choices/"), api.get(`/households/${id}/`)]).then(([c, h]) => {
      setChoices(c.data);
      const cg = h.data.caregiver;
      if (cg) {
        setCgId(cg.id);
        setHasLogin(!!cg.has_login);
        setLoginUsername(cg.login_username || "");
        pf.setForm(cg);
        pf.setConfirmed({
          surname: cg.surname_confirmed,
          id_number: cg.id_number_confirmed,
          date_of_birth: cg.date_of_birth_confirmed,
        });
        pf.setMeta({
          surname: { by: cg.surname_confirmed_by, at: cg.surname_confirmed_at },
          id_number: { by: cg.id_number_confirmed_by, at: cg.id_number_confirmed_at },
          date_of_birth: { by: cg.date_of_birth_confirmed_by, at: cg.date_of_birth_confirmed_at },
        });
      }
      setLoading(false);
    });
  }, [id]);

  const submit = async () => {
    setSaving(true);
    const payload = {
      ...pf.form,
      household: Number(id),
      surname_confirmed: pf.confirmed.surname,
      id_number_confirmed: pf.confirmed.id_number,
      date_of_birth_confirmed: pf.confirmed.date_of_birth,
    };
    try {
      let saved;
      if (cgId) saved = (await api.patch(`/caregivers/${cgId}/`, payload)).data;
      else saved = (await api.post("/caregivers/", payload)).data;
      toast.success("Caregiver saved");
      if (isAdmin && loginUsername && loginPassword) {
        setSavingLogin(true);
        await api.post(`/caregivers/${saved.id}/set-login/`, {
          username: loginUsername,
          password: loginPassword,
        });
        toast.success(hasLogin ? "Caregiver login updated" : "Caregiver can sign in now");
      }
      navigate(`/households/${id}`);
    } catch (e) {
      const data = e?.response?.data;
      toast.error(typeof data === "object" ? Object.values(data)[0] : "Could not save caregiver");
    } finally {
      setSaving(false);
    }
  };

  if (loading || !choices) return <div data-testid="loading-state">Loading...</div>;
  const f = pf.form;

  return (
    <div className="mx-auto max-w-3xl space-y-6 pb-24">
      <Button variant="ghost" onClick={() => navigate(`/households/${id}`)} className="gap-2" data-testid="back-button">
        <ArrowLeft className="h-4 w-4" /> Back to household
      </Button>
      <h1 className="text-2xl font-semibold text-slate-900">{cgId ? "Edit caregiver" : "Add caregiver"}</h1>

      <Card>
        <CardHeader><CardTitle className="text-base">Verification-required fields</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <ConfirmableField fieldKey="surname" label="Surname" hasValue={pf.hasVal("surname")} confirmed={pf.confirmed.surname} confirmedBy={pf.meta.surname?.by} confirmedAt={pf.meta.surname?.at} onConfirm={() => pf.setConfirmed((c) => ({ ...c, surname: true }))}>
            <Input value={f.surname || ""} onChange={(e) => pf.setConfirmable("surname", e.target.value)} className="h-11" data-testid="caregiver-surname-input" />
          </ConfirmableField>
          <ConfirmableField fieldKey="id_number" label="ID / Passport number" hasValue={pf.hasVal("id_number")} confirmed={pf.confirmed.id_number} confirmedBy={pf.meta.id_number?.by} confirmedAt={pf.meta.id_number?.at} onConfirm={() => pf.setConfirmed((c) => ({ ...c, id_number: true }))}>
            <Input value={f.id_number || ""} onChange={(e) => pf.setConfirmable("id_number", e.target.value)} className="h-11" data-testid="caregiver-id_number-input" />
          </ConfirmableField>
          <IdCheckHint
            idNumber={f.id_number}
            idType={f.id_type}
            excludeCaregiver={cgId}
            currentDob={f.date_of_birth}
            currentSex={f.sex}
            onApplyDob={(v) => pf.setConfirmable("date_of_birth", v)}
            onApplySex={(v) => pf.set("sex", v)}
          />
          <ConfirmableField fieldKey="date_of_birth" label="Date of birth" hasValue={pf.hasVal("date_of_birth")} confirmed={pf.confirmed.date_of_birth} confirmedBy={pf.meta.date_of_birth?.by} confirmedAt={pf.meta.date_of_birth?.at} onConfirm={() => pf.setConfirmed((c) => ({ ...c, date_of_birth: true }))}>
            <DateField value={f.date_of_birth} onChange={(v) => pf.setConfirmable("date_of_birth", v)} testId="date-picker-caregiver-dob" />
          </ConfirmableField>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Personal details</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div className="space-y-1.5"><Label>First name</Label><Input value={f.name || ""} onChange={(e) => pf.set("name", e.target.value)} className="h-11" data-testid="caregiver-name-input" /></div>
          <div className="space-y-1.5"><Label>Known as</Label><Input value={f.known_as || ""} onChange={(e) => pf.set("known_as", e.target.value)} className="h-11" /></div>
          <ChoiceSelect label="ID type" value={f.id_type} onChange={(v) => pf.set("id_type", v)} options={choices.id_type} testId="caregiver-id_type-select" />
          <div className="space-y-1.5"><Label>Nationality</Label><Input value={f.nationality || ""} onChange={(e) => pf.set("nationality", e.target.value)} className="h-11" /></div>
          <ChoiceSelect label="Sex" value={f.sex} onChange={(v) => pf.set("sex", v)} options={choices.sex} testId="caregiver-sex-select" />
          <ChoiceSelect label="Race" value={f.race} onChange={(v) => pf.set("race", v)} options={choices.race} testId="caregiver-race-select" />
          <ChoiceSelect label="Marital status" value={f.marital_status} onChange={(v) => pf.set("marital_status", v)} options={choices.marital_status} testId="caregiver-marital-select" />
          <ChoiceSelect label="Headship type" value={f.headship_type} onChange={(v) => pf.set("headship_type", v)} options={choices.headship_type} testId="caregiver-headship-select" />
          <div className="space-y-1.5"><Label>Cell number</Label><Input value={f.cell_number || ""} onChange={(e) => pf.set("cell_number", e.target.value)} className="h-11" /></div>
          <div className="space-y-1.5"><Label>Home language</Label><Input value={f.home_language || ""} onChange={(e) => pf.set("home_language", e.target.value)} className="h-11" /></div>
          <div className="space-y-1.5"><Label>Date joined</Label><DateField value={f.date_joined} onChange={(v) => pf.set("date_joined", v)} testId="date-picker-caregiver-joined" /></div>
          <div className="flex items-center gap-3 pt-6"><Checkbox checked={!!f.disability} onCheckedChange={(v) => pf.set("disability", !!v)} data-testid="caregiver-disability-checkbox" /><Label>Has a disability</Label></div>
          {f.disability && (
            <div className="space-y-1.5 sm:col-span-2"><Label>Disability description</Label><Textarea value={f.disability_description || ""} onChange={(e) => pf.set("disability_description", e.target.value)} /></div>
          )}
        </CardContent>
      </Card>

      {isAdmin && (
        <Card data-testid="caregiver-login-card">
          <CardHeader>
            <CardTitle className="text-base">{hasLogin ? "Caregiver login" : "Give this caregiver a login"}</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <p className="text-sm text-muted-foreground sm:col-span-2">
              {hasLogin
                ? "This caregiver can already sign in. Change the username or set a new password below, then save."
                : "Optional. They will only see this household file and cannot change office records."}
            </p>
            <div className="space-y-1.5">
              <Label>Username</Label>
              <Input value={loginUsername} onChange={(e) => setLoginUsername(e.target.value)} data-testid="caregiver-login-username" />
            </div>
            <div className="space-y-1.5">
              <Label>{hasLogin ? "New password" : "Password"}</Label>
              <Input type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} data-testid="caregiver-login-password" />
            </div>
          </CardContent>
        </Card>
      )}

      <div className="sticky bottom-0 flex items-center justify-between border-t border-slate-200 bg-white/95 p-3 backdrop-blur">
        <p className={pf.blocked ? "text-sm text-amber-800" : "text-sm text-emerald-800"} data-testid="save-blocked-unconfirmed-message">
          {pf.blocked ? "Confirm the highlighted fields before saving." : "All required confirmations complete."}
        </p>
        <Button onClick={submit} disabled={saving || pf.blocked} className="gap-2 bg-slate-900 hover:bg-slate-800" data-testid="caregiver-save-button">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save caregiver
        </Button>
      </div>
    </div>
  );
}
