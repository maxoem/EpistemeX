import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { Command } from "cmdk";
import {
  Search,
  Circle,
  ArrowRight,
  Play,
  Download,
  Settings,
  Database,
  Layers,
  Network,
  BringToFront,
  Sliders,
  Sparkles,
  Terminal,
  Activity,
  History,
  FileCode,
  FileSpreadsheet,
  Image,
  Cpu,
} from "lucide-react";
import { StudioNode, RunSummary } from "../api/types";
import { useRunsStore } from "../store/runsStore";
import { useProjectSettingsStore } from "../store/projectSettingsStore";

interface GlobalCommandOmnibarProps {
  nodes?: StudioNode[];
  onSelectNode: (node: StudioNode) => void;
  activeTab: "runs" | "graph" | "cypher" | "config" | "engine" | "evaluation";
  setActiveTab: (tab: "runs" | "graph" | "cypher" | "config" | "engine" | "evaluation") => void;
  onOpenSettings: () => void;
  onOpenCreds: () => void;
  className?: string;
}

const formatDuration = (seconds?: number | null): string => {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const rm = Math.round(m % 60);
  return `${h}h ${rm}m`;
};

const getStatusPip = (status: string) => {
  switch (status) {
    case "completed":
      return <span className="w-2 h-2 rounded-full bg-[#059669] shrink-0" />;
    case "running":
      return (
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#2563EB] opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-[#2563EB]" />
        </span>
      );
    case "failed":
      return <span className="w-2 h-2 rounded-full bg-[#E11D48] shrink-0" />;
    case "aborted":
      return <span className="w-2 h-2 rounded-full bg-[#D97706] shrink-0" />;
    default:
      return <span className="w-2 h-2 rounded-full bg-[#64748B] dark:bg-[#A1A1AA] shrink-0" />;
  }
};

