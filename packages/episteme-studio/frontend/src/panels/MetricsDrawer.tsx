import React, {useCallback, useEffect, useMemo, useState} from "react";
import {computeStyleConflicts, extractDescriptorDefaults, useMetricsStore} from "../store/metricsStore";
import {MetricRunInstance, MetricSizeStrength, StudioNode} from "../api/types";
import {AlgorithmPicker} from "./AlgorithmPicker";
import {CompactMultiSelect} from "./CompactMultiSelect";
import {
    Activity,
    AlertTriangle,
    ArrowLeft,
    Boxes,
    Check,
    ChevronDown,
    ChevronRight,
    Copy,
    Loader2,
    Play,
    Plus,
    RotateCcw,
    Search,
    Settings,
    Square,
    Trash2,
} from "lucide-react";

interface MetricsDrawerProps {
  selectedNode: StudioNode | null;
  onSelectNode?: (nodeId: string) => void;
  dataSource?: "artifacts" | "neo4j";
  runId?: string | null;
  graphVersion?: string;
  nodeTypesInGraph?: string[];
  edgeTypesInGraph?: string[];
}

const DEFAULT_CATEGORIES = [
  "Chapter",
  "Chunk",
  "Community",
  "Document",
  "Entity",
  "TheoryAtom",
];

const DEFAULT_RELATION_TYPES = [
  "CONFLICTS",
  "CONTAINS",
  "EXTRACTED_FROM",
  "IN_COMMUNITY",
  "NEXT",
  "SUPPORTS",
  "UNDERMINES",
  "Z1_NEUTRAL",
  "Z1_SUPPORTS",
];

