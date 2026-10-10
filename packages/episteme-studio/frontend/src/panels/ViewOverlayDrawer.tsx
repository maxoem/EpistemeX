import React, {useMemo, useState} from "react";
import {CURATED_LENSES, extractTheoriesFromGraph, SubgraphMask, useViewOverlayStore,} from "../store/viewOverlayStore";
import {GraphView, OverlayKind} from "../api/types";
import {api} from "../api/client";
import {useRunsStore} from "../store/runsStore";
import {
    Activity,
    AlertTriangle,
    ArrowLeft,
    Bookmark,
    Boxes,
    Brain,
    Check,
    CheckCircle2,
    ChevronRight,
    Eye,
    Layers,
    Loader2,
    Network,
    Play,
    RotateCcw,
    Scale,
    Share2,
    Sliders,
    Trash2,
    TrendingUp,
} from "lucide-react";

export interface ViewOverlayDrawerProps {
  graphData?: GraphView | null;
  runId?: string | null;
  graphVersion?: string;
  dataSource?: "artifacts" | "neo4j";
  nodeTypesInGraph?: string[];
  edgeTypesInGraph?: string[];
  onNavigateToCypher?: () => void;
  onClose?: () => void;
}

interface OverlayOption {
  kind: OverlayKind;
  label: string;
  badge?: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  reserved?: boolean;
}

const OVERLAY_OPTIONS: OverlayOption[] = [
  {
    kind: "tenability",
    label: "Tenability (TS)",
    badge: "Stegmüller",
    description: "Evaluates empirical model adherence & admissible blur delta tolerance (TS >= 0.5)",
    icon: Brain,
  },
  {
    kind: "gradual_strength",
    label: "Gradual Strength (ρ)",
    badge: "QBAF",
    description: "Iterative acceptability aggregation across support & attack paths",
    icon: Scale,
  },
  {
    kind: "leiden",
    label: "Leiden Communities (Hulls)",
    badge: "GDS/igraph",
    description: "Partitions the graph into modular clusters with convex bounding hulls",
    icon: Network,
  },
  {
    kind: "internal_correlation",
    label: "Internal Correlation",
    badge: "Epistemetrics",
    description: "Epistemic community cohesion score across argument clusters",
    icon: Activity,
  },
  {
    kind: "pagerank",
    label: "PageRank Centrality",
    badge: "GDS",
    description: "Recursive incoming epistemic endorsement and structural centrality",
    icon: TrendingUp,
  },
  {
    kind: "degree",
    label: "Degree Centrality",
    badge: "Topology",
    description: "Direct connectivity count across all argument and domain edges",
    icon: Share2,
  },
  {
    kind: "component",
    label: "Connected Components",
    badge: "Graph",
    description: "Weakly connected subgraphs and modular components",
    icon: Boxes,
  },
  {
    kind: "b_consistency",
    label: "B-Consistency",
    badge: "Reserved",
    description: "Maximal empirical consistency (501 Not Implemented)",
    icon: Sliders,
    reserved: true,
  },
  {
    kind: "stable_extension",
    label: "Stable Extensions",
    badge: "Reserved",
    description: "Dung acceptability semantics (501 Not Implemented)",
    icon: Sliders,
    reserved: true,
  },
];