export const GlobalCommandOmnibar: React.FC<GlobalCommandOmnibarProps> = ({
  nodes = [],
  onSelectNode,
  activeTab,
  setActiveTab,
  onOpenSettings,
  onOpenCreds,
  className,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [paletteMode, setPaletteMode] = useState<"all" | "runs">("all");
  const [search, setSearch] = useState("");
  const {
    runs,
    selectRun,
    selectedRunId,
    selectedRunDetail,
    capabilities,
    activeDataSource,
    setActiveDataSource,
  } = useRunsStore();
  const { openProjectSettings } = useProjectSettingsStore();

  // Keyboard shortcut listener for Cmd+K, Cmd+P, or '/'
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.key === "p" || e.key === "P") && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
        e.preventDefault();
        setPaletteMode("runs");
        setIsOpen(true);
      } else if (
        (e.key === "k" && (e.metaKey || e.ctrlKey)) ||
        (e.key === "/" &&
          !isOpen &&
          !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement))
      ) {
        e.preventDefault();
        setPaletteMode("all");
        setIsOpen((prev) => !prev);
      } else if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };

    const handleOpenRunSwitcher = () => {
      setPaletteMode("runs");
      setIsOpen(true);
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("glp-open-run-switcher", handleOpenRunSwitcher);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("glp-open-run-switcher", handleOpenRunSwitcher);
    };
  }, [isOpen]);

  // Group nodes by layer for structured search results
  const l3Nodes = nodes.filter((n) => n.layer === 3);
  const l2Nodes = nodes.filter((n) => n.layer === 2 || !n.layer);
  const l1Nodes = nodes.filter((n) => n.layer === 1);

  // Filter runs (recent runs vs switcher runs)
  const recentRuns = runs.slice(0, 5);
  const switcherRuns = runs.slice(0, 20);

  const isUsingNeo4j = activeDataSource === "neo4j" && Boolean(capabilities?.neo4j);

  return (
    <>
      {/* Collapsed Omnipresent Command Trigger: Borderless with primary black Search icon + ⌘K */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className={
          className ||
          "h-7 px-2 inline-flex items-center gap-1.5 text-app-muted hover:text-app-heading rounded-sm border-0 bg-transparent hover:bg-app-subtle/50 transition-colors cursor-pointer shrink-0 outline-none select-none"
        }
        title="Command Palette (⌘K)"
        aria-label="Command Palette"
      >
        <Search className="w-3.5 h-3.5 text-[#09090b] dark:text-[#f8fafc] transition-colors shrink-0" />
        <span className="font-mono text-[10px] text-app-muted/80 tracking-tight leading-none select-none">
          ⌘K
        </span>
      </button>

      {/* Floating Command Palette Modal rendered via Portal */}
      {isOpen &&
        createPortal(
          <div
            className="fixed inset-0 bg-black/60 z-50 flex items-start justify-center pt-20 px-4 select-none"
            style={{ backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)" }}
            onClick={() => setIsOpen(false)}
          >
            <div
              className="w-full max-w-2xl bg-app-surface border border-app-border rounded-lg overflow-hidden flex flex-col shadow-none animate-in fade-in zoom-in-95 duration-100"
              onClick={(e) => e.stopPropagation()}
            >
              <Command className="w-full flex flex-col" loop>
                {/* Search Input Bar */}
                <div className="flex items-center px-4 border-b border-app-border bg-app-surface gap-2">
                  <Search className="w-4 h-4 text-[#09090b] dark:text-[#f8fafc] shrink-0" />
                  <Command.Input
                    value={search}
                    onValueChange={setSearch}
                    placeholder={
                      paletteMode === "runs"
                        ? "Switch active run by document or hash (↑ ↓ to navigate, ↵ to switch)..."
                        : "Type a command, Cypher query, node label, or run ID..."
                    }
                    className="flex-1 min-w-0 w-full py-3 bg-transparent text-app-heading text-xs placeholder:text-app-muted focus:outline-none font-sans"
                    autoFocus
                  />
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={() => setPaletteMode("all")}
                      className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors cursor-pointer ${
                        paletteMode === "all"
                          ? "bg-blue-600 text-white font-semibold"
                          : "text-app-muted hover:text-app-heading bg-app-subtle/50 border border-app-border"
                      }`}
                    >
                      Commands (⌘K)
                    </button>
                    <button
                      type="button"
                      onClick={() => setPaletteMode("runs")}
                      className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors cursor-pointer ${
                        paletteMode === "runs"
                          ? "bg-blue-600 text-white font-semibold"
                          : "text-app-muted hover:text-app-heading bg-app-subtle/50 border border-app-border"
                      }`}
                    >
                      Runs (⌘P)
                    </button>
                  </div>
                  <kbd
                    onClick={() => setIsOpen(false)}
                    className="text-[10px] text-app-muted font-mono bg-app-subtle px-1.5 py-0.5 rounded border border-app-border cursor-pointer hover:text-app-heading ml-1 shrink-0"
                  >
                    ESC
                  </kbd>
                </div>

              {/* Categorical Results & Actions List */}
              <Command.List className="max-h-96 overflow-y-auto p-2 scrollbar-thin">
                <Command.Empty className="p-6 text-center text-xs text-app-muted">
                  No matching results or actions found.
                </Command.Empty>

                {/* Dedicated Run Switcher Grid View (Linear-style high density) */}
                {paletteMode === "runs" && (
                  <Command.Group
                    heading={`Switch Active Pipeline Run (${switcherRuns.length} available)`}
                    className="text-[10px] font-semibold text-app-muted uppercase tracking-wider px-2 py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-app-muted [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:mb-1.5"
                  >
                    {/* Linear-style Grid Column Headers */}
                    <div className="px-3 py-1 text-[10px] font-mono uppercase text-[#64748B] dark:text-[#A1A1AA] flex items-center justify-between border-b border-[#E2E8F0] dark:border-app-border mb-1">
                      <div className="flex items-center gap-2 flex-1">
                        <span>Target Document / Run</span>
                      </div>
                      <div className="flex items-center gap-4 text-right">
                        <span className="w-16">Yield</span>
                        <span className="w-16">Duration</span>
                        <span className="w-16">Cache</span>
                        <span className="w-20 text-center">Status</span>
                      </div>
                    </div>

                    {switcherRuns.map((r: RunSummary) => {
                      const docName = r.primary_input
                        ? r.primary_input.split(/[/\\]/).pop() || r.primary_input
                        : (r.input_sources && r.input_sources[0]
                        ? r.input_sources[0].split(/[/\\]/).pop() || r.input_sources[0]
                        : "default");
                      const durStr = formatDuration(r.duration_seconds);
                      const isSelected = selectedRunId === r.run_id;

                      return (
                        <Command.Item
                          key={r.run_id}
                          value={`${r.run_id} ${r.primary_input || ""} ${docName} ${r.status}`}
                          onSelect={() => {
                            selectRun(r.run_id);
                            if (activeTab !== "runs" && activeTab !== "graph") {
                              setActiveTab("runs");
                            }
                            setIsOpen(false);
                          }}
                          className="flex items-center justify-between px-3 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                        >
                          <div className="flex items-center gap-2.5 min-w-0 flex-1">
                            {getStatusPip(r.status)}
                            <span className="font-medium text-[12px] truncate max-w-[240px] text-app-heading group-data-[selected=true]:text-white">
                              {docName}
                            </span>
                            <span className="font-mono text-[11px] text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                              #{r.run_id.slice(0, 8)}
                            </span>
                            {isSelected && (
                              <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 group-data-[selected=true]:bg-white/20 group-data-[selected=true]:text-white shrink-0">
                                active
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-4 font-mono text-[11px] tabular-nums shrink-0 text-right">
                            <span className="w-16 text-app-muted group-data-[selected=true]:text-white/80">
                              {r.artifact_count.toLocaleString()} art
                            </span>
                            <span className="w-16 text-app-muted group-data-[selected=true]:text-white/80">
                              {durStr}
                            </span>
                            <span className="w-16 text-app-muted group-data-[selected=true]:text-white/80">
                              {r.reused_phase_count !== undefined && r.reused_phase_count > 0 ? (
                                <span className="text-cyan-600 dark:text-cyan-400 group-data-[selected=true]:text-white">cached</span>
                              ) : (
                                "—"
                              )}
                            </span>
                            <div className="w-20 flex justify-center">
                              <span
                                className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold border ${
                                  r.status === "completed"
                                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                                    : r.status === "running"
                                    ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30"
                                    : r.status === "failed"
                                    ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/30"
                                    : "bg-app-subtle text-app-muted border-app-border"
                                } group-data-[selected=true]:border-white/30 group-data-[selected=true]:text-white group-data-[selected=true]:bg-white/20`}
                              >
                                {r.status}
                              </span>
                            </div>
                          </div>
                        </Command.Item>
                      );
                    })}
                  </Command.Group>
                )}

                {/* In "all" mode, render standard command groups */}
                {paletteMode === "all" && (
                  <>

                {/* Categorical Header: System Actions */}
                <Command.Group
                  heading="Actions & Workflows"
                  className="text-[10px] font-semibold text-app-muted uppercase tracking-wider px-2 py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-app-muted [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:mb-1.5"
                >
                  <Command.Item
                    value="Launch Staged Pipeline Run New Run Execution"
                    onSelect={() => {
                      setIsOpen(false);
                      if (activeTab !== "config") {
                        setActiveTab("config");
                      }
                      window.dispatchEvent(new CustomEvent("glp-launch-run"));
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Play className="w-3.5 h-3.5 text-blue-500 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Run Pipeline / Launch Execution</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Action
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Export Graph Snapshot GraphML Gephi Scientific Topology"
                    onSelect={() => {
                      setIsOpen(false);
                      window.dispatchEvent(
                        new CustomEvent("glp-export-graph", { detail: { format: "graphml" } })
                      );
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <FileCode className="w-3.5 h-3.5 text-purple-400 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Export Graph ML (.graphml)</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Gephi/yEd
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Export Graph Snapshot GEXF NetworkX Network Model"
                    onSelect={() => {
                      setIsOpen(false);
                      window.dispatchEvent(
                        new CustomEvent("glp-export-graph", { detail: { format: "gexf" } })
                      );
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Export Graph GEXF (.gexf)</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      NetworkX
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Export Graph Snapshot Raw JSON Topology Nodes Edges"
                    onSelect={() => {
                      setIsOpen(false);
                      window.dispatchEvent(
                        new CustomEvent("glp-export-graph", { detail: { format: "json" } })
                      );
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Download className="w-3.5 h-3.5 text-app-muted group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Export Raw Node/Edge JSON</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Native
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Export Graph Snapshot High Resolution PNG Raster Render"
                    onSelect={() => {
                      setIsOpen(false);
                      window.dispatchEvent(
                        new CustomEvent("glp-export-graph", { detail: { format: "png" } })
                      );
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Image className="w-3.5 h-3.5 text-amber-400 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Export High-Res PNG Render</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Raster
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Export Graph Snapshot Vector SVG Publication Render"
                    onSelect={() => {
                      setIsOpen(false);
                      window.dispatchEvent(
                        new CustomEvent("glp-export-graph", { detail: { format: "svg" } })
                      );
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Image className="w-3.5 h-3.5 text-pink-400 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Export Vector SVG Render</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Vector
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Switch Active Data Source Neo4j Live Artifact Store"
                    disabled={selectedRunDetail?.status === "running"}
                    onSelect={() => {
                      setIsOpen(false);
                      if (selectedRunDetail?.status === "running") {
                        return;
                      }
                      if (capabilities?.neo4j) {
                        setActiveDataSource(isUsingNeo4j ? "artifacts" : "neo4j");
                      }
                    }}
                    className={`flex items-center justify-between px-2.5 py-2 rounded-md text-xs text-app-text transition-colors group ${
                      selectedRunDetail?.status === "running"
                        ? "opacity-50 cursor-not-allowed"
                        : "cursor-pointer hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Database className="w-3.5 h-3.5 text-emerald-500 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">
                        {selectedRunDetail?.status === "running"
                          ? "Data Source: Locked to Neo4j (Run in progress)"
                          : `Switch Data Source: ${isUsingNeo4j ? "Artifact Store" : "Neo4j Live"}`}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Storage
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Configure Project Infrastructure & Langfuse Telemetry"
                    onSelect={() => {
                      setIsOpen(false);
                      openProjectSettings();
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Activity className="w-3.5 h-3.5 text-emerald-400 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Project Infrastructure & Telemetry Settings</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Settings
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Studio Preferences Theme Appearance Physics Graph Settings"
                    onSelect={() => {
                      setIsOpen(false);
                      onOpenSettings();
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Settings className="w-3.5 h-3.5 text-app-muted group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Studio Preferences & Visual Physics</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      ⌘,
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Configure Neo4j Database Connection Credentials Bolt"
                    onSelect={() => {
                      setIsOpen(false);
                      onOpenCreds();
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Database className="w-3.5 h-3.5 text-emerald-500 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Configure Neo4j Connection & Credentials</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Auth
                    </span>
                  </Command.Item>
                </Command.Group>

                {/* Categorical Header: Navigation Modules */}
                <Command.Group
                  heading="Workspace Navigation"
                  className="text-[10px] font-semibold text-app-muted uppercase tracking-wider px-2 py-1.5 mt-2 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-app-muted [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:mb-1.5"
                >
                  <Command.Item
                    value="Go to Explorer Graph Network Visualization"
                    onSelect={() => {
                      setActiveTab("graph");
                      setIsOpen(false);
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Network className="w-3.5 h-3.5 text-blue-500 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Explorer</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Navigate
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Go to Corpus & Runs Pipeline History"
                    onSelect={() => {
                      setActiveTab("runs");
                      setIsOpen(false);
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Layers className="w-3.5 h-3.5 text-purple-400 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Corpus & Runs</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Navigate
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Go to System Console Cypher Query Editor"
                    onSelect={() => {
                      setActiveTab("cypher");
                      setIsOpen(false);
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Database className="w-3.5 h-3.5 text-emerald-500 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Cypher Console</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Navigate
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Go to PerceptLab Pipeline Phase Configuration Workbench"
                    onSelect={() => {
                      setActiveTab("config");
                      setIsOpen(false);
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <BringToFront className="w-3.5 h-3.5 text-red-400 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">PerceptLab</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Navigate
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Go to Pipeline Engine Settings Epistemic Schema Polarities Models"
                    onSelect={() => {
                      setActiveTab("engine");
                      setIsOpen(false);
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Cpu className="w-3.5 h-3.5 text-blue-400 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Engine Settings</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Navigate
                    </span>
                  </Command.Item>

                  <Command.Item
                    value="Go to Knowledge Graph Evaluation Workbench Benchmarks Calibration Leaderboard Triage"
                    onSelect={() => {
                      setActiveTab("evaluation");
                      setIsOpen(false);
                    }}
                    className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Activity className="w-3.5 h-3.5 text-emerald-400 group-data-[selected=true]:text-white shrink-0" />
                      <span className="font-medium truncate">Evaluation Workbench</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                      Navigate
                    </span>
                  </Command.Item>
                </Command.Group>

                {/* Categorical Header: Pipeline Runs */}
                {recentRuns.length > 0 && (
                  <Command.Group
                    heading="Pipeline Runs"
                    className="text-[10px] font-semibold text-app-muted uppercase tracking-wider px-2 py-1.5 mt-2 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-app-muted [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:mb-1.5"
                  >
                    {recentRuns.map((r: RunSummary) => {
                      const docName = r.primary_input
                        ? r.primary_input.split(/[/\\]/).pop() || r.primary_input
                        : (r.input_sources && r.input_sources[0]
                        ? r.input_sources[0].split(/[/\\]/).pop() || r.input_sources[0]
                        : "default");
                      const durStr = formatDuration(r.duration_seconds);

                      return (
                        <Command.Item
                          key={r.run_id}
                          value={`${r.run_id} ${r.primary_input || ""} ${docName} ${r.status} run`}
                          onSelect={() => {
                            selectRun(r.run_id);
                            if (activeTab !== "runs" && activeTab !== "graph") {
                              setActiveTab("runs");
                            }
                            setIsOpen(false);
                          }}
                          className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                        >
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            {getStatusPip(r.status)}
                            <span className="font-mono text-[11px] text-app-muted group-data-[selected=true]:text-white/80 shrink-0">
                              #{r.run_id.slice(0, 8)}
                            </span>
                            <span className="font-medium truncate max-w-[200px] text-app-heading group-data-[selected=true]:text-white">
                              {docName}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 font-mono text-[10px] tabular-nums shrink-0">
                            <span className="text-app-muted group-data-[selected=true]:text-white/80">
                              {r.artifact_count.toLocaleString()} art
                            </span>
                            <span className="text-app-muted group-data-[selected=true]:text-white/80">
                              {durStr}
                            </span>
                            <span
                              className={`px-1.5 py-0.2 rounded border ${
                                r.status === "completed"
                                  ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/30"
                                  : r.status === "running"
                                  ? "bg-blue-500/10 text-blue-400 border-blue-500/30"
                                  : "bg-app-subtle text-app-muted border-app-border"
                              } group-data-[selected=true]:border-white/30 group-data-[selected=true]:text-white`}
                            >
                              {r.status}
                            </span>
                            <ArrowRight className="w-3 h-3 text-app-muted group-data-[selected=true]:text-white" />
                          </div>
                        </Command.Item>
                      );
                    })}
                  </Command.Group>
                )}

                {/* Categorical Header: Graph Nodes (Layer 3) */}
                {l3Nodes.length > 0 && (
                  <Command.Group
                    heading="TheoryNet & Arguments (L3)"
                    className="text-[10px] font-semibold text-app-muted uppercase tracking-wider px-2 py-1.5 mt-2 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-app-muted [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:mb-1.5"
                  >
                    {l3Nodes.slice(0, 20).map((node) => (
                      <Command.Item
                        key={node.id}
                        value={`${node.label || ""} ${node.id} ${node.type} L3 TheoryNet`}
                        onSelect={() => {
                          onSelectNode(node);
                          setIsOpen(false);
                        }}
                        className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Circle className="w-2.5 h-2.5 fill-emerald-400 text-emerald-400 shrink-0" />
                          <span className="font-medium truncate">
                            {node.label || node.id}
                          </span>
                          <span className="text-[10px] font-mono text-app-muted bg-app-bg px-1 py-0.2 rounded border border-app-border shrink-0 group-data-[selected=true]:text-white/80 group-data-[selected=true]:border-white/30 group-data-[selected=true]:bg-white/10">
                            {node.type}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 text-[11px] text-app-muted font-mono shrink-0 group-data-[selected=true]:text-white/80">
                          <span className="truncate max-w-[120px]">{node.id}</span>
                          <ArrowRight className="w-3 h-3 text-app-muted group-data-[selected=true]:text-white" />
                        </div>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}

                {/* Categorical Header: Graph Nodes (Layer 2) */}
                {l2Nodes.length > 0 && (
                  <Command.Group
                    heading="Entities & Concepts (L2)"
                    className="text-[10px] font-semibold text-app-muted uppercase tracking-wider px-2 py-1.5 mt-2 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-app-muted [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:mb-1.5"
                  >
                    {l2Nodes.slice(0, 20).map((node) => (
                      <Command.Item
                        key={node.id}
                        value={`${node.label || ""} ${node.id} ${node.type} L2 Entity`}
                        onSelect={() => {
                          onSelectNode(node);
                          setIsOpen(false);
                        }}
                        className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Circle className="w-2.5 h-2.5 fill-purple-400 text-purple-400 shrink-0" />
                          <span className="font-medium truncate">
                            {node.label || node.id}
                          </span>
                          <span className="text-[10px] font-mono text-app-muted bg-app-bg px-1 py-0.2 rounded border border-app-border shrink-0 group-data-[selected=true]:text-white/80 group-data-[selected=true]:border-white/30 group-data-[selected=true]:bg-white/10">
                            {node.type}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 text-[11px] text-app-muted font-mono shrink-0 group-data-[selected=true]:text-white/80">
                          <span className="truncate max-w-[120px]">{node.id}</span>
                          <ArrowRight className="w-3 h-3 text-app-muted group-data-[selected=true]:text-white" />
                        </div>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}

                {/* Categorical Header: Graph Nodes (Layer 1) */}
                {l1Nodes.length > 0 && (
                  <Command.Group
                    heading="Evidence Chunks (L1)"
                    className="text-[10px] font-semibold text-app-muted uppercase tracking-wider px-2 py-1.5 mt-2 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-app-muted [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:mb-1.5"
                  >
                    {l1Nodes.slice(0, 20).map((node) => (
                      <Command.Item
                        key={node.id}
                        value={`${node.label || ""} ${node.id} ${node.type} L1 Chunk`}
                        onSelect={() => {
                          onSelectNode(node);
                          setIsOpen(false);
                        }}
                        className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-blue-600 data-[selected=true]:text-white transition-colors group"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Circle className="w-2.5 h-2.5 fill-blue-400 text-blue-400 shrink-0" />
                          <span className="font-medium truncate">
                            {node.label || node.id}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 text-[11px] text-app-muted font-mono shrink-0 group-data-[selected=true]:text-white/80">
                          <span className="truncate max-w-[120px]">{node.id}</span>
                          <ArrowRight className="w-3 h-3 text-app-muted group-data-[selected=true]:text-white" />
                        </div>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}
                  </>
                )}
              </Command.List>

              {/* Palette Footer */}
              <div className="flex items-center justify-between px-3.5 py-2.5 border-t border-app-border bg-app-bg text-[10px] text-app-muted font-mono">
                <span className="flex items-center gap-2">
                  <span>Navigate: ↑ ↓</span>
                  <span>·</span>
                  <span>Select: ↵</span>
                  <span>·</span>
                  <span>Close: Esc</span>
                </span>
                <span className="flex items-center gap-2">
                  <span>{runs.length} runs</span>
                  <span>·</span>
                  <span>{nodes.length} nodes</span>
                </span>
              </div>
            </Command>
          </div>
        </div>,
        document.body
      )}
    </>
  );
};
