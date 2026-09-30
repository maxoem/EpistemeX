import React, { useState, useMemo } from "react";
import { Sliders, Sparkles, Check, ArrowRight } from "lucide-react";

export interface ThresholdOptimizerBarProps {
  baselinePrecision?: number;
  baselineRecall?: number;
  totalTriples?: number;
  onApplyThreshold?: (threshold: number) => void;
  className?: string;
}

/**
 * Interactive Confidence Threshold Optimizer (τ).
 *
 * Implements mathematical trade-off projections between precision, recall,
 * and filtered extraction candidates. Conforms to design.md §10 (Scientific
 * Structural Telemetry Tables rather than generic SaaS metric cards).
 */
export const ThresholdOptimizerBar: React.FC<ThresholdOptimizerBarProps> = ({
  baselinePrecision = 0.88,
  baselineRecall = 0.85,
  totalTriples = 340,
  onApplyThreshold,
  className = "",
}) => {
  const [threshold, setThreshold] = useState<number>(0.82);

  // Dynamic projection mathematical model
  const projections = useMemo(() => {
    const shift = (threshold - 0.5) / 0.49; // 0.0 to 1.0

    // Higher threshold -> higher precision, lower recall
    const precision = Math.min(
      0.995,
      Math.max(0.6, baselinePrecision + (1.0 - baselinePrecision) * shift * 0.45)
    );
    const recall = Math.max(
      0.35,
      Math.min(0.99, baselineRecall - baselineRecall * shift * 0.3)
    );
    const f1 = (2 * precision * recall) / (precision + recall);

    // Filtered out stats
    const discardedValidPercent = Math.max(0, (1 - recall / baselineRecall) * 100);
    const discardedValidCount = Math.round(
      (discardedValidPercent / 100) * totalTriples * baselineRecall
    );

    const filteredHallucinationsPercent = Math.min(
      95,
      Math.max(10, shift * 75 + 15)
    );

    return {
      precision: precision * 100,
      recall: recall * 100,
      f1: f1 * 100,
      discardedValidPercent,
      discardedValidCount,
      filteredHallucinationsPercent,
    };
  }, [threshold, baselinePrecision, baselineRecall, totalTriples]);

  const presets = [
    { label: "Recall (0.65)", value: 0.65 },
    { label: "Balanced (0.82)", value: 0.82 },
    { label: "Precision (0.92)", value: 0.92 },
  ];

  return (
    <div className={`space-y-3 font-sans select-none ${className}`}>
      {/* Header & Preset Track */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <Sliders className="w-3.5 h-3.5 text-blue-500 shrink-0" />
          <h4 className="type-caption font-semibold text-app-heading uppercase tracking-wider">
            Threshold Optimizer (τ)
          </h4>
        </div>

        {/* Segmented Pill Track (design.md Segmented Control) */}
        <div className="flex items-center gap-0.5 bg-app-bg p-0.5 rounded border border-app-border text-[10px]">
          {presets.map((p) => (
            <button
              key={p.value}
              type="button"
              onClick={() => setThreshold(p.value)}
              className={`px-1.5 py-0.5 rounded transition-colors cursor-pointer ${
                Math.abs(threshold - p.value) < 0.005
                  ? "bg-app-surface text-app-heading font-medium border border-app-border/80"
                  : "text-app-muted hover:text-app-text"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Slider & Value Display */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="type-caption text-app-muted">Cutoff Parameter:</span>
          <span className="type-mono font-semibold tabular-nums text-blue-500 bg-blue-500/10 px-2 py-0.5 rounded">
            τ = {threshold.toFixed(2)}
          </span>
        </div>

        <input
          type="range"
          min={0.5}
          max={0.99}
          step={0.01}
          value={threshold}
          onChange={(e) => setThreshold(parseFloat(e.target.value))}
          className="w-full precision-slider cursor-pointer accent-blue-600"
        />

        <div className="flex items-center justify-between text-[10px] type-mono text-app-muted px-0.5">
          <span>0.50 (Permissive)</span>
          <span>0.75</span>
          <span>0.85</span>
          <span>0.99 (Strict)</span>
        </div>
      </div>

      {/* Scientific Structural Telemetry Table (design.md §10) */}
      <div className="rounded border border-app-border bg-app-bg overflow-hidden text-xs">
        <div className="px-3 py-1.5 bg-app-surface border-b border-app-border flex items-center justify-between text-[10px] text-app-muted uppercase font-semibold tracking-wider">
          <span>Projected Epistemic Invariants</span>
          <span className="type-mono">N={totalTriples}</span>
        </div>

        <div className="divide-y divide-app-border font-sans">
          {/* Row 1: Projected Precision */}
          <div className="px-3 py-1.5 flex items-center justify-between">
            <span className="type-caption text-app-muted">Projected Precision</span>
            <div className="flex items-center gap-1.5">
              <span className="type-mono font-semibold tabular-nums text-app-heading">
                {projections.precision.toFixed(1)}%
              </span>
              <span
                className={`text-[10px] type-mono tabular-nums ${
                  projections.precision >= baselinePrecision * 100
                    ? "text-emerald-500"
                    : "text-rose-500"
                }`}
              >
                ({projections.precision >= baselinePrecision * 100 ? "+" : ""}
                {(projections.precision - baselinePrecision * 100).toFixed(1)}%)
              </span>
            </div>
          </div>

          {/* Row 2: Projected Recall */}
          <div className="px-3 py-1.5 flex items-center justify-between">
            <span className="type-caption text-app-muted">Projected Recall</span>
            <div className="flex items-center gap-1.5">
              <span className="type-mono font-semibold tabular-nums text-app-heading">
                {projections.recall.toFixed(1)}%
              </span>
              <span
                className={`text-[10px] type-mono tabular-nums ${
                  projections.recall >= baselineRecall * 100
                    ? "text-emerald-500"
                    : "text-amber-500"
                }`}
              >
                ({projections.recall >= baselineRecall * 100 ? "+" : ""}
                {(projections.recall - baselineRecall * 100).toFixed(1)}%)
              </span>
            </div>
          </div>

          {/* Row 3: Macro F1 */}
          <div className="px-3 py-1.5 flex items-center justify-between">
            <span className="type-caption text-app-muted">Projected Macro F₁</span>
            <span className="type-mono font-semibold tabular-nums text-blue-500">
              {(projections.f1 / 100).toFixed(3)}
            </span>
          </div>

          {/* Row 4: Discarded Valid Triples */}
          <div className="px-3 py-1.5 flex items-center justify-between">
            <span className="type-caption text-app-muted">Discarded Valid Triples</span>
            <span className="type-mono tabular-nums text-amber-500">
              {projections.discardedValidCount} ({projections.discardedValidPercent.toFixed(1)}%)
            </span>
          </div>

          {/* Row 5: Filtered Errors */}
          <div className="px-3 py-1.5 flex items-center justify-between">
            <span className="type-caption text-app-muted">Filtered Errors</span>
            <span className="type-mono font-semibold tabular-nums text-emerald-500">
              ~{projections.filteredHallucinationsPercent.toFixed(0)}%
            </span>
          </div>
        </div>
      </div>

      {/* Apply Action */}
      {onApplyThreshold && (
        <button
          type="button"
          onClick={() => onApplyThreshold(threshold)}
          className="w-full py-1.5 px-3 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer flex items-center justify-center gap-1.5"
        >
          <span>Apply Threshold (τ = {threshold.toFixed(2)}) to Pipeline</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
};
