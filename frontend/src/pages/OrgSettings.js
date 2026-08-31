import { useEffect, useState } from "react";
import { Building2, HardDrive, Save } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export default function OrgSettings() {
  const { user } = useAuth();
  const [org, setOrg] = useState({ name: "", address: "", contact: "", logo: null });
  const [file, setFile] = useState(null);
  const [tagline, setTagline] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/organisation/").then((r) => setOrg(r.data)).catch(() => {});
    api.get("/site-config/").then((r) => setTagline(r.data.login_tagline || "")).catch(() => {});
  }, []);

  if (user && user.role !== "admin") {
    return <div className="p-8 text-center text-slate-600" data-testid="org-forbidden">Only administrators can edit the organisation profile.</div>;
  }

  const save = async () => {
    setSaving(true);
    try {
      const fd = new FormData();
      fd.append("name", org.name || "");
      fd.append("address", org.address || "");
      fd.append("contact", org.contact || "");
      if (file) fd.append("logo", file);
      const r = await api.put("/organisation/", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setOrg(r.data);
      setFile(null);
      await api.put("/site-config/", { login_tagline: tagline });
      toast.success("Organisation profile saved");
    } catch (e) {
      toast.error("Could not save organisation profile");
    } finally {
      setSaving(false);
    }
  };

  const logoUrl = org.logo ? (org.logo.startsWith("http") ? org.logo : `${BACKEND_URL}${org.logo}`) : null;

  return (
    <div className="space-y-6" data-testid="org-settings-page">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900"><Building2 className="h-6 w-6" /> Organisation profile</h1>
        <p className="text-sm text-slate-600">This name and logo appear as the letterhead on every printed DSD form.</p>
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">Letterhead details</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Organisation name</label>
            <Input value={org.name || ""} onChange={(e) => setOrg((o) => ({ ...o, name: e.target.value }))} data-testid="org-name-input" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Address</label>
            <Input value={org.address || ""} onChange={(e) => setOrg((o) => ({ ...o, address: e.target.value }))} data-testid="org-address-input" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Contact (phone / email)</label>
            <Input value={org.contact || ""} onChange={(e) => setOrg((o) => ({ ...o, contact: e.target.value }))} data-testid="org-contact-input" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Logo</label>
            {logoUrl && <img src={logoUrl} alt="logo" className="mb-2 max-h-20 rounded border border-slate-200 p-1" data-testid="org-logo-preview" />}
            <Input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="org-logo-input" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Login page tagline</label>
            <Input value={tagline} maxLength={200} onChange={(e) => setTagline(e.target.value)} placeholder="e.g. Welcome to the OVC Case Management System" data-testid="org-tagline-input" />
            <p className="mt-1 text-xs text-slate-500">Shown on the login screen, below the organisation name.</p>
          </div>
          <div className="flex justify-end">
            <Button onClick={save} disabled={saving} className="gap-2 bg-slate-900 hover:bg-slate-800" data-testid="org-save-button">
              <Save className="h-4 w-4" /> {saving ? "Saving..." : "Save"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <BackupPanel />
    </div>
  );
}

function BackupPanel() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = () => {
    api.get("/backups/").then((r) => setRows(r.data.backups || [])).catch(() => {});
  };

  useEffect(() => { load(); }, []);

  const downloadBlob = async (path, filename) => {
    const res = await api.get(path, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const create = async () => {
    setBusy(true);
    try {
      const res = await api.post("/backups/create/", {}, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ovc-backup-${new Date().toISOString().slice(0, 10)}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Backup saved on this computer");
      load();
    } catch {
      toast.error("Could not create backup");
    } finally {
      setBusy(false);
    }
  };

  const restore = async (file) => {
    if (!file) return;
    if (!window.confirm("This replaces the office file on this PC with the backup. Continue?")) return;
    const fd = new FormData();
    fd.append("file", file);
    setBusy(true);
    try {
      await api.post("/backups/restore/", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Restored. Refresh the page.");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Restore failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card data-testid="backup-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base"><HardDrive className="h-4 w-4" /> Local backup</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">Copies the database and uploaded files onto this PC. No internet, no cloud drive.</p>
        <div className="flex flex-wrap gap-2">
          <Button onClick={create} disabled={busy} data-testid="backup-create-button">Create backup zip</Button>
          <label className="inline-flex">
            <input type="file" accept=".zip" className="hidden" onChange={(e) => restore(e.target.files?.[0])} data-testid="backup-restore-input" />
            <Button type="button" variant="outline" disabled={busy} onClick={(e) => e.currentTarget.parentElement.querySelector("input").click()}>Restore from zip</Button>
          </label>
        </div>
        {rows.slice(0, 8).map((b) => (
          <button key={b.name} className="block w-full rounded-xl border border-white/50 px-3 py-2 text-left text-sm hover:bg-white/50" onClick={() => downloadBlob(`/backups/${encodeURIComponent(b.name)}/download/`, b.name)}>
            {b.name} · {(b.size / 1024).toFixed(0)} KB
          </button>
        ))}
      </CardContent>
    </Card>
  );
}
