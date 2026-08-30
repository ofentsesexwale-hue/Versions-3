import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { formatDate } from "@/lib/constants";

export function HouseholdRow({ hh, onClick }) {
  const p = hh.checklist_progress || { percent: 0, yes: 0, total: 0 };
  return (
    <button
      onClick={onClick}
      data-testid={`household-row-${hh.id}`}
      className="flex w-full items-center justify-between gap-4 border-b border-slate-100 px-4 py-3 text-left last:border-0 hover:bg-slate-50"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-900">{hh.org_household_number}</span>
          {hh.has_unconfirmed && (
            <Badge className="gap-1 border border-amber-200 bg-amber-50 text-amber-800">
              <AlertTriangle className="h-3 w-3" /> Unconfirmed
            </Badge>
          )}
        </div>
        <p className="truncate text-sm text-slate-600">
          {hh.caregiver_name || "No caregiver"} · {hh.town || "\u2014"}, {hh.province || "\u2014"}
        </p>
        <div className="mt-2 flex max-w-xs items-center gap-2">
          <Progress value={p.percent} className="h-1.5" />
          <span className="shrink-0 text-xs tabular-nums text-slate-500">{p.percent}% file</span>
        </div>
      </div>
      <div className="shrink-0 text-right text-sm text-slate-500">
        <p className="tabular-nums">{hh.member_count} members</p>
        <p className="tabular-nums">{formatDate(hh.date_registered)}</p>
      </div>
    </button>
  );
}
