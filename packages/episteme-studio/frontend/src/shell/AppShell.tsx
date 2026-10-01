import React, { useEffect, useState } from "react";
import { useRunsStore } from "../store/runsStore";
import { useProjectSettingsStore } from "../store/projectSettingsStore";
import { AppLogo } from "./AppLogo";
import { StudioSettingsModal } from "./StudioSettingsModal";
import { ProjectSettingsModal } from "./ProjectSettingsModal";
import { RunCredentialsModal } from "../panels/RunCredentialsModal";
import { GlobalCommandOmnibar } from "./GlobalCommandOmnibar";
import { ConnectionProvenancePill } from "./ConnectionProvenancePill";
import {
  Activity,
  ChevronDown,
  Cpu,
  Database,
  Laptop,
  Layers,
  Moon,
  Network,
  Settings,
  Sliders,
  Sun,
  Terminal,
} from "lucide-react";

interface AppShellProps {
  children: React.ReactNode;
  activeTab: "runs" | "graph" | "cypher" | "config" | "engine" | "evaluation";
  setActiveTab: (tab: "runs" | "graph" | "cypher" | "config" | "engine" | "evaluation") => void;
  contextSelector?: React.ReactNode;
}

const NAV_TABS = [
  {
    id: "graph" as const,
    label: "Explorer",
    title: "Graph Explorer: Topological Structure & Visual Inspection",
    icon: Network,
  },
  {
    id: "runs" as const,
    label: "Corpus",
    title: "Corpus & Pipeline Runs: Artifact Provenance & Execution Manifests",
    icon: Layers,
  },
  {
    id: "evaluation" as const,
    label: "Evaluation",
    title: "Evaluation Workbench: Benchmark Verification, Calibration & Alignment",
    icon: Activity,
  },
  {
    id: "cypher" as const,
    label: "Console",
    title: "Cypher Console: Interactive Neo4j Graph Query Terminal",
    icon: Terminal,
  },
  {
    id: "config" as const,
    label: "Execution",
    title: "Execution Workbench: Pipeline Phase Configuration & Staging",
    icon: Sliders,
  },
  {
    id: "engine" as const,
    label: "Engine",
    title: "Engine Settings: Epistemic Schemas, Polarity Matrices & Models",
    icon: Cpu,
  },
];

export const AppShell: React.FC<AppShellProps> = ({
  children,
  activeTab,
  setActiveTab,
  contextSelector,
}) => {
  const { capabilities, selectedRunDetail, searchableNodes, setFocusedNodeId } = useRunsStore();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isCredsModalOpen, setIsCredsModalOpen] = useState(false);
  const { fetchLangfuseStatus } = useProjectSettingsStore();

  useEffect(() => {
    fetchLangfuseStatus();
  }, [fetchLangfuseStatus]);

  // Keyboard shortcut for settings (Cmd+, or Ctrl+,)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === ",") {
        e.preventDefault();
        setIsSettingsOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="flex flex-col h-screen w-screen bg-app-bg text-app-text">
      {/* Global Header: Fixed 48px height, 1px bottom border coordinate axis */}
      <header className="h-12 px-4 border-b border-app-border bg-app-surface select-none flex items-center justify-between shrink-0 z-30 whitespace-nowrap relative shadow-none font-sans text-[13px]">
        {/* Left Zone: Origin & Navigation Path */}
        <div className="flex items-center h-full shrink-0 min-w-0">
          <AppLogo />

          {/* Primary Navigation: Borderless Naked Text Labels with left spacing */}
          <nav
            className="flex items-center gap-5 text-xs ml-8"
            aria-label="Workspace Navigation"
          >
                        {NAV_TABS.map((tab) => {
                            const active = activeTab === tab.id;
                            return (
                                <button
                                    key={tab.id}
                                    type="button"
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`py-1 text-xs font-sans transition-colors cursor-pointer inline-flex items-center gap-1.5 border-0 bg-transparent outline-none leading-none ${
                                        active
                                            ? "font-[600]"
                                            : "text-app-muted hover:text-app-heading font-[400]"
                                    }`}
                                    title={tab.title}
                                    aria-current={active ? "page" : undefined}
                                >
                                    <span>{tab.label}</span>
                                    {tab.id === "cypher" && !capabilities?.neo4j && (
                                        <span
                                            className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0"
                                            title="Neo4j connection offline"
                                        />
                                    )}
                                </button>
                            );
                        })}
                    </nav>
                </div>

        {/* Center: The Central Command Vector (>_ Prompt) */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-auto">
          <GlobalCommandOmnibar
            nodes={searchableNodes}
            onSelectNode={(node) => {
              setFocusedNodeId(node.id);
              if (activeTab !== "graph") {
                setActiveTab("graph");
              }
            }}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            onOpenSettings={() => setIsSettingsOpen(true)}
            onOpenCreds={() => setIsCredsModalOpen(true)}
          />
        </div>

        {/* Right: The Unified Context & Global State Selectors */}
        <div className="flex items-center justify-end shrink-0 gap-3">
          {contextSelector && (
            <div className="flex items-center">{contextSelector}</div>
          )}
          <ConnectionProvenancePill
            onOpenCreds={() => setIsCredsModalOpen(true)}
            onOpenSettings={() => setIsSettingsOpen(true)}
          />
        </div>
      </header>

            {/* Main Container */}
            <main className="flex-1 overflow-hidden flex">{children}</main>

            {/* Preferences Modal */}
            <StudioSettingsModal
                isOpen={isSettingsOpen}
                onClose={() => setIsSettingsOpen(false)}
            />

            {/* Project Infrastructure & Telemetry Settings Modal */}
            <ProjectSettingsModal/>

            {/* Neo4j Connection & Credentials Modal */}
            {isCredsModalOpen && (
                <RunCredentialsModal
                    isOpen={isCredsModalOpen}
                    onClose={() => setIsCredsModalOpen(false)}
                    runId={selectedRunDetail?.run_id}
                />
            )}
        </div>
    );
};
