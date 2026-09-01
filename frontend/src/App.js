import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { installToastChimes } from "@/lib/chimes";

installToastChimes(toast);
import { AuthProvider, useAuth } from "@/context/AuthContext";
import LaunchScreen from "@/components/LaunchScreen";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AppShell } from "@/components/AppShell";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import HouseholdDetail from "@/pages/HouseholdDetail";
import HouseholdForm from "@/pages/HouseholdForm";
import CaregiverForm from "@/pages/CaregiverForm";
import MemberForm from "@/pages/MemberForm";
import DocumentUpload from "@/pages/DocumentUpload";
import ScanIntake from "@/pages/ScanIntake";
import Checklist from "@/pages/Checklist";
import AuditLog from "@/pages/AuditLog";
import Verification from "@/pages/Verification";
import MyHouseholds from "@/pages/MyHouseholds";
import Reassign from "@/pages/Reassign";
import PrintCenter from "@/pages/PrintCenter";
import AssessmentForm from "@/pages/AssessmentForm";
import OrgSettings from "@/pages/OrgSettings";
import Staff from "@/pages/Staff";
import ChangePassword from "@/pages/ChangePassword";
import SignoffHistory from "@/pages/SignoffHistory";
import ServiceLog from "@/pages/ServiceLog";
import ServiceTargets from "@/pages/ServiceTargets";
import WorkDiary from "@/pages/WorkDiary";
import Partners from "@/pages/Partners";

function BootGate({ children }) {
  const { loading } = useAuth();
  if (loading) {
    return <LaunchScreen />;
  }
  return children;
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BootGate>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              element={
                <ProtectedRoute>
                  <AppShell />
                </ProtectedRoute>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="my-households" element={<MyHouseholds />} />
              <Route path="services" element={<ServiceLog />} />
              <Route path="work-diary" element={<WorkDiary />} />
              <Route path="partners" element={<Partners />} />
              <Route path="reassign" element={<Reassign />} />
              <Route path="print-center" element={<PrintCenter />} />
              <Route path="signoffs" element={<SignoffHistory />} />
              <Route path="settings/organisation" element={<OrgSettings />} />
              <Route
                path="settings/staff"
                element={
                  <ProtectedRoute requireRole="admin">
                    <Staff />
                  </ProtectedRoute>
                }
              />
              <Route path="settings/password" element={<ChangePassword />} />
              <Route path="settings/targets" element={<ServiceTargets />} />
              <Route path="households/:id/assessment" element={<AssessmentForm />} />
              <Route path="verification" element={<Verification />} />
              <Route path="households/new" element={<HouseholdForm />} />
              <Route path="households/:id" element={<HouseholdDetail />} />
              <Route path="households/:id/edit" element={<HouseholdForm />} />
              <Route path="households/:id/caregiver" element={<CaregiverForm />} />
              <Route path="households/:id/members/new" element={<MemberForm />} />
              <Route path="members/:id/edit" element={<MemberForm />} />
              <Route path="households/:id/checklist" element={<Checklist />} />
              <Route path="documents/upload" element={<DocumentUpload />} />
              <Route path="scan-intake" element={<ScanIntake />} />
              <Route
                path="audit"
                element={
                  <ProtectedRoute requireRole="admin">
                    <AuditLog />
                  </ProtectedRoute>
                }
              />
            </Route>
          </Routes>
        </BrowserRouter>
        </BootGate>
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </div>
  );
}

export default App;
