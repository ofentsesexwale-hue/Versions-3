import { useEffect, useMemo, useState } from "react";
import { fetchFileObjectUrl } from "@/lib/api";
import SaIdCells from "@/components/official/SaIdCells";

const ZOOM = [0.75, 1, 1.25];

function blankUrl(code, page) {
  return `/api/official-forms/${code}/blank/${page}/`;
}

function isChecked(field, values) {
  const raw = values[field.target];
  if (field.option === undefined || field.option === "") {
    return raw === true || raw === "true" || raw === "Yes" || raw === "X";
  }
  return String(raw) === String(field.option);
}

function OverlayField({ field, values, setValue, mode, focusKey, setFocusKey, crops }) {
  const [x0, y0, x1, y1] = field.box || [0, 0, 0, 0];
  const focused = focusKey === field.target + (field.option || "");
  const crop = (crops || []).find((c) => c.target === field.target && (c.option || "") === (field.option || ""));
  const style = {
    left: `${x0 * 100}%`,
    top: `${y0 * 100}%`,
    width: `${(x1 - x0) * 100}%`,
    height: `${(y1 - y0) * 100}%`,
  };
  const readOnly = mode === "print";
  const cls = `absolute overflow-hidden ${focused ? "outline outline-1 outline-black" : ""}`;

  if (field.kind === "checkbox") {
    return (
      <button
        type="button"
        disabled={readOnly}
        data-testid={`atlas-${field.target}-${field.option || "tick"}`}
        className={`${cls} flex items-center justify-center bg-transparent p-0 text-[12px] font-bold text-black`}
        style={style}
        onClick={() => {
          setFocusKey(field.target + (field.option || ""));
          if (readOnly) return;
          const on = isChecked(field, values);
          setValue(field.target, on ? "" : (field.option ?? "X"));
        }}
      >
        {isChecked(field, values) ? "X" : ""}
      </button>
    );
  }

  if (field.kind === "sa_id") {
    return (
      <div className={cls} style={style} onClick={() => setFocusKey(field.target)}>
        <SaIdCells
          value={values[field.target] || ""}
          disabled={readOnly}
          onChange={(v) => setValue(field.target, v)}
          testId={`atlas-${field.target}`}
        />
      </div>
    );
  }

  const Tag = field.kind === "narrative" ? "textarea" : "input";
  return (
    <Tag
      className={`${cls} h-full w-full resize-none border-0 bg-transparent p-0.5 text-[11px] leading-tight text-black outline-none`}
      style={style}
      value={values[field.target] || ""}
      readOnly={readOnly}
      data-testid={`atlas-${field.target}`}
      onFocus={() => setFocusKey(field.target)}
      onChange={(e) => setValue(field.target, e.target.value)}
    />
  );
}

export default function OfficialFormCanvas({
  code,
  fields,
  values,
  onChange,
  mode = "fill",
  orientation = "portrait",
  pages = 1,
  page = 0,
  onPage,
  scanImageUrl,
  alignmentFailed,
  crops,
}) {
  const [zoom, setZoom] = useState(1);
  const [blankSrc, setBlankSrc] = useState("");
  const [scanSrc, setScanSrc] = useState("");
  const [focusKey, setFocusKey] = useState("");

  useEffect(() => {
    let alive = true;
    let obj = "";
    fetchFileObjectUrl(blankUrl(code, page)).then((u) => {
      if (!alive) {
        URL.revokeObjectURL(u);
        return;
      }
      obj = u;
      setBlankSrc(u);
    }).catch(() => setBlankSrc(""));
    return () => {
      alive = false;
      if (obj) URL.revokeObjectURL(obj);
    };
  }, [code, page]);

  useEffect(() => {
    if (!scanImageUrl) {
      setScanSrc("");
      return undefined;
    }
    let alive = true;
    let obj = "";
    fetchFileObjectUrl(scanImageUrl).then((u) => {
      if (!alive) {
        URL.revokeObjectURL(u);
        return;
      }
      obj = u;
      setScanSrc(u);
    }).catch(() => {});
    return () => {
      alive = false;
      if (obj) URL.revokeObjectURL(obj);
    };
  }, [scanImageUrl]);

  const pageFields = useMemo(
    () => (fields || []).filter((f) => f.page === page),
    [fields, page]
  );

  const setValue = (target, value) => {
    if (!onChange || !target) return;
    onChange({ ...values, [target]: value });
  };

  const mm = orientation === "landscape" ? "w-[297mm]" : "w-[210mm]";

  return (
    <div className="space-y-3" data-testid="official-form-canvas">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {Array.from({ length: pages }).map((_, i) => (
          <button
            key={i}
            type="button"
            className={`border px-2 py-1 ${i === page ? "border-black bg-white" : "border-slate-300 bg-white/60"}`}
            onClick={() => onPage?.(i)}
            data-testid={`form-page-tab-${i}`}
          >
            Page {i + 1}
          </button>
        ))}
        <span className="ml-2 text-slate-500">Zoom</span>
        {ZOOM.map((z) => (
          <button
            key={z}
            type="button"
            className={`border px-2 py-1 ${zoom === z ? "border-black" : "border-slate-300"}`}
            onClick={() => setZoom(z)}
            data-testid={`form-zoom-${Math.round(z * 100)}`}
          >
            {Math.round(z * 100)}%
          </button>
        ))}
        {alignmentFailed && (
          <span className="text-amber-800">Alignment failed — check values against the photo. Keyword extract still shown.</span>
        )}
      </div>
      <div className="overflow-auto bg-[#cfcfcf] p-4">
        <div style={{ transform: `scale(${zoom})`, transformOrigin: "top center" }}>
          <div className={`relative mx-auto bg-white ${mm}`} data-testid="official-sheet">
            {blankSrc ? (
              <img src={blankSrc} alt="Official blank" className="block w-full" draggable={false} />
            ) : (
              <div className="flex aspect-[210/297] items-center justify-center text-sm text-slate-500">Loading official sheet…</div>
            )}
            {pageFields.map((field, i) => (
              <OverlayField
                key={`${field.target}-${field.option || i}`}
                field={field}
                values={values}
                setValue={setValue}
                mode={mode}
                focusKey={focusKey}
                setFocusKey={setFocusKey}
                crops={crops}
              />
            ))}
          </div>
        </div>
      </div>
      {mode === "scan-review" && (
        <div className="grid gap-3 md:grid-cols-2">
          {scanSrc && <img src={scanSrc} alt="Scan" className="max-h-64 w-full object-contain bg-white" />}
          <div className="space-y-2">
            {(pageFields.filter((f) => f.target) || []).map((f) => (
              <button
                key={f.target + (f.option || "")}
                type="button"
                className={`flex w-full items-center justify-between border px-2 py-1 text-left text-xs ${f.low_confidence ? "border-amber-400 bg-amber-50" : "border-slate-200 bg-white"}`}
                onClick={() => setFocusKey(f.target + (f.option || ""))}
              >
                <span>{f.label}</span>
                <span className="font-mono">{values[f.target] || "—"}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
