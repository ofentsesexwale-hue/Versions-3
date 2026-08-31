import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, Loader2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [branding, setBranding] = useState(null);

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

  const demo = [
    ["admin", "admin123"],
    ["supervisor", "supervisor123"],
    ["caseworker", "caseworker123"],
    ["capturer", "capturer123"],
  ];

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-[420px]">
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
            Offline case management for orphans and vulnerable children
          </p>
          {branding?.login_tagline && (
            <p className="mt-2 text-sm font-medium" data-testid="login-tagline">
              {branding.login_tagline}
            </p>
          )}
        </div>
        <div className="glass-strong rounded-[1.75rem] p-6 sm:p-7">
          <h2 className="mb-5 text-lg font-semibold tracking-tight">Sign in</h2>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
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
                data-testid="login-password-input"
              />
            </div>
            <Button type="submit" disabled={loading} className="h-12 w-full text-[15px]" data-testid="login-form-submit-button">
              {loading && <Loader2 className="h-4 w-4 animate-spin" />} Continue
            </Button>
          </form>
          <div className="mt-6">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Demo accounts</p>
            <div className="grid grid-cols-2 gap-2">
              {demo.map(([u, p]) => (
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
                  <span className="block text-muted-foreground">{p}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
