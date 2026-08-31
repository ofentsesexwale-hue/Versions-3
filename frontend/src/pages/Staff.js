import { useEffect, useState } from "react";
import { KeyRound, Plus, Save, UserCog } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const EMPTY = {
  username: "",
  password: "",
  first_name: "",
  last_name: "",
  email: "",
  role: "case-worker",
};

export default function Staff() {
  const { user } = useAuth();
  const [staff, setStaff] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [pwUser, setPwUser] = useState(null);
  const [newPw, setNewPw] = useState("");

  const load = () => {
    api.get("/staff/").then((r) => setStaff(r.data)).catch(() => toast.error("Could not load staff"));
  };

  useEffect(() => { load(); }, []);

  if (user && user.role !== "admin") {
    return <div className="p-8 text-center text-slate-600">Only administrators can add staff credentials.</div>;
  }

  const err = (e) => e?.response?.data?.detail || "Request failed";

  const create = async () => {
    if (!form.username || !form.password) {
      toast.error("Username and password are required");
      return;
    }
    setSaving(true);
    try {
      await api.post("/staff/", form);
      toast.success("Staff account created — they can sign in now");
      setForm(EMPTY);
      setOpen(false);
      load();
    } catch (e) {
      toast.error(err(e));
    } finally {
      setSaving(false);
    }
  };

  const patch = async (id, data) => {
    try {
      await api.patch(`/staff/${id}/`, data);
      toast.success("Staff updated");
      load();
    } catch (e) {
      toast.error(err(e));
    }
  };

  const setPassword = async () => {
    if (!pwUser) return;
    try {
      await api.post(`/staff/${pwUser.id}/set-password/`, { password: newPw });
      toast.success(`Password set for ${pwUser.username}`);
      setPwUser(null);
      setNewPw("");
    } catch (e) {
      toast.error(err(e));
    }
  };

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="space-y-6" data-testid="staff-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold"><UserCog className="h-6 w-6" /> Staff accounts</h1>
          <p className="text-sm text-muted-foreground">
            Add real office logins here. Demo users can stay for practice; new staff should use their own username and password.
            Passwords must be at least 8 characters and not a common password.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2" data-testid="add-staff-button"><Plus className="h-4 w-4" /> Add staff</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>New staff login</DialogTitle></DialogHeader>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1"><Label>Username</Label><Input value={form.username} onChange={(e) => set("username", e.target.value)} data-testid="staff-username-input" /></div>
              <div className="space-y-1"><Label>Password</Label><Input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} data-testid="staff-password-input" /></div>
              <div className="space-y-1"><Label>First name</Label><Input value={form.first_name} onChange={(e) => set("first_name", e.target.value)} /></div>
              <div className="space-y-1"><Label>Surname</Label><Input value={form.last_name} onChange={(e) => set("last_name", e.target.value)} /></div>
              <div className="space-y-1 sm:col-span-2"><Label>Email</Label><Input value={form.email} onChange={(e) => set("email", e.target.value)} /></div>
              <div className="space-y-1 sm:col-span-2">
                <Label>Role</Label>
                <Select value={form.role} onValueChange={(v) => set("role", v)}>
                  <SelectTrigger data-testid="staff-role-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(ROLE_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button onClick={create} disabled={saving} data-testid="staff-save-button"><Save className="h-4 w-4" /> Create account</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">{staff.length} staff</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {staff.length === 0 && <p className="text-sm text-muted-foreground">No staff yet. Add the first office login.</p>}
          {staff.map((s) => (
            <div key={s.id} className="flex flex-col gap-3 rounded-2xl border border-white/50 bg-white/40 p-4 sm:flex-row sm:items-center" data-testid={`staff-row-${s.id}`}>
              <div className="min-w-0 flex-1">
                <p className="font-medium">{s.full_name || s.username}</p>
                <p className="text-sm text-muted-foreground">{s.username} · {ROLE_LABELS[s.role] || s.role || "no role"}</p>
                {s.is_training && (
                  <p className="mt-1 text-[11px] font-medium text-amber-800">Training classroom login — dummy TEST files only</p>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Select value={s.role || "case-worker"} onValueChange={(v) => patch(s.id, { role: v })}>
                  <SelectTrigger className="h-10 w-[180px]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(ROLE_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                  </SelectContent>
                </Select>
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox checked={!!s.is_active} onCheckedChange={(v) => patch(s.id, { is_active: !!v })} />
                  Active
                </label>
                <Button variant="outline" size="sm" className="gap-1" onClick={() => { setPwUser(s); setNewPw(""); }}>
                  <KeyRound className="h-3.5 w-3.5" /> Set password
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={!!pwUser} onOpenChange={(v) => { if (!v) setPwUser(null); }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Set password for {pwUser?.username}</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">They will be signed out of any existing session and must use this password next time.</p>
          <Input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} placeholder="New password" data-testid="staff-set-password-input" />
          <DialogFooter>
            <Button onClick={setPassword} data-testid="staff-set-password-save">Save password</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
