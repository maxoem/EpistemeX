import React, { useState, useEffect } from "react";
import { AppShell } from "./shell/AppShell";
import { RunList } from "./panels/RunList";
import { RunDetailView } from "./panels/RunDetailView";
import { ConfigEditor } from "./panels/ConfigEditor";
import { PhaseConfigDiffView } from "./panels/PhaseConfigDiffView";
import { ResizablePanel } from "./panels/ResizablePanel";
import { AppDiffBottomDock } from "./shell/AppDiffBottomDock";
import { useRunsStore } from "./store/runsStore";
import { useDiffStore } from "./store/diffStore";
import { useEngineSettingsStore } from "./store/engineSettingsStore";
import { EngineSettingsPage } from "./panels/engine/EngineSettingsPage";
import { subscribeToRunEvents } from "./api/sse";

const CypherConsole = React.lazy(() =>
  import("./console/CypherConsole").then((m) => ({ default: m.CypherConsole }))
);

const GraphCanvas = React.lazy(() =>
  import("./graph/GraphCanvas").then((m) => ({ default: m.GraphCanvas }))
);

const EvaluationWorkspace = React.lazy(() =>
  import("./panels/evaluation/EvaluationWorkspace").then((m) => ({
    default: m.EvaluationWorkspace,
  }))
);

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<
    "runs" | "graph" | "cypher" | "config" | "engine" | "evaluation"
  >("runs");
  const [stagingOverride, setStagingOverride] = useState(false);
  const { isDiffActive, diffData } = useDiffStore();
  const {
    capabilities,
    fetchCapabilities,
    fetchRuns,
    selectedRunId,
    selectedRunDetail,
    addEvent,
    addEvents,
    setIsStreaming,
    refreshActiveRun,
  } = useRunsStore();

  const { fetchEngineSettings } = useEngineSettingsStore();

  // Initial load
  useEffect(() => {
    fetchCapabilities();
    fetchRuns();
    fetchEngineSettings();
  }, [fetchCapabilities, fetchRuns, fetchEngineSettings]);

  // Periodic sync when a run is active to keep manifests, durations, and DAG synced
  useEffect(() => {
    if (!selectedRunId) return;
    const isRunning =
      selectedRunDetail?.status === "running" || selectedRunDetail?.status === "planned";
    if (!isRunning) return;

    const interval = setInterval(() => {
      refreshActiveRun();
    }, 1500);

    return () => clearInterval(interval);
  }, [selectedRunId, selectedRunDetail?.status, refreshActiveRun]);

  // Live SSE connection when run is active
  useEffect(() => {
    if (!selectedRunId) return;

    const isRunning =
      selectedRunDetail?.status === "running" || selectedRunDetail?.status === "planned";

    setIsStreaming(true);

    const unsubscribe = subscribeToRunEvents(selectedRunId, {
      onEvents: (events) => {
        addEvents(events);
      },
      onEvent: (event) => {
        addEvent(event);
      },
      onOpen: () => {
        setIsStreaming(true);
      },
      onError: () => {
        setIsStreaming(false);
      },
    });

    return () => {
      unsubscribe();
      setIsStreaming(false);
    };
  }, [selectedRunId, selectedRunDetail?.status, addEvent, addEvents, setIsStreaming]);

  return (
    <AppShell activeTab={activeTab} setActiveTab={setActiveTab}>
      <div className="flex flex-col w-full h-full overflow-hidden">
        <div className="flex flex-1 w-full h-full overflow-hidden">
          {/* Left: Run Browser List (Shown for runs and graph views) */}
          {activeTab !== "cypher" &&
            activeTab !== "config" &&
            activeTab !== "engine" &&
            activeTab !== "evaluation" && (
              <ResizablePanel
                side="left"
                storageKey="glp-studio-left-sidebar-width"
                defaultWidth={280}
                minWidth={280}
                maxWidth={500}
                collapsible={true}
                collapseThreshold={120}
                showFooter={false}
                className="!bg-[#F8FAFC] dark:!bg-app-rail !border-r !border-[#E2E8F0] dark:!border-app-border"
              >
                <RunList />
              </ResizablePanel>
            )}

          {/* Right: Main Workbench View, Graph View, Cypher Console, Engine Settings, Evaluation, or Config Editor */}
          <div className="flex-1 h-full overflow-hidden bg-app-bg">
            {activeTab === "runs" ? (
              <RunDetailView
                onNavigateToConfig={() => setActiveTab("config")}
                onNavigateToGraph={() => setActiveTab("graph")}
              />
            ) : activeTab === "graph" ? (
              <React.Suspense
                fallback={
                  <div className="flex items-center justify-center h-full text-xs text-app-muted">
                    Loading Graph...
                  </div>
                }
              >
                <GraphCanvas onNavigateToCypher={() => setActiveTab("cypher")} />
              </React.Suspense>
            ) : activeTab === "evaluation" ? (
              <React.Suspense
                fallback={
                  <div className="flex items-center justify-center h-full text-xs text-app-muted">
                    Loading Evaluation Workbench...
                  </div>
                }
              >
                <EvaluationWorkspace />
              </React.Suspense>
            ) : activeTab === "cypher" ? (
              <div className="p-3 h-full">
                <React.Suspense
                  fallback={
                    <div className="flex items-center justify-center h-full text-xs text-app-muted">
                      Loading Cypher Console...
                    </div>
                  }
                >
                  <CypherConsole neo4jAvailable={capabilities?.neo4j || false} />
                </React.Suspense>
              </div>
            ) : activeTab === "engine" ? (
              <EngineSettingsPage />
            ) : isDiffActive && diffData && !stagingOverride ? (
              <PhaseConfigDiffView onSwitchToStaging={() => setStagingOverride(true)} />
            ) : (
              <ConfigEditor onNavigateToRuns={() => setActiveTab("runs")} />
            )}
          </div>
        </div>

        {/* Global Bottom Comparison Dock Bar */}
        <AppDiffBottomDock
          activeTab={activeTab}
          onNavigateTab={(tab) => {
            setStagingOverride(false);
            setActiveTab(tab);
          }}
        />
      </div>
    </AppShell>
  );
};

export default App;
