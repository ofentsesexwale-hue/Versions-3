import { useState } from "react";
import { KeyRound } from "lucide-react";
import { toast } from "sonner";
import api, { TOKEN_KEY } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ChangePassword() {
  const { reload } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (next !== confirm) {
      toast.error("New passwords do not match");
      return;
    }
    setSaving(true);
    try {
      const r = await api.post("/auth/change-password/", { current_password: current, new_password: next });
      if (r.data.token) localStorage.setItem(TOKEN_KEY, r.data.token);
      toast.success("Password updated");
      setCurrent("");
      setNext("");
      setConfirm("");
      await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not change password");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg space-y-6" data-testid="change-password-page">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold"><KeyRound className="h-6 w-6" /> Change password</h1>
        <p className="text-sm text-muted-foreground">Use this when you replace a demo login with your own password.</p>
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">Your credentials</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1"><Label>Current password</Label><Input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} /></div>
          <div className="space-y-1"><Label>New password</Label><Input type="password" value={next} onChange={(e) => setNext(e.target.value)} /></div>
          <div className="space-y-1"><Label>Confirm new password</Label><Input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></div>
          <Button onClick={save} disabled={saving || !current || !next}>Update password</Button>
        </CardContent>
      </Card>
    </div>
  );
}
