import React, { useEffect } from "react";
import { useDiffStore, DiffScrubMode, DiffFilter } from "../store/diffStore";
import {
  GitCompare,
  Zap,
  PlusCircle,
  MinusCircle,
  Sliders,
  X,
  Play,
  Square,
  Activity,
  Network,
  ArrowRight,
  Layers,
  ChevronRight,
} from "lucide-react";

interface AppDiffBottomDockProps {
  activeTab: "runs" | "graph" | "cypher" | "config" | "engine" | "evaluation";
  onNavigateTab: (tab: "runs" | "graph" | "cypher" | "config" | "engine" | "evaluation") => void;
}

export const AppDiffBottomDock: React.FC<AppDiffBottomDockProps> = ({
  activeTab,
  onNavigateTab,
}) => {
  const {
    isDiffActive,
    baseRunId,
    targetRunId,
    diffData,
    scrubMode,
    setScrubMode,
    activeFilter,
    setActiveFilter,
    isBlinking,
    toggleBlink,
    setIsPolarityModalOpen,
    closeDiff,
  } = useDiffStore();

  // Keyboard shortcut for Blink (Space) and Close (Esc)
  useEffect(() => {
    if (!isDiffActive) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
      if (e.code === "Space") {
        e.preventDefault();
        toggleBlink();
      } else if (e.key === "Escape") {
        closeDiff();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isDiffActive, toggleBlink, closeDiff]);

  // Blink interval timer: rapidly alternates scrubMode between 'run_a' and 'run_b'
  useEffect(() => {
    if (!isDiffActive || !isBlinking) return;

    const interval = setInterval(() => {
      setScrubMode(scrubMode === "run_a" ? "run_b" : "run_a");
    }, 650);

    return () => clearInterval(interval);
  }, [isDiffActive, isBlinking, scrubMode, setScrubMode]);

  if (!isDiffActive || !diffData) return null;

  const kpis = diffData.kpis;
  const inversionsCount = diffData.polarity_inversions.length;
  const configDiffCount = diffData.config_diff.length;

  return (
    <footer className="h-13 px-4 border-t border-app-border bg-app-surface/95 dark:bg-zinc-900/95 backdrop-blur-md shadow-2xl flex items-center justify-between gap-3 shrink-0 select-none z-40 animate-in fade-in slide-in-from-bottom-2 duration-150">
      {/* Left Zone: Identity and Active Pair */}
      <div className="flex items-center gap-2 min-w-0">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-500/10 border border-blue-500/30 text-blue-400">
          <GitCompare className="w-3.5 h-3.5 shrink-0" />
          <span className="font-semibold text-xs uppercase tracking-wider hidden sm:inline">Diff Session</span>
        </div>

        <div className="flex items-center gap-1.5 font-mono text-[11px] truncate">
          <span className="px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/25 font-semibold truncate max-w-[110px]" title={`Baseline: ${baseRunId}`}>
            {baseRunId?.slice(0, 12)}
          </span>
          <span className="text-app-muted text-xs">⇄</span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25 font-semibold truncate max-w-[110px]" title={`Candidate: ${targetRunId}`}>
            {targetRunId?.slice(0, 12)}
          </span>
        </div>
      </div>

      {/* Center Zone: Context-Sensitive Controls */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Graph Explorer Controls */}
        {activeTab === "graph" && (
          <div className="flex items-center gap-2">
            {/* 3-State Scrub Bar */}
            <div className="inline-flex items-center p-0.5 bg-app-bg rounded-lg border border-app-border gap-0.5">
              <button
                onClick={() => setScrubMode("run_a")}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors cursor-pointer ${
                  scrubMode === "run_a"
                    ? "bg-blue-600 text-white shadow-xs font-semibold"
                    : "text-app-muted hover:text-app-heading hover:bg-app-subtle"
                }`}
                title="Show Baseline Run A only"
              >
                Run A
              </button>
              <button
                onClick={() => setScrubMode("diff")}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors cursor-pointer ${
                  scrubMode === "diff"
                    ? "bg-app-surface text-app-heading shadow-xs font-bold border border-app-border"
                    : "text-app-muted hover:text-app-heading hover:bg-app-subtle"
                }`}
                title="Show Diff Lens with union topology and change highlights"
              >
                Diff Lens
              </button>
              <button
                onClick={() => setScrubMode("run_b")}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors cursor-pointer ${
                  scrubMode === "run_b"
                    ? "bg-emerald-600 text-white shadow-xs font-semibold"
                    : "text-app-muted hover:text-app-heading hover:bg-app-subtle"
                }`}
                title="Show Candidate Run B only"
              >
                Run B
              </button>
            </div>

            {/* Blink Comparator Button */}
            <button
              onClick={toggleBlink}
              className={`px-2 py-1 inline-flex items-center gap-1 rounded-md text-[11px] font-medium border transition-colors cursor-pointer ${
                isBlinking
                  ? "bg-amber-500/20 text-amber-500 border-amber-500/40 animate-pulse font-semibold"
                  : "bg-app-bg text-app-muted border-app-border hover:text-app-heading hover:bg-app-subtle"
              }`}
              title="Toggle A/B Blink Comparator (Hotkey: Space)"
            >
              {isBlinking ? <Square className="w-3 h-3 fill-current" /> : <Play className="w-3 h-3 fill-current" />}
              <span className="hidden md:inline">Blink (Space)</span>
            </button>

            <div className="h-4 w-px bg-app-border hidden lg:block" />

            {/* Filter Pills */}
            <div className="hidden lg:flex items-center gap-1">
              <button
                onClick={() => setActiveFilter("all")}
                className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors cursor-pointer ${
                  activeFilter === "all"
                    ? "bg-zinc-700 text-white dark:bg-zinc-300 dark:text-zinc-900"
                    : "text-app-muted hover:text-app-heading hover:bg-app-subtle"
                }`}
              >
                All ({diffData.union_graph.nodes.length})
              </button>

              {inversionsCount > 0 && (
                <button
                  onClick={() => {
                    setActiveFilter("polarity_inversions");
                    setIsPolarityModalOpen(true);
                  }}
                  className={`px-2 py-0.5 inline-flex items-center gap-1 rounded text-[10px] font-semibold transition-colors cursor-pointer border ${
                    activeFilter === "polarity_inversions"
                      ? "bg-amber-500/20 text-amber-500 border-amber-500/50"
                      : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30 hover:bg-amber-500/20"
                  }`}
                  title="Inspect contradictory claim relations"
                >
                  <Zap className="w-3 h-3 fill-current text-amber-500" />
                  <span>Polarity ({inversionsCount})</span>
                </button>
              )}

              <button
                onClick={() => setActiveFilter("gained")}
                className={`px-2 py-0.5 inline-flex items-center gap-1 rounded text-[10px] font-medium transition-colors cursor-pointer ${
                  activeFilter === "gained"
                    ? "bg-emerald-500/20 text-emerald-500 font-semibold"
                    : "text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10"
                }`}
                title="Nodes gained in Run B"
              >
                <PlusCircle className="w-3 h-3" />
                <span>+{kpis.nodes_gained}</span>
              </button>

              <button
                onClick={() => setActiveFilter("lost")}
                className={`px-2 py-0.5 inline-flex items-center gap-1 rounded text-[10px] font-medium transition-colors cursor-pointer ${
                  activeFilter === "lost"
                    ? "bg-red-500/20 text-red-500 font-semibold"
                    : "text-red-500 hover:bg-red-500/10"
                }`}
                title="Nodes lost in Run B"
              >
                <MinusCircle className="w-3 h-3" />
                <span>-{kpis.nodes_lost}</span>
              </button>
            </div>
          </div>
        )}

        {/* Cross-Tab View Switchers */}
        {activeTab !== "config" ? (
          <button
            onClick={() => onNavigateTab("config")}
            className="px-2.5 py-1 inline-flex items-center gap-1.5 rounded-md text-[11px] font-medium bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/30 transition-colors cursor-pointer"
            title="Inspect side-by-side Phase Configurations, parameters, and prompts"
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Phase Config Diff ({configDiffCount})</span>
            <ChevronRight className="w-3 h-3 opacity-70" />
          </button>
        ) : (
          <button
            onClick={() => onNavigateTab("graph")}
            className="px-2.5 py-1 inline-flex items-center gap-1.5 rounded-md text-[11px] font-medium bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/30 transition-colors cursor-pointer"
            title="Return to Graph Canvas Diff View"
          >
            <Network className="w-3.5 h-3.5" />
            <span>Graph Canvas Diff</span>
            <ChevronRight className="w-3 h-3 opacity-70" />
          </button>
        )}
      </div>

      {/* Right Zone: Summary KPIs & Dismiss Action */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="hidden xl:flex items-center gap-2.5 text-[11px] text-app-muted border-l border-app-border pl-3">
          <span>
            Similarity: <strong className="font-mono text-app-heading">{(kpis.jaccard_node_similarity * 100).toFixed(0)}%</strong>
          </span>
          {kpis.max_rho_drift > 0 && (
            <span>
              Max Δρ: <strong className="font-mono text-blue-400">+{kpis.max_rho_drift.toFixed(2)}</strong>
            </span>
          )}
        </div>

        <button
          onClick={closeDiff}
          className="h-7 px-2 inline-flex items-center gap-1 rounded-md text-app-muted hover:text-app-heading hover:bg-app-subtle text-xs font-medium border border-transparent hover:border-app-border transition-colors cursor-pointer"
          title="Exit comparison mode (Esc)"
        >
          <X className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Exit Diff</span>
        </button>
      </div>
    </footer>
  );
};
