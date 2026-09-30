import React from "react";
import {
  AlertOctagon,
  CheckCircle2,
  GitBranch,
  Link2,
  Network,
  ShieldAlert,
  Workflow,
  X,
} from "lucide-react";
import type { BourbakiSubElement } from "./types";
import { CLASS_METADATA } from "./types";
import { useEvaluationStore } from "../../../../store/evaluationStore";

export interface BourbakiNodeInspectorProps {
  element: BourbakiSubElement;
  allElements?: BourbakiSubElement[];
  onSelectElement: (el: BourbakiSubElement) => void;
  onClose: () => void;
}

/**
 * Contextual Inspector Rail for Bourbaki Structuralist Nodes.
 *
 * Implements design.md §1 & §2:
 * - Typographic flow without nested "box-in-box" borders
 * - Strict typography: Manrope headers, Inter prose, JetBrains Mono formulas & IDs
 * - Tabular numeral readouts for reference/prediction/coverage ratios
 */
export const BourbakiNodeInspector: React.FC<BourbakiNodeInspectorProps> = ({
  element,
  allElements = [],
  onSelectElement,
  onClose,
}) => {
  const { setActiveSubTab, setSelectedOverlayItem, setCycleHighlightNodeIds } = useEvaluationStore();

  const meta = CLASS_METADATA[element.classType] || {
    label: element.classType,
    symbol: element.symbol,
    color: "text-blue-500",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
    description: "",
  };

  const isMasked = element.status === "cascade_masked_orphan";
  const isOmission = element.status === "root_cause_omission";
  const isPass = element.status === "pass" || element.status === "active";

  const parentElement = element.parentAxiomId
    ? allElements.find((el) => el.id === element.parentAxiomId)
    : null;

  const childElements = allElements.filter(
    (el) => el.parentAxiomId === element.id || element.dependents?.includes(el.id)
  );

  const handleInspectOnCanvas = () => {
    setActiveSubTab("canvas");
    setSelectedOverlayItem({
      type: "node",
      item: {
        id: element.id,
        label: element.name,
        class_name: element.classType,
        symbol: element.symbol,
        alignment_status: isPass ? "true_positive" : isOmission ? "false_negative" : "borderline",
        gold_id: element.matched_count > 0 ? `gold_${element.id}` : null,
        similarity_score: element.coverage,
        is_ghost: false,
        properties: {
          reference_count: element.reference_count,
          predicted_count: element.predicted_count,
          matched_count: element.matched_count,
          formula: element.formula,
        },
      },
    });
  };

  const handleIsolateInPoset = () => {
    setCycleHighlightNodeIds([element.id, element.parentAxiomId || ""].filter(Boolean));
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-app-bg text-app-text select-none font-sans">
      {/* 44px Rail Header */}
      <div className="h-11 px-4 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className={`type-mono text-xs font-semibold ${meta.color}`}>
            {element.symbol}
          </span>
          <span className="type-caption font-semibold uppercase tracking-wider text-app-muted">
            {meta.label}
          </span>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors cursor-pointer"
          title="Deselect node"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Node Identity Bar */}
      <div className="p-4 border-b border-app-border bg-app-surface/30 shrink-0 space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="type-mono text-[11px] text-app-muted">ID: {element.id}</span>
          {isMasked ? (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-app-muted">
              <span className="w-1.5 h-1.5 rounded-full border border-app-muted shrink-0" />
              Cascade Masked
            </span>
          ) : isOmission ? (
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-rose-500">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0" />
              Root Omission
            </span>
          ) : isPass ? (
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Pass
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-600 dark:text-amber-400">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
              Partial
            </span>
          )}
        </div>

        <h3 className="type-h2 text-sm font-semibold text-app-heading leading-snug">
          {element.name}
        </h3>

        {/* Tabular Metadata Strip */}
        <div className="flex items-center gap-2.5 text-[11px] type-mono tabular-nums pt-1 text-app-muted">
          <span>Ref: <strong className="text-app-heading font-semibold">{element.reference_count}</strong></span>
          <span className="text-app-border">·</span>
          <span>Pred: <strong className="text-app-heading font-semibold">{element.predicted_count}</strong></span>
          <span className="text-app-border">·</span>
          <span>Match: <strong className="text-app-heading font-semibold">{element.matched_count}</strong></span>
          <span className="text-app-border">·</span>
          <span>Coverage: <strong className={`font-semibold ${element.coverage >= 0.85 ? "text-emerald-500" : element.coverage > 0 ? "text-amber-500" : "text-rose-500"}`}>{(element.coverage * 100).toFixed(0)}%</strong></span>
        </div>
      </div>

      {/* Body: Typographic Flow (design.md §1: No Box-in-Box) */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 text-xs">
        {/* Cascade Callout Strip */}
        {isMasked && (
          <div className="border-l-2 border-amber-500 pl-3 py-1 space-y-0.5 text-app-muted bg-amber-500/5 pr-2 rounded-r">
            <div className="flex items-center gap-1.5 font-semibold text-xs text-amber-600 dark:text-amber-400">
              <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
              <span>Bourbaki Cascade Mask Active</span>
            </div>
            <p className="type-body text-[11px] leading-relaxed">
              Foundational axiom <strong className="text-app-heading">{parentElement ? parentElement.name : element.parentAxiomId}</strong> failed extraction. Downstream loss is masked to prevent compounded penalties.
            </p>
          </div>
        )}

        {isOmission && (
          <div className="border-l-2 border-rose-500 pl-3 py-1 space-y-0.5 text-app-muted bg-rose-500/5 pr-2 rounded-r">
            <div className="flex items-center gap-1.5 font-semibold text-xs text-rose-500">
              <AlertOctagon className="w-3.5 h-3.5 shrink-0" />
              <span>Root Cause Omission Detected</span>
            </div>
            <p className="type-body text-[11px] leading-relaxed">
              Axiom missing in extraction, breaking the structural spine and causing downstream cascade masking.
            </p>
          </div>
        )}

        {/* Section 1: Mathematical Formulation */}
        <div className="space-y-1.5">
          <span className="type-caption uppercase font-semibold text-app-muted block tracking-wider">
            Mathematical Formulation
          </span>
          {element.formula ? (
            <div className="type-mono text-xs text-blue-600 dark:text-blue-400 p-2.5 rounded bg-app-surface border border-app-border overflow-x-auto">
              <code>{element.formula}</code>
            </div>
          ) : (
            <p className="type-caption text-app-muted italic">
              No symbolic equation bound to this structural element.
            </p>
          )}

          {element.rationale && (
            <p className="type-body text-[11px] text-app-muted leading-relaxed pt-1">
              <strong className="text-app-heading font-medium">Rationale: </strong>
              {element.rationale}
            </p>
          )}
        </div>

        {/* Section 2: Poset Specialization Dependencies */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="type-caption uppercase font-semibold text-app-muted block tracking-wider">
              Poset Specialization Dependencies
            </span>
            <span className="type-mono text-[10px] text-purple-500 font-semibold">
              Rank Level {element.topologicalRank ?? (element.parentAxiomId ? 1 : 0)}
            </span>
          </div>

          {/* Upstream Axiom */}
          <div className="space-y-1">
            <span className="type-caption text-[10px] text-app-muted block">Upstream Axiom:</span>
            {parentElement ? (
              <div
                onClick={() => onSelectElement(parentElement)}
                className="flex items-center justify-between py-1.5 px-2 rounded bg-app-surface/60 hover:bg-app-subtle border border-app-border transition-colors cursor-pointer text-xs group"
              >
                <div className="flex items-center gap-2 truncate">
                  <Link2 className="w-3 h-3 text-blue-500 shrink-0" />
                  <span className="type-mono text-[10px] font-semibold text-blue-500">{parentElement.symbol}</span>
                  <span className="truncate text-app-heading font-medium">{parentElement.name}</span>
                </div>
                <span className="type-caption text-blue-500 font-medium group-hover:translate-x-0.5 transition-transform shrink-0">
                  Jump →
                </span>
              </div>
            ) : (
              <p className="type-caption text-app-muted italic pl-1">
                Root Axiom: Foundational Premise (no upstream parents).
              </p>
            )}
          </div>

          {/* Downstream Dependents */}
          <div className="space-y-1 pt-1">
            <span className="type-caption text-[10px] text-app-muted block">
              Downstream Dependent Models ({childElements.length}):
            </span>
            {childElements.length > 0 ? (
              <div className="space-y-1">
                {childElements.map((child) => (
                  <div
                    key={child.id}
                    onClick={() => onSelectElement(child)}
                    className="flex items-center justify-between py-1.5 px-2 rounded bg-app-surface/60 hover:bg-app-subtle border border-app-border transition-colors cursor-pointer text-xs group"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <GitBranch className="w-3 h-3 text-purple-400 shrink-0" />
                      <span className="type-mono text-[10px] font-semibold text-purple-400">{child.symbol}</span>
                      <span className="truncate text-app-heading font-medium">{child.name}</span>
                    </div>
                    <span className="type-caption text-purple-500 font-medium group-hover:translate-x-0.5 transition-transform shrink-0">
                      Jump →
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="type-caption text-app-muted italic pl-1">
                Leaf Node: Intended application paradigm with no downstream derivations.
              </p>
            )}
          </div>
        </div>

        {/* Section 3: Inferential Polarity */}
        <div className="space-y-1.5">
          <span className="type-caption uppercase font-semibold text-app-muted block tracking-wider">
            Inferential Polarity Concordance
          </span>

          {element.inferentialPolarity ? (
            <div className="space-y-1.5 p-2.5 rounded bg-app-surface border border-app-border">
              <div className="flex items-center justify-between text-xs">
                <span className="type-caption text-app-muted">Target Relation:</span>
                <span className="type-mono font-medium text-app-heading">{element.inferentialPolarity.targetNode}</span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className="type-caption text-app-muted">Predicted:</span>
                <span className="type-mono font-semibold text-app-heading">{element.inferentialPolarity.predicate}</span>
                <span className="text-app-muted">≠</span>
                <span className="type-caption text-app-muted">Gold:</span>
                <span className="type-mono font-semibold text-app-heading">{element.inferentialPolarity.goldPredicate}</span>
                <span className="text-app-border">·</span>
                <span className="type-mono text-rose-500 text-[10px] font-semibold">Critical Inversion</span>
              </div>
              <p className="type-body text-[11px] text-app-muted leading-relaxed">
                {element.inferentialPolarity.dialecticalNote}
              </p>
            </div>
          ) : (
            <p className="type-body text-[11px] text-app-muted">
              Deductive entailment conformant with theory net schema. No inverted polarity detected.
            </p>
          )}
        </div>

        {/* Section 4: Primary Corpus Grounding Quote */}
        {element.quote && (
          <div className="space-y-1">
            <span className="type-caption uppercase font-semibold text-app-muted block tracking-wider">
              Primary Corpus Grounding
            </span>
            <blockquote className="italic text-xs text-app-text leading-relaxed bg-app-surface/60 p-2.5 rounded border-l-2 border-amber-500 font-serif">
              &ldquo;{element.quote}&rdquo;
            </blockquote>
            {element.citation && (
              <span className="type-caption text-[10px] text-app-muted block text-right">
                — {element.citation}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Footer Actions */}
      <div className="p-3 border-t border-app-border bg-app-surface/60 shrink-0 flex items-center justify-between gap-2 text-xs">
        <button
          type="button"
          onClick={handleInspectOnCanvas}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer"
        >
          <Network className="w-3.5 h-3.5" />
          <span>Canvas View</span>
        </button>

        <button
          type="button"
          onClick={handleIsolateInPoset}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded font-medium bg-app-surface hover:bg-app-subtle text-app-text border border-app-border transition-colors cursor-pointer"
        >
          <Workflow className="w-3.5 h-3.5 text-purple-400" />
          <span>Isolate Chain</span>
        </button>
      </div>
    </div>
  );
};
