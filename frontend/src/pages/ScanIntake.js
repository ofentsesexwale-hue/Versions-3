import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Camera, ImagePlus, Loader2, ScanLine, Save, Trash2 } from "lucide-react";
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

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.webp,.heic,.heif,application/pdf,image/png,image/jpeg,image/webp,image/heic,image/*";
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

function mergedFromPages(pages) {
  const values = {};
  const rows = [];
  const seen = new Set();
  (pages || []).forEach((p) => {
    (p.fields || []).forEach((f) => {
      if (!f.target || !(f.value || "").toString().trim()) return;
      values[f.target] = f.kind === "checkbox" && f.option ? f.option : f.value;
      if (seen.has(f.target)) return;
      seen.add(f.target);
      rows.push({ target: f.target, label: f.label, value: values[f.target], confirmed: f.confirmed });
    });
  });
  return { values, rows };
}

export default function ScanIntake() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const preHousehold = params.get("household");
  const isNewHousehold = location.pathname.startsWith("/households/new") && !preHousehold;
  const [files, setFiles] = useState([]);
  const [reading, setReading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [job, setJob] = useState(null);
  const [atlases, setAtlases] = useState({});
  const [pageTab, setPageTab] = useState({});
  const [openText, setOpenText] = useState({});
  const [engine, setEngine] = useState(null);

  const err = (e) => e?.response?.data?.detail || "Could not read that photo";

  useEffect(() => {
    api.get("/scan-intake/engine/").then((res) => setEngine(res.data)).catch(() => {});
  }, []);

  useEffect(() => {
    api.get("/official-forms/").then((res) => {
      const map = {};
      (res.data.forms || []).forEach((f) => { map[f.code] = f; });
      setAtlases(map);
    }).catch(() => {});
  }, []);

  const addFiles = (list) => {
    const next = Array.from(list || []);
    if (!next.length) return;
    setFiles((prev) => [...prev, ...next]);
  };

  const start = async () => {
    if (!files.length) {
      toast.error("Take photos of the physical file, then upload them here");
      return;
    }
    setReading(true);
    try {
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f));
      if (preHousehold) fd.append("household", preHousehold);
      const res = await api.post("/scan-intake/", fd, { timeout: 300000 });
      setJob(res.data);
      toast.success(`Read ${res.data.pages?.length || 0} page(s) — check names, ID and dates before saving`);
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

  const confirmTrio = (target) => {
    patchPages(job.pages.map((p) => ({
      ...p,
      fields: (p.fields || []).map((f) => (f.target === target ? { ...f, confirmed: true } : f)),
    })));
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

  const merged = job ? mergedFromPages(job.pages) : { values: {}, rows: [] };

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-24" data-testid="scan-intake-page">
      <Button variant="ghost" className="gap-2" onClick={() => navigate(-1)}>
        <ArrowLeft className="h-4 w-4" /> Back
      </Button>
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <ScanLine className="h-6 w-6" />
          {isNewHousehold ? "New household from the physical file" : "Scan Intake"}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {isNewHousehold
            ? "Photograph each form you have with your iPhone. You do not need a complete file — if C01 is missing, upload CW 05 and the other pages you have. The office PC identifies the sheet in each photo and fills that digital form. Handwriting is checked; junk text is left blank for you to type."
            : "Photograph the paper file. Pages are aligned to the official DSD/CCG sheet. Nothing is written until you confirm."}
        </p>
        {isNewHousehold && (
          <p className="mt-2 text-sm">
            <Link to="/households/new/typed" className="underline" data-testid="type-household-instead-link">
              Type the address instead
            </Link>
            {" "}if this file has no photos yet.
          </p>
        )}
      </div>

      {!job && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">1. Upload photos of the physical file</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              iPhone photos work as HEIC or JPEG. Fill the paper in the frame (avoid the desk). Upload only the pages that exist in that file. Printed names and ID numbers read better than pencil.
            </p>
            {engine && (
              <p
                className={`text-sm ${engine.rapidocr ? "text-emerald-800" : "border border-amber-300 bg-amber-50 px-3 py-2 text-amber-950"}`}
                data-testid="scan-engine-status"
              >
                {engine.message}
              </p>
            )}
            <div className="flex flex-col gap-3 sm:flex-row">
              <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-3 text-sm font-medium">
                <Camera className="h-4 w-4" />
                Take photo
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="sr-only"
                  onChange={(e) => {
                    addFiles(e.target.files);
                    e.target.value = "";
                  }}
                  data-testid="scan-intake-camera-input"
                />
              </label>
              <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-3 text-sm font-medium">
                <ImagePlus className="h-4 w-4" />
                Choose from album
                <input
                  type="file"
                  accept={ACCEPT}
                  multiple
                  className="sr-only"
                  onChange={(e) => {
                    addFiles(e.target.files);
                    e.target.value = "";
                  }}
                  data-testid="scan-intake-file-input"
                />
              </label>
            </div>
            {files.length > 0 && (
              <ul className="space-y-2 text-sm" data-testid="scan-intake-file-list">
                {files.map((f, i) => (
                  <li key={`${f.name}-${i}`} className="flex items-center justify-between gap-2 border border-slate-200 bg-white/70 px-3 py-2">
                    <span className="truncate">{f.name}</span>
                    <button
                      type="button"
                      className="text-slate-500 hover:text-rose-700"
                      aria-label={`Remove ${f.name}`}
                      onClick={() => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {preHousehold && (
              <p className="text-sm text-muted-foreground">This scan will update household #{preHousehold} if you confirm.</p>
            )}
            <Button onClick={start} disabled={reading || !files.length} className="gap-2" data-testid="scan-intake-read-button">
              {reading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanLine className="h-4 w-4" />}
              {reading ? "Reading text from photos…" : `Read text from ${files.length || 0} photo(s)`}
            </Button>
          </CardContent>
        </Card>
      )}

      {job && (
        <>
          <p className="border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
            Empty name boxes are better than guessed letters. If a name such as Hallie was left blank, type it.
            {job?.engine?.message ? ` ${job.engine.message}.` : ""}
          </p>
          {(job.forms_found || []).length > 0 && (
            <p className="text-sm" data-testid="scan-forms-found">
              Identified in this batch: {(job.forms_found || []).map((f) => f.label).join(', ')}.
              {(job.forms_found || []).some((f) => f.value === 'intake') && !(job.forms_found || []).some((f) => f.value === 'c01')
                ? ' C01 was not in these photos — CW 05 can still be saved. Add C01 later from the household file.'
                : ''}
            </p>
          )}
          <Card data-testid="scan-extracted-summary">
            <CardHeader>
              <CardTitle className="text-base">2. Text read from the photos</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {merged.rows.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No household fields could be read. Open a page below, type the missing values, or use “Type the address instead”. The photos still attach when you save.
                </p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {merged.rows.map((row) => {
                    const trio = TRIO.has(row.target);
                    if (!trio) {
                      return (
                        <div key={row.target} className="space-y-1">
                          <Label>{row.label}</Label>
                          <p className="rounded border border-slate-200 bg-white px-3 py-2 text-sm">{row.value}</p>
                        </div>
                      );
                    }
                    const pageField = (job.pages || []).flatMap((p) => p.fields || []).find((f) => f.target === row.target);
                    return (
                      <ConfirmableField
                        key={row.target}
                        fieldKey={row.target}
                        label={row.label}
                        hasValue={!!String(row.value || "").trim()}
                        confirmed={!!pageField?.confirmed}
                        onConfirm={() => confirmTrio(row.target)}
                      >
                        <span className="text-sm">{row.value}</span>
                      </ConfirmableField>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
          {job.pages.map((page) => {
            const atlas = atlases[page.form_type];
            const values = fieldsToValues(page.fields);
            const tab = pageTab[page.id] ?? page.form_page ?? 0;
            const hasCanvas = atlas && (atlas.blanks || []).length;
            return (
              <Card key={page.id} data-testid={`scan-page-${page.id}`}>
                <CardHeader>
                  <CardTitle className="text-base">
                    Photo {page.index + 1}
                    {page.original_name ? ` · ${page.original_name}` : ""}
                    {page.form_type && page.form_type !== 'unknown' ? ` · ${page.form_label} p.${(page.form_page || 0) + 1}` : ' · sheet not identified'}
                  </CardTitle>
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
                      {page.alignment_failed ? " Could not line the photo up with the official blank — text was still read from the picture." : ""}
                      {page.geometry_missing ? " No atlas geometry for this form; the photo will still attach." : ""}
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
                        <p className="text-sm text-muted-foreground">No fields on this page. The photo still attaches, and the text below is kept for checking.</p>
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
                  {hasCanvas && (page.fields || []).filter((f) => TRIO.has(f.target)).map((field) => (
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
                  <button
                    type="button"
                    className="text-sm underline"
                    onClick={() => setOpenText((s) => ({ ...s, [page.id]: !s[page.id] }))}
                    data-testid={`scan-ocr-toggle-${page.id}`}
                  >
                    {openText[page.id] ? "Hide all text from this photo" : "Show all text from this photo"}
                  </button>
                  {openText[page.id] && (
                    <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded border border-slate-200 bg-white p-3 text-xs" data-testid={`scan-ocr-text-${page.id}`}>
                      {page.ocr_text || "(no text could be read from this photo)"}
                    </pre>
                  )}
                </CardContent>
              </Card>
            );
          })}
          <div className="sticky bottom-0 flex justify-end gap-2 border-t bg-[#f3ead8]/95 p-3">
            <Button variant="outline" onClick={() => { setJob(null); setFiles([]); }}>Start over</Button>
            <Button onClick={confirm} disabled={saving} className="gap-2" data-testid="scan-intake-confirm-button">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save to case file
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
