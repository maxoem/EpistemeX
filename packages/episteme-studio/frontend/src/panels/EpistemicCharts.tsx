import React, { useEffect, useRef } from "react";
import * as echarts from "./echarts";
import { useThemeStore } from "../store/themeStore";
import { EPISTEMIC_TAXONOMY } from "./epistemicTheme";

interface BaseChartProps {
  className?: string;
  style?: React.CSSProperties;
}

function hexToRgba(hex: string, alpha: number): string {
  const sanitized = hex.replace("#", "");
  if (sanitized.length === 6) {
    const r = parseInt(sanitized.substring(0, 2), 16);
    const g = parseInt(sanitized.substring(2, 4), 16);
    const b = parseInt(sanitized.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
  return hex;
}

/**
 * Coerce raw streamed samples into finite, clamped [0..1] values so that
 * malformed payloads (NaN, Infinity, strings, out-of-range) can never poison
 * the KDE/boxplot math or crash the rendering pipeline.
 */
function sanitizeScores(samples?: number[] | null): number[] {
  if (!Array.isArray(samples)) return [];
  const clean: number[] = [];
  for (const s of samples) {
    if (typeof s === "number" && Number.isFinite(s)) {
      clean.push(Math.max(0, Math.min(1, s)));
    }
  }
  return clean;
}

function sanitizeDegrees(degrees?: number[] | null): number[] {
  if (!Array.isArray(degrees)) return [];
  const clean: number[] = [];
  for (const d of degrees) {
    if (typeof d === "number" && Number.isFinite(d) && d >= 0) {
      clean.push(Math.floor(d));
    }
  }
  return clean;
}

/**
 * 1. Probability Density Visualization:
 * Kernel Density Estimate (KDE) line with areaStyle overlaying a Box Plot
 * Exposes true variance, skewness, and multi-modality of confidence scores.
 */
export interface ConfidenceKdeChartProps extends BaseChartProps {
  layerKey?: "L1" | "L2" | "L3" | "L4";
  scores?: number[];
  comparisonScores?: number[];
  labelA?: string;
  labelB?: string;
  height?: number;
  isGhostBaseline?: boolean;
  baselineAnnotation?: string;
}

function calculateKde(samples: number[], bandwidth = 0.05, steps = 100): [number, number][] {
  const clean = sanitizeScores(samples);
  if (clean.length === 0) return [];
  const safeBandwidth = Number.isFinite(bandwidth) && bandwidth > 0 ? bandwidth : 0.05;
  const min = 0;
  const max = 1.0;
  const stepSize = (max - min) / steps;
  const points: [number, number][] = [];

  const gaussian = (u: number) => (1 / Math.sqrt(2 * Math.PI)) * Math.exp(-0.5 * u * u);

  for (let i = 0; i <= steps; i++) {
    const x = min + i * stepSize;
    let sum = 0;
    for (const s of clean) {
      sum += gaussian((x - s) / safeBandwidth);
    }
    const density = sum / (clean.length * safeBandwidth);
    points.push([parseFloat(x.toFixed(3)), Number.isFinite(density) ? parseFloat(density.toFixed(3)) : 0]);
  }
  return points;
}

function calculateBoxplotStats(samples: number[]): [number, number, number, number, number] {
  const sorted = sanitizeScores(samples).sort((a, b) => a - b);
  if (sorted.length === 0) return [0, 0, 0, 0, 0];
  const q1 = sorted[Math.floor(sorted.length * 0.25)] ?? 0;
  const median = sorted[Math.floor(sorted.length * 0.5)] ?? 0;
  const q3 = sorted[Math.floor(sorted.length * 0.75)] ?? 0;
  const min = sorted[0] ?? 0;
  const max = sorted[sorted.length - 1] ?? 0;
  return [min, q1, median, q3, max];
}

export const ConfidenceKdeChart: React.FC<ConfidenceKdeChartProps> = ({
  layerKey = "L2",
  scores,
  comparisonScores,
  labelA = "Current Run",
  labelB = "Candidate Run",
  height = 200,
  isGhostBaseline = false,
  baselineAnnotation,
  className = "",
  style,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const { theme } = useThemeStore();
  const isDark = theme !== "light";
  const epistemic = EPISTEMIC_TAXONOMY[layerKey];

  // Primary scores calculation
  const primaryScores = React.useMemo(() => {
    if (isGhostBaseline) {
      // Gaussian distribution centered at 0.78 with bw=0.2
      const ghost: number[] = [];
      for (let i = 0; i < 120; i++) {
        ghost.push(Math.min(0.99, Math.max(0.05, 0.78 + (Math.sin(i * 0.3) * 0.15) + ((i % 5 - 2) * 0.04))));
      }
      return ghost;
    }
    const clean = sanitizeScores(scores);
    if (clean.length > 0) return clean;
    const synth: number[] = [];
    for (let i = 0; i < 140; i++) {
      synth.push(Math.min(1, Math.max(0, 0.85 + (Math.random() - 0.45) * 0.16)));
    }
    for (let i = 0; i < 40; i++) {
      synth.push(Math.min(1, Math.max(0, 0.62 + (Math.random() - 0.5) * 0.2)));
    }
    for (let i = 0; i < 15; i++) {
      synth.push(Math.min(1, Math.max(0, 0.35 + Math.random() * 0.2)));
    }
    return synth;
  }, [scores, isGhostBaseline]);

  const comparisonScoresClean = React.useMemo(
    () => sanitizeScores(comparisonScores),
    [comparisonScores]
  );

  useEffect(() => {
    if (!chartRef.current) return;
    try {
      if (!chartInstance.current) {
        chartInstance.current = echarts.init(chartRef.current, isDark ? "dark" : undefined, {
          renderer: "canvas",
        });
      }

      const kdeA = calculateKde(primaryScores, isGhostBaseline ? 0.08 : 0.04, 100);
      const boxA = calculateBoxplotStats(primaryScores);

      const seriesList: any[] = [
        {
          name: isGhostBaseline ? "Baseline Benchmark" : labelA,
          type: "line",
          smooth: true,
          symbol: "none",
          data: kdeA,
          lineStyle: {
            width: isGhostBaseline ? 1.25 : 1.5,
            type: isGhostBaseline ? "dashed" : "solid",
            color: isGhostBaseline ? (isDark ? "#71717A" : "#94A3B8") : epistemic.color,
          },
          areaStyle: {
            color: isGhostBaseline
              ? (isDark ? "rgba(113, 113, 122, 0.08)" : "rgba(148, 163, 184, 0.08)")
              : hexToRgba(epistemic.color, 0.15),
          },
        },
        {
          name: isGhostBaseline ? "Baseline IQR" : `${labelA} IQR`,
          type: "boxplot",
          data: [boxA],
          itemStyle: {
            color: isDark ? "#1e293b" : "#f1f5f9",
            borderColor: isGhostBaseline ? (isDark ? "#71717A" : "#94A3B8") : epistemic.color,
            borderWidth: 1,
            borderType: isGhostBaseline ? "dashed" : "solid",
          },
          xAxisIndex: 0,
          yAxisIndex: 1,
        },
      ];

      if (!isGhostBaseline && comparisonScoresClean.length > 0) {
        const kdeB = calculateKde(comparisonScoresClean, 0.04, 100);
        const boxB = calculateBoxplotStats(comparisonScoresClean);
        seriesList.push(
          {
            name: labelB,
            type: "line",
            smooth: true,
            symbol: "none",
            data: kdeB,
            lineStyle: {
              width: 1.5,
              type: "dashed",
              color: "#ec4899",
            },
            areaStyle: {
              color: "rgba(236, 72, 153, 0.15)",
            },
          },
          {
            name: `${labelB} IQR`,
            type: "boxplot",
            data: [boxB],
            itemStyle: {
              color: isDark ? "#3f1d38" : "#fdf2f8",
              borderColor: "#ec4899",
              borderWidth: 1.5,
            },
            xAxisIndex: 0,
            yAxisIndex: 1,
          }
        );
      }

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      title: isGhostBaseline
        ? {
            text: baselineAnnotation || "Awaiting execution // Baseline: KDE (Gaussian, bw=0.2)",
            textStyle: {
              fontSize: 10,
              fontFamily: "var(--font-mono)",
              fontWeight: "normal",
              color: isDark ? "#A1A1AA" : "#71717A",
            },
            left: "center",
            top: 2,
          }
        : undefined,
      tooltip: {
        trigger: "axis",
        backgroundColor: isDark ? "rgba(15, 23, 42, 0.95)" : "rgba(255, 255, 255, 0.95)",
        borderColor: isDark ? "rgba(255, 255, 255, 0.08)" : "#e2e8f0",
        textStyle: {
          color: isDark ? "#f8fafc" : "#0f172a",
          fontSize: 11,
          fontFamily: "var(--font-mono)",
        },
        formatter: (params: any) => {
          if (!Array.isArray(params)) return "";
          const p = params[0];
          if (!p) return "";
          const xVal = p.data ? p.data[0] : "";
          let tip = `<div class="font-bold pb-1 mb-1 border-b border-app-border">Score: ${xVal}</div>`;
          params.forEach((item: any) => {
            if (item.seriesType === "line") {
              tip += `<div class="flex items-center gap-2"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background-color:${item.color};"></span><span>${item.seriesName}: <b>${item.data[1]}</b></span></div>`;
            }
          });
          return tip;
        },
      },
      grid: {
        left: "8%",
        right: "6%",
        top: "16%",
        bottom: "22%",
      },
      xAxis: {
        type: "value",
        min: 0,
        max: 1.0,
        splitNumber: 5,
        name: "Confidence Score [0.0 - 1.0]",
        nameLocation: "middle",
        nameGap: 22,
        nameTextStyle: {
          fontSize: 10,
          color: isDark ? "#94a3b8" : "#64748b",
        },
        axisLabel: {
          fontSize: 10,
          color: isDark ? "#94a3b8" : "#64748b",
          fontFamily: "var(--font-mono)",
        },
        axisLine: { lineStyle: { color: isDark ? "rgba(255, 255, 255, 0.08)" : "#cbd5e1" } },
        splitLine: {
          lineStyle: {
            color: isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(15, 23, 42, 0.06)",
          },
        },
      },
      yAxis: [
        {
          type: "value",
          name: "Density (KDE)",
          nameTextStyle: {
            fontSize: 9,
            color: isDark ? "#94a3b8" : "#64748b",
          },
          axisLabel: {
            fontSize: 9,
            color: isDark ? "#64748b" : "#94a3b8",
            fontFamily: "var(--font-mono)",
          },
          splitLine: {
            lineStyle: {
              color: isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(15, 23, 42, 0.06)",
            },
          },
        },
        {
          type: "value",
          show: false,
          min: 0,
          max: 1,
        },
      ],
      series: seriesList,
    };

      chartInstance.current.setOption(option, true);

      const handleResize = () => {
        chartInstance.current?.resize();
      };
      window.addEventListener("resize", handleResize);

      return () => {
        window.removeEventListener("resize", handleResize);
      };
    } catch (err) {
      console.warn("Failed to render Confidence KDE chart:", err);
    }
  }, [primaryScores, comparisonScoresClean, isDark, epistemic, labelA, labelB]);

  return (
    <div
      ref={chartRef}
      style={{ height: `${height}px`, width: "100%", ...style }}
      className={className}
    />
  );
};

/**
 * 2. Node Degree & Hub Topology Distribution:
 * Maps degree distributions (identifying semantic hubs and isolated nodes) using bar/scatter.
 */
export interface NodeDegreeDistributionChartProps extends BaseChartProps {
  layerKey?: "L1" | "L2" | "L3" | "L4";
  degrees?: number[];
  height?: number;
  isGhostBaseline?: boolean;
  baselineAnnotation?: string;
}

export const NodeDegreeDistributionChart: React.FC<NodeDegreeDistributionChartProps> = ({
  layerKey = "L2",
  degrees,
  height = 190,
  isGhostBaseline = false,
  baselineAnnotation,
  className = "",
  style,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const { theme } = useThemeStore();
  const isDark = theme !== "light";
  const epistemic = EPISTEMIC_TAXONOMY[layerKey];

  const degreeData = React.useMemo(() => {
    if (isGhostBaseline) {
      // Power-law baseline: N(k) ~ k^-2.1
      return [
        { degree: 1, count: 58 },
        { degree: 2, count: 28 },
        { degree: 3, count: 15 },
        { degree: 4, count: 9 },
        { degree: 5, count: 6 },
        { degree: 7, count: 3 },
        { degree: 10, count: 2 },
        { degree: 15, count: 1 },
      ];
    }
    let raw = sanitizeDegrees(degrees);
    if (raw.length === 0) {
      raw = [];
      for (let i = 0; i < 60; i++) raw.push(1);
      for (let i = 0; i < 45; i++) raw.push(2);
      for (let i = 0; i < 28; i++) raw.push(3);
      for (let i = 0; i < 18; i++) raw.push(4);
      for (let i = 0; i < 12; i++) raw.push(5);
      for (let i = 0; i < 8; i++) raw.push(7);
      for (let i = 0; i < 4; i++) raw.push(11);
      for (let i = 0; i < 2; i++) raw.push(18);
    }
    const freqMap: Record<number, number> = {};
    raw.forEach((d) => {
      freqMap[d] = (freqMap[d] || 0) + 1;
    });
    const sortedKeys = Object.keys(freqMap)
      .map(Number)
      .sort((a, b) => a - b);
    return sortedKeys.map((k) => ({ degree: k, count: freqMap[k] }));
  }, [degrees, isGhostBaseline]);

  useEffect(() => {
    if (!chartRef.current) return;
    try {
      if (!chartInstance.current) {
        chartInstance.current = echarts.init(chartRef.current, isDark ? "dark" : undefined, {
          renderer: "canvas",
        });
      }

      const categories = degreeData.map((d) => `k=${d.degree}`);
      const counts = degreeData.map((d) => d.count);

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      title: isGhostBaseline
        ? {
            text: baselineAnnotation || "Awaiting execution // Baseline: Power-Law (γ=2.1)",
            textStyle: {
              fontSize: 10,
              fontFamily: "var(--font-mono)",
              fontWeight: "normal",
              color: isDark ? "#A1A1AA" : "#71717A",
            },
            left: "center",
            top: 2,
          }
        : undefined,
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: isDark ? "rgba(15, 23, 42, 0.95)" : "rgba(255, 255, 255, 0.95)",
        borderColor: isDark ? "#334155" : "#e2e8f0",
        textStyle: {
          color: isDark ? "#f8fafc" : "#0f172a",
          fontSize: 11,
          fontFamily: "var(--font-mono)",
        },
        formatter: (params: any) => {
          const p = params[0];
          if (!p) return "";
          return `<div class="font-mono text-xs">${isGhostBaseline ? "Baseline " : ""}Degree: <b>${p.axisValue}</b><br/>Node Count: <b>${p.data}</b></div>`;
        },
      },
      grid: {
        left: "10%",
        right: "5%",
        top: isGhostBaseline ? "18%" : "14%",
        bottom: "22%",
      },
      xAxis: {
        type: "category",
        data: categories,
        name: "Node Degree (k)",
        nameLocation: "middle",
        nameGap: 22,
        nameTextStyle: {
          fontSize: 10,
          color: isDark ? "#94a3b8" : "#64748b",
        },
        axisLabel: {
          fontSize: 9,
          color: isDark ? "#94a3b8" : "#64748b",
          fontFamily: "var(--font-mono)",
        },
        axisLine: { lineStyle: { color: isDark ? "rgba(255, 255, 255, 0.08)" : "#cbd5e1" } },
      },
      yAxis: {
        type: "value",
        name: "Node Count",
        nameTextStyle: {
          fontSize: 9,
          color: isDark ? "#94a3b8" : "#64748b",
        },
        axisLabel: {
          fontSize: 9,
          color: isDark ? "#64748b" : "#94a3b8",
          fontFamily: "var(--font-mono)",
        },
        splitLine: {
          lineStyle: {
            color: isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(15, 23, 42, 0.06)",
          },
        },
      },
      series: [
        {
          name: isGhostBaseline ? "Target Baseline Frequency" : "Degree Frequency",
          type: "bar",
          data: counts,
          barMaxWidth: 24,
          itemStyle: {
            color: isGhostBaseline
              ? (isDark ? "rgba(113, 113, 122, 0.25)" : "rgba(148, 163, 184, 0.35)")
              : new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: epistemic.color },
                  { offset: 1, color: epistemic.color + "66" },
                ]),
            borderColor: isGhostBaseline ? (isDark ? "#71717A" : "#94A3B8") : undefined,
            borderType: isGhostBaseline ? "dashed" : "solid",
            borderWidth: isGhostBaseline ? 1 : 0,
            borderRadius: [3, 3, 0, 0],
          },
        },
      ],
    };

      chartInstance.current.setOption(option, true);

      const handleResize = () => {
        chartInstance.current?.resize();
      };
      window.addEventListener("resize", handleResize);

      return () => {
        window.removeEventListener("resize", handleResize);
      };
    } catch (err) {
      console.warn("Failed to render Degree Distribution chart:", err);
    }
  }, [degreeData, isDark, epistemic]);

  return (
    <div
      ref={chartRef}
      style={{ height: `${height}px`, width: "100%", ...style }}
      className={className}
    />
  );
};

