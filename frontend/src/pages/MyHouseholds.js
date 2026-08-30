import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Briefcase } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { HouseholdRow } from "@/components/HouseholdRow";

export default function MyHouseholds() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get("/households/", { params: { assigned_to_me: 1, page } })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  }, [page]);

  const rows = data?.results || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900">
          <Briefcase className="h-6 w-6" /> My households
        </h1>
        <p className="text-sm text-slate-600">Households assigned to you ({data?.count ?? 0}).</p>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-3 p-4" data-testid="loading-state">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          ) : rows.length === 0 ? (
            <div className="p-8 text-center text-slate-600" data-testid="empty-state">
              No households are assigned to you yet.
              {(user?.role === "supervisor" || user?.role === "admin") &&
                " Assign case workers to households from the household edit page."}
            </div>
          ) : (
            rows.map((hh) => (
              <HouseholdRow key={hh.id} hh={hh} onClick={() => navigate(`/households/${hh.id}`)} />
            ))
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-end gap-2">
        <Button variant="outline" size="sm" disabled={!data?.previous} onClick={() => setPage((p) => Math.max(1, p - 1))}>Previous</Button>
        <Button variant="outline" size="sm" disabled={!data?.next} onClick={() => setPage((p) => p + 1)}>Next</Button>
      </div>
    </div>
  );
}
