import React, { useEffect, useRef, useMemo } from "react";
import * as echarts from "echarts/core";
import {
  ScatterChart,
  LineChart,
} from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useLeaderboardStore } from "../../../store/leaderboardStore";
import { useThemeStore } from "../../../store/themeStore";
import type { LeaderboardEntry } from "../../../api/types";

echarts.use([
  ScatterChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  CanvasRenderer,
]);

interface ParetoFrontierPlotProps {
  className?: string;
  onSelectRun?: (runId: string) => void;
}

export const ParetoFrontierPlot: React.FC<ParetoFrontierPlotProps> = ({
  className = "",
  onSelectRun,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);

  const { theme } = useThemeStore();
  const {
    entries,
    xAxis,
    yAxis,
    setXAxis,
    setYAxis,
    selectedRunIdA,
    selectedRunIdB,
    toggleRunForDiff,
  } = useLeaderboardStore();

  const isDark = theme === "dark";

  // Helper to extract metric values
  const getXValue = (entry: LeaderboardEntry, axis: string): number => {
    switch (axis) {
      case "cost":
        return entry.total_cost_usd ?? entry.metrics.cost ?? 0.05;
      case "duration":
        return entry.duration_seconds ?? entry.metrics.duration ?? 2.5;
      case "ece":
        return entry.metrics.ece ?? 0.04;
      case "tokens":
        return entry.metrics.tokens ?? 1200;
      default:
        return entry.metrics[axis] ?? 0;
    }
  };

  const getYValue = (entry: LeaderboardEntry, axis: string): number => {
    switch (axis) {
      case "f1":
        return entry.metrics.f1 ?? entry.metrics.macro_f1 ?? 0.85;
      case "delta_star":
        return entry.metrics.delta_star ?? entry.metrics.tenability ?? 0.88;
      case "mrr":
        return entry.metrics.mrr ?? 0.82;
      case "polarity":
        return entry.metrics.polarity_accuracy ?? 0.94;
      default:
        return entry.metrics[axis] ?? 0;
    }
  };

  const getAxisLabel = (axis: string): string => {
    switch (axis) {
      case "cost":
        return "Inference Cost ($ USD)";
      case "duration":
        return "Latency / Duration (s)";
      case "ece":
        return "Expected Calibration Error (ECE)";
      case "tokens":
        return "Total Prompt Tokens";
      case "f1":
        return "Macro F₁ Score";
      case "delta_star":
        return "Bourbaki Tenability (δ*)";
      case "mrr":
        return "Retrieval MRR";
      case "polarity":
        return "Polarity Accuracy";
      default:
        return axis;
    }
  };

  // Compute Pareto non-dominated frontier points
  const { paretoPoints, dominatedPoints, frontierStepLine } = useMemo(() => {
    const pPoints: Array<{ entry: LeaderboardEntry; x: number; y: number }> = [];
    const dPoints: Array<{ entry: LeaderboardEntry; x: number; y: number }> = [];

    entries.forEach((e) => {
      const x = getXValue(e, xAxis);
      const y = getYValue(e, yAxis);
      if (e.is_pareto_optimal) {
        pPoints.push({ entry: e, x, y });
      } else {
        dPoints.push({ entry: e, x, y });
      }
    });

    // Sort pareto points by X ascending to construct step-line
    const sortedPareto = [...pPoints].sort((a, b) => a.x - b.x);
    const stepLine: [number, number][] = sortedPareto.map((p) => [p.x, p.y]);

    return {
      paretoPoints: pPoints,
      dominatedPoints: dPoints,
      frontierStepLine: stepLine,
    };
  }, [entries, xAxis, yAxis]);

  // Initialize and update ECharts
  useEffect(() => {
    if (!chartRef.current) return;

    if (!chartInstanceRef.current) {
      chartInstanceRef.current = echarts.init(chartRef.current);

      chartInstanceRef.current.on("click", (params: any) => {
        if (params.data && params.data.entry) {
          const runId = params.data.entry.run_id;
          toggleRunForDiff(runId);
          onSelectRun?.(runId);
        }
      });
    }

    const chart = chartInstanceRef.current;

    const textColor = isDark ? "#A1A1AA" : "#64748B";
    const gridLineColor = isDark ? "rgba(255, 255, 255, 0.06)" : "rgba(0, 0, 0, 0.06)";
    const tooltipBg = isDark ? "#18181B" : "#FFFFFF";
    const tooltipBorder = isDark ? "rgba(255, 255, 255, 0.12)" : "#E2E8F0";

    const option: echarts.EChartsCoreOption = {
      backgroundColor: "transparent",
      animationDuration: 400,
      grid: {
        left: 55,
        right: 30,
        top: 25,
        bottom: 45,
      },
      tooltip: {
        trigger: "item",
        backgroundColor: tooltipBg,
        borderColor: tooltipBorder,
        borderWidth: 1,
        padding: [8, 12],
        textStyle: {
          color: isDark ? "#F4F4F5" : "#0F172A",
          fontSize: 11,
          fontFamily: "Inter, sans-serif",
        },
        formatter: (params: any) => {
          if (!params.data || !params.data.entry) return "";
          const entry: LeaderboardEntry = params.data.entry;
          const isPareto = entry.is_pareto_optimal;
          const isSelectedA = selectedRunIdA === entry.run_id;
          const isSelectedB = selectedRunIdB === entry.run_id;

          return `
            <div style="font-family: Inter, sans-serif;">
              <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 4px;">
                <span style="font-weight: 600; font-size: 12px; color: ${isDark ? "#FFFFFF" : "#09090B"};">
                  ${entry.model_name || entry.run_id}
                </span>
                <span style="font-size: 10px; font-family: monospace; padding: 1px 4px; border-radius: 3px; background: ${
                  isPareto ? "rgba(59, 130, 246, 0.15)" : "rgba(113, 113, 122, 0.15)"
                }; color: ${isPareto ? "#3B82F6" : "#A1A1AA"}; font-weight: 600;">
                  ${isPareto ? "PARETO OPTIMAL" : "DOMINATED"}
                </span>
              </div>
              <div style="font-family: monospace; font-size: 10px; color: #94A3B8; margin-bottom: 6px;">
                run_id: ${entry.run_id}
              </div>
              <div style="display: grid; grid-template-columns: auto auto; gap: 3px 12px; font-size: 11px; margin-bottom: 4px;">
                <span style="color: ${textColor};">${getAxisLabel(xAxis)}:</span>
                <span style="font-family: monospace; font-weight: 600; text-align: right;">${params.data.value[0]}</span>
                <span style="color: ${textColor};">${getAxisLabel(yAxis)}:</span>
                <span style="font-family: monospace; font-weight: 600; text-align: right;">${params.data.value[1]}</span>
                <span style="color: ${textColor};">Prompt:</span>
                <span style="font-size: 10px; text-align: right;">${entry.prompt_strategy || "default"}</span>
              </div>
              ${
                isSelectedA || isSelectedB
                  ? `<div style="margin-top: 4px; padding-top: 4px; border-top: 1px solid ${gridLineColor}; font-size: 10px; color: #3B82F6; font-weight: 500;">
                      ✓ Selected for Pairwise Diff (${isSelectedA ? "Run A" : "Run B"})
                    </div>`
                  : `<div style="margin-top: 4px; font-size: 10px; color: ${textColor}; font-style: italic;">
                      Click to select for pairwise diff
                    </div>`
              }
            </div>
          `;
        },
      },
      xAxis: {
        type: "value",
        name: getAxisLabel(xAxis),
        nameLocation: "middle",
        nameGap: 28,
        nameTextStyle: {
          color: textColor,
          fontSize: 10,
          fontWeight: 500,
        },
        splitLine: {
          lineStyle: {
            color: gridLineColor,
            type: "dashed",
          },
        },
        axisLabel: {
          color: textColor,
          fontSize: 10,
          fontFamily: "monospace",
        },
        axisLine: {
          lineStyle: {
            color: gridLineColor,
          },
        },
      },
      yAxis: {
        type: "value",
        name: getAxisLabel(yAxis),
        nameTextStyle: {
          color: textColor,
          fontSize: 10,
          fontWeight: 500,
        },
        splitLine: {
          lineStyle: {
            color: gridLineColor,
            type: "dashed",
          },
        },
        axisLabel: {
          color: textColor,
          fontSize: 10,
          fontFamily: "monospace",
        },
        axisLine: {
          lineStyle: {
            color: gridLineColor,
          },
        },
      },
      series: [
        // Non-dominated step-line
        {
          name: "Pareto Frontier",
          type: "line",
          step: "end",
          data: frontierStepLine,
          smooth: false,
          showSymbol: false,
          lineStyle: {
            color: "#3B82F6",
            width: 1.5,
            type: "dashed",
          },
          z: 1,
        },
        // Dominated runs (muted gray)
        {
          name: "Dominated Runs",
          type: "scatter",
          data: dominatedPoints.map((p) => {
            const isA = p.entry.run_id === selectedRunIdA;
            const isB = p.entry.run_id === selectedRunIdB;
            return {
              value: [p.x, p.y],
              entry: p.entry,
              itemStyle: {
                color: isA ? "#F59E0B" : isB ? "#8B5CF6" : isDark ? "#71717A" : "#94A3B8",
                borderColor: isA || isB ? "#FFFFFF" : "transparent",
                borderWidth: isA || isB ? 2 : 0,
              },
              symbolSize: isA || isB ? 11 : 7,
            };
          }),
          z: 2,
        },
        // Pareto-optimal runs (glowing operational blue)
        {
          name: "Pareto Optimal",
          type: "scatter",
          data: paretoPoints.map((p) => {
            const isA = p.entry.run_id === selectedRunIdA;
            const isB = p.entry.run_id === selectedRunIdB;
            return {
              value: [p.x, p.y],
              entry: p.entry,
              itemStyle: {
                color: isA ? "#F59E0B" : isB ? "#8B5CF6" : "#3B82F6",
                borderColor: "rgba(59, 130, 246, 0.4)",
                borderWidth: isA || isB ? 6 : 4,
                shadowBlur: 10,
                shadowColor: "#3B82F6",
              },
              symbolSize: isA || isB ? 14 : 11,
            };
          }),
          z: 3,
        },
      ],
    };

    chart.setOption(option);

    const handleResize = () => {
      chart.resize();
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, [
    paretoPoints,
    dominatedPoints,
    frontierStepLine,
    xAxis,
    yAxis,
    isDark,
    selectedRunIdA,
    selectedRunIdB,
    toggleRunForDiff,
    onSelectRun,
  ]);

  // Clean up chart on unmount
  useEffect(() => {
    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.dispose();
        chartInstanceRef.current = null;
      }
    };
  }, []);

  return (
    <div className={`flex flex-col h-full w-full bg-app-surface select-none font-sans ${className}`}>
      {/* 40px Top Controls: Axis Pickers */}
      <div className="h-10 px-4 border-b border-app-border shrink-0 flex items-center justify-between text-xs bg-app-bg/40">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-medium text-app-muted uppercase">Y-Axis:</span>
            <select
              value={yAxis}
              onChange={(e) => setYAxis(e.target.value)}
              className="bg-app-surface text-app-text text-xs px-2 py-1 rounded border border-app-border focus:border-blue-500 focus:outline-hidden"
            >
              <option value="f1">Macro F₁ Score</option>
              <option value="delta_star">Bourbaki Tenability (δ*)</option>
              <option value="mrr">Retrieval MRR</option>
              <option value="polarity">Polarity Accuracy</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-medium text-app-muted uppercase">X-Axis:</span>
            <select
              value={xAxis}
              onChange={(e) => setXAxis(e.target.value)}
              className="bg-app-surface text-app-text text-xs px-2 py-1 rounded border border-app-border focus:border-blue-500 focus:outline-hidden"
            >
              <option value="cost">Inference Cost ($ USD)</option>
              <option value="duration">Latency / Duration (s)</option>
              <option value="ece">Calibration Error (ECE)</option>
              <option value="tokens">Total Tokens</option>
            </select>
          </div>
        </div>

        {/* Legend Indicator */}
        <div className="flex items-center gap-3 text-[11px] text-app-muted">
          <div className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500 ring-2 ring-blue-500/20" />
            <span>Pareto Optimal ({paretoPoints.length})</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-zinc-400 dark:bg-zinc-600" />
            <span>Dominated ({dominatedPoints.length})</span>
          </div>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="flex-1 w-full relative min-h-[280px]">
        <div ref={chartRef} className="absolute inset-0 w-full h-full" />
      </div>
    </div>
  );
};
