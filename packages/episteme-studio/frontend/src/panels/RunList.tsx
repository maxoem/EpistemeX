import React, {useCallback, useEffect, useMemo, useState} from "react";
import {useRunsStore} from "../store/runsStore";
import {RunStatus, RunSummary} from "../api/types";
import {Check, Copy, List, RotateCcw, Scale, Search, Sliders, X,} from "lucide-react";
import {AboutModal} from "../shell/AboutModal";
import {APP_CONFIG} from "@/config/app";
import {resolvePhaseKey} from "./phaseConfig/phaseConfigResolver";
import {PipelineDagViewer} from "./PipelineDagViewer";

const formatDuration = (seconds?: number | null): string => {
  if (seconds === null || seconds === undefined) return "";
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const rm = Math.round(m % 60);
  return `${h}h ${rm}m`;
};

/**
 * Minimalist geometric status dot:
 * Solid dot ● for fresh compute
 * Hollow ring ○ for cached/hydrated
 * Oscillating pulse for active execution
 * Amber dash — for aborted/skipped
 */
const getStatusDot = (status: RunStatus | string, isCached: boolean = false) => {
  switch (status) {
    case "completed":
      if (isCached) {
        return (
          <span
            className="w-2 h-2 rounded-full border border-emerald-600 dark:border-emerald-400 bg-transparent shrink-0"
            title="Cached execution"
          />
        );
      }
      return (
        <span
          className="w-2 h-2 rounded-full bg-emerald-600 dark:bg-emerald-500 shrink-0"
          title="Fresh compute"
        />
      );
    case "running":
      return (
        <span className="relative flex h-2 w-2 shrink-0" title="Running">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-500 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-600" />
        </span>
      );
    case "failed":
      return (
        <span
          className="w-2 h-2 rounded-full bg-rose-600 dark:bg-rose-500 shrink-0"
          title="Failed"
        />
      );
    case "aborted":
      return (
        <span
          className="w-2 h-2 rounded-full bg-amber-600 dark:bg-amber-500 shrink-0"
          title="Aborted"
        />
      );
    default:
      return (
        <span
          className="w-2 h-2 rounded-full bg-app-border shrink-0"
          title={status}
        />
      );
  }
};

