import { useRef } from "react";

export function digitsFromId(value) {
  return String(value || "").replace(/\D/g, "").slice(0, 13);
}

export function fanOutId(value) {
  const digits = digitsFromId(value);
  return Array.from({ length: 13 }, (_, i) => digits[i] || "");
}

export default function SaIdCells({ value, onChange, disabled, testId }) {
  const cells = fanOutId(value);
  const refs = useRef([]);

  const emit = (next) => onChange(next.join(""));

  const onPaste = (e) => {
    const text = e.clipboardData?.getData("text") || "";
    const digits = digitsFromId(text);
    if (!digits) return;
    e.preventDefault();
    emit(fanOutId(digits));
    const idx = Math.min(digits.length, 12);
    refs.current[idx]?.focus();
  };

  const onKey = (i, e) => {
    if (e.key === "Backspace") {
      e.preventDefault();
      const next = [...cells];
      if (next[i]) {
        next[i] = "";
        emit(next);
      } else if (i > 0) {
        next[i - 1] = "";
        emit(next);
        refs.current[i - 1]?.focus();
      }
      return;
    }
    if (e.key === "ArrowLeft" && i > 0) {
      e.preventDefault();
      refs.current[i - 1]?.focus();
    }
    if (e.key === "ArrowRight" && i < 12) {
      e.preventDefault();
      refs.current[i + 1]?.focus();
    }
  };

  const onInput = (i, raw) => {
    const d = String(raw || "").replace(/\D/g, "").slice(-1);
    const next = [...cells];
    next[i] = d;
    emit(next);
    if (d && i < 12) refs.current[i + 1]?.focus();
  };

  return (
    <div className="flex h-full w-full items-stretch gap-px" data-testid={testId} onPaste={onPaste}>
      {cells.map((ch, i) => (
        <input
          key={i}
          ref={(el) => { refs.current[i] = el; }}
          value={ch}
          disabled={disabled}
          inputMode="numeric"
          maxLength={1}
          onChange={(e) => onInput(i, e.target.value)}
          onKeyDown={(e) => onKey(i, e)}
          className="min-w-0 flex-1 border-0 bg-transparent p-0 text-center text-[11px] leading-none text-black outline-none focus:ring-1 focus:ring-black"
          aria-label={`ID digit ${i + 1}`}
        />
      ))}
    </div>
  );
}