/**
 * 3. Layer Yield Breakdown Donut / Radial Chart:
 * Displays distribution of generated artifacts across L1, L2, L3, L4 epistemic layers.
 */
export interface LayerYieldDonutChartProps extends BaseChartProps {
  l1Count: number;
  l2Count: number;
  l3Count: number;
  l4Count: number;
  height?: number;
}

export const LayerYieldDonutChart: React.FC<LayerYieldDonutChartProps> = ({
  l1Count,
  l2Count,
  l3Count,
  l4Count,
  height = 190,
  className = "",
  style,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const { theme } = useThemeStore();
  const isDark = theme !== "light";

  useEffect(() => {
    if (!chartRef.current) return;
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, isDark ? "dark" : undefined, {
        renderer: "canvas",
      });
    }

    const data = [
      { value: l1Count, name: "L1 Foundation", itemStyle: { color: EPISTEMIC_TAXONOMY.L1.color } },
      { value: l2Count, name: "L2 Knowledge Graph", itemStyle: { color: EPISTEMIC_TAXONOMY.L2.color } },
      { value: l3Count, name: "L3 Argument Web", itemStyle: { color: EPISTEMIC_TAXONOMY.L3.color } },
      { value: l4Count, name: "L4 TheoryNet", itemStyle: { color: EPISTEMIC_TAXONOMY.L4.color } },
    ].filter((d) => d.value > 0);

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        backgroundColor: isDark ? "rgba(15, 23, 42, 0.95)" : "rgba(255, 255, 255, 0.95)",
        borderColor: isDark ? "rgba(255, 255, 255, 0.08)" : "#e2e8f0",
        textStyle: {
          color: isDark ? "#f8fafc" : "#0f172a",
          fontSize: 11,
          fontFamily: "var(--font-mono)",
        },
        formatter: "{b}: <b>{c}</b> ({d}%)",
      },
      legend: {
        orient: "horizontal",
        bottom: "0%",
        textStyle: {
          fontSize: 10,
          color: isDark ? "#94a3b8" : "#64748b",
        },
      },
      series: [
        {
          name: "Epistemic Yield",
          type: "pie",
          radius: ["42%", "72%"],
          center: ["50%", "45%"],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 4,
            borderColor: isDark ? "#09090B" : "#ffffff",
            borderWidth: 2,
          },
          label: {
            show: false,
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 11,
              fontWeight: "bold",
            },
          },
          data,
        },
      ],
    };

    chartInstance.current.setOption(option, true);

    const handleResize = () => {
      chartInstance.current?.resize();
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [l1Count, l2Count, l3Count, l4Count, isDark]);

  return (
    <div
      ref={chartRef}
      style={{ height: `${height}px`, width: "100%", ...style }}
      className={className}
    />
  );
};

