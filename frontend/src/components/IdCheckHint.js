import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, BadgeCheck } from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";

export function IdCheckHint({
  idNumber,
  idType,
  householdId,
  excludeCaregiver,
  excludeMember,
  onApplyDob,
  onApplySex,
  currentDob,
  currentSex,
}) {
  const [info, setInfo] = useState(null);

  useEffect(() => {
    const digits = String(idNumber || "").replace(/\D/g, "");
    if (idType && idType !== "SA ID Number") {
      setInfo(null);
      return;
    }
    if (digits.length < 6) {
      setInfo(null);
      return;
    }
    const t = setTimeout(() => {
      api
        .get("/id-check/", {
          params: {
            q: idNumber,
            exclude_household: householdId || undefined,
            exclude_caregiver: excludeCaregiver || undefined,
            exclude_member: excludeMember || undefined,
          },
        })
        .then((r) => setInfo(r.data))
        .catch(() => setInfo(null));
    }, 350);
    return () => clearTimeout(t);
  }, [idNumber, idType, householdId, excludeCaregiver, excludeMember]);

  if (!info) return null;

  return (
    <div className="space-y-2 text-sm" data-testid="id-check-hint">
      {(info.valid ?? info.luhn_ok) ? (
        <p className="flex items-center gap-1.5 text-emerald-800">
          <BadgeCheck className="h-4 w-4" /> {info.message}
        </p>
      ) : info.message ? (
        <p className="flex items-center gap-1.5 text-amber-800">
          <AlertTriangle className="h-4 w-4" /> {info.message}
        </p>
      ) : null}
      {info.luhn_ok && (info.dob || info.sex) && (
        <div className="flex flex-wrap gap-2">
          {info.dob && info.dob !== currentDob && (
            <Button type="button" size="sm" variant="outline" onClick={() => onApplyDob?.(info.dob)} data-testid="id-apply-dob">
              Use date of birth {info.dob}
            </Button>
          )}
          {info.sex && info.sex !== currentSex && (
            <Button type="button" size="sm" variant="outline" onClick={() => onApplySex?.(info.sex)} data-testid="id-apply-sex">
              Use sex {info.sex}
            </Button>
          )}
        </div>
      )}
      {info.duplicates?.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-amber-950" data-testid="id-duplicate-warning">
          <p className="font-medium">This ID is already on another file</p>
          <ul className="mt-1 space-y-1">
            {info.duplicates.map((d) => (
              <li key={`${d.role}-${d.household_id}`}>
                <Link className="underline" to={`/households/${d.household_id}`}>
                  {d.name || "Unnamed"} · {d.org_household_number} ({d.role})
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
