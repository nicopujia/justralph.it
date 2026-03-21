import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/system/app-shell";
import { LandingPage } from "@/components/system/landing-page";
import { PricingPage } from "@/components/system/pricing-page";
import { ProjectDetailPage } from "@/components/system/project-detail-page";
import { ProjectsPage } from "@/components/system/projects-page";
import { ProjectStoreProvider } from "@/components/system/project-store";
import { SettingsPage } from "@/components/system/settings-page";
import "./index.css";

export function App() {
  return (
    <ProjectStoreProvider>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app" element={<AppShell />}>
          <Route index element={<Navigate to="projects" replace />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="pricing" element={<PricingPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ProjectStoreProvider>
  );
}

export default App;