/**
 * 3b. Predicate Composition Donut Chart:
 * Clean, high-density scientific ring chart for relation ontology distribution.
 */
export interface PredicateCompositionDonutChartProps extends BaseChartProps {
  hierarchical: number;
  associative: number;
  causal: number;
  dialectical: number;
  unmapped?: number;
  height?: number;
}

export const PredicateCompositionDonutChart: React.FC<PredicateCompositionDonutChartProps> = ({
  hierarchical,
  associative,
  causal,
  dialectical,
  unmapped = 0,
  height = 140,
  className = "",
  style,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const { theme } = useThemeStore();
  const isDark = theme !== "light";

  useEffect(() => {
    if (!chartRef.current) return;
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, isDark ? "dark" : undefined, {
        renderer: "canvas",
      });
    }

    const data = [
      { value: hierarchical, name: "Hierarchical", itemStyle: { color: "#3B82F6" } },
      { value: associative, name: "Associative", itemStyle: { color: "#8B5CF6" } },
      { value: causal, name: "Causal", itemStyle: { color: "#10B981" } },
      { value: dialectical, name: "Dialectical", itemStyle: { color: "#F59E0B" } },
      ...(unmapped > 0
        ? [{ value: unmapped, name: "Unmapped", itemStyle: { color: "#F43F5E" } }]
        : []),
    ].filter((d) => d.value > 0);

    const total = data.reduce((acc, d) => acc + d.value, 0);

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        backgroundColor: isDark ? "rgba(15, 23, 42, 0.95)" : "rgba(255, 255, 255, 0.95)",
        borderColor: isDark ? "rgba(255, 255, 255, 0.08)" : "#e2e8f0",
        padding: [6, 10],
        textStyle: {
          color: isDark ? "#f8fafc" : "#0f172a",
          fontSize: 11,
          fontFamily: "var(--font-mono)",
        },
        formatter: "{b}: <b>{c}</b> ({d}%)",
      },
      series: [
        {
          name: "Predicate Breakdown",
          type: "pie",
          radius: ["46%", "76%"],
          center: ["50%", "50%"],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 3,
            borderColor: isDark ? "#18181B" : "#F8FAFC",
            borderWidth: 2,
          },
          label: {
            show: true,
            position: "center",
            formatter: () => `${total}\nTriples`,
            fontSize: 11,
            fontWeight: 600,
            color: isDark ? "#f8fafc" : "#0f172a",
            fontFamily: "Inter, sans-serif",
            lineHeight: 14,
          },
          emphasis: {
            scale: true,
            scaleSize: 4,
            label: {
              show: true,
              fontSize: 11,
              fontWeight: "bold",
            },
          },
          data,
        },
      ],
    };

    chartInstance.current.setOption(option, true);

    const handleResize = () => {
      chartInstance.current?.resize();
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [hierarchical, associative, causal, dialectical, unmapped, isDark]);

  return (
    <div
      ref={chartRef}
      style={{ height: `${height}px`, width: "100%", ...style }}
      className={className}
    />
  );
};

