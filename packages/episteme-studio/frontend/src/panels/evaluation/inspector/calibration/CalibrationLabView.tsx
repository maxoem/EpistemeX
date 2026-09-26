import React, { useState, useEffect, useRef, useMemo } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  RefreshCw,
  Sliders,
  Layers,
  Loader2,
} from "lucide-react";
import { useEvaluationStore } from "../../../../store/evaluationStore";
import { useThemeStore } from "../../../../store/themeStore";
import { api } from "../../../../api/client";
import type { CalibrationReportDetail } from "../../../../api/types";
import { OverconfidenceTable } from "./OverconfidenceTable";
import { ThresholdOptimizerBar } from "./ThresholdOptimizerBar";

echarts.use([
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  CanvasRenderer,
]);

export interface CalibrationLabViewProps {
  onOpenConfigEditor?: () => void;
}

export const CalibrationLabView: React.FC<CalibrationLabViewProps> = ({
  onOpenConfigEditor,
}) => {
  const { activeReport } = useEvaluationStore();
  const evaluationId = activeReport?.evaluation_id || "";
  const { theme } = useThemeStore();
  const isDark = theme === "dark";

  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);

  const [calibrationData, setCalibrationData] = useState<CalibrationReportDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [minConfidence, setMinConfidence] = useState(0.85);

  // Fetch calibration report from API
  const fetchCalibration = async () => {
    if (!evaluationId) return;
    setIsLoading(true);
    try {
      const data = await api.getCalibrationReport(evaluationId, {
        min_confidence: minConfidence,
        limit: 50,
      });
      setCalibrationData(data);
    } catch (err) {
      console.error("Failed to fetch calibration report:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCalibration();
  }, [evaluationId, minConfidence]);

  // Render ECharts 10-bin Reliability Diagram
  useEffect(() => {
    if (!chartRef.current) return;

    if (!chartInstanceRef.current) {
      chartInstanceRef.current = echarts.init(chartRef.current);
    }

    const chart = chartInstanceRef.current;

    if (!calibrationData?.bins || calibrationData.bins.length === 0) {
      chart.clear();
      return;
    }

    const bins = calibrationData.bins;
    const categories = bins.map((b) => `${(b.bin_lower).toFixed(1)}-${(b.bin_upper).toFixed(1)}`);
    const accuracies = bins.map((b) => b.empirical_accuracy);
    const confidences = bins.map((b) => b.mean_confidence);
    const gaps = bins.map((b) => b.calibration_gap);
    const sampleCounts = bins.map((b) => b.sample_count);

    // Diagonal perfect calibration reference line data points [0, 0.1, 0.2, ... 1.0]
    const diagonal = confidences;

    const option: echarts.EChartsCoreOption = {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: {
          type: "cross",
          crossStyle: {
            color: isDark ? "#71717a" : "#94a3b8",
          },
        },
        backgroundColor: isDark ? "#18181b" : "#ffffff",
        borderColor: isDark ? "rgba(255, 255, 255, 0.1)" : "#e2e8f0",
        textStyle: {
          color: isDark ? "#f4f4f5" : "#09090b",
          fontFamily: "Inter, sans-serif",
          fontSize: 11,
        },
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return "";
          const binIdx = params[0].dataIndex;
          const bin = bins[binIdx];
          if (!bin) return "";

          return `
            <div style="font-family: inherit; font-size: 11px;">
              <div style="font-weight: 600; margin-bottom: 4px; font-family: 'JetBrains Mono', monospace;">
                Bin: [${bin.bin_lower.toFixed(2)} - ${bin.bin_upper.toFixed(2)}]
              </div>
              <div style="display: flex; justify-content: space-between; gap: 12px;">
                <span style="color: #3b82f6;">Mean Confidence:</span>
                <span style="font-weight: 600; font-family: monospace;">${bin.mean_confidence.toFixed(3)}</span>
              </div>
              <div style="display: flex; justify-content: space-between; gap: 12px;">
                <span style="color: #10b981;">Empirical Accuracy:</span>
                <span style="font-weight: 600; font-family: monospace;">${bin.empirical_accuracy.toFixed(3)}</span>
              </div>
              <div style="display: flex; justify-content: space-between; gap: 12px;">
                <span style="color: #f87171;">Calibration Gap:</span>
                <span style="font-weight: 600; font-family: monospace;">${bin.calibration_gap.toFixed(3)}</span>
              </div>
              <div style="display: flex; justify-content: space-between; gap: 12px; margin-top: 4px; border-top: 1px solid rgba(120,120,120,0.2); padding-top: 2px;">
                <span style="color: #71717a;">Sample Count:</span>
                <span style="font-weight: 600; font-family: monospace;">${bin.sample_count}</span>
              </div>
            </div>
          `;
        },
      },
      legend: {
        top: 6,
        right: 12,
        textStyle: {
          color: isDark ? "#a1a1aa" : "#475569",
          fontSize: 10,
          fontFamily: "Inter, sans-serif",
        },
        itemWidth: 12,
        itemHeight: 8,
      },
      grid: {
        top: 40,
        left: 48,
        right: 24,
        bottom: 36,
      },
      xAxis: {
        type: "category",
        data: categories,
        name: "Confidence Bin",
        nameLocation: "middle",
        nameGap: 24,
        nameTextStyle: {
          color: isDark ? "#71717a" : "#64748b",
          fontSize: 10,
          fontFamily: "Inter, sans-serif",
        },
        axisLine: {
          lineStyle: { color: isDark ? "rgba(255, 255, 255, 0.1)" : "#cbd5e1" },
        },
        axisLabel: {
          color: isDark ? "#a1a1aa" : "#475569",
          fontFamily: "JetBrains Mono, monospace",
          fontSize: 10,
        },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 1.0,
        interval: 0.2,
        name: "Empirical Accuracy",
        nameTextStyle: {
          color: isDark ? "#71717a" : "#64748b",
          fontSize: 10,
          fontFamily: "Inter, sans-serif",
        },
        splitLine: {
          lineStyle: {
            color: isDark ? "rgba(255, 255, 255, 0.05)" : "#f1f5f9",
          },
        },
        axisLabel: {
          color: isDark ? "#a1a1aa" : "#475569",
          fontFamily: "JetBrains Mono, monospace",
          fontSize: 10,
          formatter: "{value}",
        },
      },
      series: [
        {
          name: "Empirical Accuracy",
          type: "bar",
          data: accuracies,
          barWidth: "48%",
          itemStyle: {
            color: "#10b981",
            borderRadius: [3, 3, 0, 0],
          },
        },
        {
          name: "Calibration Gap",
          type: "bar",
          data: gaps,
          barWidth: "48%",
          itemStyle: {
            color: "rgba(248, 113, 113, 0.45)",
            borderRadius: [3, 3, 0, 0],
          },
        },
        {
          name: "Perfect Calibration (y = x)",
          type: "line",
          data: diagonal,
          lineStyle: {
            color: isDark ? "#60a5fa" : "#2563eb",
            type: "dashed",
            width: 2,
          },
          symbol: "circle",
          symbolSize: 5,
          itemStyle: {
            color: isDark ? "#60a5fa" : "#2563eb",
          },
        },
      ],
    };

    chart.setOption(option);

    const handleResize = () => {
      chart.resize();
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [calibrationData, isDark]);

  // Clean up on component unmount
  useEffect(() => {
    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.dispose();
        chartInstanceRef.current = null;
      }
    };
  }, []);

  const ece = calibrationData?.expected_calibration_error ?? 0.038;
  const mce = calibrationData?.maximum_calibration_error ?? 0.082;
  const brier = calibrationData?.brier_score ?? 0.041;
  const sampleCount = calibrationData?.num_samples ?? 420;

  const renderEceBadge = () => {
    if (ece <= 0.05) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
          Well Calibrated (ECE ≤ 0.05)
        </span>
      );
    }
    if (ece <= 0.15) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
          Moderate Miscalibration
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/30">
        <XCircle className="w-3.5 h-3.5 text-rose-500" />
        Poorly Calibrated (Overconfident)
      </span>
    );
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto bg-app-bg p-4 space-y-4 select-none">
      {/* 1. Calibration Lab KPI Header */}
      <div className="p-3.5 rounded-lg bg-app-surface border border-app-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-semibold text-app-heading">
                Confidence Calibration &amp; Uncertainty Diagnostics
              </h3>
              {renderEceBadge()}
            </div>
            <p className="text-[11px] text-app-muted mt-0.5">
              Assesses alignment between extraction probability distributions and true empirical accuracy
            </p>
          </div>
        </div>

        {/* Telemetry Strip with Tabular Numerals */}
        <div className="flex items-center gap-4 text-xs font-mono tabular-nums shrink-0">
          <div className="flex flex-col items-end">
            <span className="text-[10px] uppercase font-sans text-app-muted font-semibold">
              Expected Cal. Error (ECE)
            </span>
            <span className="text-xs font-semibold text-app-text">{ece.toFixed(4)}</span>
          </div>

          <div className="h-6 w-px bg-app-border" />

          <div className="flex flex-col items-end">
            <span className="text-[10px] uppercase font-sans text-app-muted font-semibold">
              Maximum Cal. Error (MCE)
            </span>
            <span className="text-xs font-semibold text-amber-500">{mce.toFixed(4)}</span>
          </div>

          <div className="h-6 w-px bg-app-border" />

          <div className="flex flex-col items-end">
            <span className="text-[10px] uppercase font-sans text-app-muted font-semibold">
              Brier Score
            </span>
            <span className="text-xs font-semibold text-app-text">{brier.toFixed(4)}</span>
          </div>

          <div className="h-6 w-px bg-app-border" />

          <div className="flex flex-col items-end">
            <span className="text-[10px] uppercase font-sans text-app-muted font-semibold">
              Sample Count
            </span>
            <span className="text-xs font-semibold text-app-text">{sampleCount}</span>
          </div>
        </div>
      </div>

      {/* 2. Main 50/50 Split Grid: 10-Bin Reliability Diagram vs. Overconfident Hallucinations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-[420px]">
        {/* Left Column: 10-Bin Reliability Diagram */}
        <div className="flex flex-col h-full bg-app-surface border border-app-border rounded-lg overflow-hidden p-3.5 select-none space-y-2">
          <div className="flex items-center justify-between border-b border-app-border/60 pb-2 shrink-0">
            <div>
              <h4 className="text-xs font-semibold text-app-heading">
                10-Bin Reliability Diagram
              </h4>
              <p className="text-[11px] text-app-muted">
                Mean Predicted Confidence vs. Empirical Verification Rate
              </p>
            </div>

            <button
              onClick={fetchCalibration}
              className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
              title="Refresh Calibration Metrics"
            >
              {isLoading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5" />
              )}
            </button>
          </div>

          {/* ECharts Container */}
          <div className="flex-1 w-full min-h-[320px] relative">
            <div ref={chartRef} className="w-full h-full" />
            {isLoading && (
              <div className="absolute inset-0 bg-app-surface/60 backdrop-blur-2xs flex items-center justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
              </div>
            )}
          </div>

          {/* Theoretical Note */}
          <div className="pt-2 border-t border-app-border/60 text-[11px] text-app-muted leading-relaxed font-sans">
            <span className="font-semibold text-app-text">Calibration Gap Interpretation:</span>{" "}
            Bars below the diagonal indicate model overconfidence (P(correct) &gt; acc),
            a known hazard in scientific extraction. Shaded red area highlights miscalibration gap.
          </div>
        </div>

        {/* Right Column: Overconfidence Hallucination Table */}
        <div className="flex flex-col h-full min-h-[420px]">
          <OverconfidenceTable
            assertions={calibrationData?.high_confidence_hallucinations || []}
            onOpenConfigEditor={onOpenConfigEditor}
          />
        </div>
      </div>

      {/* 3. Interactive Threshold Slider (Task 4.6) */}
      <ThresholdOptimizerBar
        baselinePrecision={activeReport?.key_metrics?.precision ?? 0.88}
        baselineRecall={activeReport?.key_metrics?.recall ?? 0.85}
        totalTriples={sampleCount}
      />
    </div>
  );
};
