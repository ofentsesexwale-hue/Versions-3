import { AlertTriangle, BadgeCheck, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/**
 * Wraps one of the confirm-before-save fields (surname / id_number / date_of_birth).
 * - Has value + unconfirmed  => amber warning + Confirm button (blocks save)
 * - Confirmed                => green meta with who/when
 * - Empty                    => neutral
 */
export function ConfirmableField({
  fieldKey,
  label,
  hasValue,
  confirmed,
  confirmedBy,
  confirmedAt,
  onConfirm,
  children,
}) {
  let container = "border-slate-200 bg-white";
  if (hasValue && !confirmed) container = "border-amber-300 bg-amber-50/60";
  else if (hasValue && confirmed) container = "border-emerald-200 bg-emerald-50/50";

  return (
    <div className={cn("rounded-lg border p-3", container)} data-testid={`confirmable-${fieldKey}`}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <Label className="text-sm font-medium text-slate-800">{label}</Label>
        {hasValue && !confirmed && (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={onConfirm}
            data-testid={`confirm-field-${fieldKey}-button`}
            className="h-8 gap-1 bg-amber-500 text-white hover:bg-amber-600"
          >
            <Check className="h-4 w-4" /> Confirm
          </Button>
        )}
        {hasValue && confirmed && (
          <span
            className="inline-flex items-center gap-1 rounded-md bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-800"
            data-testid={`confirmed-pill-${fieldKey}`}
          >
            <BadgeCheck className="h-4 w-4" /> Confirmed
          </span>
        )}
      </div>
      {children}
      {hasValue && !confirmed && (
        <p className="mt-2 flex items-center gap-1 text-xs text-amber-800">
          <AlertTriangle className="h-3.5 w-3.5" /> Confirm this value to continue. Saving is blocked
          until confirmed.
        </p>
      )}
      {hasValue && confirmed && (confirmedBy || confirmedAt) && (
        <p className="mt-2 text-xs text-emerald-800">
          Confirmed{confirmedBy ? ` by ${confirmedBy}` : ""}
          {confirmedAt ? ` \u2022 ${new Date(confirmedAt).toLocaleString("en-ZA")}` : ""}
        </p>
      )}
    </div>
  );
}
