import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { GraduationCap, Loader2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";

const TRAINING = [
  ["admin", "admin123", "Administrator"],
  ["supervisor", "supervisor123", "Supervisor"],
  ["caseworker", "caseworker123", "Case worker"],
  ["capturer", "capturer123", "Data capturer"],
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [branding, setBranding] = useState(null);
  const [showTraining, setShowTraining] = useState(false);

  useEffect(() => {
    api.get("/branding/").then((r) => setBranding(r.data)).catch(() => {});
  }, []);

  const brandingLogo = branding?.logo
    ? (branding.logo.startsWith("http") ? branding.logo : `${process.env.REACT_APP_BACKEND_URL || ""}${branding.logo}`)
    : null;

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(username, password);
      toast.success("Signed in");
      navigate("/");
    } catch (err) {
      toast.error("Invalid username or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-[440px]">
        <div className="mb-8 flex flex-col items-center text-center">
          {brandingLogo ? (
            <img src={brandingLogo} alt="logo" className="mb-4 h-16 max-w-[200px] object-contain" data-testid="login-org-logo" />
          ) : (
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-[1.4rem] bg-foreground text-[#f3ead8] shadow-lg">
              <ShieldCheck className="h-8 w-8" />
            </div>
          )}
          <h1 className="text-[28px] font-semibold tracking-tight">{branding?.name || "OVC CaseFile"}</h1>
          <p className="mt-1 max-w-sm text-[15px] text-muted-foreground">
            Office case files for orphans and vulnerable children
          </p>
          {branding?.login_tagline && (
            <p className="mt-2 text-sm font-medium" data-testid="login-tagline">
              {branding.login_tagline}
            </p>
          )}
        </div>
        <div className="glass-strong rounded-[1.75rem] p-6 sm:p-7">
          <h2 className="mb-1 text-lg font-semibold tracking-tight">Office sign-in</h2>
          <p className="mb-5 text-[13px] text-muted-foreground">Use your staff username. Training classroom logins are separate, below.</p>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                autoComplete="username"
                data-testid="login-username-input"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                data-testid="login-password-input"
              />
            </div>
            <Button type="submit" disabled={loading} className="h-12 w-full text-[15px]" data-testid="login-form-submit-button">
              {loading && <Loader2 className="h-4 w-4 animate-spin" />} Continue
            </Button>
          </form>
          <div className="mt-6 border-t border-white/40 pt-4">
            <button
              type="button"
              onClick={() => setShowTraining((v) => !v)}
              className="flex w-full items-center gap-2 text-left text-[13px] text-muted-foreground hover:text-foreground"
              data-testid="toggle-training-logins"
            >
              <GraduationCap className="h-4 w-4" />
              {showTraining ? "Hide training classroom" : "Open training classroom"}
            </button>
            {showTraining && (
              <div className="mt-3">
                <p className="mb-2 text-xs text-muted-foreground">
                  These logins only open fictional TEST- files. They never see live households.
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {TRAINING.map(([u, p, role]) => (
                    <button
                      key={u}
                      type="button"
                      onClick={() => {
                        setUsername(u);
                        setPassword(p);
                      }}
                      className="rounded-2xl border border-white/50 bg-white/35 px-3 py-2 text-left text-xs hover:bg-white/55"
                      data-testid={`demo-fill-${u}`}
                    >
                      <span className="font-medium">{u}</span>
                      <span className="block text-muted-foreground">{role}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
