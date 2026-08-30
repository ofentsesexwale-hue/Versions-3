import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft } from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { HouseholdRow } from "@/components/HouseholdRow";

const FIELD_LABELS = {
  id_number: "ID numbers",
  surname: "surnames",
  date_of_birth: "dates of birth",
};

export default function Verification() {
  const [params] = useSearchParams();
  const field = params.get("field") || "id_number";
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => setPage(1), [field]);

  useEffect(() => {
    setLoading(true);
    api
      .get("/households/", { params: { unconfirmed: field, page } })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  }, [field, page]);

  const rows = data?.results || [];

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate("/")} className="gap-2" data-testid="back-button">
        <ArrowLeft className="h-4 w-4" /> Back to dashboard
      </Button>
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900">
          <AlertTriangle className="h-6 w-6 text-amber-500" /> Verification queue
        </h1>
        <p className="text-sm text-slate-600">
          Households with unconfirmed {FIELD_LABELS[field]} that still need supervisor verification.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {Object.keys(FIELD_LABELS).map((f) => (
          <Button
            key={f}
            variant={f === field ? "default" : "outline"}
            size="sm"
            className={f === field ? "bg-slate-900" : ""}
            onClick={() => navigate(`/verification?field=${f}`)}
            data-testid={`verification-tab-${f}`}
          >
            Unconfirmed {FIELD_LABELS[f]}
          </Button>
        ))}
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-3 p-4" data-testid="loading-state">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          ) : rows.length === 0 ? (
            <div className="p-8 text-center text-slate-600" data-testid="empty-state">
              No households with unconfirmed {FIELD_LABELS[field]}. All verified.
            </div>
          ) : (
            rows.map((hh) => (
              <HouseholdRow key={hh.id} hh={hh} onClick={() => navigate(`/households/${hh.id}`)} />
            ))
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">{data?.count || 0} households</p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={!data?.previous} onClick={() => setPage((p) => Math.max(1, p - 1))}>Previous</Button>
          <Button variant="outline" size="sm" disabled={!data?.next} onClick={() => setPage((p) => p + 1)}>Next</Button>
        </div>
      </div>
    </div>
  );
}
