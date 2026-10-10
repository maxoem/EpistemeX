import React, {useEffect} from "react";
import {useDiffStore} from "../store/diffStore";
import {Activity, GitCompare, MinusCircle, Play, PlusCircle, Sliders, Square, X, Zap,} from "lucide-react";

export const GraphDiffHud: React.FC = () => {
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
    setIsBlinking,
    isConfigDrawerOpen,
    setIsConfigDrawerOpen,
    setIsPolarityModalOpen,
    closeDiff,
  } = useDiffStore();

  // Keyboard shortcut for Blink (Space) and Close (Esc)
  useEffect(() => {
    if (!isDiffActive) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in an input
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

  // Blink interval timer: rapidly switches scrubMode between 'run_a' and 'run_b'
  useEffect(() => {
    if (!isDiffActive || !isBlinking) return;

    const interval = setInterval(() => {
      setScrubMode(scrubMode === "run_a" ? "run_b" : "run_a");
    }, 600);

    return () => clearInterval(interval);
  }, [isDiffActive, isBlinking, scrubMode, setScrubMode]);

  if (!isDiffActive || !diffData) return null;

  const kpis = diffData.kpis;
  const inversionsCount = diffData.polarity_inversions.length;
  const configDiffCount = diffData.config_diff.length;

  return (
    <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 max-w-[95%] w-auto flex flex-wrap items-center gap-2 p-1.5 bg-app-surface/95 dark:bg-zinc-900/95 backdrop-blur-md border border-app-border rounded-xl shadow-xl text-xs select-none animate-in fade-in slide-in-from-top-2 duration-150">
      {/* Run Badge and Title */}
      <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-app-subtle border border-app-border/80">
        <GitCompare className="w-3.5 h-3.5 text-blue-500 shrink-0" />
        <span className="font-semibold text-app-heading text-[11px] hidden sm:inline">Diff:</span>
        <span className="font-mono text-[10px] text-blue-600 dark:text-blue-400 font-medium truncate max-w-[90px]" title={baseRunId || ""}>
          {baseRunId?.slice(0, 10)}
        </span>
        <span className="text-app-muted text-[10px]">vs</span>
        <span className="font-mono text-[10px] text-emerald-600 dark:text-emerald-400 font-medium truncate max-w-[90px]" title={targetRunId || ""}>
          {targetRunId?.slice(0, 10)}
        </span>
      </div>

      <div className="h-4 w-px bg-app-border hidden sm:block" />

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
          title="Show Diff Lens with union coordinates and change highlights"
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
            ? "bg-amber-500/20 text-amber-500 border-amber-500/40 animate-pulse"
            : "bg-app-bg text-app-muted border-app-border hover:text-app-heading hover:bg-app-subtle"
        }`}
        title="Toggle A/B Blink Comparator (Hotkey: Space)"
      >
        {isBlinking ? <Square className="w-3 h-3 fill-current" /> : <Play className="w-3 h-3 fill-current" />}
        <span className="hidden sm:inline">Blink (Space)</span>
      </button>

      <div className="h-4 w-px bg-app-border hidden md:block" />

      {/* Focus Filter Pills */}
      <div className="hidden md:flex items-center gap-1">
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

        {/* Polarity Inversions trigger */}
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
            title="Inspect claim relations that inverted polarity (e.g. +1 vs -1)"
          >
            <Zap className="w-3 h-3 fill-current text-amber-500" />
            <span>Polarity ({inversionsCount})</span>
          </button>
        )}

        {/* Gained Nodes */}
        <button
          onClick={() => setActiveFilter("gained")}
          className={`px-2 py-0.5 inline-flex items-center gap-1 rounded text-[10px] font-medium transition-colors cursor-pointer ${
            activeFilter === "gained"
              ? "bg-emerald-500/20 text-emerald-500 font-semibold"
              : "text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10"
          }`}
          title="Nodes discovered in Run B"
        >
          <PlusCircle className="w-3 h-3" />
          <span>Gained ({kpis.nodes_gained})</span>
        </button>

        {/* Lost Nodes */}
        <button
          onClick={() => setActiveFilter("lost")}
          className={`px-2 py-0.5 inline-flex items-center gap-1 rounded text-[10px] font-medium transition-colors cursor-pointer ${
            activeFilter === "lost"
              ? "bg-red-500/20 text-red-500 font-semibold"
              : "text-red-500 hover:bg-red-500/10"
          }`}
          title="Nodes dropped in Run B"
        >
          <MinusCircle className="w-3 h-3" />
          <span>Lost ({kpis.nodes_lost})</span>
        </button>

        {/* Argument Drift */}
        {kpis.max_rho_drift > 0 && (
          <button
            onClick={() => setActiveFilter("arg_drift")}
            className={`px-2 py-0.5 inline-flex items-center gap-1 rounded text-[10px] font-medium transition-colors cursor-pointer ${
              activeFilter === "arg_drift"
                ? "bg-purple-500/20 text-purple-500 font-semibold"
                : "text-purple-400 hover:bg-purple-500/10"
            }`}
            title="Gradual strength divergence on theory atoms"
          >
            <Activity className="w-3 h-3" />
            <span>Δρ ({kpis.max_rho_drift})</span>
          </button>
        )}
      </div>

      <div className="h-4 w-px bg-app-border" />

      {/* Config Differences Trigger */}
      <button
        onClick={() => setIsConfigDrawerOpen(!isConfigDrawerOpen)}
        className={`px-2 py-1 inline-flex items-center gap-1 rounded-md text-[11px] font-medium border transition-colors cursor-pointer ${
          isConfigDrawerOpen
            ? "bg-cyan-500/20 text-cyan-400 border-cyan-500/40"
            : "bg-app-bg text-app-muted border-app-border hover:text-app-heading hover:bg-app-subtle"
        }`}
        title="View side-by-side configuration parameters"
      >
        <Sliders className="w-3 h-3 text-cyan-400" />
        <span className="hidden sm:inline">Config ({configDiffCount})</span>
      </button>

      {/* Exit Diff Mode */}
      <button
        onClick={closeDiff}
        className="p-1 rounded-md text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer ml-1"
        title="Exit Diff Mode (Esc)"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
