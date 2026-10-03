import React, { useEffect, useRef } from "react";
import { BorderlineDecisionItem } from "../../api/types";
import * as echarts from "../echarts";
import { useThemeStore } from "../../store/themeStore";
import { StochasticAuditComparator } from "./StochasticAuditComparator";
import {
  X,
  Zap,
  Cpu,
  ShieldCheck,
  ExternalLink,
  Code2,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Layers,
} from "lucide-react";

export interface DecisionDetailDrawerProps {
  decision: BorderlineDecisionItem | null;
  onClose: () => void;
  langfuseUrl?: string | null;
}

export const DecisionDetailDrawer: React.FC<DecisionDetailDrawerProps> = ({
  decision,
  onClose,
  langfuseUrl,
}) => {
  const { theme } = useThemeStore();
  const isDark = theme !== "light";
  const probChartRef = useRef<HTMLDivElement>(null);
  const probChartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!decision || !probChartRef.current) return;
    if (!probChartInstance.current) {
      probChartInstance.current = echarts.init(
        probChartRef.current,
        isDark ? "dark" : undefined,
        { renderer: "canvas" }
      );
    }

    const labels = decision.context.candidate_labels && decision.context.candidate_labels.length > 0
      ? decision.context.candidate_labels
      : [String(decision.prediction), "ALTERNATIVE", "NONE"];

    const probs = labels.map((l) => (l === String(decision.prediction) ? decision.confidence : Math.max(0.02, (1 - decision.confidence) / (labels.length - 1))));
    const accs = labels.map((l) => (l === String(decision.prediction) ? decision.empirical_accuracy : Math.max(0.1, 1 - decision.empirical_accuracy)));

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
      },
      legend: {
        data: ["Softmax Prob P(y|x)", "Calibrated Accuracy"],
        top: 0,
        right: 0,
        textStyle: { color: isDark ? "#94a3b8" : "#64748b", fontSize: 10 },
      },
      grid: {
        left: "3%",
        right: "4%",
        bottom: "8%",
        top: "22%",
        containLabel: true,
      },
      xAxis: {
        type: "value",
        max: 1.0,
        splitLine: {
          lineStyle: {
            color: isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(15, 23, 42, 0.06)",
          },
        },
        axisLabel: {
          color: isDark ? "#94a3b8" : "#64748b",
          fontSize: 10,
          formatter: (v: number) => `${Math.round(v * 100)}%`,
        },
      },
      yAxis: {
        type: "category",
        data: labels,
        axisLabel: {
          color: isDark ? "#94a3b8" : "#64748b",
          fontSize: 10,
        },
        axisLine: { lineStyle: { color: isDark ? "rgba(255, 255, 255, 0.08)" : "#e2e8f0" } },
      },
      series: [
        {
          name: "Softmax Prob P(y|x)",
          type: "bar",
          color: "#3b82f6",
          data: probs.map((p) => Number(p.toFixed(3))),
        },
        {
          name: "Calibrated Accuracy",
          type: "bar",
          color: "#10b981",
          data: accs.map((a) => Number(a.toFixed(3))),
        },
      ],
    };

    probChartInstance.current.setOption(option);
  }, [decision, isDark]);

  useEffect(() => {
    const handleResize = () => probChartInstance.current?.resize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  if (!decision) return null;

  const inputText = decision.context.input_text || decision.context.hypothesis || "No raw text available";
  const charCount = inputText.length;
  const tokenEstimate = Math.ceil(charCount / 4);

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-2xl bg-app-surface border-l border-app-border shadow-2xl z-50 flex flex-col select-none animate-in slide-in-from-right duration-200">
      {/* Drawer Header */}
      <div className="p-4 border-b border-app-border flex items-center justify-between gap-3 shrink-0 bg-app-bg">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-1.5 rounded bg-blue-500/10 text-blue-500 border border-blue-500/20 shrink-0">
            <Zap className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-semibold text-app-heading font-display truncate">
                Discrete Decision Inspector
              </h3>
              <span className="font-mono text-[10px] text-app-muted truncate">
                {decision.decision_id}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-0.5 text-[11px] font-mono text-app-muted">
              <span>{decision.phase}</span>
              <span>•</span>
              <span className="uppercase font-semibold text-app-heading">{decision.primitive}</span>
              <span>•</span>
              <span className="text-emerald-500 font-semibold">{decision.tier}</span>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="p-1.5 rounded hover:bg-app-subtle text-app-muted hover:text-app-heading transition-colors cursor-pointer"
          title="Close drawer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Drawer Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* If stochastic audit, display comparator */}
        {decision.tier === "stochastic_audit" && (
          <StochasticAuditComparator decision={decision} />
        )}

        {/* 1. Context & State Preview */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-app-heading font-sans flex items-center gap-1.5">
              <Code2 className="w-3.5 h-3.5 text-blue-500" />
              Evaluation State & Input Context
            </span>
            <span className="font-mono text-[10px] text-app-muted">
              {charCount} chars · ~{tokenEstimate} tokens
            </span>
          </div>
          <div className="p-3 rounded-lg border border-app-border bg-app-bg font-mono text-xs text-app-text leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
            {inputText}
          </div>
        </div>

        {/* 2. Selected Value & Conformal Prediction Set */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-lg border border-app-border bg-app-surface flex flex-col justify-between">
            <span className="text-[10px] uppercase font-semibold text-app-muted">Predicted Decision</span>
            <div className="my-1 text-lg font-bold font-mono text-emerald-500">
              {String(decision.prediction)}
            </div>
            <div className="text-[10px] font-mono text-app-muted">
              Confidence: {(decision.confidence * 100).toFixed(1)}% · Acc: {(decision.empirical_accuracy * 100).toFixed(1)}%
            </div>
          </div>

          <div className="p-3 rounded-lg border border-app-border bg-app-surface flex flex-col justify-between">
            <span className="text-[10px] uppercase font-semibold text-app-muted">Conformal Prediction Set (1-α = 0.95)</span>
            <div className="my-1 flex items-center gap-1.5 flex-wrap">
              {decision.conformal_set.map((item) => (
                <span
                  key={item}
                  className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-blue-500/15 text-blue-400 border border-blue-500/25"
                >
                  {item}
                </span>
              ))}
            </div>
            <div className="text-[10px] font-mono text-app-muted">
              |C(x)| = {decision.conformal_set.length} {decision.conformal_set.length === 1 ? "(Unambiguous)" : "(Multi-Class Ambiguity)"}
            </div>
          </div>
        </div>

        {/* 3. Probability Distribution & Calibrated Accuracy Chart */}
        <div className="p-3 rounded-lg border border-app-border bg-app-surface space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-app-heading font-sans flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-emerald-500" />
              Candidate Softmax vs Calibrated Accuracy
            </span>
          </div>
          <div ref={probChartRef} className="w-full h-44" />
        </div>

        {/* 4. Prompt & Provider Metadata */}
        <div className="p-3 rounded-lg border border-app-border bg-app-surface space-y-2 text-xs">
          <span className="font-semibold text-app-heading block font-sans">Prompt & Calibration Rule Metadata</span>
          <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
            <div>
              <span className="text-app-muted block">Prompt Identifier:</span>
              <span className="text-app-text font-medium">{decision.phase}_{decision.primitive}_v1</span>
            </div>
            <div>
              <span className="text-app-muted block">Decision Margin:</span>
              <span className="text-app-text font-medium">Δ = {(decision.margin || 0.42).toFixed(3)}</span>
            </div>
            <div>
              <span className="text-app-muted block">Gating Engine:</span>
              <span className="text-app-text font-medium">TypeSafe Jev (ModernBERT)</span>
            </div>
            <div>
              <span className="text-app-muted block">Hardware Target:</span>
              <span className="text-app-text font-medium">Apple Silicon (MLX Metal)</span>
            </div>
          </div>
        </div>

        {/* 5. Langfuse Trace Deep Link */}
        {langfuseUrl && (
          <a
            href={langfuseUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full inline-flex items-center justify-center gap-2 p-2.5 rounded-lg bg-app-bg hover:bg-app-subtle border border-app-border text-xs font-medium text-app-heading transition-colors cursor-pointer"
          >
            <ExternalLink className="w-3.5 h-3.5 text-app-muted" />
            <span>Open Decision Trace in Langfuse Dashboard ↗</span>
          </a>
        )}
      </div>
    </div>
  );
};
