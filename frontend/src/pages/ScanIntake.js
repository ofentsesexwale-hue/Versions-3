import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Loader2, ScanLine, Save } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmableField } from "@/components/ConfirmableField";
import OfficialFormCanvas from "@/components/official/OfficialFormCanvas";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";
const TRIO = new Set([
  "caregiver.surname", "caregiver.id_number", "caregiver.date_of_birth",
  "member.surname", "member.id_number", "member.date_of_birth",
  "member.0.surname", "member.0.id_number", "member.0.date_of_birth",
]);

function fieldsToValues(fields) {
  const values = {};
  (fields || []).forEach((f) => {
    if (!f.target || f.value === undefined || f.value === "") return;
    if (f.kind === "checkbox" && f.option && f.value && f.value !== "X") {
      values[f.target] = f.option;
    } else if (f.kind === "checkbox") {
      if (f.value === "X" || f.value === true) values[f.target] = f.option || "X";
    } else {
      values[f.target] = f.value;
    }
  });
  return values;
}

function mergeValuesIntoFields(fields, values) {
  return (fields || []).map((f) => {
    if (!f.target || !(f.target in values)) return f;
    const next = values[f.target];
    if (f.kind === "checkbox") {
      const on = f.option ? String(next) === String(f.option) : !!next;
      return { ...f, value: on ? (f.option || "X") : "" };
    }
    return { ...f, value: next };
  });
}

export default function ScanIntake() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const preHousehold = params.get("household");
  const [files, setFiles] = useState([]);
  const [reading, setReading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [job, setJob] = useState(null);
  const [atlases, setAtlases] = useState({});
  const [pageTab, setPageTab] = useState({});

  const err = (e) => e?.response?.data?.detail || "Could not read that scan";

  useEffect(() => {
    api.get("/official-forms/").then((res) => {
      const map = {};
      (res.data.forms || []).forEach((f) => { map[f.code] = f; });
      setAtlases(map);
    }).catch(() => {});
  }, []);

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

  const setPageValues = (pageId, values) => {
    patchPages(job.pages.map((p) => {
      if (p.id !== pageId) return p;
      return { ...p, fields: mergeValuesIntoFields(p.fields, values) };
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

  const engineMsg = job?.engine && !job.engine.scan_engine ? job.engine.message : "";

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-24" data-testid="scan-intake-page">
      <Button variant="ghost" className="gap-2" onClick={() => navigate(-1)}>
        <ArrowLeft className="h-4 w-4" /> Back
      </Button>
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <ScanLine className="h-6 w-6" /> Scan Intake
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Photograph the paper file. Pages are aligned to the official DSD/CCG sheet. Nothing is written until you confirm.
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
          <p className="border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
            OCR stays on this PC. Handwriting and ticks need a check. Amber means low confidence.
            {engineMsg ? ` ${engineMsg}.` : ""}
          </p>
          {job.pages.map((page) => {
            const atlas = atlases[page.form_type];
            const values = fieldsToValues(page.fields);
            const tab = pageTab[page.id] || 0;
            const hasCanvas = atlas && (atlas.blanks || []).length;
            return (
              <Card key={page.id} data-testid={`scan-page-${page.id}`}>
                <CardHeader>
                  <CardTitle className="text-base">Page {page.index + 1}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-1.5 max-w-md">
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
                      Suggested {page.form_label} ({Math.round((page.form_confidence || 0) * 100)}% match).
                      {page.alignment_failed ? " Alignment failed — keyword extract is shown." : ""}
                      {page.geometry_missing ? " No atlas geometry for this form; page will still attach." : ""}
                    </p>
                  </div>
                  {hasCanvas ? (
                    <OfficialFormCanvas
                      code={page.form_type}
                      fields={(atlas.fields || []).map((f) => {
                        const hit = (page.fields || []).find((x) => x.target === f.target && (x.option || "") === (f.option || ""));
                        return { ...f, low_confidence: hit?.low_confidence };
                      })}
                      values={values}
                      onChange={(v) => setPageValues(page.id, v)}
                      mode="scan-review"
                      orientation={atlas.orientation}
                      pages={atlas.pages || atlas.blanks.length}
                      page={tab}
                      onPage={(i) => setPageTab((s) => ({ ...s, [page.id]: i }))}
                      scanImageUrl={page.warped_url || page.image_url}
                      alignmentFailed={page.alignment_failed}
                    />
                  ) : (
                    <div className="grid gap-5 lg:grid-cols-2">
                      {(page.fields || []).length === 0 && (
                        <p className="text-sm text-muted-foreground">No fields could be read. Choose the template or type the file as usual.</p>
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
                  )}
                  {hasCanvas && (page.fields || []).filter((f) => TRIO.has(f.target)).map((field, i) => (
                    <ConfirmableField
                      key={`trio-${page.id}-${field.target}`}
                      fieldKey={field.target}
                      label={field.label}
                      hasValue={!!(field.value || values[field.target] || "").toString().trim()}
                      confirmed={!!field.confirmed}
                      onConfirm={() => {
                        const idx = page.fields.findIndex((x) => x.target === field.target);
                        if (idx >= 0) setField(page.id, idx, { confirmed: true });
                      }}
                    >
                      <span className="text-sm">{values[field.target] || field.value}</span>
                    </ConfirmableField>
                  ))}
                </CardContent>
              </Card>
            );
          })}
          <div className="sticky bottom-0 flex justify-end gap-2 border-t bg-[#f3ead8]/95 p-3">
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
