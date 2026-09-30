import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Layers,
  Network,
  PanelRightClose,
  Workflow,
  Scale,
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

interface CompletenessEntry {
  symbol: string;
  label: string;
  completeness: number;
}

const COMPLETENESS_SYMBOLS = ["Mp", "M", "Mpp", "C", "I"] as const;

const DEFAULT_COMPLETENESS: Record<string, number> = {
  Mp: 0.8,
  M: 0.8,
  Mpp: 0.94,
  C: 0.88,
  I: 0.8,
};

function resolveDecompositionEntry(
  decomposition: any[],
  symbol: string
): { completeness?: number } | undefined {
  return decomposition.find((d) => {
    const className = (d.class_name ?? "").toLowerCase();
    return (
      d.symbol === symbol ||
      className.startsWith(symbol.toLowerCase()) ||
      (symbol === "Mp" && className.includes("potential") && !className.includes("partial")) ||
      (symbol === "M" && className.includes("actual")) ||
      (symbol === "Mpp" && className.includes("partial")) ||
      (symbol === "C" && className.includes("constraint")) ||
      (symbol === "I" && className.includes("intended"))
    );
  });
}

function computeCompletenessSummary(activeReport?: any): CompletenessEntry[] {
  const decomposition = activeReport?.model_decomposition || [];
  return COMPLETENESS_SYMBOLS.map((sym) => {
    const entry = resolveDecompositionEntry(decomposition, sym);
    const meta = CLASS_METADATA[sym];
    const completeness = entry?.completeness ?? DEFAULT_COMPLETENESS[sym];
    return {
      symbol: sym,
      label: meta?.label || sym,
      completeness: Math.round(completeness * 100),
    };
  });
}

export type TheoryNetLens = "bourbaki" | "poset" | "polarity";

/**
 * Sub-View 3.2: Formal Epistemic Invariants & Dialectical Verification.
 *
 * Implements design.md §4 & §8 (Zero-Box Segmented Scope Architecture):
 * - Eliminates arbitrary 50/50 two-column squashing
 * - Single-Controller IDE navigation model with 3 dedicated epistemic lenses:
 *   1. Bourbaki Structuralist Completeness (⟨Mp → M → I⟩)
 *   2. Specialization Poset & Strict DAG Acyclicity
 *   3. Inferential Polarity Concordance (SUPPORTS vs. ATTACKS)
 * - Docked Edge-to-Edge Master-Detail Workbench with keyboard triage (j/k)
 */
