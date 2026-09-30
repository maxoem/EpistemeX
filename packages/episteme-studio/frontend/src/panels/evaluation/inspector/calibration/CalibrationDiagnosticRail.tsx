import React from "react";
import { AlertTriangle, ShieldAlert, Sparkles, X, Sliders } from "lucide-react";
import type { MiscalibratedAssertionItem } from "../../../../api/types";
import { ActionableHookPill } from "../../components/ActionableHookPill";
import { ThresholdOptimizerBar } from "./ThresholdOptimizerBar";

export interface CalibrationDiagnosticRailProps {
  selectedAssertion: MiscalibratedAssertionItem | null;
  baselinePrecision?: number;
  baselineRecall?: number;
  totalTriples?: number;
  onApplyThreshold?: (threshold: number) => void;
  onOpenConfigEditor?: () => void;
  onClose?: () => void;
}

/**
 * Right Diagnostic Rail for Confidence Calibration & Uncertainty Lab.
 *
 * Implements the persistent analytical rail doctrine (design.md §Layout & §10):
 * - Selected Hallucination Diagnostic with text grounding and failure rationale
 * - High-Density Threshold Optimizer (τ) with projected structural graph invariants
 */
export const CalibrationDiagnosticRail: React.FC<CalibrationDiagnosticRailProps> = ({
  selectedAssertion,
  baselinePrecision,
  baselineRecall,
  totalTriples,
  onApplyThreshold,
  onOpenConfigEditor,
  onClose,
}) => {
  return (
    <div className="flex flex-col h-full overflow-hidden bg-app-bg text-app-text select-none font-sans">
      {/* Rail Header (44px Action Bar alignment) */}
      <div className="h-11 px-4 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <Sliders className="w-3.5 h-3.5 text-blue-500" />
          <h3 className="font-semibold text-app-heading type-caption uppercase tracking-wider">
            Calibration Inspector
          </h3>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors cursor-pointer"
            title="Close Diagnostic Rail"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Rail Body */}
      <div className="flex-1 overflow-y-auto divide-y divide-app-border text-xs">
        {/* Section 1: Selected Assertion Diagnostic */}
        <div className="p-4 space-y-3.5">
          <div className="flex items-center justify-between">
            <span className="type-caption font-semibold uppercase tracking-wider text-app-muted">
              Selected Assertion Diagnostic
            </span>
            {selectedAssertion && (
              <span className="type-mono text-xs font-semibold text-rose-500">
                Discrepancy: +{selectedAssertion.discrepancy.toFixed(2)}
              </span>
            )}
          </div>

          {selectedAssertion ? (
            <div className="space-y-3">
              {/* Assertion Descriptor */}
              <div>
                <span className="type-caption text-[10px] text-app-muted uppercase font-semibold block mb-1">
                  Extraction Descriptor ({selectedAssertion.assertion_type})
                </span>
                <div className="p-2.5 rounded bg-app-surface border border-app-border type-mono text-xs text-app-heading break-words">
                  {selectedAssertion.descriptor}
                </div>
              </div>

              {/* Confidence Readout */}
              <div className="flex items-center justify-between text-xs py-1 px-2 rounded bg-app-subtle/30 border border-app-border">
                <span className="type-caption text-app-muted">Model Confidence:</span>
                <span className="type-mono font-semibold tabular-nums text-rose-500">
                  {(selectedAssertion.confidence * 100).toFixed(1)}% (Overconfident FP)
                </span>
              </div>

              {/* Source Context Quotation */}
              {selectedAssertion.evidence_text ? (
                <div className="space-y-1">
                  <span className="type-caption text-[10px] text-app-muted uppercase font-semibold block">
                    Source Text Grounding:
                  </span>
                  <blockquote className="text-xs text-app-text italic bg-app-surface/60 p-2.5 rounded border-l-2 border-blue-500 font-serif leading-relaxed">
                    &ldquo;{selectedAssertion.evidence_text}&rdquo;
                  </blockquote>
                </div>
              ) : null}

              {/* Failure Mode Rationale */}
              {selectedAssertion.rationale ? (
                <div className="space-y-1">
                  <span className="type-caption text-[10px] text-app-muted uppercase font-semibold block">
                    Failure Mode Rationale:
                  </span>
                  <div className="text-xs text-rose-600 dark:text-rose-400 bg-rose-500/10 p-2.5 rounded border-l-2 border-rose-500 leading-relaxed font-sans">
                    {selectedAssertion.rationale}
                  </div>
                </div>
              ) : null}

              {/* Actionable Hook to Engine Config */}
              <div className="pt-1 flex justify-end">
                <ActionableHookPill
                  type="overconfidence"
                  sourceText={selectedAssertion.evidence_text || selectedAssertion.descriptor}
                  assertionId={selectedAssertion.assertion_id}
                  phaseKey="phase2"
                  onClick={onOpenConfigEditor}
                />
              </div>
            </div>
          ) : (
            <div className="py-8 text-center text-app-muted space-y-1.5">
              <ShieldAlert className="w-6 h-6 opacity-30 mx-auto" />
              <p className="type-body text-xs">No assertion selected.</p>
              <p className="type-caption text-[11px] text-app-muted/70">
                Click any row in the table to inspect failure context.
              </p>
            </div>
          )}
        </div>

        {/* Section 2: Threshold Optimizer Bar */}
        <div className="p-4 bg-app-surface/20">
          <ThresholdOptimizerBar
            baselinePrecision={baselinePrecision}
            baselineRecall={baselineRecall}
            totalTriples={totalTriples}
            onApplyThreshold={onApplyThreshold}
          />
        </div>
      </div>
    </div>
  );
};
