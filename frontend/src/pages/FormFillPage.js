import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Loader2, Printer, Save } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { printForm } from "@/lib/print";
import { Button } from "@/components/ui/button";
import OfficialFormCanvas from "@/components/official/OfficialFormCanvas";

export default function FormFillPage() {
  const { code, id } = useParams();
  const [params] = useSearchParams();
  const householdId = id || params.get("household");
  const navigate = useNavigate();
  const [meta, setMeta] = useState(null);
  const [values, setValues] = useState({});
  const [page, setPage] = useState(0);
  const [saving, setSaving] = useState(false);
  const [dupes, setDupes] = useState([]);
  const [errors, setErrors] = useState([]);

  useEffect(() => {
    if (!householdId) return;
    api.get(`/official-forms/${code}/`, { params: { household: householdId } }).then((res) => {
      setMeta(res.data);
      setValues(res.data.values || {});
    }).catch(() => toast.error("Could not load the official form"));
  }, [code, householdId]);

  const idNumber = values["caregiver.id_number"] || "";

  useEffect(() => {
    if (idNumber.replace(/\D/g, "").length < 13) {
      setDupes([]);
      return undefined;
    }
    const t = setTimeout(() => {
      api.get("/id-check/", { params: { q: idNumber, exclude_household: householdId } }).then((res) => {
        setDupes(res.data.duplicates || []);
      }).catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  }, [idNumber, householdId]);

  const save = async () => {
    setSaving(true);
    setErrors([]);
    try {
      const res = await api.put(`/official-forms/${code}/values/`, { household: householdId, values });
      setValues(res.data.values || values);
      toast.success(`Saved ${res.data.org_household_number}`);
      if (res.data.household) navigate(`/households/${res.data.household}`);
    } catch (e) {
      const data = e?.response?.data;
      setErrors([data?.detail || "Could not save"]);
      toast.error(data?.detail || "Could not save");
    } finally {
      setSaving(false);
    }
  };

  if (!meta) {
    return <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }

  return (
    <div className="space-y-4 pb-24" data-testid="form-fill-page">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" className="gap-2" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
        <h1 className="text-xl font-semibold">{meta.official_title || meta.title}</h1>
        <span className="text-xs text-slate-500">Atlas {meta.atlas_version}</span>
      </div>
      <OfficialFormCanvas
        code={code}
        fields={meta.fields}
        values={values}
        onChange={setValues}
        mode="fill"
        orientation={meta.orientation}
        pages={meta.pages || meta.blanks?.length || 1}
        page={page}
        onPage={setPage}
      />
      <aside className="space-y-2 border border-slate-200 bg-white/80 p-3 text-sm" data-testid="form-side-rail">
        {errors.map((err) => <p key={err} className="text-rose-700">{err}</p>)}
        {dupes.length > 0 && (
          <p className="text-amber-900">This ID already appears on another file. Check before you save.</p>
        )}
        <p className="text-slate-600">Type on the official sheet. Print uses this same page. Nothing is stored until you save.</p>
        <div className="flex gap-2">
          <Button onClick={save} disabled={saving} className="gap-2" data-testid="official-form-save">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save to case file
          </Button>
          <Button variant="outline" className="gap-2" onClick={() => printForm(code === "c01" ? "c01" : code, { householdId })}>
            <Printer className="h-4 w-4" /> Print
          </Button>
        </div>
      </aside>
    </div>
  );
}
