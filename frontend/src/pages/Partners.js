import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

export default function Partners() {
  const [rows, setRows] = useState([]);
  const [kinds, setKinds] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", kind: "clinic", phone: "", address: "", contact_person: "" });

  const load = () => {
    api.get("/partners/", { params: { page_size: 200 } }).then((r) => setRows(r.data.results || r.data)).catch(() => {});
  };

  useEffect(() => {
    api.get("/choices/").then((r) => setKinds(r.data.partner_kinds || [])).catch(() => {});
    load();
  }, []);

  const save = async () => {
    try {
      await api.post("/partners/", form);
      toast.success("Partner saved on this office PC");
      setOpen(false);
      setForm({ name: "", kind: "clinic", phone: "", address: "", contact_person: "" });
      load();
    } catch {
      toast.error("Could not save partner");
    }
  };

  return (
    <div className="space-y-6" data-testid="partners-page">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Partner directory</h1>
          <p className="text-sm text-muted-foreground">Clinics, SASSA, schools and SAPS you work with. Stored on this computer — nothing is looked up online.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="gap-1" data-testid="add-partner-button"><Plus className="h-4 w-4" /> Add partner</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Add a local partner</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1"><Label>Name</Label><Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="partner-name-input" /></div>
              <div className="space-y-1">
                <Label>Kind</Label>
                <Select value={form.kind} onValueChange={(v) => setForm((f) => ({ ...f, kind: v }))}>
                  <SelectTrigger className="h-11"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {kinds.map((k) => <SelectItem key={k.value} value={k.value}>{k.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1"><Label>Phone</Label><Input value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} /></div>
              <div className="space-y-1"><Label>Address</Label><Input value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} /></div>
              <div className="space-y-1"><Label>Contact person</Label><Input value={form.contact_person} onChange={(e) => setForm((f) => ({ ...f, contact_person: e.target.value }))} /></div>
            </div>
            <DialogFooter><Button onClick={save} data-testid="partner-save-button">Save</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">This office</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {rows.length === 0 && <p className="py-8 text-center text-sm text-muted-foreground">No partners yet. Add the SASSA office and clinic you actually use.</p>}
          {rows.map((p) => (
            <div key={p.id} className="flex items-start justify-between rounded-2xl border border-white/50 bg-white/40 p-3">
              <div>
                <p className="font-medium">{p.name}</p>
                <p className="text-sm text-muted-foreground">{p.kind_display}{p.phone ? ` · ${p.phone}` : ""}{p.address ? ` · ${p.address}` : ""}</p>
              </div>
              <Button variant="ghost" size="icon" className="text-rose-700" onClick={async () => { await api.delete(`/partners/${p.id}/`); load(); }}><Trash2 className="h-4 w-4" /></Button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
