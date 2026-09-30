import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
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
  RefreshCw,
  Loader2,
  Search,
  PanelRightClose,
  Sliders,
} from "lucide-react";
import { useEvaluationStore } from "../../../../store/evaluationStore";
import { useThemeStore } from "../../../../store/themeStore";
import { api } from "../../../../api/client";
import type { CalibrationReportDetail } from "../../../../api/types";
import { OverconfidenceTable } from "./OverconfidenceTable";
import { CalibrationDiagnosticRail } from "./CalibrationDiagnosticRail";
import { ResizablePanel } from "../../../ResizablePanel";

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

/**
 * Sub-View 3.4: Confidence Calibration & Reliability Lab.
 *
 * Implements the Persistent Three-Rail Scientific Cockpit (design.md §Layout):
 * - Fixed 44px Contextual Action Bar with operational state and invariant telemetry
 * - Fluid Center Stage: Top 10-Bin Reliability Diagram vitrine + Bottom Linear Data Grid
 * - Right Diagnostic Rail (380px resizable): Threshold Optimizer (τ) + Assertion failure context
 */
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
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedAssertionId, setSelectedAssertionId] = useState<string | null>(null);

  // Right Rail Collapsed State
  const [isRightRailCollapsed, setIsRightRailCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem("episteme-calibration-rail-collapsed") === "true";
    } catch {
      return false;
    }
  });

  const toggleRightRail = useCallback(() => {
    setIsRightRailCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("episteme-calibration-rail-collapsed", String(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  // Fetch calibration report from API
  const fetchCalibration = useCallback(async () => {
    if (!evaluationId) {
      setCalibrationData(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getCalibrationReport(evaluationId, {
        min_confidence: 0.85,
        limit: 50,
      });
      setCalibrationData(data);
      if (data?.high_confidence_hallucinations?.length) {
        setSelectedAssertionId(data.high_confidence_hallucinations[0].assertion_id);
      }
    } catch (err) {
      console.error("Failed to fetch calibration report:", err);
      setError("Failed to load calibration report. Verify the evaluation run exists and has samples.");
      setCalibrationData(null);
    } finally {
      setIsLoading(false);
    }
  }, [evaluationId]);

  useEffect(() => {
    fetchCalibration();
  }, [fetchCalibration]);

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
    const categories = bins.map((b) => `${b.bin_lower.toFixed(1)}-${b.bin_upper.toFixed(1)}`);
    const accuracies = bins.map((b) => b.empirical_accuracy);
    const confidences = bins.map((b) => b.mean_confidence);
    const gaps = bins.map((b) => b.calibration_gap);
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
        top: 4,
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
        top: 28,
        left: 42,
        right: 20,
        bottom: 24,
      },
      xAxis: {
        type: "category",
        data: categories,
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
          barWidth: "44%",
          itemStyle: {
            color: "#10b981",
            borderRadius: [2, 2, 0, 0],
          },
        },
        {
          name: "Calibration Gap",
          type: "bar",
          data: gaps,
          barWidth: "44%",
          itemStyle: {
            color: "rgba(248, 113, 113, 0.45)",
            borderRadius: [2, 2, 0, 0],
          },
        },
        {
          name: "Perfect Calibration (y = x)",
          type: "line",
          data: diagonal,
          lineStyle: {
            color: isDark ? "#60a5fa" : "#2563eb",
            type: "dashed",
            width: 1.5,
          },
          symbol: "circle",
          symbolSize: 4,
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

  useEffect(() => {
    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.dispose();
        chartInstanceRef.current = null;
      }
    };
  }, []);

  const hasData = calibrationData != null;
  const ece = calibrationData?.expected_calibration_error ?? null;
  const mce = calibrationData?.maximum_calibration_error ?? null;
  const brier = calibrationData?.brier_score ?? null;
  const sampleCount = calibrationData?.num_samples ?? null;
  const isWellCalibrated = calibrationData?.is_well_calibrated ?? false;

  const formatMetric = (value: number | null, digits = 4) =>
    value == null ? "—" : value.toFixed(digits);

  const selectedAssertion = useMemo(() => {
    if (!calibrationData?.high_confidence_hallucinations) return null;
    return (
      calibrationData.high_confidence_hallucinations.find(
        (a) => a.assertion_id === selectedAssertionId
      ) ||
      calibrationData.high_confidence_hallucinations[0] ||
      null
    );
  }, [calibrationData?.high_confidence_hallucinations, selectedAssertionId]);

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-hidden bg-app-bg text-app-text select-none font-sans">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 1. Contextual Action Bar (44px, docked edge-to-edge border-b)       */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="h-11 px-4 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs gap-3">
        {/* Left: Breadcrumbs & Operational State */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-blue-500 shrink-0" />
            <h2 className="type-caption font-semibold text-app-heading uppercase tracking-wider">
              Confidence Calibration &amp; Uncertainty Lab
            </h2>
          </div>

          {/* Operational State Badge */}
          {hasData &&
            (isWellCalibrated ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                Well Calibrated
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                Miscalibrated
              </span>
            ))}

          {/* Sample count pill */}
          <span className="text-[11px] type-mono text-app-muted border border-app-border px-1.5 py-0.5 rounded bg-app-bg">
            {calibrationData?.high_confidence_hallucinations?.length ?? 0} Flagged
          </span>
        </div>

        {/* Center: Search Filter */}
        <div className="hidden md:flex items-center max-w-xs w-full relative">
          <Search className="w-3.5 h-3.5 text-app-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter assertions or predicates..."
            className="w-full pl-8 pr-2.5 py-1 text-xs rounded bg-app-bg border border-app-border focus:border-blue-500 focus:outline-hidden text-app-text placeholder-app-muted"
          />
        </div>

        {/* Right: Key Telemetry Strip & Toggles */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="hidden lg:flex items-center gap-2.5 text-xs">
            <div className="flex items-center gap-1">
              <span className="type-caption text-app-muted">ECE:</span>
              <span className="type-mono font-semibold tabular-nums text-app-text">
                {formatMetric(ece)}
              </span>
            </div>
            <span className="text-app-border">·</span>
            <div className="flex items-center gap-1">
              <span className="type-caption text-app-muted">MCE:</span>
              <span className="type-mono font-semibold tabular-nums text-app-text">
                {formatMetric(mce)}
              </span>
            </div>
            <span className="text-app-border">·</span>
            <div className="flex items-center gap-1">
              <span className="type-caption text-app-muted">Brier:</span>
              <span className="type-mono font-semibold tabular-nums text-app-text">
                {formatMetric(brier)}
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={fetchCalibration}
            className="p-1.5 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors cursor-pointer"
            title="Refresh Calibration Metrics"
          >
            {isLoading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5" />
            )}
          </button>

          <button
            type="button"
            onClick={toggleRightRail}
            className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs border transition-colors cursor-pointer ${
              isRightRailCollapsed
                ? "bg-blue-500/10 border-blue-500/30 text-blue-500 hover:bg-blue-500/20"
                : "bg-app-bg border-app-border text-app-muted hover:text-app-text hover:bg-app-subtle"
            }`}
            title={isRightRailCollapsed ? "Expand Diagnostic Rail" : "Collapse Diagnostic Rail"}
          >
            <PanelRightClose className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">
              {isRightRailCollapsed ? "Diagnostic Rail" : "Collapse"}
            </span>
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 2. Workspace: Fluid Center Stage + Right Diagnostic Rail            */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden">
        {/* Center Stage: Split between Reliability Diagram & Assertion Table */}
        <div className="flex-1 flex flex-col h-full overflow-hidden min-w-0">
          {/* Top Stage Vitrine: 10-Bin Reliability Diagram (220px fixed) */}
          <div className="h-[220px] border-b border-app-border bg-app-surface/30 shrink-0 flex flex-col overflow-hidden">
            {/* Diagram Micro-Bar */}
            <div className="h-7 px-4 border-b border-app-border/60 bg-app-surface/50 flex items-center justify-between text-[11px] text-app-muted">
              <span className="font-semibold text-app-heading">
                10-Bin Empirical Reliability Diagram
              </span>
              <span className="type-caption">
                Bars below diagonal indicate model overconfidence (P(correct) &gt; acc)
              </span>
            </div>

            {/* ECharts Area */}
            <div className="flex-1 w-full h-full relative">
              <div ref={chartRef} className="w-full h-full" />
              {!isLoading && error && (
                <div className="absolute inset-0 bg-app-surface/60 flex items-center justify-center p-4">
                  <p className="type-caption text-app-muted text-center">{error}</p>
                </div>
              )}
              {!isLoading && !error && !hasData && (
                <div className="absolute inset-0 bg-app-surface/60 flex items-center justify-center p-4">
                  <p className="type-caption text-app-muted text-center">
                    No calibration data available for this evaluation run.
                  </p>
                </div>
              )}
              {isLoading && (
                <div className="absolute inset-0 bg-app-surface/60 backdrop-blur-2xs flex items-center justify-center">
                  <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                </div>
              )}
            </div>
          </div>

          {/* Bottom Stage: Linear Data Grid for Overconfident Assertions */}
          <div className="flex-1 overflow-hidden min-h-0">
            <OverconfidenceTable
              assertions={calibrationData?.high_confidence_hallucinations || []}
              selectedId={selectedAssertionId}
              onSelectId={(id) => {
                setSelectedAssertionId(id);
                if (isRightRailCollapsed) setIsRightRailCollapsed(false);
              }}
              searchQuery={searchQuery}
            />
          </div>
        </div>

        {/* Right Diagnostic Rail (Cursor Resizable, 420px default) */}
        <ResizablePanel
          side="right"
          storageKey="episteme-calibration-rail-width"
          defaultWidth={420}
          minWidth={340}
          maxWidth={640}
          collapsible={true}
          collapseThreshold={140}
          collapsed={isRightRailCollapsed}
          onToggleCollapse={toggleRightRail}
          className="!border-l !border-app-border flex flex-col h-full bg-app-surface"
        >
          <CalibrationDiagnosticRail
            selectedAssertion={selectedAssertion}
            baselinePrecision={activeReport?.key_metrics?.precision ?? 0.88}
            baselineRecall={activeReport?.key_metrics?.recall ?? 0.85}
            totalTriples={sampleCount ?? undefined}
            onOpenConfigEditor={onOpenConfigEditor}
            onClose={() => setIsRightRailCollapsed(true)}
          />
        </ResizablePanel>
      </div>
    </div>
  );
};
