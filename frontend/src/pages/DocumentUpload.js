import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DateField } from "@/components/DateField";

export default function DocumentUpload() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const preHousehold = params.get("household");
  const [choices, setChoices] = useState(null);
  const [householdQuery, setHouseholdQuery] = useState("");
  const [results, setResults] = useState([]);
  const [household, setHousehold] = useState(null);
  const [targets, setTargets] = useState([]);
  const [target, setTarget] = useState("");
  const [category, setCategory] = useState("");
  const [label, setLabel] = useState("");
  const [docDate, setDocDate] = useState(new Date().toISOString().slice(0, 10));
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    api.get("/choices/").then((r) => setChoices(r.data));
    if (preHousehold) loadHousehold(preHousehold);
  }, []);

  const loadHousehold = async (hid) => {
    const res = await api.get(`/households/${hid}/`);
    const h = res.data;
    setHousehold(h);
    const t = [{ value: `household:${h.id}`, label: `Household ${h.org_household_number}` }];
    if (h.caregiver) t.push({ value: `caregiver:${h.caregiver.id}`, label: `Caregiver: ${h.caregiver.name} ${h.caregiver.surname}` });
    (h.members || []).forEach((m) => t.push({ value: `householdmember:${m.id}`, label: `Member: ${m.name} ${m.surname}` }));
    setTargets(t);
    setTarget(t[0].value);
  };

  const searchHouseholds = async (e) => {
    e.preventDefault();
    const res = await api.get("/households/", { params: { q: householdQuery } });
    setResults(res.data.results || []);
  };

  const submit = async () => {
    if (!file) return toast.error("Choose a file to upload");
    if (!category) return toast.error("Choose a category");
    if (!target) return toast.error("Choose where to attach the document");
    const [parentType, parentId] = target.split(":");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("parent_type", parentType);
    fd.append("parent_id", parentId);
    fd.append("category", category);
    fd.append("label", label);
    if (docDate) fd.append("date_of_document", docDate);
    setUploading(true);
    try {
      await api.post("/documents/", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Document uploaded");
      navigate(`/households/${household.id}`);
    } catch (e) {
      const data = e?.response?.data;
      toast.error(typeof data === "object" ? JSON.stringify(Object.values(data)[0]) : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  if (!choices) return <div data-testid="loading-state">Loading...</div>;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Button variant="ghost" onClick={() => navigate(-1)} className="gap-2" data-testid="back-button">
        <ArrowLeft className="h-4 w-4" /> Back
      </Button>
      <h1 className="text-2xl font-semibold text-slate-900">Upload supporting document</h1>
      <p className="text-sm text-slate-600">Files are stored exactly as uploaded. No processing is performed.</p>

      {!household ? (
        <Card>
          <CardHeader><CardTitle className="text-base">Find a household</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <form onSubmit={searchHouseholds} className="flex gap-2">
              <Input value={householdQuery} onChange={(e) => setHouseholdQuery(e.target.value)} placeholder="Surname, ID or household number" className="h-11" data-testid="upload-household-search" />
              <Button type="submit" className="h-11">Search</Button>
            </form>
            <div className="divide-y divide-slate-100">
              {results.map((h) => (
                <button key={h.id} onClick={() => loadHousehold(h.id)} className="block w-full px-2 py-2 text-left text-sm hover:bg-slate-50" data-testid={`upload-pick-household-${h.id}`}>
                  <span className="font-medium">{h.org_household_number}</span> - {h.caregiver_name}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader><CardTitle className="text-base">Document details</CardTitle></CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-1.5">
              <Label>Household</Label>
              <div className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                <span>{household.org_household_number}</span>
                {!preHousehold && <Button variant="ghost" size="sm" onClick={() => setHousehold(null)}>Change</Button>}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Attach to</Label>
              <Select value={target} onValueChange={setTarget}>
                <SelectTrigger className="h-11" data-testid="upload-target-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {targets.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Category</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="h-11" data-testid="upload-category-select"><SelectValue placeholder="Select category" /></SelectTrigger>
                <SelectContent>
                  {choices.category.map((c) => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Label</Label>
              <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Birth Certificate" className="h-11" data-testid="upload-label-input" />
            </div>
            <div className="space-y-1.5">
              <Label>Date of document</Label>
              <DateField value={docDate} onChange={setDocDate} testId="date-picker-document" />
            </div>
            <div className="space-y-1.5">
              <Label>File (PDF or image, max 25MB)</Label>
              <Input type="file" accept=".pdf,image/*" onChange={(e) => setFile(e.target.files[0])} className="h-11" data-testid="document-upload-file-input" />
            </div>
            <Button onClick={submit} disabled={uploading} className="w-full gap-2 bg-slate-900 hover:bg-slate-800" data-testid="document-upload-submit">
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} Upload document
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
