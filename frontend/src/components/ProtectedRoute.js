import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import LaunchScreen from "@/components/LaunchScreen";

export function ProtectedRoute({ children, requireRole }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <LaunchScreen message="Opening your office session…" />;
  }
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  if (requireRole && user.role !== requireRole) {
    return <Navigate to="/" replace />;
  }
  return children;
}
