import { useState } from "react";
import Sidebar, { PageKey } from "./components/sidebar";
import Dashboard from "./pages/dashboard";
import NewAnalysis from "./pages/newanalysis";
import RepositoryExplorer from "./pages/repositoryexplorer";
import ArchitectureView from "./pages/architectureview";
import KnowledgeExplorer from "./pages/knowledgeexplorer";
import SprintTimeline from "./pages/sprinttimeline";
import ImplementationDesigner from "./pages/implementationdesigner";
import PromptGenerator from "./pages/promptgenerator";

export interface ProjectCtx {
  id: number;
  name: string;
}

export default function App() {
  const [page, setPage] = useState<PageKey>("dashboard");
  const [project, setProject] = useState<ProjectCtx | null>(null);

  const openProject = (p: ProjectCtx, target?: PageKey) => {
    setProject(p);
    if (target) setPage(target);
    else setPage("repository");
  };

  return (
    <div className="app">
      <Sidebar page={page} setPage={setPage} project={project} />
      <div className="main">
        {page === "dashboard" && <Dashboard openProject={openProject} />}
        {page === "new" && (
          <NewAnalysis onCreated={(p) => { setProject(p); setPage("repository"); }} />
        )}
        {page === "repository" && project && (
          <RepositoryExplorer project={project} setPage={setPage} />
        )}
        {page === "architecture" && project && <ArchitectureView project={project} />}
        {page === "knowledge" && project && <KnowledgeExplorer project={project} />}
        {page === "sprints" && project && <SprintTimeline project={project} />}
        {page === "designer" && project && <ImplementationDesigner project={project} />}
        {page === "prompt" && project && <PromptGenerator project={project} />}
        {!project && page !== "dashboard" && page !== "new" && (
          <div className="card">
            <h2>No project selected</h2>
            <p className="subtitle">Pick a project from the Dashboard or start a New Analysis.</p>
          </div>
        )}
      </div>
    </div>
  );
}
