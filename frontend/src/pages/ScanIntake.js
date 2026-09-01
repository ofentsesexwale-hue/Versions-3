import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Loader2, ScanLine, Save } from "lucide-react";
import { toast } from "sonner";
import api, { fetchFileObjectUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmableField } from "@/components/ConfirmableField";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";
const TRIO = new Set([
  "caregiver.surname", "caregiver.id_number", "caregiver.date_of_birth",
  "member.surname", "member.id_number", "member.date_of_birth",
]);

function PagePreview({ url }) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    if (!url) return undefined;
    let objectUrl = "";
    let alive = true;
    fetchFileObjectUrl(url).then((u) => {
      if (!alive) {
        URL.revokeObjectURL(u);
        return;
      }
      objectUrl = u;
      setSrc(u);
    }).catch(() => {});
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);
  if (!src) return <div className="flex h-48 items-center justify-center rounded-2xl bg-white/40 text-sm text-muted-foreground">No page image</div>;
  return <img src={src} alt="Scanned page" className="max-h-80 w-full rounded-2xl object-contain bg-white/50" />;
}

export default function ScanIntake() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const preHousehold = params.get("household");
  const [files, setFiles] = useState([]);
  const [reading, setReading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [job, setJob] = useState(null);

  const err = (e) => e?.response?.data?.detail || "Could not read that scan";

  const start = async () => {
    if (!files.length) {
      toast.error("Choose a PDF or photo of the paper file");
      return;
    }
    setReading(true);
    try {
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f));
      if (preHousehold) fd.append("household", preHousehold);
      const res = await api.post("/scan-intake/", fd);
      setJob(res.data);
      toast.success("Pages read — check every field before saving");
    } catch (e) {
      toast.error(err(e));
    } finally {
      setReading(false);
    }
  };

  const patchPages = (pages) => setJob((j) => ({ ...j, pages }));

  const setFormType = async (pageId, formType) => {
    const pages = job.pages.map((p) => (p.id === pageId ? { ...p, form_type: formType } : p));
    patchPages(pages);
    try {
      const res = await api.patch(`/scan-intake/${job.id}/`, { pages: [{ id: pageId, form_type: formType }] });
      setJob(res.data);
    } catch (e) {
      toast.error(err(e));
    }
  };

  const setField = (pageId, index, patch) => {
    patchPages(job.pages.map((p) => {
      if (p.id !== pageId) return p;
      const fields = p.fields.map((f, i) => (i === index ? { ...f, ...patch } : f));
      return { ...p, fields };
    }));
  };

  const confirm = async () => {
    setSaving(true);
    try {
      const res = await api.post(`/scan-intake/${job.id}/confirm/`, { pages: job.pages });
      toast.success(`Saved to file ${res.data.org_household_number}`);
      navigate(`/households/${res.data.household}`);
    } catch (e) {
      toast.error(err(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-24" data-testid="scan-intake-page">
      <Button variant="ghost" className="gap-2" onClick={() => navigate(-1)}>
        <ArrowLeft className="h-4 w-4" /> Back
      </Button>
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <ScanLine className="h-6 w-6" /> Scan Intake
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Photograph the paper file on a phone (Notes or Photos, save as PDF), then import it here.
          The office reads each page against the DSD templates. Nothing is written to a household until you confirm.
        </p>
      </div>

      {!job && (
        <Card>
          <CardHeader><CardTitle className="text-base">Import pages</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label>PDF or JPEG/PNG</Label>
              <Input type="file" accept={ACCEPT} multiple onChange={(e) => setFiles([...e.target.files])} data-testid="scan-intake-file-input" />
            </div>
            {preHousehold && (
              <p className="text-sm text-muted-foreground">This scan will update household #{preHousehold} if you confirm.</p>
            )}
            <Button onClick={start} disabled={reading} className="gap-2" data-testid="scan-intake-read-button">
              {reading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanLine className="h-4 w-4" />}
              Read pages
            </Button>
          </CardContent>
        </Card>
      )}

      {job && (
        <>
          <p className="rounded-2xl bg-amber-100/80 px-4 py-3 text-sm text-amber-950">
            Office OCR is local (Tesseract when installed). Handwriting and tick-boxes are often wrong — amber fields need a careful check.
            Nothing was sent to a cloud OCR service.
          </p>
          {job.pages.map((page) => (
            <Card key={page.id} data-testid={`scan-page-${page.id}`}>
              <CardHeader>
                <CardTitle className="text-base">Page {page.index + 1}</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-5 lg:grid-cols-2">
                <PagePreview url={page.image_url} />
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <Label>DSD template</Label>
                    <Select value={page.form_type || "unknown"} onValueChange={(v) => setFormType(page.id, v)}>
                      <SelectTrigger data-testid={`scan-form-type-${page.id}`}><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {(job.form_types || []).map((t) => (
                          <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Suggested {page.form_label} ({Math.round((page.form_confidence || 0) * 100)}% match). Change this if the page is the wrong form.
                    </p>
                  </div>
                  {(page.fields || []).length === 0 && (
                    <p className="text-sm text-muted-foreground">No fields could be read on this page. Choose the correct template or type the file in as usual.</p>
                  )}
                  {(page.fields || []).map((field, i) => {
                    const trio = TRIO.has(field.target);
                    const inner = (
                      <Input
                        value={field.value || ""}
                        onChange={(e) => setField(page.id, i, { value: e.target.value })}
                        className={field.low_confidence ? "border-amber-400" : ""}
                      />
                    );
                    if (!trio) {
                      return (
                        <div key={`${page.id}-${i}`} className="space-y-1">
                          <Label>{field.label}</Label>
                          {inner}
                          {field.low_confidence && <p className="text-xs text-amber-800">Low confidence — check against the page.</p>}
                        </div>
                      );
                    }
                    return (
                      <ConfirmableField
                        key={`${page.id}-${i}`}
                        fieldKey={field.target}
                        label={field.label}
                        hasValue={!!(field.value || "").trim()}
                        confirmed={!!field.confirmed}
                        onConfirm={() => setField(page.id, i, { confirmed: true })}
                      >
                        {inner}
                      </ConfirmableField>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          ))}
          <div className="sticky bottom-0 flex justify-end gap-2 border-t border-white/50 bg-[#f3ead8]/95 p-3">
            <Button variant="outline" onClick={() => setJob(null)}>Start over</Button>
            <Button onClick={confirm} disabled={saving} className="gap-2" data-testid="scan-intake-confirm-button">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save to case file
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