export const EpistemicTheoryNetView: React.FC = () => {
  const {
    activeReport,
    selectedBourbakiElement,
    setSelectedBourbakiElement,
  } = useEvaluationStore();

  const [activeLens, setActiveLens] = useState<TheoryNetLens>("bourbaki");
  const [allElements, setAllElements] = useState<BourbakiSubElement[]>([]);

  // Right Inspector Collapsed State (Bourbaki Node Inspector)
  const [isRightPanelCollapsed, setIsRightPanelCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem("episteme-eval-theorynet-right-panel-collapsed") === "true";
    } catch {
      return false;
    }
  });

  const toggleRightPanel = useCallback(() => {
    setIsRightPanelCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("episteme-eval-theorynet-right-panel-collapsed", String(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  useEffect(() => {
    setAllElements(getBourbakiSubElements(activeReport));
  }, [activeReport]);

  const handleSelectElement = (el: BourbakiSubElement | null) => {
    setSelectedBourbakiElement(el);
    if (el && isRightPanelCollapsed) {
      setIsRightPanelCollapsed(false);
    }
  };

  const completenessSummary = useMemo(
    () => computeCompletenessSummary(activeReport),
    [activeReport]
  );

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-hidden bg-app-bg text-app-text select-none font-sans">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 1. Contextual Action Bar (44px, docked edge-to-edge border-b)       */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="h-11 px-4 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs gap-3">
        {/* Left: Breadcrumbs & Completeness Pills */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-blue-500 shrink-0" />
            <h2 className="type-caption font-semibold text-app-heading uppercase tracking-wider">
              Epistemic TheoryNet
            </h2>
          </div>

          {/* Completeness Summary Strip (Inter tabular numerals) */}
          <div className="hidden xl:flex items-center gap-2 border-l border-app-border pl-3 text-xs">
            {completenessSummary.map((c) => (
              <div key={c.symbol} className="flex items-center gap-1 text-[11px]">
                <span className="type-mono font-semibold text-app-heading">{c.symbol}:</span>
                <span
                  className={`type-mono font-semibold tabular-nums ${
                    c.completeness >= 85
                      ? "text-emerald-500"
                      : c.completeness >= 70
                      ? "text-blue-500"
                      : "text-amber-500"
                  }`}
                >
                  {c.completeness}%
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Center: Zero-Box Segmented Lens Control (design.md §4 & §8) */}
        <div className="flex items-center gap-1 bg-app-bg p-0.5 rounded border border-app-border text-xs">
          <button
            type="button"
            onClick={() => setActiveLens("bourbaki")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded transition-colors cursor-pointer ${
              activeLens === "bourbaki"
                ? "bg-app-surface text-app-heading font-medium border border-app-border/80"
                : "text-app-muted hover:text-app-text"
            }`}
            title="Bourbaki Decomposition Lens: Inspect Axioms, Models, and Intended Applications"
          >
            <Layers className="w-3.5 h-3.5 text-blue-500" />
            <span>Bourbaki Structuralism</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveLens("poset")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded transition-colors cursor-pointer ${
              activeLens === "poset"
                ? "bg-app-surface text-app-heading font-medium border border-app-border/80"
                : "text-app-muted hover:text-app-text"
            }`}
            title="Specialization Poset Lens: Strict DAG Acyclicity and Invariants"
          >
            <Workflow className="w-3.5 h-3.5 text-purple-500" />
            <span>Poset DAG Invariants</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveLens("polarity")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded transition-colors cursor-pointer ${
              activeLens === "polarity"
                ? "bg-app-surface text-app-heading font-medium border border-app-border/80"
                : "text-app-muted hover:text-app-text"
            }`}
            title="Inferential Polarity Lens: SUPPORTS vs ATTACKS Dialectics"
          >
            <Scale className="w-3.5 h-3.5 text-amber-500" />
            <span>Polarity Concordance</span>
          </button>
        </div>

        {/* Right: Operational Status Pill & Panel Toggle */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="hidden sm:inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
            <CheckCircle2 className="w-3 h-3 text-emerald-500" />
            DAG Invariants Verified
          </span>

          {activeLens === "bourbaki" && (
            <button
              type="button"
              onClick={toggleRightPanel}
              className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs border transition-colors cursor-pointer ${
                isRightPanelCollapsed
                  ? "bg-blue-500/10 border-blue-500/30 text-blue-500 hover:bg-blue-500/20"
                  : "bg-app-bg border-app-border text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
              title={isRightPanelCollapsed ? "Expand Node Inspector" : "Collapse Node Inspector"}
            >
              <PanelRightClose className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">
                {isRightPanelCollapsed ? "Node Inspector" : "Collapse"}
              </span>
            </button>
          )}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 2. Main Content Stage (Docked Edge-to-Edge Master-Detail)           */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden flex">
        {activeLens === "bourbaki" ? (
          /* Lens 1: Bourbaki Structuralist Completeness */
          <div className="flex-1 flex h-full w-full overflow-hidden">
            {/* Center Stage: Headless Linear Data Grid */}
            <div className="flex-1 flex flex-col h-full overflow-hidden min-w-0">
              <CascadingBourbakiGrid
                selectedElement={selectedBourbakiElement}
                onSelectElement={handleSelectElement}
                onElementsCalculated={setAllElements}
              />
            </div>

            {/* Right Diagnostic Rail: Bourbaki Node Inspector */}
            <ResizablePanel
              side="right"
              storageKey="episteme-eval-theorynet-right-panel-width"
              defaultWidth={460}
              minWidth={340}
              maxWidth={800}
              collapsible={true}
              collapseThreshold={140}
              collapsed={isRightPanelCollapsed}
              onToggleCollapse={toggleRightPanel}
              className="!border-l !border-app-border flex flex-col h-full bg-app-surface"
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
                    <h4 className="type-h2 text-sm font-semibold text-app-heading">
                      Select a Node to Inspect
                    </h4>
                    <p className="type-body text-xs text-app-muted leading-relaxed">
                      Click any Axiom, Sub-Model, Constraint, or Empirical Claim in the table on the
                      left or use <kbd className="px-1 py-0.5 rounded bg-app-bg border border-app-border text-[10px] type-mono">j</kbd> /{" "}
                      <kbd className="px-1 py-0.5 rounded bg-app-bg border border-app-border text-[10px] type-mono">k</kbd> to step through nodes.
                    </p>
                  </div>
                </div>
              )}
            </ResizablePanel>
          </div>
        ) : activeLens === "poset" ? (
          /* Lens 2: Specialization Poset & Strict DAG Acyclicity */
          <div className="flex-1 flex h-full w-full overflow-hidden">
            <PosetDagViewer />
          </div>
        ) : (
          /* Lens 3: Inferential Polarity Concordance */
          <div className="flex-1 flex h-full w-full overflow-hidden">
            <PolarityConflictMatrix />
          </div>
        )}
      </div>
    </div>
  );
};
