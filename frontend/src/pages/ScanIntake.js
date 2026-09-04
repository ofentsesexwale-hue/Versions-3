import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Camera, ImagePlus, Loader2, ScanLine, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmableField } from "@/components/ConfirmableField";
import { IdCheckHint } from "@/components/IdCheckHint";
import OfficialFormCanvas from "@/components/official/OfficialFormCanvas";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.webp,.heic,.heif,application/pdf,image/png,image/jpeg,image/webp,image/heic,image/*";
const TRIO_FIELDS = new Set(["surname", "id_number", "date_of_birth"]);

// Surname, ID and date of birth need a person to sign them off, for every
// member slot on the sheet and not just the first. Mirrors
// needs_staff_confirmation() in backend/core/form_io.py.
function needsConfirm(target) {
  const parts = String(target || "").split(".");
  if (parts.length === 2 && parts[0] === "caregiver") return TRIO_FIELDS.has(parts[1]);
  if (parts.length === 3 && parts[0] === "member" && /^\d+$/.test(parts[1])) {
    return TRIO_FIELDS.has(parts[2]);
  }
  return false;
}

// One field now stands for a whole tick group and carries the group's options,
// so its value is the chosen option rather than an "X" on a single box.
const isGroup = (f) => f.kind === "checkbox" && Array.isArray(f.options) && f.options.length > 0;

function fieldsToValues(fields) {
  const values = {};
  (fields || []).forEach((f) => {
    if (!f.target || f.value === undefined || f.value === "") return;
    if (isGroup(f)) {
      values[f.target] = f.value;
    } else if (f.kind === "checkbox" && f.option && f.value && f.value !== "X") {
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
    if (isGroup(f)) {
      const picked = f.options.find((o) => String(o) === String(next));
      return { ...f, value: picked || "", option: picked || undefined };
    }
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
  const byTarget = new Map();
  (pages || []).forEach((p) => {
    (p.fields || []).forEach((f) => {
      if (!f.target) return;
      const value = (f.value || "").toString().trim();
      // A field left blank because two readings disagreed still belongs in the
      // summary: the note is the only place staff learn about the clash.
      const flagged = !!(f.note || f.conflict || f.invalid_id);
      if (!value && !flagged) return;
      if (value) values[f.target] = f.kind === "checkbox" && f.option ? f.option : f.value;
      const existing = byTarget.get(f.target);
      if (existing) {
        if (!existing.value && value) existing.value = values[f.target];
        if (!existing.note && f.note) existing.note = f.note;
        return;
      }
      const row = {
        target: f.target,
        label: f.label,
        value: value ? values[f.target] : "",
        confirmed: f.confirmed,
        note: f.note || "",
      };
      byTarget.set(f.target, row);
      rows.push(row);
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
  const [duplicates, setDuplicates] = useState(null);

  const err = (e) => {
    const data = e?.response?.data || {};
    const detail = data.detail || "Could not read that photo";
    if (data.conflicts?.length) {
      const first = data.conflicts[0];
      const readings = (first.values || [])
        .map((v) => `“${v.value}” on photo ${(v.page_index ?? 0) + 1}`)
        .join(" and ");
      return `${detail} ${first.label}: ${readings}.`;
    }
    if (data.unconfirmed?.length) return `${detail} (${data.unconfirmed.join(", ")})`;
    return detail;
  };

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
    setDuplicates(null);
    patchPages(job.pages.map((p) => {
      if (p.id !== pageId) return p;
      const fields = p.fields.map((f, i) => (i === index ? { ...f, ...patch } : f));
      return { ...p, fields };
    }));
  };

  const setPageValues = (pageId, values) => {
    setDuplicates(null);
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

  const confirm = async (acceptDuplicates = false) => {
    setSaving(true);
    try {
      const res = await api.post(`/scan-intake/${job.id}/confirm/`, {
        pages: job.pages,
        ...(acceptDuplicates ? { accept_duplicates: true } : {}),
      });
      setDuplicates(null);
      toast.success(`Saved to file ${res.data.org_household_number}`);
      if (res.data.held_back?.length) {
        toast.warning(res.data.detail, { duration: 12000 });
      }
      navigate(`/households/${res.data.household}`);
    } catch (e) {
      const found = e?.response?.data?.duplicates;
      setDuplicates(found?.length ? found : null);
      toast.error(err(e));
    } finally {
      setSaving(false);
    }
  };

  const merged = job ? mergedFromPages(job.pages) : { values: {}, rows: [] };
  // Readings the app could not attribute to a person, e.g. an ID number found
  // loose in the page text. Shown so nothing is lost, never written.
  const unplaced = (job?.pages || []).flatMap((p) =>
    (p.fields || []).filter((f) => !f.target && (f.value || "").trim()),
  );

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
              <div className="space-y-2 text-sm" data-testid="scan-engine-status">
                <p
                  className={
                    engine.trocr || engine.trocr_ready || engine.rapidocr
                      ? "text-emerald-800"
                      : "border border-amber-300 bg-amber-50 px-3 py-2 text-amber-950"
                  }
                >
                  {engine.message}
                </p>
                <ul className="grid gap-1 sm:grid-cols-2 text-slate-700">
                  <li data-testid="scan-engine-trocr">
                    TrOCR (handwriting):{" "}
                    {engine.trocr
                      ? "loaded"
                      : engine.trocr_ready
                        ? "ready — loads on first crop"
                        : engine.trocr_error
                          ? `not loaded (${engine.trocr_error})`
                          : "not loaded"}
                  </li>
                  <li data-testid="scan-engine-qwen">
                    Qwen2.5-VL (fallback):{" "}
                    {engine.qwen
                      ? "loaded"
                      : engine.qwen_ready
                        ? "ready — loads when TrOCR is weak"
                        : engine.qwen_error
                          ? `not loaded (${engine.qwen_error})`
                          : "not loaded"}
                  </li>
                  <li data-testid="scan-engine-rapidocr">
                    RapidOCR (printed / ID): {engine.rapidocr ? "loaded" : "not loaded"}
                  </li>
                  <li data-testid="scan-engine-tesseract">
                    Tesseract (printed / ID): {engine.tesseract ? "loaded" : "not loaded"}
                  </li>
                </ul>
              </div>
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
                    const pageField = (job.pages || []).flatMap((p) => p.fields || []).find((f) => f.target === row.target);
                    const note = row.note ? (
                      <p className="mt-2 flex items-start gap-1.5 text-xs text-amber-800" data-testid={`scan-note-${row.target}`}>
                        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {row.note}
                      </p>
                    ) : null;
                    const idHint = row.target.endsWith("id_number") ? (
                      <div className="mt-2">
                        <IdCheckHint
                          idNumber={row.value}
                          idType={merged.values[`${row.target.replace(/\.id_number$/, "")}.id_type`]}
                          householdId={preHousehold || undefined}
                        />
                      </div>
                    ) : null;
                    if (!needsConfirm(row.target)) {
                      return (
                        <div key={row.target} className="space-y-1">
                          <Label>{row.label}</Label>
                          <p className="rounded border border-slate-200 bg-white px-3 py-2 text-sm">{row.value}</p>
                          {note}
                          {idHint}
                        </div>
                      );
                    }
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
                        {note}
                        {idHint}
                      </ConfirmableField>
                    );
                  })}
                </div>
              )}
              {unplaced.length > 0 && (
                <div
                  className="rounded-lg border border-amber-300 bg-amber-50/60 p-3"
                  data-testid="scan-unplaced-readings"
                >
                  <p className="flex items-center gap-1.5 text-sm font-medium text-amber-900">
                    <AlertTriangle className="h-4 w-4" /> Read on the paper, but not placed
                  </p>
                  <ul className="mt-2 space-y-2 text-sm text-amber-950">
                    {unplaced.map((f, i) => (
                      <li key={`${f.label}-${i}`}>
                        <span className="font-medium">{f.value}</span> — {f.note || f.label}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-amber-900">
                    These are not saved. Type them onto the right person below.
                  </p>
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
                        const pageFields = page.fields || [];
                        const hit = pageFields.find((x) => x.target === f.target && (x.option || "") === (f.option || ""))
                          // A tick group the app could not read has no chosen
                          // option, so flag every box in the group for a look.
                          || pageFields.find((x) => x.target === f.target && isGroup(x));
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
                        const trio = needsConfirm(field.target);
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
                  {hasCanvas && (page.fields || []).filter((f) => needsConfirm(f.target)).map((field) => (
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
          {duplicates && (
            <div
              className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"
              data-testid="scan-duplicate-warning"
            >
              <p className="flex items-center gap-1.5 font-medium">
                <AlertTriangle className="h-4 w-4" />
                {duplicates.some((d) => d.matches?.length)
                  ? "This ID is already on another file"
                  : "The same ID was read onto two people"}
              </p>
              {duplicates.map((dup) => (
                <div key={dup.target} className="mt-2">
                  <p>
                    {dup.label} {dup.id_number}
                  </p>
                  <ul className="mt-1 space-y-1">
                    {(dup.matches || []).map((m) => (
                      <li key={`${m.role}-${m.household_id}`}>
                        <Link className="underline" to={`/households/${m.household_id}`}>
                          {m.name || "Unnamed"} · {m.org_household_number} ({m.role})
                        </Link>
                      </li>
                    ))}
                    {(dup.same_scan || []).map((label) => (
                      <li key={label}>Also read as {label} on this scan</li>
                    ))}
                  </ul>
                </div>
              ))}
              <p className="mt-3 text-amber-900">
                Check whether this is the same person. If it is somebody else, correct the ID
                before saving.
              </p>
            </div>
          )}
          <div className="sticky bottom-0 flex justify-end gap-2 border-t bg-[#f3ead8]/95 p-3">
            <Button variant="outline" onClick={() => { setJob(null); setFiles([]); }}>Start over</Button>
            {duplicates ? (
              <Button
                variant="secondary"
                onClick={() => confirm(true)}
                disabled={saving}
                className="gap-2 bg-amber-500 text-white hover:bg-amber-600"
                data-testid="scan-intake-save-anyway-button"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save anyway
              </Button>
            ) : (
              <Button onClick={() => confirm()} disabled={saving} className="gap-2" data-testid="scan-intake-confirm-button">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save to case file
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