export const MetricsDrawer: React.FC<MetricsDrawerProps> = ({
  selectedNode,
  onSelectNode,
  dataSource = "neo4j",
  runId,
  graphVersion,
  nodeTypesInGraph = [],
  edgeTypesInGraph = [],
}) => {
  const {
    descriptors,
    instances,
    activeInstanceId,
    currentView,
    scaleMode,
    isDrawerOpen,
    fetchDescriptors,
    addInstance,
    removeInstance,
    updateInstance,
    updateInstanceStyling,
    setScaleMode,
    setCurrentView,
    openDetailView,
    closeDrawer,
    runInstance,
    cancelInstance,
  } = useMetricsStore();

  const executionElapsed = useMetricsStore((s) => s.executionElapsed);
  const [openConfigIds, setOpenConfigIds] = useState<Record<string, boolean>>({});
  const [collapsedIds, setCollapsedIds] = useState<Record<string, boolean>>({});
  const [activePickerInstanceId, setActivePickerInstanceId] = useState<string | null>(null);
  const [showNodesTable, setShowNodesTable] = useState(true);
  const [showEdgesTable, setShowEdgesTable] = useState(true);
  const [nodeFilter, setNodeFilter] = useState("");
  const [catalogSearch, setCatalogSearch] = useState("");
  const [copiedTargetId, setCopiedTargetId] = useState(false);
  const [pendingStyling, setPendingStyling] = useState<Record<string, boolean>>({});

  const isStylingPending = useCallback(
    (instanceId: string, channel?: "sizeScaling" | "colorGradient" | "sizeStrength") => {
      if (channel) {
        return Boolean(pendingStyling[`${instanceId}:${channel}`]);
      }
      return Boolean(
        pendingStyling[`${instanceId}:sizeScaling`] ||
        pendingStyling[`${instanceId}:colorGradient`] ||
        pendingStyling[`${instanceId}:sizeStrength`]
      );
    },
    [pendingStyling]
  );

  const handleToggleStyling = useCallback(
    async (instanceId: string, channel: "sizeScaling" | "colorGradient") => {
      const key = `${instanceId}:${channel}`;
      if (pendingStyling[key] || isStylingPending(instanceId)) return;

      // Lock channel immediately to disable duplicate/rapid calls
      setPendingStyling((prev) => ({ ...prev, [key]: true }));

      const inst = instances.find((i) => i.instanceId === instanceId);
      if (!inst) {
        setPendingStyling((prev) => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
        return;
      }

      const nextVal = !inst.styling[channel];
      updateInstanceStyling(instanceId, { [channel]: nextVal });

      // Processing debounce: gives canvas and React time to render while showing the loader
      await new Promise((resolve) => setTimeout(resolve, 450));

      setPendingStyling((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    },
    [instances, isStylingPending, pendingStyling, updateInstanceStyling]
  );

  const handleUpdateSizeStrength = useCallback(
    async (instanceId: string, strength: MetricSizeStrength) => {
      const key = `${instanceId}:sizeStrength`;
      if (pendingStyling[key] || isStylingPending(instanceId)) return;

      setPendingStyling((prev) => ({ ...prev, [key]: true }));
      updateInstanceStyling(instanceId, { sizeStrength: strength });

      await new Promise((resolve) => setTimeout(resolve, 400));

      setPendingStyling((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    },
    [isStylingPending, pendingStyling, updateInstanceStyling]
  );

  const toggleInstanceConfigLocal = useCallback((id: string) => {
    setOpenConfigIds((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const toggleInstanceCollapsedLocal = useCallback((id: string) => {
    setCollapsedIds((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  // Available categories and relations merged with graph data
  const availableCategories = useMemo(() => {
    const set = new Set([...DEFAULT_CATEGORIES, ...nodeTypesInGraph]);
    return Array.from(set).sort();
  }, [nodeTypesInGraph]);

  const availableRelationTypes = useMemo(() => {
    const set = new Set([...DEFAULT_RELATION_TYPES, ...edgeTypesInGraph]);
    return Array.from(set).sort();
  }, [edgeTypesInGraph]);

  // Load descriptors once
  useEffect(() => {
    fetchDescriptors();
  }, [fetchDescriptors]);

  // Calculate style conflicts across active completed instances
  const conflicts = useMemo(() => computeStyleConflicts(instances), [instances]);

  // Find detail instance if in detail view
  const detailInstance = useMemo(() => {
    return instances.find((i) => i.instanceId === activeInstanceId) || instances[0];
  }, [instances, activeInstanceId]);

  const detailDescriptor = useMemo(() => {
    if (!detailInstance) return undefined;
    return descriptors.find((d) => d.id === detailInstance.metricId);
  }, [descriptors, detailInstance]);

  const handleCopyTargetId = () => {
    if (!selectedNode?.id) return;
    navigator.clipboard.writeText(selectedNode.id);
    setCopiedTargetId(true);
    setTimeout(() => setCopiedTargetId(false), 1800);
  };

  const handleRunInstance = async (inst: MetricRunInstance) => {
    await runInstance(inst.instanceId, {
      source: dataSource,
      runId,
      graphVersion,
    });
  };

  const handleResetInstanceConfig = (inst: MetricRunInstance) => {
    const desc = descriptors.find((d) => d.id === inst.metricId);
    updateInstance(inst.instanceId, {
      params: extractDescriptorDefaults(desc),
      nodeLabels: [],
      relationshipTypes: [],
      orientation: "natural",
      relationshipWeightProperty: undefined,
    });
  };

  if (!isDrawerOpen) return null;

  return (
    <div className="w-full h-full flex flex-col bg-app-surface text-xs text-app-text overflow-hidden select-none">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* GLOBAL DRAWER HEADER                                               */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="px-4 py-2.5 border-b border-app-border bg-app-surface flex items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-app-heading shrink-0" />
          <div className="flex items-center gap-2">
            <h2 className="font-display text-sm font-semibold text-app-heading leading-tight tracking-tight">
              Graph Analysis
            </h2>
            <span className="px-1.5 py-0.5 rounded-full bg-app-subtle font-mono text-[10px] text-app-muted border border-app-border-subtle tabular-nums">
              {instances.length}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {currentView === "stack" && (
            <button
              onClick={() => addInstance()}
              className="flex items-center gap-1 text-[11px] font-medium text-app-heading px-2 py-1 rounded border border-app-border bg-app-bg hover:bg-app-hover transition-colors cursor-pointer"
              title="Add algorithm layer"
            >
              <Plus className="w-3 h-3 text-app-muted" />
              <span>Add</span>
            </button>
          )}

          <button
            onClick={() => fetchDescriptors()}
            className="p-1 text-app-muted hover:text-app-heading hover:bg-app-hover rounded transition-colors cursor-pointer"
            title="Refresh algorithms catalog"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={closeDrawer}
            className="p-1 text-app-muted hover:text-app-heading hover:bg-app-hover rounded transition-colors cursor-pointer"
            title="Collapse Analysis Pane"
            aria-label="Collapse Analysis Pane"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Navigation Sub-Tabs: Stack Workbench / Catalog / Detail */}
      <div className="flex border-b border-app-border bg-app-surface px-4 text-xs gap-6 shrink-0">
        <button
          onClick={() => setCurrentView("stack")}
          className={`py-2 text-xs transition-colors cursor-pointer relative flex items-center gap-1.5 ${
            currentView === "stack"
              ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
              : "text-app-muted hover:text-app-heading"
          }`}
        >
          <span>Algorithms</span>
          <span className="font-mono text-[10px] text-app-muted tabular-nums">({instances.length})</span>
        </button>

        <button
          onClick={() => setCurrentView("catalog")}
          className={`py-2 text-xs transition-colors cursor-pointer relative flex items-center gap-1.5 ${
            currentView === "catalog"
              ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
              : "text-app-muted hover:text-app-heading"
          }`}
        >
          <span>Catalog</span>
          <span className="font-mono text-[10px] text-app-muted tabular-nums">({descriptors.length})</span>
        </button>

        {currentView === "detail" && detailInstance && (
          <button
            onClick={() => setCurrentView("detail")}
            className="py-2 text-xs text-app-heading font-medium transition-colors cursor-pointer relative after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500 truncate max-w-[140px]"
            title={`Inspect ${detailDescriptor?.label || detailInstance.metricId}`}
          >
            Inspect ({detailDescriptor?.label || detailInstance.metricId})
          </button>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* VIEW 1: STACKABLE ALGORITHMS WORKBENCH (PRIMARY)                   */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {currentView === "stack" && (
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {/* Global Conflict Resolution Notice Bar */}
          {(conflicts.hasSizeConflict || conflicts.hasColorConflict) && (
            <div className="p-2.5 rounded bg-amber-500/10 border border-amber-500/30 text-xs space-y-2">
              <div className="flex items-center gap-1.5 text-amber-700 dark:text-amber-300 font-medium">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                <span>Style Conflict Detected</span>
              </div>

              {/* Size scaling conflict & mode selector */}
              {conflicts.hasSizeConflict && (
                <div className="space-y-1.5 pt-1 border-t border-amber-500/20">
                  <div className="flex items-center justify-between text-[11px] text-app-text">
                    <span>
                      <strong className="font-mono tabular-nums">{conflicts.activeSizeCount}</strong> algorithms applying Size Scaling
                    </span>
                  </div>

                  <div className="flex items-center justify-between gap-2 text-[11px]">
                    <span className="text-app-muted">Scale Mode:</span>
                    <div className="flex items-center bg-app-bg rounded-sm border border-app-border-subtle p-0.5">
                      <button
                        onClick={() => setScaleMode("stack")}
                        className={`px-2 py-0.5 rounded-xs text-[10px] font-medium transition-colors cursor-pointer ${
                          scaleMode === "stack"
                            ? "bg-app-hover text-app-heading font-semibold"
                            : "text-app-muted hover:text-app-heading"
                        }`}
                        title="Compound and multiply sizes across active algorithms"
                      >
                        Stack (+)
                      </button>
                      <button
                        onClick={() => setScaleMode("overwrite")}
                        className={`px-2 py-0.5 rounded-xs text-[10px] font-medium transition-colors cursor-pointer ${
                          scaleMode === "overwrite"
                            ? "bg-app-hover text-app-heading font-semibold"
                            : "text-app-muted hover:text-app-heading"
                        }`}
                        title="Top card sets size scale; lower cards are overridden"
                      >
                        Overwrite (Top)
                      </button>
                    </div>
                  </div>

                  {scaleMode === "stack" && (
                    <div className="pt-1.5 border-t border-amber-500/15 space-y-1.5">
                      <div className="flex items-center justify-between text-[10px] text-amber-800 dark:text-amber-300 font-medium">
                        <span>Layer Influence Weights</span>
                        <span className="font-mono text-[9px] text-app-muted">Subtle · Normal · Strong</span>
                      </div>
                      <div className="space-y-1 bg-app-bg/50 p-1.5 rounded border border-amber-500/20">
                        {instances
                          .filter(
                            (i) =>
                              i.status === "completed" &&
                              i.result &&
                              i.styling?.enabled !== false &&
                              i.styling?.sizeScaling
                          )
                          .map((sizeInst) => {
                            const desc = descriptors.find((d) => d.id === sizeInst.metricId);
                            const curStrength = sizeInst.styling.sizeStrength || "normal";
                            const isBusy = isStylingPending(sizeInst.instanceId);
                            return (
                              <div
                                key={sizeInst.instanceId}
                                className="flex items-center justify-between gap-2 text-[10px]"
                              >
                                <span
                                  className="truncate font-medium text-app-text max-w-[130px]"
                                  title={desc?.label || sizeInst.metricId}
                                >
                                  {desc?.label || sizeInst.metricId}
                                </span>
                                <div className="flex items-center bg-app-surface rounded-xs border border-app-border-subtle p-0.5">
                                  {(["subtle", "normal", "strong"] as const).map((str) => (
                                    <button
                                      key={str}
                                      type="button"
                                      disabled={isBusy}
                                      onClick={() => handleUpdateSizeStrength(sizeInst.instanceId, str)}
                                      className={`px-1.5 py-0.2 rounded-2xs text-[9px] font-medium capitalize transition-colors ${
                                        curStrength === str
                                          ? "bg-blue-600 text-white font-semibold"
                                          : "text-app-muted hover:text-app-heading"
                                      } ${
                                        isBusy
                                          ? "cursor-wait opacity-60 pointer-events-none"
                                          : "cursor-pointer"
                                      }`}
                                      title={`${str} influence (${
                                        str === "subtle" ? "0.5×" : str === "strong" ? "1.8×" : "1.0×"
                                      })`}
                                    >
                                      {str}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Color gradient conflict notice */}
              {conflicts.hasColorConflict && (
                <div className="text-[11px] text-app-muted pt-1 border-t border-amber-500/20 leading-relaxed">
                  Multiple color gradients active. The top algorithm sets node body fill; secondary is routed to node outer border/halo.
                </div>
              )}
            </div>
          )}

          {/* Empty Workbench State */}
          {instances.length === 0 ? (
            <div className="py-14 text-center text-app-muted space-y-3 px-4">
              <Boxes className="w-8 h-8 mx-auto text-app-muted/40" />
              <div className="font-display text-xs font-medium text-app-heading">
                No Algorithms in Layer Stack
              </div>
              <p className="text-[11px] text-app-muted leading-relaxed max-w-xs mx-auto">
                Add algorithms to run PageRank, QBAF gradual strength, community detection, or centrality, and composite their visual channels.
              </p>
              <button
                onClick={() => addInstance()}
                className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors cursor-pointer inline-flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Algorithm</span>
              </button>
            </div>
          ) : (
            /* Stack of Algorithm Cards */
            <div className="space-y-3">
              {instances.map((inst, index) => {
                const desc = descriptors.find((d) => d.id === inst.metricId);
                const isRunning = inst.status === "running";
                const isCompleted = inst.status === "completed" && Boolean(inst.result);
                const isFailed = inst.status === "failed";
                const isPickerOpen = activePickerInstanceId === inst.instanceId;
                const isConfigOpen = Boolean(openConfigIds[inst.instanceId]);
                const isCollapsed = Boolean(collapsedIds[inst.instanceId]);
                const elapsedSec = (executionElapsed[inst.instanceId] || inst.elapsedSeconds || 0).toFixed(1);
                const isCardStylingBusy = isStylingPending(inst.instanceId);
                const isSizeScalingBusy = isStylingPending(inst.instanceId, "sizeScaling");
                const isColorGradientBusy = isStylingPending(inst.instanceId, "colorGradient");
                const isSizeStrengthBusy = isStylingPending(inst.instanceId, "sizeStrength");

                return (
                  <div
                    key={inst.instanceId}
                    className="border border-app-border rounded-lg bg-app-surface overflow-hidden transition-all"
                  >
                    {/* ─── CARD HEADER ─── */}
                    <div className="px-3 py-2 flex items-center justify-between gap-2 border-b border-app-border-subtle bg-app-subtle/30">
                      <div className="flex items-center gap-2 min-w-0">
                        <button
                          onClick={() => toggleInstanceCollapsedLocal(inst.instanceId)}
                          className="p-0.5 text-app-muted hover:text-app-heading transition-colors cursor-pointer"
                          title={isCollapsed ? "Expand card" : "Collapse card"}
                        >
                          {isCollapsed ? (
                            <ChevronRight className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5" />
                          )}
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            setActivePickerInstanceId(
                              isPickerOpen ? null : inst.instanceId
                            )
                          }
                          className="font-display font-medium text-xs text-app-heading hover:text-blue-500 transition-colors flex items-center gap-1.5 truncate cursor-pointer text-left"
                          title="Click to switch algorithm"
                        >
                          <span className="truncate">{desc?.label || inst.metricId}</span>
                          <ChevronDown className="w-3 h-3 text-app-muted shrink-0" />
                        </button>

                        {desc && (
                          <span className="font-mono text-[9px] text-app-muted uppercase px-1.5 py-0.2 rounded bg-app-subtle border border-app-border-subtle shrink-0">
                            {desc.engine} · {desc.scope === "single_node" ? "node" : "global"}
                          </span>
                        )}

                        {/* Operational State Pill */}
                        {isRunning ? (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-500 text-[10px] font-mono">
                            <Loader2 className="w-2.5 h-2.5 animate-spin shrink-0" />
                            <span>running</span>
                          </span>
                        ) : isCompleted ? (
                          <span
                            className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0"
                            title="Result calculated"
                          />
                        ) : isFailed ? (
                          <span
                            className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0"
                            title="Calculation failed"
                          />
                        ) : (
                          <span
                            className="w-1.5 h-1.5 rounded-full bg-app-muted/40 shrink-0"
                            title="Idle"
                          />
                        )}
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        {/* Config Toggle Button in Card Header */}
                        <button
                          type="button"
                          onClick={() => toggleInstanceConfigLocal(inst.instanceId)}
                          className={`px-1.5 py-0.5 rounded text-[10px] font-medium border transition-colors cursor-pointer flex items-center gap-1 ${
                            isConfigOpen
                              ? "bg-blue-500/15 border-blue-500/40 text-blue-600 dark:text-blue-400 font-semibold"
                              : "border-app-border text-app-muted hover:text-app-heading hover:bg-app-hover"
                          }`}
                          title="Toggle configuration & parameters"
                        >
                          <Settings className="w-3 h-3" />
                          <span>Config</span>
                        </button>

                        {/* Scene / Inspect Button */}
                        <button
                          onClick={() => openDetailView(inst.instanceId)}
                          disabled={!isCompleted}
                          className={`px-2 py-0.5 rounded text-[10px] font-medium border transition-colors cursor-pointer ${
                            isCompleted
                              ? "bg-app-surface text-app-heading border-app-border hover:bg-app-hover"
                              : "opacity-40 cursor-not-allowed border-transparent text-app-muted"
                          }`}
                          title="Inspect detailed causal paths & affected nodes table"
                        >
                          Inspect
                        </button>

                        {/* Delete Card Button */}
                        <button
                          onClick={() => removeInstance(inst.instanceId)}
                          className="p-1 text-app-muted hover:text-rose-500 hover:bg-rose-500/10 rounded transition-colors cursor-pointer opacity-70 hover:opacity-100"
                          title="Remove algorithm from workbench"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* ─── CARD BODY ─── */}
                    {!isCollapsed && (
                      <div className="p-3 space-y-3">
                        {/* Inline Algorithm Picker Popover (if active) */}
                        {isPickerOpen && (
                          <div className="pb-1">
                            <AlgorithmPicker
                              descriptors={descriptors}
                              selectedMetricId={inst.metricId}
                              onSelect={(newMetricId) => {
                                updateInstance(inst.instanceId, { metricId: newMetricId });
                                setActivePickerInstanceId(null);
                              }}
                              onClose={() => setActivePickerInstanceId(null)}
                            />
                          </div>
                        )}

                        {/* Epistemic / Theoretical Purpose Description */}
                        <p className="text-[11px] text-app-muted leading-relaxed select-text">
                          {inst.metricId === "pagerank_global"
                            ? "Measures structural prominence and epistemic authority based on recursive endorsement across directed inference paths."
                            : desc?.description}
                        </p>

                        {/* Single Node Target Card */}
                        {desc?.scope === "single_node" && (
                          <div className="p-2 rounded bg-app-subtle/40 border border-app-border-subtle text-[11px] space-y-1">
                            <div className="flex items-center justify-between text-app-heading font-medium">
                              <span>Target Node</span>
                              {selectedNode && (
                                <span className="font-mono text-[10px] text-app-muted">
                                  L{selectedNode.layer} · {selectedNode.type}
                                </span>
                              )}
                            </div>
                            {selectedNode ? (
                              <div className="font-mono text-[10px] text-app-text truncate" title={selectedNode.id}>
                                {selectedNode.label || selectedNode.id}
                              </div>
                            ) : (
                              <div className="text-amber-600 dark:text-amber-400 flex items-center gap-1">
                                <AlertTriangle className="w-3 h-3 shrink-0" />
                                <span>Select a node in canvas as focus target</span>
                              </div>
                            )}
                          </div>
                        )}

                        {/* ─── STREAMLINED CONFIGURATION SECTION (NO BOX-IN-BOX) ─── */}
                        {isConfigOpen && (
                          <div className="pt-2.5 border-t border-app-border-subtle space-y-3 animate-in fade-in duration-150">
                            <div className="flex items-center justify-between pb-1 border-b border-app-border-subtle">
                              <span className="font-display font-medium text-xs text-app-heading">
                                Configuration
                              </span>
                              <button
                                type="button"
                                onClick={() => handleResetInstanceConfig(inst)}
                                className="text-[10px] text-blue-500 hover:text-blue-400 hover:underline cursor-pointer flex items-center gap-1"
                                title="Reset scope and parameters to default values"
                              >
                                <RotateCcw className="w-2.5 h-2.5" />
                                <span>Reset All Defaults</span>
                              </button>
                            </div>

                            <div className="space-y-1">
                              <div className="text-[10px] font-mono uppercase tracking-wider text-app-muted">
                                Scope & Graph Projection
                              </div>
                              <div className="grid grid-cols-2 gap-2 pt-0.5">
                                <CompactMultiSelect
                                  label="Categories"
                                  allOptions={availableCategories}
                                  selectedOptions={inst.nodeLabels}
                                  onChange={(next) =>
                                    updateInstance(inst.instanceId, { nodeLabels: next })
                                  }
                                />
                                <CompactMultiSelect
                                  label="Relationships"
                                  allOptions={availableRelationTypes}
                                  selectedOptions={inst.relationshipTypes}
                                  onChange={(next) =>
                                    updateInstance(inst.instanceId, { relationshipTypes: next })
                                  }
                                />
                              </div>
                            </div>

                            {/* Direction & Relationship Weighted Property in clean 2-column grid */}
                            <div className="grid grid-cols-2 gap-2">
                              <div className="space-y-1">
                                <label className="text-[11px] font-medium text-app-muted">
                                  Direction
                                </label>
                                <div className="grid grid-cols-3 gap-0.5 bg-app-bg p-0.5 rounded border border-app-border-subtle text-center">
                                  {(["natural", "reversed", "undirected"] as const).map((orient) => {
                                    const isActive = (inst.orientation || "natural") === orient;
                                    return (
                                      <button
                                        key={orient}
                                        type="button"
                                        onClick={() =>
                                          updateInstance(inst.instanceId, { orientation: orient })
                                        }
                                        className={`py-1 text-[10px] font-medium rounded-xs transition-colors capitalize cursor-pointer text-center ${
                                          isActive
                                            ? "bg-app-hover text-app-heading font-semibold"
                                            : "text-app-muted hover:text-app-heading"
                                        }`}
                                        title={`${orient} edge direction`}
                                      >
                                        {orient === "natural"
                                          ? "Natural"
                                          : orient === "reversed"
                                          ? "Reverse"
                                          : "Both"}
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>

                              <div className="space-y-1">
                                <label className="text-[11px] font-medium text-app-muted">
                                  Edge Weight
                                </label>
                                <select
                                  value={inst.relationshipWeightProperty || ""}
                                  onChange={(e) =>
                                    updateInstance(inst.instanceId, {
                                      relationshipWeightProperty: e.target.value || undefined,
                                    })
                                  }
                                  className="w-full px-2 py-1 text-xs bg-app-bg border border-app-border rounded text-app-heading focus:outline-none cursor-pointer"
                                >
                                  <option value="">Default (Unweighted)</option>
                                  <option value="weight">weight (φ)</option>
                                  <option value="polarity">polarity</option>
                                  <option value="confidence">confidence</option>
                                </select>
                              </div>
                            </div>

                            {/* Dynamic Parameter Schema Inputs (Exact Numerical Stepper Fields) */}
                            {desc?.param_schema?.properties &&
                              Object.keys(desc.param_schema.properties).length > 0 && (
                                <div className="space-y-2 pt-2 border-t border-app-border-subtle">
                                  <div className="text-[10px] font-mono uppercase tracking-wider text-app-muted">
                                    Parameters
                                  </div>
                                  <div className="space-y-1.5">
                                    {Object.entries<any>(desc.param_schema.properties).map(
                                      ([key, spec]) => {
                                        const val = inst.params[key] ?? spec.default ?? "";
                                        const isModified =
                                          spec.default !== undefined && val !== spec.default;
                                        const isSmallFloat =
                                          spec.type === "number" &&
                                          ((spec.default !== undefined && spec.default < 0.01) ||
                                            (typeof val === "number" && val < 0.01));

                                        return (
                                          <div
                                            key={key}
                                            className="flex items-center justify-between gap-2 py-0.5"
                                          >
                                            <div className="flex items-center gap-1.5 min-w-0">
                                              <span
                                                className="text-xs text-app-text truncate"
                                                title={spec.description || key}
                                              >
                                                {spec.title || key}
                                              </span>
                                              {spec.default !== undefined && (
                                                <span
                                                  className="text-[10px] text-app-muted font-mono"
                                                  title={`Default: ${spec.default}`}
                                                >
                                                  ({spec.default})
                                                </span>
                                              )}
                                            </div>

                                            <div className="flex items-center gap-1 shrink-0">
                                              {isModified && (
                                                <button
                                                  type="button"
                                                  onClick={() =>
                                                    updateInstance(inst.instanceId, {
                                                      params: {
                                                        ...inst.params,
                                                        [key]: spec.default,
                                                      },
                                                    })
                                                  }
                                                  className="p-1 text-app-muted hover:text-blue-500 rounded transition-colors cursor-pointer"
                                                  title={`Reset to default (${spec.default})`}
                                                >
                                                  <RotateCcw className="w-3 h-3" />
                                                </button>
                                              )}

                                              <input
                                                type={
                                                  spec.type === "integer" ||
                                                  spec.type === "number"
                                                    ? "number"
                                                    : "text"
                                                }
                                                step={
                                                  isSmallFloat
                                                    ? "any"
                                                    : spec.type === "integer"
                                                    ? "1"
                                                    : spec.step || "0.01"
                                                }
                                                min={spec.minimum}
                                                max={spec.maximum}
                                                value={val}
                                                onChange={(e) => {
                                                  const raw = e.target.value;
                                                  let parsed: any = raw;
                                                  if (spec.type === "integer") {
                                                    parsed = parseInt(raw, 10);
                                                    if (isNaN(parsed)) parsed = 0;
                                                  } else if (spec.type === "number") {
                                                    parsed = parseFloat(raw);
                                                    if (isNaN(parsed)) parsed = 0;
                                                  }
                                                  updateInstance(inst.instanceId, {
                                                    params: { ...inst.params, [key]: parsed },
                                                  });
                                                }}
                                                className="w-24 px-2 py-0.5 bg-app-bg border border-app-border rounded text-xs text-app-heading font-mono text-right focus:outline-none focus:border-blue-500 transition-colors [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                              />
                                            </div>
                                          </div>
                                        );
                                      }
                                    )}
                                  </div>
                                </div>
                              )}
                          </div>
                        )}

                        {/* Error Message */}
                        {inst.error && (
                          <div className="p-2 rounded bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-[11px] space-y-1">
                            <div className="font-semibold flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" />
                              <span>Execution Error</span>
                            </div>
                            <p className="font-mono">{inst.error}</p>
                          </div>
                        )}

                        {/* ─── RUN ALGORITHM ACTION BUTTON ─── */}
                        <div>
                          {isRunning ? (
                            <button
                              onClick={() => cancelInstance(inst.instanceId)}
                              className="w-full py-1.5 px-3 rounded text-xs font-medium bg-rose-600 hover:bg-rose-500 text-white transition-colors flex items-center justify-center gap-2 cursor-pointer"
                            >
                              <Square className="w-3.5 h-3.5 fill-current" />
                              <span>Cancel ({elapsedSec}s)</span>
                            </button>
                          ) : (
                            <button
                              onClick={() => handleRunInstance(inst)}
                              disabled={
                                !desc?.available ||
                                (desc?.scope === "single_node" && !selectedNode)
                              }
                              className={`w-full py-1.5 px-3 rounded text-xs font-medium transition-colors flex items-center justify-center gap-2 border ${
                                !desc?.available ||
                                (desc?.scope === "single_node" && !selectedNode)
                                  ? "bg-app-subtle text-app-muted border-app-border-subtle cursor-not-allowed"
                                  : "bg-blue-600 hover:bg-blue-500 text-white border-transparent cursor-pointer"
                              }`}
                            >
                              <Play className="w-3.5 h-3.5 fill-current" />
                              <span>Run Algorithm</span>
                            </button>
                          )}
                        </div>

                        {/* ─── RESULT SUMMARY ROW & TOP EPISTEMIC HUBS (WHEN COMPLETED) ─── */}
                        {isCompleted && inst.result && (
                          <div className="space-y-2 pt-1">
                            <div className="p-2 rounded bg-app-subtle/30 border border-app-border-subtle grid grid-cols-3 gap-2 text-center font-mono">
                              <div className="flex flex-col items-center">
                                <span className="text-[10px] font-sans text-app-muted">Value</span>
                                <span className="font-semibold text-app-heading tabular-nums text-xs mt-0.5">
                                  {inst.result.result_value !== null &&
                                  inst.result.result_value !== undefined
                                    ? Number(inst.result.result_value).toFixed(4)
                                    : "—"}
                                </span>
                              </div>
                              <div className="flex flex-col items-center border-l border-r border-app-border-subtle">
                                <span className="text-[10px] font-sans text-app-muted">Duration</span>
                                <span className="font-semibold text-app-heading tabular-nums text-xs mt-0.5">
                                  {inst.result.duration_ms < 1000
                                    ? `${inst.result.duration_ms}ms`
                                    : `${(inst.result.duration_ms / 1000).toFixed(2)}s`}
                                </span>
                              </div>
                              <div className="flex flex-col items-center">
                                <span className="text-[10px] font-sans text-app-muted">Nodes</span>
                                <span className="font-semibold text-app-heading tabular-nums text-xs mt-0.5">
                                  {Object.keys(inst.result.affected_nodes).length}
                                </span>
                              </div>
                            </div>

                            {/* Top Epistemic Hubs preview */}
                            {(() => {
                              const entries = Object.entries(inst.result.affected_nodes);
                              const topHubs = entries
                                .filter(
                                  ([_, d]) =>
                                    d.net_contribution !== null && d.net_contribution !== undefined
                                )
                                .sort(
                                  (a, b) =>
                                    (b[1].net_contribution ?? 0) - (a[1].net_contribution ?? 0)
                                )
                                .slice(0, 3);

                              if (topHubs.length === 0) return null;

                              return (
                                <div className="space-y-1.5 pt-1">
                                  <div className="flex items-center justify-between text-[11px]">
                                    <span className="font-medium text-app-muted">Top Epistemic Hubs</span>
                                    <button
                                      type="button"
                                      onClick={() => openDetailView(inst.instanceId)}
                                      className="text-[10px] text-blue-500 hover:text-blue-400 hover:underline cursor-pointer"
                                    >
                                      Inspect all ({entries.length}) →
                                    </button>
                                  </div>
                                  <div className="space-y-1 font-mono text-[11px]">
                                    {topHubs.map(([nid, detail], i) => (
                                      <div
                                        key={nid}
                                        onClick={() => onSelectNode?.(nid)}
                                        className="flex items-center justify-between px-2 py-1 rounded bg-app-subtle/40 hover:bg-app-hover border border-app-border-subtle transition-colors cursor-pointer group"
                                        title={`Focus node in graph: ${nid}`}
                                      >
                                        <div className="flex items-center gap-1.5 truncate max-w-[190px]">
                                          <span className="text-app-muted text-[10px]">{i + 1}.</span>
                                          <span className="text-app-heading group-hover:text-blue-500 truncate">
                                            {nid}
                                          </span>
                                        </div>
                                        <span className="text-blue-500 font-semibold tabular-nums shrink-0 ml-2">
                                          {detail.net_contribution?.toFixed(4)}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              );
                            })()}
                          </div>
                        )}

                        {/* ─── RULE-BASED STYLING ─── */}
                        <div className="space-y-2 pt-1 border-t border-app-border-subtle">
                          <div className="flex items-center justify-between">
                            <span className="font-display font-medium text-xs text-app-heading">
                              Rule-Based Styling
                            </span>
                          </div>

                          <div className="space-y-2.5">
                            {/* Size Scaling Toggle */}
                            <div className="space-y-1.5">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-1.5 min-w-0">
                                  <span className="text-xs text-app-text select-none">Size scaling</span>
                                  {isSizeScalingBusy && (
                                    <span className="inline-flex items-center gap-1 text-[10px] text-blue-500 font-mono animate-pulse">
                                      <Loader2 className="w-2.5 h-2.5 animate-spin shrink-0" />
                                      <span>Applying...</span>
                                    </span>
                                  )}
                                </div>
                                <button
                                  type="button"
                                  role="switch"
                                  aria-checked={inst.styling.sizeScaling}
                                  aria-busy={isSizeScalingBusy}
                                  disabled={isCardStylingBusy}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleToggleStyling(inst.instanceId, "sizeScaling");
                                  }}
                                  className={`relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors ${
                                    isCardStylingBusy
                                      ? "cursor-wait opacity-75 pointer-events-none"
                                      : "cursor-pointer"
                                  } ${
                                    inst.styling.sizeScaling
                                      ? "bg-blue-600"
                                      : "bg-app-subtle border border-app-border"
                                  }`}
                                  title={
                                    isSizeScalingBusy
                                      ? "Applying size scaling to graph nodes..."
                                      : inst.styling.sizeScaling
                                      ? "Disable size scaling"
                                      : "Enable size scaling"
                                  }
                                >
                                  <span
                                    className={`inline-flex items-center justify-center h-2.5 w-2.5 rounded-full bg-white transition-transform ${
                                      inst.styling.sizeScaling ? "translate-x-3.5" : "translate-x-0.5"
                                    }`}
                                  >
                                    {isSizeScalingBusy && (
                                      <Loader2 className="w-2 h-2 animate-spin text-blue-600" />
                                    )}
                                  </span>
                                </button>
                              </div>

                              {inst.styling.sizeScaling && (
                                <div className="space-y-1.5 pl-0.5 pt-0.5 animate-in fade-in duration-150">
                                  {/* Sizing Influence / Strength Toggle */}
                                  <div className="flex items-center justify-between gap-2 pt-1 border-t border-app-border-subtle/50">
                                    <div className="flex items-center gap-1.5">
                                      <span className="text-[11px] text-app-muted">Influence Strength</span>
                                      {isSizeStrengthBusy && (
                                        <Loader2 className="w-2.5 h-2.5 animate-spin text-blue-500 shrink-0" />
                                      )}
                                    </div>
                                    <div className="flex items-center bg-app-bg rounded-sm border border-app-border-subtle p-0.5">
                                      {(["subtle", "normal", "strong"] as const).map((strength) => {
                                        const curStrength = inst.styling.sizeStrength || "normal";
                                        const isActive = curStrength === strength;
                                        return (
                                          <button
                                            key={strength}
                                            type="button"
                                            disabled={isCardStylingBusy}
                                            onClick={() =>
                                              handleUpdateSizeStrength(inst.instanceId, strength)
                                            }
                                            className={`px-1.5 py-0.5 rounded-xs text-[10px] font-medium transition-colors capitalize ${
                                              isActive
                                                ? "bg-app-hover text-app-heading font-semibold shadow-2xs"
                                                : "text-app-muted hover:text-app-heading"
                                            } ${
                                              isCardStylingBusy
                                                ? "cursor-wait opacity-60 pointer-events-none"
                                                : "cursor-pointer"
                                            }`}
                                            title={
                                              strength === "subtle"
                                                ? "Subtle influence (0.5× size multiplier)"
                                                : strength === "normal"
                                                ? "Normal influence (1.0× size multiplier)"
                                                : "Strong influence (1.8× size multiplier)"
                                            }
                                          >
                                            {strength}
                                          </button>
                                        );
                                      })}
                                    </div>
                                  </div>

                                  <div className="text-[10px] text-app-muted">
                                    {conflicts.hasSizeConflict ? (
                                      scaleMode === "stack" ? (
                                        <span className="text-blue-600 dark:text-blue-400 font-mono">
                                          ℹ️ Stacking influence: {inst.styling.sizeStrength || "normal"} ({
                                            (inst.styling.sizeStrength || "normal") === "subtle"
                                              ? "0.5×"
                                              : (inst.styling.sizeStrength || "normal") === "strong"
                                              ? "1.8×"
                                              : "1.0×"
                                          }) weight in compound size
                                        </span>
                                      ) : index === 0 ? (
                                        <span className="text-emerald-600 dark:text-emerald-400 font-mono">
                                          ℹ️ Primary scale ({inst.styling.sizeStrength || "normal"}): top priority
                                        </span>
                                      ) : (
                                        <span className="text-amber-600 dark:text-amber-400 font-mono">
                                          ⚠️ Overwritten by higher card in stack
                                        </span>
                                      )
                                    ) : (
                                      <span>
                                        Scales node diameter by metric score ({inst.styling.sizeStrength || "normal"} intensity)
                                      </span>
                                    )}
                                  </div>
                                </div>
                              )}
                            </div>

                            {/* Color Gradient Toggle */}
                            <div className="space-y-1">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-1.5 min-w-0">
                                  <span className="text-xs text-app-text select-none">Color gradient</span>
                                  {isColorGradientBusy && (
                                    <span className="inline-flex items-center gap-1 text-[10px] text-blue-500 font-mono animate-pulse">
                                      <Loader2 className="w-2.5 h-2.5 animate-spin shrink-0" />
                                      <span>Applying...</span>
                                    </span>
                                  )}
                                </div>
                                <button
                                  type="button"
                                  role="switch"
                                  aria-checked={inst.styling.colorGradient}
                                  aria-busy={isColorGradientBusy}
                                  disabled={isCardStylingBusy}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleToggleStyling(inst.instanceId, "colorGradient");
                                  }}
                                  className={`relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors ${
                                    isCardStylingBusy
                                      ? "cursor-wait opacity-75 pointer-events-none"
                                      : "cursor-pointer"
                                  } ${
                                    inst.styling.colorGradient
                                      ? "bg-blue-600"
                                      : "bg-app-subtle border border-app-border"
                                  }`}
                                  title={
                                    isColorGradientBusy
                                      ? "Applying color gradient to graph..."
                                      : inst.styling.colorGradient
                                      ? "Disable color gradient"
                                      : "Enable color gradient"
                                  }
                                >
                                  <span
                                    className={`inline-flex items-center justify-center h-2.5 w-2.5 rounded-full bg-white transition-transform ${
                                      inst.styling.colorGradient ? "translate-x-3.5" : "translate-x-0.5"
                                    }`}
                                  >
                                    {isColorGradientBusy && (
                                      <Loader2 className="w-2 h-2 animate-spin text-blue-600" />
                                    )}
                                  </span>
                                </button>
                              </div>

                              {inst.styling.colorGradient && (
                                <div className="text-[10px] text-app-muted pl-0.5">
                                  {conflicts.hasColorConflict ? (
                                    index === 0 ? (
                                      <span className="text-blue-600 dark:text-blue-400 font-mono">
                                        ℹ️ Active fill gradient (top priority)
                                      </span>
                                    ) : (
                                      <span className="text-purple-600 dark:text-purple-400 font-mono">
                                        ℹ️ Routed to outer node border / halo
                                      </span>
                                    )
                                  ) : (
                                    <span>Applies sequential gradient across scores</span>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* VIEW 2: PER-METRIC DETAILED INSPECTION VIEW                        */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {currentView === "detail" && detailInstance && detailDescriptor && (
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 text-xs select-text">
          {/* Header Bar */}
          <div className="flex items-center justify-between pb-2 border-b border-app-border">
            <button
              onClick={() => setCurrentView("stack")}
              className="flex items-center gap-1.5 text-xs text-blue-500 hover:text-blue-400 transition-colors font-medium cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Algorithms</span>
            </button>
            <span className="font-mono text-[10px] text-app-muted uppercase">
              {detailDescriptor.engine} · {detailDescriptor.scope}
            </span>
          </div>

          {/* Overview */}
          <div className="space-y-1.5">
            <h3 className="font-display text-sm font-semibold text-app-heading">
              {detailDescriptor.label}
            </h3>
            <p className="text-xs leading-relaxed text-app-text border-l-2 border-blue-500/40 pl-3 py-0.5">
              {detailDescriptor.description}
            </p>
          </div>

          {/* Target Node (for local QBAF) */}
          {detailDescriptor.scope === "single_node" && (
            <div className="space-y-1.5">
              <div className="pb-1 border-b border-app-border-subtle flex items-center justify-between">
                <span className="font-display text-xs font-semibold text-app-heading">Target Node</span>
                {selectedNode && (
                  <span className="font-mono text-[10px] text-app-muted">
                    L{selectedNode.layer} · {selectedNode.type}
                  </span>
                )}
              </div>
              {selectedNode ? (
                <div className="p-2.5 rounded bg-app-subtle/30 border border-app-border-subtle space-y-1">
                  <div className="font-medium text-app-heading text-xs truncate">
                    {selectedNode.label || selectedNode.id}
                  </div>
                  <div className="flex items-center justify-between pt-0.5">
                    <span className="font-mono text-[10px] text-app-muted truncate max-w-[200px]">
                      {selectedNode.id}
                    </span>
                    <button
                      onClick={handleCopyTargetId}
                      className="p-1 text-app-muted hover:text-app-heading rounded transition-colors cursor-pointer"
                      title="Copy Target Node ID"
                    >
                      {copiedTargetId ? (
                        <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                      ) : (
                        <Copy className="w-3 h-3" />
                      )}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-2.5 rounded bg-app-subtle/20 border border-app-border-subtle text-app-muted text-center">
                  No target node selected in graph canvas.
                </div>
              )}
            </div>
          )}

          {/* Results Telemetry & High Density Data Grid */}
          {detailInstance.result ? (
            <div className="space-y-4 pt-1">
              {/* Telemetry KPI Grid */}
              <div className="p-2.5 rounded bg-app-subtle/30 border border-app-border-subtle grid grid-cols-4 gap-2 text-center font-mono">
                <div className="flex flex-col items-center">
                  <span className="text-[10px] font-sans text-app-muted uppercase tracking-wider">
                    Value
                  </span>
                  <span className="font-mono text-sm font-semibold text-app-heading tabular-nums mt-0.5">
                    {detailInstance.result.result_value !== null &&
                    detailInstance.result.result_value !== undefined
                      ? Number(detailInstance.result.result_value).toFixed(4)
                      : "—"}
                  </span>
                </div>
                <div className="flex flex-col items-center border-l border-app-border-subtle">
                  <span className="text-[10px] font-sans text-app-muted uppercase tracking-wider">
                    Duration
                  </span>
                  <span className="font-mono text-sm font-semibold text-app-heading tabular-nums mt-0.5">
                    {detailInstance.result.duration_ms < 1000
                      ? `${detailInstance.result.duration_ms}ms`
                      : `${(detailInstance.result.duration_ms / 1000).toFixed(2)}s`}
                  </span>
                </div>
                <div className="flex flex-col items-center border-l border-app-border-subtle">
                  <span className="text-[10px] font-sans text-app-muted uppercase tracking-wider">
                    Nodes
                  </span>
                  <span className="font-mono text-sm font-semibold text-app-heading tabular-nums mt-0.5">
                    {Object.keys(detailInstance.result.affected_nodes).length}
                  </span>
                </div>
                <div className="flex flex-col items-center border-l border-app-border-subtle">
                  <span className="text-[10px] font-sans text-app-muted uppercase tracking-wider">
                    Edges
                  </span>
                  <span className="font-mono text-sm font-semibold text-app-heading tabular-nums mt-0.5">
                    {detailInstance.result.affected_edges.length}
                  </span>
                </div>
              </div>

              {/* Affected Nodes Linear-Style Data Grid */}
              <div className="space-y-0 border border-app-border-subtle rounded overflow-hidden">
                <button
                  onClick={() => setShowNodesTable(!showNodesTable)}
                  className="w-full flex items-center justify-between p-2.5 bg-app-subtle/30 text-left cursor-pointer select-none group"
                >
                  <div className="flex items-center gap-1.5">
                    {showNodesTable ? (
                      <ChevronDown className="w-3.5 h-3.5 text-app-muted" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-app-muted" />
                    )}
                    <span className="font-display text-xs font-semibold text-app-heading group-hover:text-blue-500 transition-colors">
                      Affected Nodes
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-app-muted tabular-nums">
                    ({Object.keys(detailInstance.result.affected_nodes).length})
                  </span>
                </button>

                {showNodesTable && (
                  <div className="space-y-0">
                    <div className="p-2 border-b border-app-border-subtle bg-app-bg/50">
                      <div className="relative">
                        <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-app-muted" />
                        <input
                          type="text"
                          placeholder="Filter node ID..."
                          value={nodeFilter}
                          onChange={(e) => setNodeFilter(e.target.value)}
                          className="w-full pl-6 pr-2 py-1 text-[11px] bg-app-surface border border-app-border-subtle rounded focus:outline-none focus:border-blue-500/60 font-mono text-app-heading placeholder:text-app-muted"
                        />
                      </div>
                    </div>

                    {/* Data Grid Column Headers per Anti-Pattern 9 in design.md */}
                    <div className="flex items-center justify-between px-3 py-1.5 bg-app-subtle/40 border-b border-app-border-subtle font-sans text-[10px] font-semibold text-app-muted uppercase tracking-[0.05em]">
                      <span>Node Identifier</span>
                      <div className="flex items-center gap-4">
                        <span>Role</span>
                        <span className="w-14 text-right">Contribution</span>
                      </div>
                    </div>

                    <div className="divide-y divide-app-border-subtle font-mono text-[11px] max-h-56 overflow-y-auto">
                      {Object.entries(detailInstance.result.affected_nodes)
                        .filter(([nid]) =>
                          nodeFilter
                            ? nid.toLowerCase().includes(nodeFilter.toLowerCase())
                            : true
                        )
                        .map(([nid, detail]) => (
                          <div
                            key={nid}
                            onClick={() => onSelectNode?.(nid)}
                            className="py-1.5 px-3 flex items-center justify-between hover:bg-app-hover cursor-pointer group transition-colors"
                            title={`Inspect node: ${nid}`}
                          >
                            <span className="text-app-heading truncate max-w-[130px] group-hover:text-blue-500 font-medium">
                              {nid}
                            </span>
                            <div className="flex items-center gap-2 shrink-0">
                              {detail.roles.includes("support") && (
                                <span className="text-[10px] font-mono px-1 py-0.2 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 font-medium">
                                  +sup
                                </span>
                              )}
                              {detail.roles.includes("attack") && (
                                <span className="text-[10px] font-mono px-1 py-0.2 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 font-medium">
                                  -att
                                </span>
                              )}
                              {detail.net_contribution !== null &&
                              detail.net_contribution !== undefined ? (
                                <span className="text-[10px] text-app-heading font-mono tabular-nums w-14 text-right">
                                  {detail.net_contribution > 0 ? "+" : ""}
                                  {detail.net_contribution.toFixed(2)}
                                </span>
                              ) : (
                                <span className="text-[10px] text-app-muted font-mono w-14 text-right">
                                  —
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Affected Pathways Data Grid */}
              <div className="space-y-0 border border-app-border-subtle rounded overflow-hidden">
                <button
                  onClick={() => setShowEdgesTable(!showEdgesTable)}
                  className="w-full flex items-center justify-between p-2.5 bg-app-subtle/30 text-left cursor-pointer select-none group"
                >
                  <div className="flex items-center gap-1.5">
                    {showEdgesTable ? (
                      <ChevronDown className="w-3.5 h-3.5 text-app-muted" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-app-muted" />
                    )}
                    <span className="font-display text-xs font-semibold text-app-heading group-hover:text-blue-500 transition-colors">
                      Affected Pathways
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-app-muted tabular-nums">
                    ({detailInstance.result.affected_edges.length})
                  </span>
                </button>

                {showEdgesTable && (
                  <div>
                    {/* Column Headers */}
                    <div className="flex items-center justify-between px-3 py-1.5 bg-app-subtle/40 border-b border-app-border-subtle font-sans text-[10px] font-semibold text-app-muted uppercase tracking-[0.05em]">
                      <span>Source → Target</span>
                      <span>Role</span>
                    </div>

                    <div className="divide-y divide-app-border-subtle font-mono text-[10px] max-h-56 overflow-y-auto">
                      {detailInstance.result.affected_edges.map((edge, idx) => (
                        <div
                          key={edge.relationship_id || idx}
                          className="py-1.5 px-3 flex items-center justify-between hover:bg-app-hover transition-colors"
                        >
                          <span className="truncate max-w-[170px] text-app-heading">
                            {edge.source_node_id} → {edge.target_node_id}
                          </span>
                          <span
                            className={`font-mono text-[10px] px-1 py-0.2 rounded border font-medium uppercase ${
                              edge.role === "support"
                                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                                : edge.role === "attack"
                                ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20"
                                : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                            }`}
                          >
                            {edge.role}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="py-12 text-center text-app-muted text-xs">
              No results calculated yet. Return to Algorithms to run this metric.
            </div>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* VIEW 3: REGISTERED ALGORITHM CATALOG                               */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {currentView === "catalog" && (
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Catalog Search Filter */}
          <div className="px-4 py-2.5 border-b border-app-border bg-app-surface shrink-0">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-app-muted" />
              <input
                type="text"
                placeholder="Filter algorithms, engines, descriptions..."
                value={catalogSearch}
                onChange={(e) => setCatalogSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-app-bg border border-app-border rounded text-app-heading placeholder:text-app-muted focus:outline-none focus:border-blue-500/60"
              />
            </div>
          </div>

          {/* Catalog List */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2 divide-y divide-app-border-subtle">
            {descriptors
              .filter(
                (d) =>
                  !catalogSearch.trim() ||
                  d.label.toLowerCase().includes(catalogSearch.toLowerCase()) ||
                  d.id.toLowerCase().includes(catalogSearch.toLowerCase()) ||
                  d.description.toLowerCase().includes(catalogSearch.toLowerCase()) ||
                  d.engine.toLowerCase().includes(catalogSearch.toLowerCase())
              )
              .map((d) => (
                <div
                  key={d.id}
                  className="pt-2.5 first:pt-0 pb-2.5 hover:bg-app-subtle/30 -mx-2 px-2 rounded transition-colors space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-display font-medium text-xs text-app-heading">
                      {d.label}
                    </span>
                    <button
                      onClick={() => {
                        addInstance(d.id);
                        setCurrentView("stack");
                      }}
                      className="px-2 py-0.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-[10px] font-medium flex items-center gap-1 cursor-pointer transition-colors"
                      title="Add to analysis stack"
                    >
                      <Plus className="w-3 h-3" />
                      <span>Add</span>
                    </button>
                  </div>
                  <p className="text-[11px] text-app-muted leading-relaxed line-clamp-2">
                    {d.description}
                  </p>
                  <div className="flex items-center gap-2 text-[10px] font-mono text-app-muted">
                    <span className="uppercase">{d.engine}</span>
                    <span>·</span>
                    <span>{d.scope === "single_node" ? "node" : "global"}</span>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
};
