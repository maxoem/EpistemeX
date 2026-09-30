import React, { useState, useMemo } from "react";
import { Sliders, Sparkles, AlertCircle, CheckCircle2, TrendingUp } from "lucide-react";

export interface ThresholdOptimizerBarProps {
  baselinePrecision?: number;
  baselineRecall?: number;
  totalTriples?: number;
  onApplyThreshold?: (threshold: number) => void;
}

export const ThresholdOptimizerBar: React.FC<ThresholdOptimizerBarProps> = ({
  baselinePrecision = 0.88,
  baselineRecall = 0.85,
  totalTriples = 340,
  onApplyThreshold,
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
    const discardedValidCount = Math.round((discardedValidPercent / 100) * totalTriples * baselineRecall);

    const filteredHallucinationsPercent = Math.min(
      95,
      Math.max(10, (shift * 75) + 15)
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

  return (
    <div className="p-3.5 bg-app-surface border border-app-border rounded-lg select-none shrink-0 space-y-3">
      {/* Header and Presets */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="p-1 rounded bg-blue-500/10 text-blue-500">
            <Sliders className="w-3.5 h-3.5" />
          </div>
          <div>
            <h4 className="text-xs font-semibold text-app-heading">
              Interactive Confidence Threshold Optimizer (τ)
            </h4>
            <p className="text-[11px] text-app-muted">
              Project trade-offs between precision, recall, and discarded triples
            </p>
          </div>
        </div>

        {/* Preset Buttons */}
        <div className="flex items-center gap-1.5 text-[11px]">
          <span className="text-app-muted font-sans mr-1 hidden md:inline">Presets:</span>
          <button
            onClick={() => setThreshold(0.65)}
            className={`px-2 py-0.5 rounded border transition-colors ${
              threshold === 0.65
                ? "bg-blue-600 text-white border-blue-600 font-semibold"
                : "bg-app-bg text-app-muted hover:text-app-text border-app-border"
            }`}
          >
            High Recall (0.65)
          </button>
          <button
            onClick={() => setThreshold(0.82)}
            className={`px-2 py-0.5 rounded border transition-colors ${
              threshold === 0.82
                ? "bg-blue-600 text-white border-blue-600 font-semibold"
                : "bg-app-bg text-app-muted hover:text-app-text border-app-border"
            }`}
          >
            Balanced F₁ (0.82)
          </button>
          <button
            onClick={() => setThreshold(0.92)}
            className={`px-2 py-0.5 rounded border transition-colors ${
              threshold === 0.92
                ? "bg-blue-600 text-white border-blue-600 font-semibold"
                : "bg-app-bg text-app-muted hover:text-app-text border-app-border"
            }`}
          >
            High Precision (0.92)
          </button>
        </div>
      </div>

      {/* Slider Control */}
      <div className="space-y-1.5 pt-1">
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-app-muted font-sans text-[11px]">Extraction Threshold:</span>
          <span className="font-semibold text-blue-500 tabular-nums bg-blue-500/10 px-2 py-0.5 rounded">
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
          className="w-full precision-slider"
        />

        <div className="relative h-4 text-[10px] font-mono text-app-muted">
          <span className="absolute left-0">0.50 (Permissive)</span>
          <span className="absolute -translate-x-1/2" style={{ left: "51.0%" }}>0.75</span>
          <span className="absolute -translate-x-1/2" style={{ left: "71.4%" }}>0.85</span>
          <span className="absolute right-0">0.99 (Ultra-Conservative)</span>
        </div>
      </div>

      {/* Projected Metrics Readout */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 pt-1">
        <div className="p-2 rounded bg-app-bg border border-app-border">
          <span className="text-[10px] text-app-muted uppercase font-sans block">
            Projected Precision
          </span>
          <div className="flex items-baseline justify-between mt-1">
            <span className="font-mono text-xs font-semibold tabular-nums text-app-text">
              {projections.precision.toFixed(1)}%
            </span>
            <span className={`text-[10px] font-mono ${projections.precision >= baselinePrecision * 100 ? "text-emerald-500" : "text-rose-500"}`}>
              ({projections.precision >= baselinePrecision * 100 ? "+" : ""}
              {(projections.precision - baselinePrecision * 100).toFixed(1)}%)
            </span>
          </div>
        </div>

        <div className="p-2 rounded bg-app-bg border border-app-border">
          <span className="text-[10px] text-app-muted uppercase font-sans block">
            Projected Recall
          </span>
          <div className="flex items-baseline justify-between mt-1">
            <span className="font-mono text-xs font-semibold tabular-nums text-app-text">
              {projections.recall.toFixed(1)}%
            </span>
            <span className={`text-[10px] font-mono ${projections.recall >= baselineRecall * 100 ? "text-emerald-500" : "text-amber-500"}`}>
              ({projections.recall >= baselineRecall * 100 ? "+" : ""}
              {(projections.recall - baselineRecall * 100).toFixed(1)}%)
            </span>
          </div>
        </div>

        <div className="p-2 rounded bg-app-bg border border-app-border">
          <span className="text-[10px] text-app-muted uppercase font-sans block">
            Projected Macro F₁
          </span>
          <div className="flex items-baseline justify-between mt-1">
            <span className="font-mono text-xs font-semibold tabular-nums text-app-text">
              {(projections.f1 / 100).toFixed(3)}
            </span>
            <span className="text-[10px] font-mono text-emerald-500">Optimal</span>
          </div>
        </div>

        <div className="p-2 rounded bg-app-bg border border-app-border">
          <span className="text-[10px] text-app-muted uppercase font-sans block">
            Discarded Valid Triples
          </span>
          <div className="flex items-baseline justify-between mt-1">
            <span className="font-mono text-xs font-semibold tabular-nums text-amber-500">
              {projections.discardedValidCount} ({projections.discardedValidPercent.toFixed(1)}%)
            </span>
          </div>
        </div>

        <div className="p-2 rounded bg-app-bg border border-app-border col-span-2 sm:col-span-1 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-app-muted uppercase font-sans block">
              Filtered Errors
            </span>
            <span className="font-mono text-xs font-semibold tabular-nums text-emerald-500">
              ~{projections.filteredHallucinationsPercent.toFixed(0)}%
            </span>
          </div>
          {onApplyThreshold && (
            <button
              onClick={() => onApplyThreshold(threshold)}
              className="px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-medium transition-colors cursor-pointer"
            >
              Apply τ
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