export const RunList: React.FC = () => {
  const {
    runs,
    selectedRunId,
    selectRun,
    isLoadingRuns,
    fetchRuns,
    selectedRunDetail,
    selectedPhaseKey,
    setSelectedPhaseKey,
  } = useRunsStore();

  const [isAboutOpen, setIsAboutOpen] = useState(false);
  const [navMode, setNavMode] = useState<"stages" | "catalog">("stages");
  const [searchFilter, setSearchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "completed" | "failed" | "running">("all");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Derive active phases from current run detail or standard 8-stage sequence
  const stageItems = useMemo(() => {
    if (!selectedRunDetail?.phase_records || selectedRunDetail.phase_records.length === 0) {
      return [
        { ordinal: 1, name: "Foundation & Ingestion", key: "phase1", status: "pending" as RunStatus, count: 0, reused: false },
        { ordinal: 2, name: "Entity & Local Extraction", key: "phase2", status: "pending" as RunStatus, count: 0, reused: false },
        { ordinal: 3, name: "Global Relations", key: "phase3", status: "pending" as RunStatus, count: 0, reused: false },
        { ordinal: 4, name: "Latent Transitivity", key: "phase3b", status: "pending" as RunStatus, count: 0, reused: false },
        { ordinal: 5, name: "Entity Maturation", key: "phase4_maturation", status: "pending" as RunStatus, count: 0, reused: false },
        { ordinal: 6, name: "Argument Mining", key: "phase4", status: "pending" as RunStatus, count: 0, reused: false },
        { ordinal: 7, name: "Argument Fusion", key: "phase5", status: "pending" as RunStatus, count: 0, reused: false },
        { ordinal: 8, name: "TheoryNet & Bridges", key: "phase6", status: "pending" as RunStatus, count: 0, reused: false },
      ];
    }

    return selectedRunDetail.phase_records.map((p) => ({
      ordinal: p.phase_ordinal,
      name: p.phase_name,
      key: resolvePhaseKey(p),
      status: p.status,
      count: p.artifact_count,
      reused: p.reused,
    }));
  }, [selectedRunDetail?.phase_records]);

  // Filtered runs list for catalog view
  const filteredRuns = useMemo(() => {
    return runs.filter((run) => {
      if (statusFilter !== "all" && run.status !== statusFilter) {
        return false;
      }
      if (!searchFilter.trim()) return true;
      const q = searchFilter.toLowerCase();
      const matchId = run.run_id.toLowerCase().includes(q);
      const matchDoc = (run.primary_input || "").toLowerCase().includes(q);
      const matchSources = (run.input_sources || []).some((s) => s.toLowerCase().includes(q));
      return matchId || matchDoc || matchSources;
    });
  }, [runs, searchFilter, statusFilter]);

  // Active run display attributes
  const activeDocName = selectedRunDetail?.primary_input
    ? selectedRunDetail.primary_input.split(/[/\\]/).pop() || selectedRunDetail.primary_input
    : selectedRunDetail?.input_sources && selectedRunDetail.input_sources[0]
    ? selectedRunDetail.input_sources[0].split(/[/\\]/).pop() || selectedRunDetail.input_sources[0]
    : "active run";
  const activeShortHash = selectedRunDetail?.run_id ? selectedRunDetail.run_id.slice(0, 8) : "";
  const activeDur = formatDuration(selectedRunDetail?.duration_seconds);

  // Trigger global Command Omnibar in Run Switcher mode (Cmd + P)
  const handleOpenRunSwitcher = useCallback(() => {
    window.dispatchEvent(new CustomEvent("glp-open-run-switcher"));
  }, []);

  // Keyboard navigation: j / k triage for stages or run catalog
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select" || (e.target as HTMLElement)?.isContentEditable) {
        return;
      }

      if (navMode === "stages") {
        const stageKeys: (string | null)[] = [null, "generations", ...stageItems.map((s) => s.key)];
        const currentIndex = stageKeys.indexOf(selectedPhaseKey);

        if (e.key === "j" || e.key === "ArrowDown") {
          e.preventDefault();
          const nextIndex = currentIndex < 0 ? 0 : Math.min(currentIndex + 1, stageKeys.length - 1);
          setSelectedPhaseKey(stageKeys[nextIndex]);
        } else if (e.key === "k" || e.key === "ArrowUp") {
          e.preventDefault();
          const prevIndex = currentIndex < 0 ? 0 : Math.max(currentIndex - 1, 0);
          setSelectedPhaseKey(stageKeys[prevIndex]);
        }
      } else {
        // Navigating run catalog
        if (e.key === "j" || e.key === "ArrowDown") {
          if (filteredRuns.length === 0) return;
          e.preventDefault();
          const currentIndex = filteredRuns.findIndex((r) => r.run_id === selectedRunId);
          const nextIndex = currentIndex < 0 ? 0 : Math.min(currentIndex + 1, filteredRuns.length - 1);
          selectRun(filteredRuns[nextIndex].run_id);
        } else if (e.key === "k" || e.key === "ArrowUp") {
          if (filteredRuns.length === 0) return;
          e.preventDefault();
          const currentIndex = filteredRuns.findIndex((r) => r.run_id === selectedRunId);
          const prevIndex = currentIndex < 0 ? 0 : Math.max(currentIndex - 1, 0);
          selectRun(filteredRuns[prevIndex].run_id);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [navMode, stageItems, selectedPhaseKey, setSelectedPhaseKey, filteredRuns, selectedRunId, selectRun]);

  const handleCopyHash = useCallback((e: React.MouseEvent, runId: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(runId);
    setCopiedId(runId);
    setTimeout(() => setCopiedId(null), 1500);
  }, []);

  return (
    <div className="flex flex-col h-full bg-app-bg/70 text-app-heading overflow-hidden select-none border-r border-app-border">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Execution Terminal Status Bar: run · target · eval                  */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {selectedRunDetail && (
        <div
          onClick={handleOpenRunSwitcher}
          className="px-3 py-1.5 border-b border-app-border bg-app-subtle/50 hover:bg-app-subtle transition-colors cursor-pointer flex items-center justify-between gap-2 shrink-0 group font-mono text-[10px]"
          title="Click or press ⌘P to switch run"
        >
          <div className="flex items-center gap-2 min-w-0 flex-1 truncate">
            {getStatusDot(
              selectedRunDetail.status,
              (selectedRunDetail.reused_phase_count ?? 0) > 0
            )}
            <div className="flex items-center gap-1.5 truncate">
              <span className="text-app-muted">target:</span>
              <span className="text-app-heading font-medium truncate">
                {activeDocName}
              </span>
              <span className="text-app-muted">|</span>
              <span className="text-app-muted">eval:</span>
              <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                L1–L4
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0 text-app-muted">
            {activeDur && <span className="tabular-nums">{activeDur}</span>}
            <kbd className="text-[9px] font-mono text-app-muted bg-app-surface px-1 py-0.2 rounded border border-app-border group-hover:border-blue-500/40 group-hover:text-blue-500 transition-colors">
              ⌘P
            </kbd>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setNavMode((prev) => (prev === "stages" ? "catalog" : "stages"));
              }}
              className="p-1 rounded hover:bg-app-subtle text-app-muted hover:text-app-heading transition-colors cursor-pointer"
              title={navMode === "stages" ? "Browse Run Catalog" : "Inspect Active Stages"}
            >
              {navMode === "stages" ? <List className="w-3 h-3" /> : <Sliders className="w-3 h-3" />}
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                fetchRuns();
              }}
              className="p-1 rounded hover:bg-app-subtle text-app-muted hover:text-app-heading transition-colors cursor-pointer inline-flex items-center justify-center"
              title="Refresh run manifests"
            >
              <RotateCcw className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* VIEW A: Topological Pipeline DAG Stage Navigation                   */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {navMode === "stages" ? (
        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
          <PipelineDagViewer
            phaseRecords={selectedRunDetail?.phase_records || []}
            selectedPhaseKey={selectedPhaseKey}
            onSelectPhase={setSelectedPhaseKey}
            showOverviewOption={true}
            showHeader={false}
            llmModel={selectedRunDetail?.models?.llm_model}
          />
        </div>
      ) : (
        /* ───────────────────────────────────────────────────────────────── */
        /* VIEW B: Disciplined Flush Tabular Run Catalog List                */
        /* ───────────────────────────────────────────────────────────────── */
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {/* Scoping & Filter Toolbar */}
          <div className="px-2.5 py-1.5 border-b border-app-border bg-app-surface space-y-1.5 shrink-0">
            {/* Borderless Search Input */}
            <div className="relative flex items-center">
              <Search className="w-3.5 h-3.5 absolute left-2 text-app-muted pointer-events-none" />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Filter doc or hash..."
                className="w-full h-6 pl-7 pr-6 rounded bg-app-subtle text-app-heading placeholder-app-muted border border-app-border text-[11px] font-mono focus:outline-none focus:border-blue-500"
              />
              {searchFilter && (
                <button
                  type="button"
                  onClick={() => setSearchFilter("")}
                  className="absolute right-1.5 text-app-muted hover:text-app-heading p-0.5 cursor-pointer"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            {/* Status Toggle Pill Track */}
            <div className="p-0.5 inline-flex items-center bg-app-subtle rounded border border-app-border gap-0.5 text-[9px] font-mono w-full">
              <button
                type="button"
                onClick={() => setStatusFilter("all")}
                className={`flex-1 py-0.5 rounded transition-all cursor-pointer text-center font-medium ${
                  statusFilter === "all"
                    ? "bg-app-bg text-app-heading font-semibold shadow-2xs"
                    : "text-app-muted hover:text-app-heading"
                }`}
              >
                All
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter("completed")}
                className={`flex-1 py-0.5 rounded transition-all cursor-pointer text-center font-medium ${
                  statusFilter === "completed"
                    ? "bg-app-bg text-emerald-600 dark:text-emerald-400 font-semibold shadow-2xs"
                    : "text-app-muted hover:text-app-heading"
                }`}
              >
                Done
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter("running")}
                className={`flex-1 py-0.5 rounded transition-all cursor-pointer text-center font-medium ${
                  statusFilter === "running"
                    ? "bg-app-bg text-blue-600 dark:text-blue-400 font-semibold shadow-2xs"
                    : "text-app-muted hover:text-app-heading"
                }`}
              >
                Live
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter("failed")}
                className={`flex-1 py-0.5 rounded transition-all cursor-pointer text-center font-medium ${
                  statusFilter === "failed"
                    ? "bg-app-bg text-rose-600 dark:text-rose-400 font-semibold shadow-2xs"
                    : "text-app-muted hover:text-app-heading"
                }`}
              >
                Fail
              </button>
            </div>
          </div>

          {/* Runs List: Flush 32px Tabular List */}
          <div className="flex-1 overflow-y-auto divide-y divide-app-border/80">
            {isLoadingRuns && runs.length === 0 ? (
              <div className="p-4 text-center text-xs text-app-muted">Loading runs...</div>
            ) : filteredRuns.length === 0 ? (
              <div className="p-4 text-center text-xs text-app-muted font-mono">
                No matching runs.
              </div>
            ) : (
              filteredRuns.map((run: RunSummary) => {
                const isSelected = selectedRunId === run.run_id;
                const durStr = formatDuration(run.duration_seconds);
                const shortHash = run.run_id.slice(0, 8);
                const docName = run.primary_input
                  ? run.primary_input.split(/[/\\]/).pop() || run.primary_input
                  : run.input_sources && run.input_sources[0]
                  ? run.input_sources[0].split(/[/\\]/).pop() || run.input_sources[0]
                  : "default";

                return (
                  <div
                    key={run.run_id}
                    onClick={() => {
                      selectRun(run.run_id);
                    }}
                    className={`h-9 px-3 cursor-pointer transition-colors text-xs flex items-center justify-between relative group ${
                      isSelected
                        ? "bg-app-subtle font-medium"
                        : "bg-transparent hover:bg-app-subtle"
                    }`}
                  >
                    {/* Active bridge indicator */}
                    {isSelected && (
                      <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-blue-600 dark:bg-blue-500" />
                    )}

                    {/* Left: Status dot + Doc Name */}
                    <div className="flex items-center gap-2 min-w-0 flex-1 pr-2">
                      {getStatusDot(
                        run.status,
                        (run.reused_phase_count ?? 0) > 0
                      )}
                      <span
                        className={`truncate text-[11px] font-sans min-w-0 ${
                          isSelected
                            ? "font-semibold text-app-heading"
                            : "text-app-muted"
                        }`}
                        title={docName}
                      >
                        {docName}
                      </span>
                      <span className="text-[10px] font-mono text-app-muted shrink-0 select-all">
                        #{shortHash}
                      </span>
                    </div>

                    {/* Right: Tabular Artifacts + Duration */}
                    <div className="flex items-center gap-2 shrink-0 font-mono text-[10px] tabular-nums text-app-muted">
                      <span>{run.artifact_count.toLocaleString()} art</span>
                      <span className="w-10 text-right">
                        {durStr || (run.status === "running" ? "live" : "—")}
                      </span>

                      {/* Copy hash on hover */}
                      <button
                        type="button"
                        onClick={(e) => handleCopyHash(e, run.run_id)}
                        className="opacity-0 group-hover:opacity-100 p-0.5 hover:text-app-heading text-app-muted transition-opacity cursor-pointer"
                        title="Copy Run ID"
                      >
                        {copiedId === run.run_id ? (
                          <Check className="w-3 h-3 text-emerald-500" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Bottom Footer: Legal, Credits & Licensing                          */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="px-3 py-1.5 border-t border-app-border bg-app-surface flex items-center justify-between text-[10px] font-mono text-app-muted select-none shrink-0">
        <button
          type="button"
          onClick={() => setIsAboutOpen(true)}
          className="flex items-center gap-1.5 text-app-muted hover:text-app-heading transition-colors cursor-pointer"
          title="About Episteme, framework citations & licensing"
        >
          <Scale className="w-3 h-3" />
          <span>Episteme {APP_CONFIG.version}</span>
        </button>
        <button
          type="button"
          onClick={() => setIsAboutOpen(true)}
          className="hover:text-app-heading transition-colors cursor-pointer opacity-70 hover:opacity-100"
        >
          Credits
        </button>
      </div>

      {/* About & Legal Modal */}
      <AboutModal isOpen={isAboutOpen} onClose={() => setIsAboutOpen(false)} />
    </div>
  );
};
