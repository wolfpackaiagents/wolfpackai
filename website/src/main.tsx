import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./index.css";
import { I18nProvider } from "./i18n/context";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import LandingPage from "./pages/LandingPage";
import FrameworkSection from "./pages/FrameworkSection";
import ControlPlaneSection from "./pages/ControlPlaneSection";
import ControlPlaneFirstSteps from "./pages/ControlPlaneFirstSteps";
import ExamplePage from "./pages/ExamplePage";
import CategoryPage from "./pages/CategoryPage";
import AllExamples from "./pages/AllExamples";
import InstallationPage from "./pages/InstallationPage";
import ConceptAgentLoop from "./pages/ConceptAgentLoop";
import ConceptTeamDelegation from "./pages/ConceptTeamDelegation";
import ConceptChatArchitecture from "./pages/ConceptChatArchitecture";
import ConceptObserverFlow from "./pages/ConceptObserverFlow";
import ConceptAMPControlPlane from "./pages/ConceptAMPControlPlane";
import ConceptFrameworkOverview from "./pages/ConceptFrameworkOverview";
import AuthorPage from "./pages/AuthorPage";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route element={<Layout />}>
            <Route path="/docs" element={<Home />} />
            <Route path="/sobre-o-autor" element={<AuthorPage />} />
            <Route path="/installation" element={<InstallationPage />} />
            <Route path="/framework/:sectionId" element={<FrameworkSection />} />
            <Route path="/control-plane/first-steps" element={<ControlPlaneFirstSteps />} />
            <Route path="/control-plane/:sectionId" element={<ControlPlaneSection />} />
            <Route path="/examples" element={<AllExamples />} />
            <Route path="/examples/category/:categoryName" element={<CategoryPage />} />
            <Route path="/examples/:exampleId" element={<ExamplePage />} />
            <Route path="/concepts/agent-loop" element={<ConceptAgentLoop />} />
            <Route path="/concepts/team-delegation" element={<ConceptTeamDelegation />} />
            <Route path="/concepts/chat-architecture" element={<ConceptChatArchitecture />} />
            <Route path="/concepts/observer-flow" element={<ConceptObserverFlow />} />
            <Route path="/concepts/amp-control-plane" element={<ConceptAMPControlPlane />} />
            <Route path="/concepts/framework-overview" element={<ConceptFrameworkOverview />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </I18nProvider>
  </StrictMode>
);