/**
 * 4. High-Density Ontological Distribution Summary Bar:
 * Compact, proportional horizontal distribution bar showing L1-L4 ratios
 * with tabular numerals matching design.md section 10.
 */
export interface InlineOntologicalDistributionBarProps {
  l1Count: number;
  l2Count: number;
  l3Count: number;
  l4Count: number;
  className?: string;
  showLegend?: boolean;
}

export const InlineOntologicalDistributionBar: React.FC<InlineOntologicalDistributionBarProps> = ({
  l1Count,
  l2Count,
  l3Count,
  l4Count,
  className = "",
  showLegend = true,
}) => {
  const total = l1Count + l2Count + l3Count + l4Count;
  const p1 = total > 0 ? (l1Count / total) * 100 : 0;
  const p2 = total > 0 ? (l2Count / total) * 100 : 0;
  const p3 = total > 0 ? (l3Count / total) * 100 : 0;
  const p4 = total > 0 ? (l4Count / total) * 100 : 0;

  return (
    <div className={`space-y-2 select-none ${className}`}>
      {/* Stacked Proportional Bar */}
      <div className="w-full h-2 rounded-[3px] overflow-hidden flex bg-app-subtle border border-app-border/40">
        {p1 > 0 && (
          <div
            style={{ width: `${p1}%`, backgroundColor: EPISTEMIC_TAXONOMY.L1.color }}
            className="h-full transition-all"
            title={`L1 Foundation: ${l1Count.toLocaleString()} (${p1.toFixed(1)}%)`}
          />
        )}
        {p2 > 0 && (
          <div
            style={{ width: `${p2}%`, backgroundColor: EPISTEMIC_TAXONOMY.L2.color }}
            className="h-full transition-all"
            title={`L2 Knowledge Graph: ${l2Count.toLocaleString()} (${p2.toFixed(1)}%)`}
          />
        )}
        {p3 > 0 && (
          <div
            style={{ width: `${p3}%`, backgroundColor: EPISTEMIC_TAXONOMY.L3.color }}
            className="h-full transition-all"
            title={`L3 Argument Web: ${l3Count.toLocaleString()} (${p3.toFixed(1)}%)`}
          />
        )}
        {p4 > 0 && (
          <div
            style={{ width: `${p4}%`, backgroundColor: EPISTEMIC_TAXONOMY.L4.color }}
            className="h-full transition-all"
            title={`L4 TheoryNet: ${l4Count.toLocaleString()} (${p4.toFixed(1)}%)`}
          />
        )}
      </div>

      {/* Legend with Tabular Numerals */}
      {showLegend && (
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] font-sans">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-app-muted truncate">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: EPISTEMIC_TAXONOMY.L1.color }} />
              <span className="truncate">L1 Foundation</span>
            </span>
            <span className="font-mono tabular-nums text-app-heading font-medium">{l1Count.toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-app-muted truncate">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: EPISTEMIC_TAXONOMY.L2.color }} />
              <span className="truncate">L2 KG</span>
            </span>
            <span className="font-mono tabular-nums text-app-heading font-medium">{l2Count.toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-app-muted truncate">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: EPISTEMIC_TAXONOMY.L3.color }} />
              <span className="truncate">L3 Arguments</span>
            </span>
            <span className="font-mono tabular-nums text-app-heading font-medium">{l3Count.toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-app-muted truncate">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: EPISTEMIC_TAXONOMY.L4.color }} />
              <span className="truncate">L4 TheoryNet</span>
            </span>
            <span className="font-mono tabular-nums text-app-heading font-medium">{l4Count.toLocaleString()}</span>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * 8. Diachronic Lakatosian Degeneration Trajectory Chart
 * Plots the longitudinal Degeneration Index (DI) across successive theory versions T_0 -> T_1 -> T_2
 * alongside Delta Auxiliary vs Delta Empirical bars and progressive threshold line (DI = 1.0).
 */
export interface LakatosianDegenerationTrajectoryChartProps extends BaseChartProps {
  steps?: string[];
  diSeries?: number[];
  deltaAuxiliarySeries?: number[];
  deltaEmpiricalSeries?: number[];
  anomaliesSeries?: number[];
  overallDi?: number;
  height?: number;
}

export const LakatosianDegenerationTrajectoryChart: React.FC<LakatosianDegenerationTrajectoryChartProps> = ({
  steps = [],
  diSeries = [],
  deltaAuxiliarySeries = [],
  deltaEmpiricalSeries = [],
  anomaliesSeries = [],
  overallDi,
  className,
  style,
  height = 300,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const { theme } = useThemeStore();
  const isDark = theme === "dark";

  const safeSteps = steps.length > 0 ? steps : ["T_0 -> T_1", "T_1 -> T_2", "T_2 -> T_3"];
  const safeDi = diSeries.length > 0 ? diSeries : [0.45, 0.72, 1.25];
  const safeAux = deltaAuxiliarySeries.length > 0 ? deltaAuxiliarySeries : [2, 5, 8];
  const safeEmp = deltaEmpiricalSeries.length > 0 ? deltaEmpiricalSeries : [5, 6, 4];

  useEffect(() => {
    if (!chartRef.current) return;
    try {
      if (!chartInstance.current) {
        chartInstance.current = echarts.init(chartRef.current, isDark ? "dark" : undefined, {
          renderer: "canvas",
        });
      }

      const option: any = {
        backgroundColor: "transparent",
        animation: true,
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "cross" },
        },
        legend: {
          data: ["Degeneration Index (DI)", "Delta Auxiliary", "Delta Empirical Content"],
          top: 4,
          textStyle: {
            color: isDark ? "#A1A1AA" : "#4B5563",
            fontSize: 11,
          },
        },
        grid: {
          top: 36,
          left: 45,
          right: 45,
          bottom: 25,
        },
        xAxis: {
          type: "category",
          data: safeSteps,
          axisLine: { lineStyle: { color: isDark ? "#3F3F46" : "#E2E8F0" } },
          axisLabel: { color: isDark ? "#A1A1AA" : "#64748B", fontSize: 11 },
        },
        yAxis: [
          {
            type: "value",
            name: "DI",
            position: "left",
            axisLine: { lineStyle: { color: isDark ? "#3F3F46" : "#E2E8F0" } },
            axisLabel: { color: isDark ? "#A1A1AA" : "#64748B", fontSize: 10 },
            splitLine: { lineStyle: { color: isDark ? "#27272A" : "#F1F5F9" } },
          },
          {
            type: "value",
            name: "Count",
            position: "right",
            axisLine: { lineStyle: { color: isDark ? "#3F3F46" : "#E2E8F0" } },
            axisLabel: { color: isDark ? "#A1A1AA" : "#64748B", fontSize: 10 },
            splitLine: { show: false },
          },
        ],
        series: [
          {
            name: "Delta Auxiliary",
            type: "bar",
            yAxisIndex: 1,
            data: safeAux,
            itemStyle: { color: "#F59E0B" },
          },
          {
            name: "Delta Empirical Content",
            type: "bar",
            yAxisIndex: 1,
            data: safeEmp,
            itemStyle: { color: "#10B981" },
          },
          {
            name: "Degeneration Index (DI)",
            type: "line",
            yAxisIndex: 0,
            data: safeDi,
            lineStyle: { width: 2.5, color: "#8B5CF6" },
            itemStyle: { color: "#8B5CF6" },
            markLine: {
              silent: true,
              data: [
                {
                  yAxis: 1.0,
                  name: "Progressive Threshold (DI = 1.0)",
                  lineStyle: { color: "#EF4444", type: "dashed", width: 1.5 },
                  label: {
                    formatter: "DI = 1.0 (Degenerating)",
                    position: "middle",
                    color: "#EF4444",
                    fontSize: 10,
                  },
                },
              ],
            },
          },
        ],
      };

      chartInstance.current.setOption(option, true);
    } catch (e) {
      console.error("Failed to render LakatosianDegenerationTrajectoryChart", e);
    }
  }, [isDark, safeSteps, safeDi, safeAux, safeEmp]);

  useEffect(() => {
    const handleResize = () => chartInstance.current?.resize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return (
    <div className={className} style={{ width: "100%", height, ...style }}>
      <div ref={chartRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
};
