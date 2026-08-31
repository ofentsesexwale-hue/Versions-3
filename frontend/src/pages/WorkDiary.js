import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarClock, Send } from "lucide-react";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/lib/constants";

export default function WorkDiary() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/work-diary/").then((r) => setData(r.data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="space-y-3"><Skeleton className="h-24 w-full" /><Skeleton className="h-48 w-full" /></div>;

  const counts = data?.counts || {};

  return (
    <div className="space-y-6" data-testid="work-diary-page">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Work diary</h1>
        <p className="text-sm text-muted-foreground">Overdue home visits and open referrals — the caseload list most OVC systems keep next to the household file.</p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card><CardContent className="p-5"><p className="text-[28px] font-semibold tabular-nums">{counts.overdue_visits ?? 0}</p><p className="text-sm text-muted-foreground">Overdue visits</p></CardContent></Card>
        <Card><CardContent className="p-5"><p className="text-[28px] font-semibold tabular-nums">{counts.upcoming_visits ?? 0}</p><p className="text-sm text-muted-foreground">Visits in the next 14 days</p></CardContent></Card>
        <Card><CardContent className="p-5"><p className="text-[28px] font-semibold tabular-nums">{counts.open_referrals ?? 0}</p><p className="text-sm text-muted-foreground">Open referrals</p></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><CalendarClock className="h-4 w-4" /> Overdue visits</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {(data?.overdue_visits || []).length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">No overdue planned visits.</p>}
          {(data?.overdue_visits || []).map((v) => (
            <button key={v.id} className="flex w-full items-center justify-between rounded-xl border border-white/50 px-3 py-2 text-left hover:bg-white/50" onClick={() => navigate(`/households/${v.household}`)} data-testid={`diary-overdue-${v.id}`}>
              <span className="text-sm">{v.household_number} · {v.caregiver_name || "—"} · {v.purpose || v.visit_type_display}</span>
              <span className="text-xs text-rose-700">{formatDate(v.visit_date)}</span>
            </button>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><CalendarClock className="h-4 w-4" /> Coming up</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {(data?.upcoming_visits || []).length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">No visits booked in the next two weeks.</p>}
          {(data?.upcoming_visits || []).map((v) => (
            <button key={v.id} className="flex w-full items-center justify-between rounded-xl border border-white/50 px-3 py-2 text-left hover:bg-white/50" onClick={() => navigate(`/households/${v.household}`)}>
              <span className="text-sm">{v.household_number} · {v.caregiver_name || "—"} · {v.purpose || v.visit_type_display}</span>
              <span className="text-xs text-muted-foreground">{formatDate(v.visit_date)}</span>
            </button>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Send className="h-4 w-4" /> Open referrals</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {(data?.open_referrals || []).length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">No open referrals.</p>}
          {(data?.open_referrals || []).map((r) => (
            <button key={r.id} className="flex w-full items-center justify-between rounded-xl border border-white/50 px-3 py-2 text-left hover:bg-white/50" onClick={() => navigate(`/households/${r.household}`)} data-testid={`diary-referral-${r.id}`}>
              <span className="text-sm">{r.household_number} · {r.partner_name} · {r.reason_display}</span>
              <span className="text-xs text-muted-foreground">{r.status_display}</span>
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
