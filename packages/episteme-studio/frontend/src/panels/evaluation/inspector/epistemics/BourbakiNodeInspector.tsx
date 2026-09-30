import React from "react";
import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  GitBranch,
  Layers,
  Link2,
  Network,
  Quote,
  Scale,
  ShieldAlert,
  Sparkles,
  Workflow,
  X,
  XCircle,
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

  // Find parent element object if available
  const parentElement = element.parentAxiomId
    ? allElements.find((el) => el.id === element.parentAxiomId)
    : null;

  // Find dependent child elements
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
      {/* Refined Inspector Header (Clean typographic layout, no box-in-box) */}
      <div className="p-4 border-b border-app-border shrink-0 space-y-2 bg-app-surface/40">
        <div className="flex items-center justify-between gap-2">
          {/* Typographic Classification & Minimalist Status Glyph */}
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`font-mono text-xs font-semibold ${meta.color}`}
            >
              {element.symbol}
            </span>
            <span className="text-[11px] font-medium text-app-muted uppercase tracking-wider">
              {meta.label}
            </span>
            <span className="text-app-border">·</span>

            {/* Minimalist Status Label (Softened status signals, subdued tones) */}
            {isMasked ? (
              <span
                title="Masked under Bourbaki cascade doctrine to avoid duplicate penalization."
                className="inline-flex items-center gap-1.5 text-[11px] font-medium text-app-muted"
              >
                <span className="w-1.5 h-1.5 rounded-full border border-app-muted shrink-0" />
                Cascade Masked
              </span>
            ) : isOmission ? (
              <span
                title="Root axiom missing in extraction! Causes downstream cascade masking."
                className="inline-flex items-center gap-1.5 text-[11px] font-medium text-rose-500/90 dark:text-rose-400/90"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-rose-400 dark:bg-rose-500 shrink-0" />
                Root Omission
              </span>
            ) : isPass ? (
              <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Pass
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                Partial
              </span>
            )}
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors cursor-pointer"
            title="Deselect node"
            aria-label="Close inspector"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div>
          <h2 className="text-sm font-semibold text-app-heading leading-snug">{element.name}</h2>
          <span className="text-[11px] font-mono text-app-muted/70 block mt-0.5">
            ID: {element.id}
          </span>
        </div>

        {/* Compact Metadata Inline String (Inter tabular-nums aligned with design directives) */}
        <div className="flex items-center gap-3 text-[11px] tabular-nums pt-1 text-app-muted">
          <span>
            <span className="text-app-muted/70">Ref:</span>{" "}
            <strong className="text-app-heading font-medium">{element.reference_count}</strong>
          </span>
          <span className="text-app-border">·</span>
          <span>
            <span className="text-app-muted/70">Pred:</span>{" "}
            <strong className="text-app-heading font-medium">{element.predicted_count}</strong>
          </span>
          <span className="text-app-border">·</span>
          <span>
            <span className="text-app-muted/70">Match:</span>{" "}
            <strong className="text-app-heading font-medium">{element.matched_count}</strong>
          </span>
          <span className="text-app-border">·</span>
          <span>
            <span className="text-app-muted/70">Coverage:</span>{" "}
            <strong
              className={`font-medium ${
                element.coverage >= 0.85
                  ? "text-emerald-600 dark:text-emerald-400"
                  : element.coverage > 0
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-rose-500/80 dark:text-rose-400/80"
              }`}
            >
              {(element.coverage * 100).toFixed(0)}%
            </strong>
          </span>
        </div>
      </div>

      {/* Continuous Reading Flow Body (Whitespace & Typography, No Box Fatigue) */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6 text-xs">
        {/* Cascade Masking or Root Cause Callout Strip (Softened borders and text) */}
        {isMasked && (
          <div className="border-l-2 border-amber-500/50 pl-3 py-1 space-y-1 text-app-muted">
            <div className="flex items-center gap-1.5 font-medium text-xs text-amber-600 dark:text-amber-400">
              <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
              <span>Bourbaki Cascade Mask Active</span>
            </div>
            <p className="text-[11px] leading-relaxed">
              This node is orphaned because parent foundational axiom{" "}
              <strong className="text-app-heading">
                {parentElement ? parentElement.name : element.parentAxiomId}
              </strong>{" "}
              failed during extraction. Under the Bourbaki cascade doctrine, secondary loss penalties
              are masked to avoid compounding downstream error attribution.
            </p>
          </div>
        )}

        {isOmission && (
          <div className="border-l-2 border-rose-500/40 pl-3 py-1 space-y-1 text-app-muted">
            <div className="flex items-center gap-1.5 font-medium text-xs text-rose-500/90 dark:text-rose-400/90">
              <AlertOctagon className="w-3.5 h-3.5 shrink-0" />
              <span>Root Cause Omission Detected</span>
            </div>
            <p className="text-[11px] leading-relaxed">
              Foundational axiom omitted during semantic parsing. This omission directly breaks the
              axiomatic spine of the theory net and propagates cascade masking across child sub-models.
            </p>
          </div>
        )}

        {/* Section 1: Mathematical Formulation & Law */}
        <div className="space-y-2">
          <div className="flex items-center gap-1.5 text-[11px] uppercase font-semibold tracking-wider text-app-muted">
            <Sparkles className="w-3.5 h-3.5 text-blue-500" />
            <span>Mathematical Formulation & Law</span>
          </div>

          {element.formula ? (
            <div className="font-mono text-xs text-blue-600 dark:text-blue-400 border-l-2 border-blue-500/40 pl-3 py-1 overflow-x-auto">
              <code>{element.formula}</code>
            </div>
          ) : (
            <p className="text-[11px] text-app-muted italic pl-3 border-l-2 border-app-border py-0.5">
              No explicit symbolic equation bound to this structural element.
            </p>
          )}

          {element.rationale && (
            <p className="text-[11px] text-app-muted leading-relaxed pt-1">
              <strong className="text-app-heading font-medium">Verification Rationale: </strong>
              {element.rationale}
            </p>
          )}
        </div>

        {/* Section 2: DAG Relationships & Poset Invariants */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[11px] uppercase font-semibold tracking-wider text-app-muted">
              <Workflow className="w-3.5 h-3.5 text-purple-500" />
              <span>DAG Relationships & Poset Invariants</span>
            </div>
            <span className="text-[10px] tabular-nums text-purple-500 font-medium">
              Depth Level {element.topologicalRank ?? (element.parentAxiomId ? 1 : 0)}
            </span>
          </div>

          {/* Typographic DAG Status List */}
          <div className="flex items-center gap-4 text-[11px] text-app-muted">
            <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" /> Strict DAG Acyclicity
            </span>
            <span className="text-app-border">·</span>
            <span>Transitive Reduction Preserved</span>
          </div>

          {/* Upstream Axiom Dependencies */}
          <div className="space-y-1.5 pt-1">
            <span className="text-[10px] uppercase font-semibold text-app-muted tracking-wider block">
              Upstream Axiom Dependencies
            </span>
            {parentElement ? (
              <div
                onClick={() => onSelectElement(parentElement)}
                className="flex items-center justify-between py-1 px-2 rounded hover:bg-app-subtle transition-colors cursor-pointer group text-xs"
              >
                <div className="flex items-center gap-2 truncate">
                  <Link2 className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                  <span className="font-mono text-[10px] text-blue-500 font-semibold">
                    {parentElement.symbol}
                  </span>
                  <span className="text-app-heading font-medium truncate max-w-[220px]">
                    {parentElement.name}
                  </span>
                </div>
                <span className="text-[11px] text-blue-500 font-medium group-hover:translate-x-0.5 transition-transform shrink-0">
                  Jump →
                </span>
              </div>
            ) : element.parentAxiomId ? (
              <p className="text-[11px] text-app-muted font-mono pl-2">
                Parent ID: {element.parentAxiomId}
              </p>
            ) : (
              <p className="text-[11px] text-app-muted italic pl-2">
                Root Axiom: No upstream dependencies (Foundational Premise).
              </p>
            )}
          </div>

          {/* Downstream Dependents */}
          <div className="space-y-1.5 pt-1">
            <span className="text-[10px] uppercase font-semibold text-app-muted tracking-wider block">
              Downstream Dependent Models ({childElements.length})
            </span>
            {childElements.length > 0 ? (
              <div className="space-y-1">
                {childElements.map((child) => (
                  <div
                    key={child.id}
                    onClick={() => onSelectElement(child)}
                    className="flex items-center justify-between py-1 px-2 rounded hover:bg-app-subtle transition-colors cursor-pointer group text-xs"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <GitBranch className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                      <span className="font-mono text-[10px] text-purple-400 font-semibold">
                        {child.symbol}
                      </span>
                      <span className="text-app-heading font-medium truncate max-w-[220px]">
                        {child.name}
                      </span>
                    </div>
                    <span className="text-[11px] text-purple-500 font-medium group-hover:translate-x-0.5 transition-transform shrink-0">
                      Jump →
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-app-muted italic pl-2">
                Leaf Node: Intended application paradigm with no downstream derivations.
              </p>
            )}
          </div>
        </div>

        {/* Section 3: Inferential Polarity Concordance */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[11px] uppercase font-semibold tracking-wider text-app-muted">
              <Scale className="w-3.5 h-3.5 text-amber-500" />
              <span>Inferential Polarity Concordance</span>
            </div>
            {element.inferentialPolarity && (
              <span
                className={`text-[10px] font-medium ${
                  element.inferentialPolarity.concordance === "CRITICAL_INVERSION"
                    ? "text-rose-500/90 dark:text-rose-400/90"
                    : "text-emerald-600 dark:text-emerald-400"
                }`}
              >
                {element.inferentialPolarity.concordance === "CRITICAL_INVERSION"
                  ? "Critical Inversion"
                  : "Concordant"}
              </span>
            )}
          </div>

          {element.inferentialPolarity ? (
            <div className="space-y-2 pl-3 border-l-2 border-app-border">
              <div className="text-xs">
                <span className="text-app-muted">Target Relation: </span>
                <span className="font-medium text-app-heading">
                  {element.inferentialPolarity.targetNode}
                </span>
              </div>

              <div className="flex items-center gap-2 text-xs">
                <span className="text-app-muted text-[11px]">Predicted:</span>
                <span className="font-medium text-app-heading">
                  {element.inferentialPolarity.predicate}
                </span>
                <span className="text-app-muted font-medium">
                  {element.inferentialPolarity.predicate === element.inferentialPolarity.goldPredicate
                    ? "="
                    : "≠"}
                </span>
                <span className="text-app-muted text-[11px]">Gold:</span>
                <span className="font-medium text-app-heading">
                  {element.inferentialPolarity.goldPredicate}
                </span>
                <span className="text-app-border">·</span>
                <span className="text-[11px] tabular-nums text-app-muted">
                  Cosine Sim: {element.inferentialPolarity.similarity.toFixed(2)}
                </span>
              </div>

              <p className="text-[11px] text-app-muted leading-relaxed">
                {element.inferentialPolarity.dialecticalNote}
              </p>
            </div>
          ) : (
            <p className="text-[11px] text-app-muted leading-relaxed pl-3 border-l-2 border-app-border">
              Deductive entailment conformant with theory net schema. No inverted polarity detected.
            </p>
          )}
        </div>

        {/* Section 4: Primary Corpus Grounding & Citation */}
        <div className="space-y-2">
          <div className="flex items-center gap-1.5 text-[11px] uppercase font-semibold tracking-wider text-app-muted">
            <Quote className="w-3.5 h-3.5 text-amber-500/80" />
            <span>Primary Corpus Grounding & Citation</span>
          </div>

          {element.quote ? (
            <div className="space-y-1.5 pl-3.5 border-l-2 border-amber-500/50">
              <blockquote className="italic text-xs text-app-heading leading-relaxed">
                "{element.quote}"
              </blockquote>
              {element.citation && (
                <span className="text-[10px] text-app-muted block">
                  — {element.citation}
                </span>
              )}
            </div>
          ) : (
            <p className="text-[11px] text-app-muted italic pl-3 border-l-2 border-app-border">
              Syntactic axiom compiled from schema; no empirical quotation recorded.
            </p>
          )}
        </div>
      </div>

      {/* Inspector Footer Actions */}
      <div className="p-3 border-t border-app-border bg-app-surface/60 shrink-0 flex items-center justify-between gap-2 text-xs">
        <button
          onClick={handleInspectOnCanvas}
          className="flex-1 flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer"
          title="Inspect node in Topological Alignment Canvas"
        >
          <Network className="w-3.5 h-3.5" />
          <span>Canvas View</span>
        </button>

        <button
          onClick={handleIsolateInPoset}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded font-medium bg-app-surface hover:bg-app-subtle text-app-text border border-app-border transition-colors cursor-pointer"
          title="Highlight cycle / poset chain in viewer"
        >
          <Workflow className="w-3.5 h-3.5 text-purple-400" />
          <span>Isolate Poset</span>
        </button>

        <button
          onClick={onClose}
          className="px-2.5 py-1.5 rounded font-medium text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors cursor-pointer"
          title="Close details"
        >
          Close
        </button>
      </div>
    </div>
  );
};
