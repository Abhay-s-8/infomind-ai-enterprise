import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import AnalyticsPage from "./features/analytics/AnalyticsPage";
import AssistantPage from "./features/assistant/AssistantPage";
import AuditPage from "./features/audit/AuditPage";
import LoginPage from "./features/auth/LoginPage";
import ClassificationPage from "./features/classification/ClassificationPage";
import DashboardPage from "./features/dashboard/DashboardPage";
import DocumentDetailPage from "./features/documents/DocumentDetailPage";
import DocumentsPage from "./features/documents/DocumentsPage";
import ReviewsPage from "./features/reviews/ReviewsPage";
import SearchPage from "./features/search/SearchPage";
import SettingsPage from "./features/settings/SettingsPage";
import { useAuth } from "./lib/auth";
import type { Role } from "./types";

function Guard({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, loading, can } = useAuth();
  if (loading) return <Spinner label="Restoring session" />;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !(roles.length ? can(...roles) : can())) return <Navigate to={user.role === "reviewer" ? "/reviews" : "/settings"} replace />;
  return <>{children}</>;
}

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route element={<Guard><Layout /></Guard>}>
        <Route index element={<Guard roles={["analyst"]}><DashboardPage /></Guard>} />
        <Route path="documents" element={<Guard roles={["analyst"]}><DocumentsPage /></Guard>} />
        <Route path="documents/:id" element={<Guard><DocumentDetailPage /></Guard>} />
        <Route path="assistant" element={<Guard roles={["analyst"]}><AssistantPage /></Guard>} />
        <Route path="search" element={<Guard roles={["analyst"]}><SearchPage /></Guard>} />
        <Route path="classification" element={<Guard roles={["analyst"]}><ClassificationPage /></Guard>} />
        <Route path="analytics" element={<Guard roles={["analyst"]}><AnalyticsPage /></Guard>} />
        <Route path="reviews" element={<Guard roles={["reviewer"]}><ReviewsPage /></Guard>} />
        <Route path="audit" element={<Guard roles={[]}><AuditPage /></Guard>} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