export const ViewOverlayDrawer: React.FC<ViewOverlayDrawerProps> = ({
  graphData,
  runId,
  graphVersion,
  dataSource = "artifacts",
  nodeTypesInGraph = [],
  edgeTypesInGraph = [],
  onNavigateToCypher,
  onClose,
}) => {
  const { capabilities } = useRunsStore();
  const {
    activeMask,
    customPresets,
    activeOverlay,
    activeTab,
    setActiveLens,
    setCustomMask,
    resetMask,
    saveCustomPreset,
    deleteCustomPreset,
    setActiveOverlay,
    clearOverlay,
    setActiveTab,
    closeDrawer,
  } = useViewOverlayStore();

  const [currentView, setCurrentView] = useState<"catalog" | "config">("catalog");
  const [selectedOverlay, setSelectedOverlay] = useState<OverlayOption | null>(null);
  const [overlayParams, setOverlayParams] = useState<Record<string, any>>({});
  const [presetNameInput, setPresetNameInput] = useState("");
  const [showSavePreset, setShowSavePreset] = useState(false);
  const [isLoadingOverlay, setIsLoadingOverlay] = useState(false);
  const [overlayError, setOverlayError] = useState<string | null>(null);

  // Dynamically extract theory elements from the active graph (generic Phi_spec)
  const dynamicTheories = useMemo(() => {
    return extractTheoriesFromGraph(graphData || null);
  }, [graphData]);

  // Group curated domain-agnostic lenses
  const partitionLenses = useMemo(
    () => CURATED_LENSES.filter((l) => l.category === "partition"),
    []
  );
  const layerLenses = useMemo(
    () => CURATED_LENSES.filter((l) => l.category === "layer" || l.category === "general"),
    []
  );

  const totalLensesCount =
    dynamicTheories.length + partitionLenses.length + layerLenses.length + Object.keys(customPresets).length;

  const handleClose = () => {
    closeDrawer();
    if (onClose) onClose();
  };

  const handleResetAll = () => {
    resetMask();
    clearOverlay();
  };

  const handleSelectLens = (lensId: string, mask?: SubgraphMask) => {
    setActiveLens(lensId, mask);
  };

  const handleSelectOverlayOption = (opt: OverlayOption) => {
    setSelectedOverlay(opt);
    setOverlayError(null);

    // Set default parameters
    if (opt.kind === "tenability") {
      setOverlayParams({
        tenability_threshold: 0.5,
        theory_id: dynamicTheories.length > 0 ? dynamicTheories[0].theoryId : "",
      });
    } else if (opt.kind === "gradual_strength") {
      setOverlayParams({ iterations: 10, tolerance: 0.0001 });
    } else {
      setOverlayParams({});
    }

    setCurrentView("config");
  };

  const handleExecuteOverlay = async () => {
    if (!selectedOverlay) return;
    setOverlayError(null);

    if (selectedOverlay.reserved) {
      setOverlayError(`${selectedOverlay.label} is reserved and not implemented yet (HTTP 501).`);
      return;
    }

    if (dataSource === "neo4j" && !capabilities?.neo4j) {
      if (onNavigateToCypher) {
        onNavigateToCypher();
      } else {
        setOverlayError("Neo4j is disconnected. Please connect first.");
      }
      return;
    }

    setIsLoadingOverlay(true);
    try {
      const cleanParams: Record<string, any> = { ...overlayParams };
      // Remove empty theory_id so backend evaluates across all theories
      if (cleanParams.theory_id === "") {
        delete cleanParams.theory_id;
      }

      const computed = await api.computeOverlay({
        run_id: dataSource === "artifacts" ? runId : undefined,
        source: dataSource,
        graph_version: graphVersion || graphData?.graph_version,
        kind: selectedOverlay.kind,
        params: cleanParams,
      });
      setActiveOverlay(computed);
    } catch (err: any) {
      console.error("Failed to compute overlay:", err);
      setOverlayError(err?.detail || err?.title || "Failed to compute overlay.");
      setActiveOverlay(null);
    } finally {
      setIsLoadingOverlay(false);
    }
  };

  const handleToggleNodeType = (type: string) => {
    const current = activeMask.allowedNodeTypes;
    if (current === null) {
      const remaining = nodeTypesInGraph.filter((t) => t !== type);
      setCustomMask({ allowedNodeTypes: remaining });
    } else if (current.includes(type)) {
      const next = current.filter((t) => t !== type);
      setCustomMask({ allowedNodeTypes: next.length === nodeTypesInGraph.length ? null : next });
    } else {
      const next = [...current, type];
      setCustomMask({ allowedNodeTypes: next.length === nodeTypesInGraph.length ? null : next });
    }
  };

  const handleToggleEdgeType = (type: string) => {
    const current = activeMask.allowedEdgeTypes;
    if (current === null) {
      const remaining = edgeTypesInGraph.filter((t) => t !== type);
      setCustomMask({ allowedEdgeTypes: remaining });
    } else if (current.includes(type)) {
      const next = current.filter((t) => t !== type);
      setCustomMask({ allowedEdgeTypes: next.length === edgeTypesInGraph.length ? null : next });
    } else {
      const next = [...current, type];
      setCustomMask({ allowedEdgeTypes: next.length === edgeTypesInGraph.length ? null : next });
    }
  };

  const handleTogglePolarity = (pol: number | null) => {
    const current = activeMask.allowedPolarities;
    const allPols: (number | null)[] = [1, -1, 0, null];
    if (current === null) {
      setCustomMask({ allowedPolarities: allPols.filter((p) => p !== pol) });
    } else if (current.includes(pol)) {
      const next = current.filter((p) => p !== pol);
      setCustomMask({ allowedPolarities: next.length === 4 ? null : next });
    } else {
      const next = [...current, pol];
      setCustomMask({ allowedPolarities: next.length === 4 ? null : next });
    }
  };

  const handleSavePreset = () => {
    if (!presetNameInput.trim()) return;
    saveCustomPreset(presetNameInput.trim(), activeMask);
    setPresetNameInput("");
    setShowSavePreset(false);
  };

  const isMaskFiltered =
    (activeMask.lensId !== null && activeMask.lensId !== "all") ||
    activeMask.theoryId !== null ||
    activeMask.allowedNodeTypes !== null ||
    activeMask.allowedEdgeTypes !== null ||
    activeMask.allowedPolarities !== null ||
    activeMask.partitionFilter !== null;

  return (
    <div className="w-full h-full flex flex-col bg-app-surface text-app-text overflow-hidden select-none">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* PAGE 1: CATALOG VIEW                                              */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {currentView === "catalog" || !selectedOverlay ? (
        <>
          {/* Header: Matching RunList / Left Sidebar Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-app-border bg-app-surface shrink-0">
            <div className="flex items-center space-x-2">
              <Sliders className="w-4 h-4 text-app-muted shrink-0" />
              <h2 className="text-xs font-semibold text-app-heading uppercase tracking-wider">
                Views & Overlays
              </h2>
            </div>
            <div className="flex items-center space-x-1">
              <button
                onClick={handleResetAll}
                className="flex items-center gap-1 text-[11px] text-app-muted hover:text-app-heading px-1.5 py-0.5 rounded hover:bg-app-subtle transition-colors cursor-pointer"
                title="Reset all lenses, masks, and overlays"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Reset</span>
              </button>
              <button
                onClick={handleClose}
                className="p-1 text-app-muted hover:text-app-heading hover:bg-app-subtle rounded transition-colors cursor-pointer"
                title="Collapse Views & Overlays Pane"
                aria-label="Collapse Views & Overlays Pane"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Minimalist Tabs: Lenses / Custom Mask / Overlays */}
          <div className="flex border-b border-app-border bg-app-surface px-3 text-xs gap-6 shrink-0">
            <button
              onClick={() => setActiveTab("previews")}
              className={`py-2 text-xs transition-colors cursor-pointer relative ${
                activeTab === "previews"
                  ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
                  : "text-app-muted hover:text-app-heading"
              }`}
            >
              Lenses <span className="font-mono tabular-nums text-[11px]">({totalLensesCount})</span>
            </button>
            <button
              onClick={() => setActiveTab("custom")}
              className={`py-2 text-xs transition-colors flex items-center gap-1.5 cursor-pointer relative ${
                activeTab === "custom"
                  ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
                  : "text-app-muted hover:text-app-heading"
              }`}
            >
              <span>Custom Mask</span>
              {isMaskFiltered && (
                <span className="w-1.5 h-1.5 rounded-full bg-purple-500 shrink-0" />
              )}
            </button>
            <button
              onClick={() => setActiveTab("overlays")}
              className={`py-2 text-xs transition-colors flex items-center gap-1.5 cursor-pointer relative ${
                activeTab === "overlays"
                  ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
                  : "text-app-muted hover:text-app-heading"
              }`}
            >
              <span>Overlays</span>
              <span className="font-mono tabular-nums text-[11px]">({OVERLAY_OPTIONS.length})</span>
              {activeOverlay && (
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
              )}
            </button>
          </div>

          {/* Tab Content: Lenses List */}
          {activeTab === "previews" && (
            <div className="flex-1 overflow-y-auto divide-y divide-app-border-subtle">
              {/* Dynamic Theory Elements Section (Phi_spec Generic Induction) */}
              <div>
                <div className="px-3 py-1.5 text-[10px] uppercase font-mono font-medium text-app-muted tracking-wider flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <Brain className="w-3 h-3 text-app-muted" />
                    <span>Theory Elements (Φ_spec Lenses)</span>
                  </div>
                  <span className="text-[10px] font-mono text-purple-400">
                    {dynamicTheories.length} Active
                  </span>
                </div>

                {dynamicTheories.length === 0 ? (
                  <div className="p-3 text-app-muted text-[11px] leading-relaxed italic">
                    No dynamic theory elements detected in active graph. Theories are dynamically induced during pipeline post-processing (Theoretical Enrichment).
                  </div>
                ) : (
                  dynamicTheories.map((theory) => {
                    const isActive = activeMask.theoryId === theory.theoryId;
                    return (
                      <div
                        key={theory.theoryId}
                        onClick={() => handleSelectLens(theory.mask.lensId!, theory.mask)}
                        className={`px-3 py-2.5 cursor-pointer transition-colors text-xs flex flex-col space-y-1.5 hover:bg-app-hover group ${
                          isActive ? "bg-purple-500/10 border-l-2 border-purple-500" : ""
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1">
                          <div className="flex items-center space-x-1.5 min-w-0">
                            <Brain
                              className={`w-3.5 h-3.5 shrink-0 transition-colors ${
                                isActive ? "text-purple-400" : "text-app-muted group-hover:text-app-heading"
                              }`}
                            />
                            <span
                              className={`font-medium truncate max-w-[155px] ${
                                isActive
                                  ? "text-purple-400 font-semibold"
                                  : "text-app-heading group-hover:text-purple-400"
                              }`}
                              title={theory.name}
                            >
                              {theory.name}
                            </span>
                          </div>
                          <div className="flex items-center space-x-1 text-[10px] text-app-muted shrink-0">
                            <span className="font-mono px-1.5 py-0.5 rounded border uppercase text-[9px] text-purple-400 bg-purple-500/15 border-purple-500/30">
                              {theory.badge}
                            </span>
                            {isActive && (
                              <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse ml-0.5" />
                            )}
                            <ChevronRight className="w-3 h-3 text-app-muted group-hover:text-app-heading transition-transform group-hover:translate-x-0.5" />
                          </div>
                        </div>

                        <div className="flex items-center justify-between text-xs text-app-muted pt-0.5">
                          <span className="truncate max-w-[210px] text-[11px]" title={theory.description}>
                            {theory.description}
                          </span>
                          <span className="text-[10px] font-mono tabular-nums text-app-muted shrink-0">
                            {theory.elementCount} nodes
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* General & Layer Projections */}
              <div>
                <div className="px-3 py-1.5 bg-app-bg/60 text-[10px] uppercase font-bold text-app-muted tracking-wider flex items-center gap-1.5 border-t border-app-border">
                  <Layers className="w-3 h-3 text-app-muted" />
                  <span>General & Layer Projections ({layerLenses.length})</span>
                </div>

                {layerLenses.map((lens) => {
                  const isActive = activeMask.lensId === lens.id;
                  return (
                    <div
                      key={lens.id}
                      onClick={() => handleSelectLens(lens.id)}
                      className={`px-3 py-2.5 cursor-pointer transition-colors text-xs flex flex-col space-y-1.5 hover:bg-app-hover group ${
                        isActive ? "bg-blue-500/10 border-l-2 border-blue-500" : ""
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <div className="flex items-center space-x-1.5 min-w-0">
                          <Eye
                            className={`w-3.5 h-3.5 shrink-0 transition-colors ${
                              isActive ? "text-blue-500" : "text-app-muted group-hover:text-app-heading"
                            }`}
                          />
                          <span
                            className={`font-medium truncate max-w-[155px] ${
                              isActive
                                ? "text-blue-500 font-semibold"
                                : "text-app-heading group-hover:text-blue-500 dark:group-hover:text-blue-400"
                            }`}
                            title={lens.name}
                          >
                            {lens.name}
                          </span>
                        </div>
                        <div className="flex items-center space-x-1 text-[10px] text-app-muted shrink-0">
                          {lens.badge && (
                            <span className="font-mono px-1.5 py-0.5 rounded border uppercase text-[9px] text-app-muted bg-app-subtle border-app-border">
                              {lens.badge}
                            </span>
                          )}
                          {isActive && (
                            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse ml-0.5" />
                          )}
                          <ChevronRight className="w-3 h-3 text-app-muted group-hover:text-app-heading transition-transform group-hover:translate-x-0.5" />
                        </div>
                      </div>

                      <div className="flex items-center justify-between text-xs text-app-muted pt-0.5">
                        <span className="truncate max-w-[210px] text-[11px]" title={lens.description}>
                          {lens.description}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Ontological Partitions (M_pp / M) */}
              <div>
                <div className="px-3 py-1.5 bg-app-bg/60 text-[10px] uppercase font-bold text-app-muted tracking-wider flex items-center justify-between border-t border-app-border">
                  <div className="flex items-center gap-1.5">
                    <Scale className="w-3 h-3 text-app-muted" />
                    <span>Ontological Partitions ({partitionLenses.length})</span>
                  </div>
                  <span className="text-[9px] font-mono text-emerald-500">M_pp / M</span>
                </div>

                {partitionLenses.map((lens) => {
                  const isActive = activeMask.lensId === lens.id;
                  return (
                    <div
                      key={lens.id}
                      onClick={() => handleSelectLens(lens.id)}
                      className={`px-3 py-2.5 cursor-pointer transition-colors text-xs flex flex-col space-y-1.5 hover:bg-app-hover group ${
                        isActive ? "bg-emerald-500/10 border-l-2 border-emerald-500" : ""
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <div className="flex items-center space-x-1.5 min-w-0">
                          <Scale
                            className={`w-3.5 h-3.5 shrink-0 transition-colors ${
                              isActive ? "text-emerald-500" : "text-app-muted group-hover:text-app-heading"
                            }`}
                          />
                          <span
                            className={`font-medium truncate max-w-[155px] ${
                              isActive
                                ? "text-emerald-500 font-semibold"
                                : "text-app-heading group-hover:text-emerald-500"
                            }`}
                            title={lens.name}
                          >
                            {lens.name}
                          </span>
                        </div>
                        <div className="flex items-center space-x-1 text-[10px] text-app-muted shrink-0">
                          {lens.badge && (
                            <span className="font-mono px-1.5 py-0.5 rounded border uppercase text-[9px] text-emerald-600 dark:text-emerald-400 bg-emerald-500/15 border-emerald-500/30">
                              {lens.badge}
                            </span>
                          )}
                          {isActive && (
                            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse ml-0.5" />
                          )}
                          <ChevronRight className="w-3 h-3 text-app-muted group-hover:text-app-heading transition-transform group-hover:translate-x-0.5" />
                        </div>
                      </div>

                      <div className="flex items-center justify-between text-xs text-app-muted pt-0.5">
                        <span className="truncate max-w-[210px] text-[11px]" title={lens.description}>
                          {lens.description}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* User Saved Presets */}
              {Object.keys(customPresets).length > 0 && (
                <div>
                  <div className="px-3 py-1.5 bg-app-bg/60 text-[10px] uppercase font-bold text-app-muted tracking-wider flex items-center gap-1.5 border-t border-app-border">
                    <Bookmark className="w-3 h-3 text-app-muted" />
                    <span>Custom Saved Presets ({Object.keys(customPresets).length})</span>
                  </div>

                  {Object.entries(customPresets).map(([name, mask]) => {
                    const isActive = activeMask.lensId === name;
                    return (
                      <div
                        key={name}
                        className={`px-3 py-2.5 transition-colors text-xs flex items-center justify-between hover:bg-app-hover group ${
                          isActive ? "bg-cyan-500/10 border-l-2 border-cyan-400" : ""
                        }`}
                      >
                        <div
                          onClick={() => handleSelectLens(name)}
                          className="flex items-center space-x-1.5 min-w-0 flex-1 cursor-pointer"
                        >
                          <Bookmark className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                          <span className="font-medium text-app-heading truncate">{name}</span>
                        </div>
                        <button
                          onClick={() => deleteCustomPreset(name)}
                          className="p-1 text-app-muted hover:text-red-400 transition-colors cursor-pointer"
                          title="Delete preset"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Tab Content: Custom Mask */}
          {activeTab === "custom" && (
            <div className="flex-1 overflow-y-auto p-3 space-y-4 text-xs">
              {/* Active Filter Summary Bar */}
              <div className="flex items-center justify-between px-2.5 py-1.5 bg-app-bg rounded-lg border border-app-border text-[11px]">
                <span className="text-app-muted">
                  {isMaskFiltered ? "Custom Filter Active" : "Showing All Elements"}
                </span>
                {isMaskFiltered && (
                  <button
                    onClick={resetMask}
                    className="flex items-center gap-1 text-blue-500 hover:text-blue-400 font-medium cursor-pointer"
                  >
                    <RotateCcw className="w-3 h-3" />
                    <span>Reset Mask</span>
                  </button>
                )}
              </div>

              {/* Node Types Multi-Select */}
              <div className="space-y-1.5">
                <div className="text-[10px] font-semibold text-app-muted uppercase tracking-wider flex items-center justify-between">
                  <span>Node Types</span>
                  <span className="text-[9px] font-mono text-app-muted">
                    {activeMask.allowedNodeTypes === null
                      ? "All types"
                      : `${activeMask.allowedNodeTypes.length}/${nodeTypesInGraph.length}`}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {nodeTypesInGraph.length === 0 ? (
                    <span className="text-[11px] text-app-muted italic">No nodes loaded in graph</span>
                  ) : (
                    nodeTypesInGraph.map((type) => {
                      const isChecked =
                        activeMask.allowedNodeTypes === null ||
                        activeMask.allowedNodeTypes.includes(type);
                      return (
                        <button
                          key={type}
                          onClick={() => handleToggleNodeType(type)}
                          className={`px-2 py-0.5 rounded text-[11px] font-mono border transition-all cursor-pointer flex items-center gap-1 ${
                            isChecked
                              ? "bg-blue-500/15 text-blue-600 dark:text-blue-300 border-blue-500/30 font-medium"
                              : "bg-app-bg text-app-muted border-app-border hover:bg-app-subtle"
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              isChecked ? "bg-blue-500" : "bg-app-border"
                            }`}
                          />
                          <span>{type}</span>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>

              {/* Edge Types Multi-Select */}
              <div className="space-y-1.5">
                <div className="text-[10px] font-semibold text-app-muted uppercase tracking-wider flex items-center justify-between">
                  <span>Edge Relation Types</span>
                  <span className="text-[9px] font-mono text-app-muted">
                    {activeMask.allowedEdgeTypes === null
                      ? "All relations"
                      : `${activeMask.allowedEdgeTypes.length}/${edgeTypesInGraph.length}`}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {edgeTypesInGraph.length === 0 ? (
                    <span className="text-[11px] text-app-muted italic">No edges loaded in graph</span>
                  ) : (
                    edgeTypesInGraph.map((type) => {
                      const isChecked =
                        activeMask.allowedEdgeTypes === null ||
                        activeMask.allowedEdgeTypes.includes(type);
                      return (
                        <button
                          key={type}
                          onClick={() => handleToggleEdgeType(type)}
                          className={`px-2 py-0.5 rounded text-[11px] font-mono border transition-all cursor-pointer flex items-center gap-1 ${
                            isChecked
                              ? "bg-purple-500/15 text-purple-600 dark:text-purple-300 border-purple-500/30 font-medium"
                              : "bg-app-bg text-app-muted border-app-border hover:bg-app-subtle"
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              isChecked ? "bg-purple-500" : "bg-app-border"
                            }`}
                          />
                          <span>{type}</span>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>

              {/* Polarity Filter */}
              <div className="space-y-1.5">
                <div className="text-[10px] font-semibold text-app-muted uppercase tracking-wider">
                  Argumentative Polarity
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  {[
                    { pol: 1, label: "Support (+1)", color: "text-emerald-500 border-emerald-500/30" },
                    { pol: -1, label: "Attack (-1)", color: "text-red-500 border-red-500/30" },
                    { pol: 0, label: "Neutral (0)", color: "text-slate-400 border-slate-500/30" },
                    { pol: null, label: "Unmapped (null)", color: "text-amber-500 border-amber-500/30" },
                  ].map(({ pol, label, color }) => {
                    const isChecked =
                      activeMask.allowedPolarities === null ||
                      activeMask.allowedPolarities.includes(pol);
                    return (
                      <button
                        key={label}
                        onClick={() => handleTogglePolarity(pol)}
                        className={`px-2.5 py-1.5 rounded text-[11px] font-medium border text-left flex items-center justify-between cursor-pointer transition-colors ${
                          isChecked
                            ? `bg-app-subtle ${color} font-semibold`
                            : "bg-app-bg text-app-muted border-app-border hover:bg-app-subtle"
                        }`}
                      >
                        <span>{label}</span>
                        {isChecked && <Check className="w-3 h-3" />}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Save Custom Preset Button */}
              <div className="pt-2 border-t border-app-border">
                {!showSavePreset ? (
                  <button
                    onClick={() => setShowSavePreset(true)}
                    className="w-full py-2 px-3 rounded-lg border border-app-border bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-heading text-[11px] font-medium flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <Bookmark className="w-3 h-3" />
                    <span>Save Active Mask as Custom Preset</span>
                  </button>
                ) : (
                  <div className="space-y-2 bg-app-bg p-2.5 rounded-lg border border-app-border">
                    <input
                      type="text"
                      placeholder="Preset name (e.g. My Subgraph Filter)"
                      value={presetNameInput}
                      onChange={(e) => setPresetNameInput(e.target.value)}
                      className="w-full px-2.5 py-1.5 text-xs bg-app-surface border border-app-border rounded focus:outline-none focus:border-blue-500 text-app-heading"
                      autoFocus
                    />
                    <div className="flex items-center gap-2 justify-end">
                      <button
                        onClick={() => setShowSavePreset(false)}
                        className="px-2.5 py-1 text-[11px] text-app-muted hover:text-app-heading cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleSavePreset}
                        disabled={!presetNameInput.trim()}
                        className="px-3 py-1 text-[11px] bg-blue-600 hover:bg-blue-500 text-white rounded font-medium disabled:opacity-50 cursor-pointer"
                      >
                        Save Preset
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab Content: Overlays Catalog */}
          {activeTab === "overlays" && (
            <div className="flex-1 overflow-y-auto divide-y divide-app-border-subtle">
              <div className="px-3 py-1.5 bg-app-bg/60 text-[10px] uppercase font-bold text-app-muted tracking-wider flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <Layers className="w-3 h-3 text-app-muted" />
                  <span>Analytical Overlays ({OVERLAY_OPTIONS.length})</span>
                </div>
                {activeOverlay && (
                  <span className="text-[9px] font-mono text-app-heading font-medium">
                    Active: {activeOverlay.kind}
                  </span>
                )}
              </div>

              {OVERLAY_OPTIONS.map((opt) => {
                const IconComp = opt.icon;
                const isSelected = activeOverlay?.kind === opt.kind;
                return (
                  <div
                    key={opt.kind}
                    onClick={() => handleSelectOverlayOption(opt)}
                    className={`px-3 py-2.5 cursor-pointer transition-colors text-xs flex flex-col space-y-1.5 hover:bg-app-hover group ${
                      isSelected ? "bg-app-subtle border-l-2 border-app-heading" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <div className="flex items-center space-x-1.5 min-w-0">
                        <IconComp
                          className={`w-3.5 h-3.5 shrink-0 transition-colors ${
                            isSelected ? "text-app-heading" : "text-app-muted group-hover:text-app-heading"
                          }`}
                        />
                        <span
                          className={`font-medium truncate max-w-[155px] ${
                            isSelected
                              ? "text-app-heading font-semibold"
                              : "text-app-heading group-hover:text-blue-500 dark:group-hover:text-blue-400"
                          }`}
                          title={opt.label}
                        >
                          {opt.label}
                        </span>
                      </div>
                      <div className="flex items-center space-x-1 text-[10px] text-app-muted shrink-0">
                        {opt.badge && (
                          <span className="font-mono px-1.5 py-0.5 rounded border uppercase text-[9px] text-app-muted bg-app-subtle border-app-border">
                            {opt.badge}
                          </span>
                        )}
                        {isSelected && (
                          <span className="w-1.5 h-1.5 rounded-full bg-app-muted ml-0.5" />
                        )}
                        <ChevronRight className="w-3 h-3 text-app-muted group-hover:text-app-heading transition-transform group-hover:translate-x-0.5" />
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-xs text-app-muted pt-0.5">
                      <span className="truncate max-w-[210px] text-[11px]" title={opt.description}>
                        {opt.description}
                      </span>
                    </div>

                    {opt.reserved && (
                      <div className="text-[10px] text-amber-600 dark:text-amber-400 italic flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3 shrink-0" />
                        <span>Reserved (HTTP 501 Not Implemented)</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      ) : (
        /* ─────────────────────────────────────────────────────────────────── */
        /* PAGE 2: OVERLAY CONFIGURATION & RESULTS VIEW                       */
        /* ─────────────────────────────────────────────────────────────────── */
        <>
          {/* Header with Back button matching MetricsDrawer */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-app-border bg-app-surface shrink-0">
            <button
              onClick={() => setCurrentView("catalog")}
              className="flex items-center gap-1 text-xs text-app-muted hover:text-app-heading px-1 py-0.5 rounded transition-colors cursor-pointer"
              title="Return to overlays list"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Catalog</span>
            </button>

            <div className="flex items-center gap-1.5 min-w-0 flex-1 justify-center px-1">
              <selectedOverlay.icon className="w-3.5 h-3.5 text-app-muted shrink-0" />
              <span
                className="font-medium text-app-heading text-xs truncate max-w-[140px]"
                title={selectedOverlay.label}
              >
                {selectedOverlay.label}
              </span>
            </div>

            <button
              onClick={handleClose}
              className="p-1 text-app-muted hover:text-app-heading hover:bg-app-subtle rounded transition-colors cursor-pointer"
              title="Collapse Views & Overlays Pane"
              aria-label="Collapse Views & Overlays Pane"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Full-Height Configuration & Execution Content (Flat borderless design) */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 text-xs">
            {/* Overlay Overview */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-medium text-app-heading text-xs">
                  {selectedOverlay.label}
                </span>
                {selectedOverlay.badge && (
                  <span className="font-mono uppercase text-[9px] text-app-muted">
                    {selectedOverlay.badge}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-app-muted leading-relaxed">
                {selectedOverlay.description}
              </p>
            </div>

            {/* Tenability Theory Filter & Threshold Controls */}
            {selectedOverlay.kind === "tenability" && (
              <div className="space-y-2 pt-2 border-t border-app-border-subtle">
                <div className="text-[10px] uppercase font-mono tracking-wider font-medium text-app-muted">
                  Parameters
                </div>
                <div className="space-y-3 divide-y divide-app-border-subtle">
                  {/* Target Theory Selector */}
                  <div className="space-y-1 pb-2">
                    <label className="text-xs text-app-heading font-medium flex items-center justify-between">
                      <span>Target Theory Element</span>
                      <span className="text-[10px] text-app-muted font-mono">Φ_spec</span>
                    </label>
                    <select
                      value={overlayParams.theory_id || ""}
                      onChange={(e) =>
                        setOverlayParams((prev) => ({ ...prev, theory_id: e.target.value }))
                      }
                      className="w-full px-2 py-1 bg-transparent border-b border-app-border text-xs text-app-heading focus:outline-none focus:border-app-muted cursor-pointer"
                    >
                      <option value="" className="bg-app-surface text-app-heading">All Claimant Theories (Global Scope)</option>
                      {dynamicTheories.map((t) => (
                        <option key={t.theoryId} value={t.theoryId} className="bg-app-surface text-app-heading">
                          {t.name} ({t.badge})
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Tenability Anomaly Threshold Slider */}
                  <div className="space-y-1 pt-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-app-heading font-medium">Anomaly Threshold (TS)</span>
                      <span className="font-mono text-app-heading font-bold">
                        {overlayParams.tenability_threshold ?? 0.5}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0.1}
                      max={0.9}
                      step={0.05}
                      value={overlayParams.tenability_threshold ?? 0.5}
                      onChange={(e) =>
                        setOverlayParams((prev) => ({
                          ...prev,
                          tenability_threshold: parseFloat(e.target.value),
                        }))
                      }
                      className="w-full accent-app-heading cursor-pointer"
                    />
                    <div className="flex justify-between text-[10px] text-app-muted font-mono">
                      <span>0.1 (Permissive)</span>
                      <span>0.5 (Default)</span>
                      <span>0.9 (Strict)</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Gradual Strength Parameters */}
            {selectedOverlay.kind === "gradual_strength" && (
              <div className="space-y-2 pt-2 border-t border-app-border-subtle">
                <div className="text-[10px] uppercase font-mono tracking-wider font-medium text-app-muted">
                  Parameters
                </div>
                <div className="space-y-1 py-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-app-heading font-medium">Max Iterations</span>
                    <span className="font-mono text-app-heading font-bold">
                      {overlayParams.iterations ?? 10}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={50}
                    step={1}
                    value={overlayParams.iterations ?? 10}
                    onChange={(e) =>
                      setOverlayParams((prev) => ({
                        ...prev,
                        iterations: parseInt(e.target.value, 10),
                      }))
                    }
                    className="w-full accent-app-heading cursor-pointer"
                  />
                </div>
              </div>
            )}

            {/* Error Message */}
            {overlayError && (
              <div className="py-2 text-red-600 dark:text-red-400 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span className="leading-tight">{overlayError}</span>
              </div>
            )}

            {/* Execution Button */}
            <div className="space-y-2 pt-2 border-t border-app-border-subtle">
              <button
                onClick={handleExecuteOverlay}
                disabled={selectedOverlay.reserved || isLoadingOverlay}
                className={`w-full py-1.5 px-3 rounded text-xs font-medium transition-colors flex items-center justify-center gap-2 border ${
                  selectedOverlay.reserved || isLoadingOverlay
                    ? "bg-app-subtle text-app-muted border-app-border cursor-not-allowed"
                    : "bg-app-heading text-app-surface hover:opacity-90 border-transparent cursor-pointer"
                }`}
              >
                {isLoadingOverlay ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Computing {selectedOverlay.label}...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>Apply {selectedOverlay.label}</span>
                  </>
                )}
              </button>
            </div>

            {/* Active Overlay Status & KPI Results Card */}
            {activeOverlay && activeOverlay.kind === selectedOverlay.kind && (
              <div className="border-t border-app-border-subtle pt-3 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-app-heading font-medium text-xs">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                    <span>Overlay Active on Canvas</span>
                  </div>
                  <button
                    onClick={clearOverlay}
                    className="text-[10px] text-app-muted hover:text-app-heading underline cursor-pointer"
                    title="Remove overlay decoration from graph canvas"
                  >
                    Clear Overlay
                  </button>
                </div>

                {/* KPI Metrics: Clean horizontal baseline layout */}
                <div className="flex items-baseline gap-8 py-1 border-t border-b border-app-border-subtle">
                  <div className="flex flex-col">
                    <div className="text-[10px] text-app-muted uppercase font-mono tracking-wider">Scale</div>
                    <div className="font-mono font-medium text-sm text-app-heading mt-0.5 capitalize">
                      {activeOverlay.scale}
                    </div>
                  </div>
                  <div className="flex flex-col">
                    <div className="text-[10px] text-app-muted uppercase font-mono tracking-wider">Decorated Nodes</div>
                    <div className="font-mono font-medium text-sm text-app-heading mt-0.5 tabular-nums">
                      {Object.keys(activeOverlay.node_values || {}).length}
                    </div>
                  </div>
                </div>

                {activeOverlay.incomplete_inputs > 0 && (
                  <div className="text-amber-600 dark:text-amber-400 text-[11px] flex items-center gap-2 font-mono">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                    <span>{activeOverlay.incomplete_inputs} nodes or edges skipped due to missing values.</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
