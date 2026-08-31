import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { DateField } from "@/components/DateField";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { CASE_STATUS_LABELS } from "@/lib/constants";

const FILE_FIELD = [
  "org_household_number",
  "Office file number",
  true,
  "The code this office gives the family file, e.g. SI-0041. Search uses this number.",
];

const ADDRESS_FIELDS = [
  ["house_number", "Street / stand number", false, "The number on the house or stand, e.g. 12. Not the office file number."],
  ["street", "Street", false, ""],
  ["town", "Town", false, ""],
  ["province", "Province", false, ""],
  ["district", "District", false, ""],
  ["municipality", "Municipality", false, ""],
  ["ward", "Ward", false, ""],
];

export default function HouseholdForm() {
  const { id } = useParams();
  const isEdit = !!id;
  const navigate = useNavigate();
  const { user } = useAuth();
  const canAssign = user?.role === "supervisor" || user?.role === "admin";
  const [form, setForm] = useState({ nationality: "South African" });
  const [dateRegistered, setDateRegistered] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [assigned, setAssigned] = useState([]);
  const [caseworkers, setCaseworkers] = useState([]);
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (canAssign) {
      api.get("/users/").then((res) =>
        setCaseworkers(res.data.filter((u) => u.role === "case-worker"))
      );
    }
    if (isEdit) {
      api.get(`/households/${id}/`).then((res) => {
        setForm(res.data);
        setDateRegistered(res.data.date_registered);
        setAssigned(res.data.assigned_to || []);
        setLoading(false);
      });
    }
  }, [id]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.org_household_number) {
      toast.error("Office file number is required");
      return;
    }
    setSaving(true);
    const payload = { ...form, date_registered: dateRegistered, assigned_to: assigned };
    try {
      let res;
      if (isEdit) {
        res = await api.patch(`/households/${id}/`, payload);
      } else {
        res = await api.post("/households/", payload);
      }
      toast.success("Household saved");
      navigate(`/households/${res.data.id}`);
    } catch (e) {
      if (e?.response?.status === 409) {
        toast.error("This record was modified by another user. Please refresh and re-apply your changes.");
        const fresh = await api.get(`/households/${id}/`);
        setForm(fresh.data);
        setAssigned(fresh.data.assigned_to || []);
      } else {
        toast.error("Could not save household");
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div data-testid="loading-state">Loading...</div>;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Button variant="ghost" onClick={() => navigate(-1)} className="gap-2" data-testid="back-button">
        <ArrowLeft className="h-4 w-4" /> Back
      </Button>
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          {isEdit ? "Edit household" : "New household"}
        </h1>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Office file</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label>
              {FILE_FIELD[1]}
              <span className="ml-1 text-rose-600">*</span>
            </Label>
            <Input
              value={form[FILE_FIELD[0]] || ""}
              onChange={(e) => set(FILE_FIELD[0], e.target.value)}
              className="h-11"
              placeholder="e.g. SI-0041"
              data-testid={`household-${FILE_FIELD[0]}-input`}
            />
            <p className="text-[13px] text-muted-foreground">{FILE_FIELD[3]}</p>
          </div>
          <div className="space-y-1.5">
            <Label>Date registered</Label>
            <DateField value={dateRegistered} onChange={setDateRegistered} testId="date-picker-date_registered" />
          </div>
          <div className="space-y-1.5">
            <Label>Case status</Label>
            <Select value={form.status || "open"} onValueChange={(v) => set("status", v)}>
              <SelectTrigger className="h-11" data-testid="household-status-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {Object.entries(CASE_STATUS_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          {form.status && form.status !== "open" && (
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Status reason / notes</Label>
              <Input value={form.status_reason || ""} onChange={(e) => set("status_reason", e.target.value)} data-testid="household-status-reason-input" />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Home address</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          {ADDRESS_FIELDS.map(([key, label, required, hint]) => (
            <div key={key} className="space-y-1.5">
              <Label>
                {label}
                {required && <span className="ml-1 text-rose-600">*</span>}
              </Label>
              <Input
                value={form[key] || ""}
                onChange={(e) => set(key, e.target.value)}
                className="h-11"
                data-testid={`household-${key}-input`}
              />
              {hint ? <p className="text-[13px] text-muted-foreground">{hint}</p> : null}
            </div>
          ))}
        </CardContent>
      </Card>

      {canAssign && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Assign to case workers</CardTitle>
            <p className="text-sm text-slate-600">Case workers only see households assigned to them.</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {caseworkers.length === 0 && <p className="text-sm text-slate-500">No case workers available.</p>}
            {caseworkers.map((cw) => (
              <label key={cw.id} className="flex items-center gap-3" data-testid={`assign-cw-${cw.id}`}>
                <Checkbox
                  checked={assigned.includes(cw.id)}
                  onCheckedChange={(v) =>
                    setAssigned((a) => (v ? [...a, cw.id] : a.filter((x) => x !== cw.id)))
                  }
                />
                <span className="text-sm text-slate-800">{cw.full_name} ({cw.username})</span>
              </label>
            ))}
          </CardContent>
        </Card>
      )}

      <div className="flex justify-end">
        <Button onClick={submit} disabled={saving} className="gap-2 bg-slate-900 hover:bg-slate-800" data-testid="household-save-button">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save household
        </Button>
      </div>
    </div>
  );
}
