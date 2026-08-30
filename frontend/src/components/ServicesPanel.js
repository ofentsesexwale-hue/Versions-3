import { useEffect, useState } from "react";
import { HeartHandshake, Plus, Printer, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { printServiceReport } from "@/lib/print";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDate } from "@/lib/constants";

const NONE = "__household__";

export function ServicesPanel({ householdId, caregiver, members = [] }) {
  const [services, setServices] = useState([]);
  const [types, setTypes] = useState([]);
  const [adding, setAdding] = useState(false);
  const [serviceType, setServiceType] = useState("");
  const [serviceDate, setServiceDate] = useState(new Date().toISOString().slice(0, 10));
  const [beneficiary, setBeneficiary] = useState(NONE);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const load = () => {
    api.get("/services/", { params: { household: householdId, page_size: 200 } })
      .then((r) => setServices(r.data.results || r.data))
      .catch(() => {});
  };

  useEffect(() => {
    load();
    api.get("/choices/").then((r) => setTypes(r.data.service_types || [])).catch(() => {});
  }, [householdId]);

  const beneficiaryOptions = [
    { key: NONE, label: "Whole household" },
    ...(caregiver ? [{ key: `caregiver:${caregiver.id}`, label: `${caregiver.name} ${caregiver.surname} (caregiver)` }] : []),
    ...members.map((m) => ({ key: `householdmember:${m.id}`, label: `${m.name} ${m.surname} (member)` })),
  ];

  const save = async () => {
    if (!serviceType) return toast.error("Select a service type");
    setSaving(true);
    const payload = { household: Number(householdId), service_type: serviceType, service_date: serviceDate, notes };
    if (beneficiary !== NONE) {
      const [btype, bid] = beneficiary.split(":");
      payload.beneficiary_type = btype;
      payload.beneficiary_id = Number(bid);
    }
    try {
      await api.post("/services/", payload);
      toast.success("Service logged");
      setAdding(false);
      setServiceType(""); setNotes(""); setBeneficiary(NONE);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not log service");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (sid) => {
    await api.delete(`/services/${sid}/`);
    toast.success("Service removed");
    load();
  };

  return (
    <Card data-testid="services-panel">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2 text-base">
          <HeartHandshake className="h-4 w-4" /> Services delivered ({services.length})
        </CardTitle>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="gap-1" onClick={() => printServiceReport({ report: "household", householdId })} data-testid="print-service-history-button">
            <Printer className="h-3.5 w-3.5" /> Print history
          </Button>
          <Button size="sm" className="gap-1 bg-slate-900 hover:bg-slate-800" onClick={() => setAdding((v) => !v)} data-testid="add-service-button">
            <Plus className="h-3.5 w-3.5" /> Log service
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {adding && (
          <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4" data-testid="service-add-form">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Service type</label>
                <Select value={serviceType} onValueChange={setServiceType}>
                  <SelectTrigger data-testid="service-type-select"><SelectValue placeholder="Select service" /></SelectTrigger>
                  <SelectContent>
                    {types.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Date</label>
                <Input type="date" max={new Date().toISOString().slice(0, 10)} value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} data-testid="service-date-input" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Beneficiary</label>
                <Select value={beneficiary} onValueChange={setBeneficiary}>
                  <SelectTrigger data-testid="service-beneficiary-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {beneficiaryOptions.map((o) => <SelectItem key={o.key} value={o.key}>{o.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Notes (optional)</label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} data-testid="service-notes-input" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setAdding(false)}>Cancel</Button>
              <Button size="sm" className="bg-slate-900 hover:bg-slate-800" onClick={save} disabled={saving} data-testid="service-save-button">
                {saving ? "Saving..." : "Save service"}
              </Button>
            </div>
          </div>
        )}

        {services.length === 0 ? (
          <p className="py-4 text-center text-sm text-slate-600" data-testid="services-empty">No services recorded yet.</p>
        ) : (
          <div className="space-y-2">
            {services.map((s) => (
              <div key={s.id} className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 p-3" data-testid={`service-row-${s.id}`}>
                <div>
                  <p className="text-sm font-medium text-slate-900">{s.service_type}</p>
                  <p className="text-xs text-slate-500">
                    {formatDate(s.service_date)} · {s.beneficiary_name || "Whole household"}{s.delivered_by ? ` · by ${s.delivered_by}` : ""}
                  </p>
                  {s.notes && <p className="mt-1 text-xs text-slate-600">{s.notes}</p>}
                </div>
                <Button variant="ghost" size="icon" className="text-rose-700" onClick={() => remove(s.id)} data-testid={`service-delete-${s.id}`}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
