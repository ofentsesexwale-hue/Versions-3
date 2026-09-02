import { useEffect, useState } from "react";
import { KeyRound, Pencil, Plus, Save, UserCog } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { LIVE_OFFICE_TITLES, ROLE_LABELS, ROLE_PERMISSIONS } from "@/lib/constants";
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
  role: "cycw",
  household_id: "",
};

function titleLabel(role, isAdminOwner) {
  if (isAdminOwner) return "Administrator";
  return ROLE_LABELS[role] || role || "no title";
}

export default function Staff() {
  const { user } = useAuth();
  const [staff, setStaff] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [pwUser, setPwUser] = useState(null);
  const [newPw, setNewPw] = useState("");
  const [newUsername, setNewUsername] = useState("");
  const [editUser, setEditUser] = useState(null);
  const [editForm, setEditForm] = useState(EMPTY);

  const load = () => {
    api.get("/staff/").then((r) => setStaff(r.data)).catch(() => toast.error("Could not load staff"));
  };

  useEffect(() => { load(); }, []);

  if (user && user.role !== "admin") {
    return <div className="p-8 text-center text-slate-600">Only the office administrator can add staff credentials.</div>;
  }

  const err = (e) => e?.response?.data?.detail || "Request failed";

  const create = async () => {
    if (!form.username || !form.password) {
      toast.error("Username and password are required");
      return;
    }
    if (!form.first_name || !form.last_name) {
      toast.error("First name and surname are required");
      return;
    }
    setSaving(true);
    try {
      const payload = { ...form };
      if (form.role !== "caregiver") delete payload.household_id;
      await api.post("/staff/", payload);
      toast.success("Account created — they can sign in now");
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

  const saveEdit = async () => {
    if (!editUser) return;
    try {
      await api.patch(`/staff/${editUser.id}/`, {
        first_name: editForm.first_name,
        last_name: editForm.last_name,
        email: editForm.email,
        ...(editUser.is_system_builder ? {} : { role: editForm.role }),
        household_id: editForm.role === "caregiver" ? editForm.household_id : undefined,
      });
      toast.success("Name and title saved");
      setEditUser(null);
      load();
    } catch (e) {
      toast.error(err(e));
    }
  };

  const setCredentials = async () => {
    if (!pwUser) return;
    try {
      if (newUsername && newUsername !== pwUser.username) {
        await api.patch(`/staff/${pwUser.id}/`, { username: newUsername });
      }
      if (newPw) {
        await api.post(`/staff/${pwUser.id}/set-password/`, { password: newPw });
      }
      if (!newPw && (!newUsername || newUsername === pwUser.username)) {
        toast.error("Enter a new username or password");
        return;
      }
      toast.success(`Login updated for ${newUsername || pwUser.username}`);
      setPwUser(null);
      setNewPw("");
      setNewUsername("");
      load();
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
            Orphan Coordinator is the live office Administrator. Add E.P.W.P and Poverty Alleviator Coordinators,
            CYCWs, Auxiliaries, Caregivers, Caregiver(E.P.W.P), and other staff with a name, title, and login.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2" data-testid="add-staff-button"><Plus className="h-4 w-4" /> Add user</Button>
          </DialogTrigger>
          <DialogContent className="max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle>New office user</DialogTitle></DialogHeader>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1"><Label>First name</Label><Input value={form.first_name} onChange={(e) => set("first_name", e.target.value)} data-testid="staff-first-name-input" /></div>
              <div className="space-y-1"><Label>Surname</Label><Input value={form.last_name} onChange={(e) => set("last_name", e.target.value)} data-testid="staff-last-name-input" /></div>
              <div className="space-y-1"><Label>Username</Label><Input value={form.username} onChange={(e) => set("username", e.target.value)} data-testid="staff-username-input" /></div>
              <div className="space-y-1"><Label>Password</Label><Input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} data-testid="staff-password-input" /></div>
              <div className="space-y-1 sm:col-span-2"><Label>Email</Label><Input value={form.email} onChange={(e) => set("email", e.target.value)} /></div>
              <div className="space-y-1 sm:col-span-2">
                <Label>Title</Label>
                <Select value={form.role} onValueChange={(v) => set("role", v)}>
                  <SelectTrigger data-testid="staff-role-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {LIVE_OFFICE_TITLES.map((k) => <SelectItem key={k} value={k}>{ROLE_LABELS[k]}</SelectItem>)}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground" data-testid="staff-permission-summary">
                  {ROLE_PERMISSIONS[form.role]}
                </p>
              </div>
              {form.role === "caregiver" && (
                <div className="space-y-1 sm:col-span-2">
                  <Label>Household file id (optional)</Label>
                  <Input
                    value={form.household_id}
                    onChange={(e) => set("household_id", e.target.value)}
                    placeholder="Numeric id from the household file URL"
                    data-testid="staff-household-id-input"
                  />
                  <p className="text-xs text-muted-foreground">
                    Link this login to a household caregiver so they only see that file. You can also set a login on the caregiver form.
                  </p>
                </div>
              )}
            </div>
            <DialogFooter>
              <Button onClick={create} disabled={saving} data-testid="staff-save-button"><Save className="h-4 w-4" /> Create account</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">{staff.length} people</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {staff.length === 0 && <p className="text-sm text-muted-foreground">No live office staff yet. Add the first login.</p>}
          {staff.map((s) => (
            <div key={s.id} className="flex flex-col gap-3 rounded-2xl border border-white/50 bg-white/40 p-4 sm:flex-row sm:items-center" data-testid={`staff-row-${s.id}`}>
              <div className="min-w-0 flex-1">
                <p className="font-medium">{s.full_name || s.username}</p>
                <p className="text-sm text-muted-foreground">
                  {s.username} · {titleLabel(s.role, s.is_system_builder)}
                </p>
                <p className="mt-1 text-[11px] text-muted-foreground">{s.permission_summary}</p>
                {s.linked_household && (
                  <p className="mt-1 text-[11px] font-medium text-emerald-800">
                    Linked to file {s.linked_household.org_household_number}
                  </p>
                )}
                {s.is_system_builder && (
                  <p className="mt-1 text-[11px] font-medium text-emerald-800">
                    Live office Administrator. These privileges cannot be removed.
                  </p>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {s.is_system_builder ? (
                  <span className="inline-flex h-10 items-center rounded-md border border-white/60 bg-white/50 px-3 text-sm">
                    Administrator
                  </span>
                ) : (
                  <Select value={s.role || "cycw"} onValueChange={(v) => patch(s.id, { role: v })}>
                    <SelectTrigger className="h-10 w-[180px]"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {LIVE_OFFICE_TITLES.map((k) => <SelectItem key={k} value={k}>{ROLE_LABELS[k]}</SelectItem>)}
                    </SelectContent>
                  </Select>
                )}
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={!!s.is_active}
                    disabled={!!s.is_system_builder}
                    onCheckedChange={(v) => patch(s.id, { is_active: !!v })}
                  />
                  Active
                </label>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1"
                  onClick={() => {
                    setEditUser(s);
                    setEditForm({
                      first_name: s.first_name || "",
                      last_name: s.last_name || "",
                      email: s.email || "",
                      role: s.role || "cycw",
                      household_id: s.linked_household?.id ? String(s.linked_household.id) : "",
                    });
                  }}
                >
                  <Pencil className="h-3.5 w-3.5" /> Name
                </Button>
                <Button variant="outline" size="sm" className="gap-1" onClick={() => { setPwUser(s); setNewPw(""); setNewUsername(s.username); }}>
                  <KeyRound className="h-3.5 w-3.5" /> Login
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={!!pwUser} onOpenChange={(v) => { if (!v) setPwUser(null); }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit login for {pwUser?.full_name || pwUser?.username}</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">Change the username and/or password. They will need the new details next time they sign in.</p>
          <div className="space-y-2">
            <Label>Username</Label>
            <Input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} disabled={!!pwUser?.is_system_builder} data-testid="staff-set-username-input" />
          </div>
          <div className="space-y-2">
            <Label>New password</Label>
            <Input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} placeholder="Leave blank to keep the current password" data-testid="staff-set-password-input" />
          </div>
          <DialogFooter>
            <Button onClick={setCredentials} data-testid="staff-set-password-save">Save login</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!editUser} onOpenChange={(v) => { if (!v) setEditUser(null); }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit name and title</DialogTitle></DialogHeader>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1"><Label>First name</Label><Input value={editForm.first_name} onChange={(e) => setEditForm((f) => ({ ...f, first_name: e.target.value }))} /></div>
            <div className="space-y-1"><Label>Surname</Label><Input value={editForm.last_name} onChange={(e) => setEditForm((f) => ({ ...f, last_name: e.target.value }))} /></div>
            <div className="space-y-1 sm:col-span-2">
              <Label>Title</Label>
              {editUser?.is_system_builder ? (
                <p className="text-sm">Administrator</p>
              ) : (
                <Select value={editForm.role} onValueChange={(v) => setEditForm((f) => ({ ...f, role: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {LIVE_OFFICE_TITLES.map((k) => <SelectItem key={k} value={k}>{ROLE_LABELS[k]}</SelectItem>)}
                  </SelectContent>
                </Select>
              )}
              <p className="mt-1 text-xs text-muted-foreground">{ROLE_PERMISSIONS[editUser?.is_system_builder ? "admin" : editForm.role]}</p>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={saveEdit}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
