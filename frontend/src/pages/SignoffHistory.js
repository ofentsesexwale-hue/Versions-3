import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/constants";

export default function SignoffHistory() {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);

  useEffect(() => {
    api.get("/households/", { params: { signed: 1, page_size: 200 } })
      .then((r) => setRows(r.data.results || []))
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-6" data-testid="signoff-history-page">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900"><ShieldCheck className="h-6 w-6" /> Checklist sign-off history</h1>
        <p className="text-sm text-slate-600">Households whose case-file checklist has been signed off by a supervisor.</p>
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">Signed checklists ({rows.length})</CardTitle></CardHeader>
        <CardContent className="p-0">
          {rows.length === 0 ? (
            <p className="p-8 text-center text-slate-600" data-testid="signoff-empty">No checklists have been signed off yet.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              <div className="grid grid-cols-[1.2fr_1.5fr_1fr_1fr] gap-3 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                <span>Household</span><span>Signed by</span><span>SACSSP</span><span>Date</span>
              </div>
              {rows.map((h) => (
                <button
                  key={h.id}
                  onClick={() => navigate(`/households/${h.id}/checklist`)}
                  className="grid w-full grid-cols-[1.2fr_1.5fr_1fr_1fr] gap-3 px-4 py-3 text-left text-sm hover:bg-slate-50"
                  data-testid={`signoff-row-${h.id}`}
                >
                  <span className="font-medium text-slate-900">{h.org_household_number}</span>
                  <span className="text-slate-700">{h.checklist_signed_name || "\u2014"}</span>
                  <span className="text-slate-600">{h.checklist_signed_sacssp || "\u2014"}</span>
                  <span className="text-slate-600">{h.checklist_signed_at ? formatDate(h.checklist_signed_at) : "\u2014"}</span>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
