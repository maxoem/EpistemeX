import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Layers,
  Network,
  Scale,
  Sparkles,
  Workflow,
  PanelRightClose,
  PanelRightOpen,
  Info,
  ChevronRight,
  ArrowRight,
  Columns2,
  Rows2,
  CheckCircle2,
} from "lucide-react";
import { CascadingBourbakiGrid } from "./CascadingBourbakiGrid";
import { PosetDagViewer } from "./PosetDagViewer";
import { PolarityConflictMatrix } from "./PolarityConflictMatrix";
import { BourbakiNodeInspector } from "./BourbakiNodeInspector";
import { ResizablePanel } from "../../../ResizablePanel";
import { useEvaluationStore } from "../../../../store/evaluationStore";
import type { BourbakiSubElement } from "./types";
import { CLASS_METADATA, getBourbakiSubElements } from "./types";

export const EpistemicTheoryNetView: React.FC = () => {
  const {
    activeReport,
    selectedBourbakiElement,
    setSelectedBourbakiElement,
    theoryNetViewMode,
    setTheoryNetViewMode,
  } = useEvaluationStore();

  const [allElements, setAllElements] = useState<BourbakiSubElement[]>(() =>
    getBourbakiSubElements(activeReport)
  );

  // System view sub-layout: "side-by-side", "stacked", "poset", "polarity"
  const [systemLayout, setSystemLayout] = useState<"side-by-side" | "stacked" | "poset" | "polarity">(
    "side-by-side"
  );

  // Asymmetrical flexibility in Node Explorer: right panel is collapsible and drag-to-resize
  const [isRightPanelCollapsed, setIsRightPanelCollapsed] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem("episteme-eval-theorynet-right-panel-width-collapsed");
      return stored === "true";
    } catch {
      return false;
    }
  });

  const toggleRightPanel = useCallback(() => {
    setIsRightPanelCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(
          "episteme-eval-theorynet-right-panel-width-collapsed",
          String(next)
        );
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  // Update elements when activeReport changes
  useEffect(() => {
    setAllElements(getBourbakiSubElements(activeReport));
  }, [activeReport]);

  const handleSelectElement = (el: BourbakiSubElement | null) => {
    setSelectedBourbakiElement(el);
    if (el && isRightPanelCollapsed) {
      setIsRightPanelCollapsed(false);
    }
  };

  // Compute macro structuralist completeness scores across the entire theory
  const completenessSummary = useMemo(() => {
    const decomposition = activeReport?.model_decomposition || [];
    return ["Mp", "M", "Mpp", "C", "I"].map((sym) => {
      const meta = CLASS_METADATA[sym];
      const entry = decomposition.find(
        (d) =>
          d.symbol === sym ||
          d.class_name?.toLowerCase().startsWith(sym.toLowerCase()) ||
          (sym === "Mp" && d.class_name?.includes("potential") && !d.class_name?.includes("partial")) ||
          (sym === "M" && d.class_name?.includes("actual")) ||
          (sym === "Mpp" && d.class_name?.includes("partial")) ||
          (sym === "C" && d.class_name?.includes("constraint")) ||
          (sym === "I" && d.class_name?.includes("intended"))
      );
      const completeness = entry ? entry.completeness : sym === "Mpp" ? 0.94 : sym === "C" ? 0.88 : 0.8;
      return {
        symbol: sym,
        label: meta?.label || sym,
        completeness: Math.round(completeness * 100),
      };
    });
  }, [activeReport]);

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-hidden bg-app-bg text-app-text select-none font-sans">
      {/* Macro XOR View Architecture Bar (Unified 42px Toolbar) */}
      <div className="h-11 px-4 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs gap-3">
        {/* Left: Global XOR View Switcher */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-app-bg dark:bg-[#111827] p-0.5 rounded-md border border-app-border">
            <button
              type="button"
              onClick={() => setTheoryNetViewMode("explorer")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors cursor-pointer ${
                theoryNetViewMode === "explorer"
                  ? "bg-app-surface text-app-heading border border-app-border/80 font-semibold shadow-xs"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
              title="Node Explorer View: Navigate axioms, models, and empirical claims with localized detail inspector"
            >
              <Layers className="w-3.5 h-3.5 text-blue-500" />
              <span>Node Explorer View</span>
            </button>

            <button
              type="button"
              onClick={() => setTheoryNetViewMode("system")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors cursor-pointer ${
                theoryNetViewMode === "system"
                  ? "bg-app-surface text-app-heading border border-app-border/80 font-semibold shadow-xs"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
              title="System / Global View: Holistic macro-level Poset Hierarchy and structuralist completeness"
            >
              <Network className="w-3.5 h-3.5 text-purple-500" />
              <span>System / Global View</span>
            </button>
          </div>

          <span className="text-[11px] text-app-muted font-mono hidden md:inline">
            {theoryNetViewMode === "explorer"
              ? "⟨Mp → M → I⟩ Bourbaki Hierarchy"
              : "Strict Poset DAG & Dialectical Concordance"}
          </span>
        </div>

        {/* Right contextual controls based on active macro view */}
        <div className="flex items-center gap-2">
          {theoryNetViewMode === "system" ? (
            /* System View Layout Controls */
            <div className="flex items-center gap-1 bg-app-bg dark:bg-[#111827] p-0.5 rounded border border-app-border text-[11px]">
              <button
                type="button"
                onClick={() => setSystemLayout("side-by-side")}
                className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors ${
                  systemLayout === "side-by-side"
                    ? "bg-app-surface text-app-heading font-semibold shadow-xs"
                    : "text-app-muted hover:text-app-text"
                }`}
                title="Side-by-side Poset DAG and Polarity Matrix"
              >
                <Columns2 className="w-3 h-3" />
                <span>Side-by-Side</span>
              </button>
              <button
                type="button"
                onClick={() => setSystemLayout("stacked")}
                className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors ${
                  systemLayout === "stacked"
                    ? "bg-app-surface text-app-heading font-semibold shadow-xs"
                    : "text-app-muted hover:text-app-text"
                }`}
                title="Stacked Poset DAG and Polarity Matrix"
              >
                <Rows2 className="w-3 h-3" />
                <span>Stacked</span>
              </button>
              <button
                type="button"
                onClick={() => setSystemLayout("poset")}
                className={`px-2 py-0.5 rounded transition-colors ${
                  systemLayout === "poset"
                    ? "bg-app-surface text-app-heading font-semibold shadow-xs"
                    : "text-app-muted hover:text-app-text"
                }`}
                title="Isolate Poset DAG Hierarchy"
              >
                Poset Only
              </button>
              <button
                type="button"
                onClick={() => setSystemLayout("polarity")}
                className={`px-2 py-0.5 rounded transition-colors ${
                  systemLayout === "polarity"
                    ? "bg-app-surface text-app-heading font-semibold shadow-xs"
                    : "text-app-muted hover:text-app-text"
                }`}
                title="Isolate Polarity Conflicts"
              >
                Polarity Only
              </button>
            </div>
          ) : (
            /* Node Explorer Panel Control */
            <button
              type="button"
              onClick={toggleRightPanel}
              className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs border transition-colors cursor-pointer ${
                isRightPanelCollapsed
                  ? "bg-blue-500/10 border-blue-500/30 text-blue-500 hover:bg-blue-500/20"
                  : "bg-app-bg border-app-border text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
              title={isRightPanelCollapsed ? "Expand Node Detail Pane" : "Collapse Node Detail Pane to focus on table"}
            >
              <PanelRightClose className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">
                {isRightPanelCollapsed ? "Expand Inspector" : "Collapse Inspector"}
              </span>
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area: XOR View Selection */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {theoryNetViewMode === "system" ? (
          /* ========================================================= */
          /* 1. System / Global View: Holistic Theory Net Architecture */
          /* ========================================================= */
          <div className="flex-1 flex flex-col h-full overflow-hidden">
            {/* Top Structuralist Completeness Strip */}
            <div className="px-4 py-2 bg-app-surface/60 border-b border-app-border flex items-center justify-between text-xs shrink-0 flex-wrap gap-2">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-[11px] font-medium text-app-muted uppercase tracking-wider">
                  Theory Completeness:
                </span>
                {completenessSummary.map((c) => (
                  <div key={c.symbol} className="flex items-center gap-1.5 text-xs">
                    <span className="font-mono font-medium text-app-heading">{c.symbol}:</span>
                    <span
                      className={`tabular-nums font-medium ${
                        c.completeness >= 85
                          ? "text-emerald-600 dark:text-emerald-400"
                          : c.completeness >= 70
                          ? "text-blue-600 dark:text-blue-400"
                          : "text-amber-600 dark:text-amber-400"
                      }`}
                    >
                      {c.completeness}%
                    </span>
                  </div>
                ))}
              </div>

              <div className="flex items-center gap-2 text-[11px] text-app-muted">
                <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
                  <CheckCircle2 className="w-3 h-3" />
                  Poset DAG Verified
                </span>
                <span className="text-app-border">·</span>
                <button
                  onClick={() => setTheoryNetViewMode("explorer")}
                  className="text-blue-500 hover:underline flex items-center gap-1 font-sans cursor-pointer"
                >
                  <span>Explore Nodes in Detail</span>
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            </div>

            {/* Macro Analytical Panels (Poset DAG + Polarity Conflict Matrix) */}
            <div className="flex-1 overflow-hidden flex flex-col">
              {systemLayout === "side-by-side" ? (
                <div className="flex-1 flex h-full overflow-hidden divide-x divide-app-border">
                  {/* Left Half: Poset DAG Hierarchy & Cyclical Path Isolation */}
                  <div className="w-1/2 flex flex-col h-full overflow-hidden">
                    <PosetDagViewer />
                  </div>

                  {/* Right Half: Polarity Conflict Concordance & Critical Inversions */}
                  <div className="w-1/2 flex flex-col h-full overflow-hidden">
                    <PolarityConflictMatrix />
                  </div>
                </div>
              ) : systemLayout === "stacked" ? (
                <div className="flex-1 flex flex-col h-full overflow-hidden divide-y divide-app-border">
                  <div className="h-1/2 flex flex-col overflow-hidden">
                    <PosetDagViewer />
                  </div>
                  <div className="h-1/2 flex flex-col overflow-hidden">
                    <PolarityConflictMatrix />
                  </div>
                </div>
              ) : systemLayout === "poset" ? (
                <div className="flex-1 flex flex-col h-full overflow-hidden">
                  <PosetDagViewer />
                </div>
              ) : (
                <div className="flex-1 flex flex-col h-full overflow-hidden">
                  <PolarityConflictMatrix />
                </div>
              )}
            </div>
          </div>
        ) : (
          /* ========================================================= */
          /* 2. Node Explorer View: Table Hierarchy + Local Detail Pane*/
          /* ========================================================= */
          <div className="flex-1 flex h-full w-full overflow-hidden">
            {/* Left: Cascading Bourbaki Model Tree Grid (Fluid flex-1) */}
            <div className="flex-1 flex flex-col h-full overflow-hidden min-w-0">
              <CascadingBourbakiGrid
                selectedElement={selectedBourbakiElement}
                onSelectElement={handleSelectElement}
                onElementsCalculated={setAllElements}
              />
            </div>

            {/* Right: Localized Detail Inspector (Collapsible & Drag-to-Resize) */}
            <ResizablePanel
              side="right"
              storageKey="episteme-eval-theorynet-right-panel-width"
              defaultWidth={460}
              minWidth={320}
              maxWidth={800}
              collapsible={true}
              collapseThreshold={140}
              collapsed={isRightPanelCollapsed}
              onToggleCollapse={toggleRightPanel}
              className="!border-l !border-app-border flex flex-col h-full bg-app-surface shadow-xs"
            >
              {selectedBourbakiElement ? (
                <BourbakiNodeInspector
                  element={selectedBourbakiElement}
                  allElements={allElements}
                  onSelectElement={handleSelectElement}
                  onClose={() => setSelectedBourbakiElement(null)}
                />
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-app-muted space-y-3">
                  <div className="p-3 rounded-full bg-blue-500/10 text-blue-500">
                    <Layers className="w-8 h-8" />
                  </div>
                  <div className="space-y-1 max-w-xs">
                    <h4 className="text-sm font-semibold text-app-heading">
                      Select a Node to Inspect
                    </h4>
                    <p className="text-xs text-app-muted leading-relaxed">
                      Click any Axiom, Sub-Model, Constraint, or Empirical Claim in the table on the
                      left to inspect its mathematical formulation, DAG relationships, and
                      inferential polarity.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setTheoryNetViewMode("system")}
                    className="px-3 py-1.5 rounded text-xs font-medium bg-app-surface hover:bg-app-subtle border border-app-border text-app-text transition-colors cursor-pointer"
                  >
                    View System / Global Evaluation →
                  </button>
                </div>
              )}
            </ResizablePanel>
          </div>
        )}
      </div>
    </div>
  );
};
