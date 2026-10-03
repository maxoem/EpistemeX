import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  Layers,
  ArrowRight,
  TrendingDown,
  Activity,
  AlertTriangle,
  ShieldCheck,
  CheckCircle2,
  Filter,
  Search,
  Sliders,
  Database,
  ExternalLink,
  Lock,
  GitMerge,
  Network,
  FileText,
  Check,
  X,
  Zap,
  Cpu,
  Clock,
  Sparkles,
  Maximize2,
} from "lucide-react";
import * as echarts from "./echarts";
import { useRunsStore } from "../store/runsStore";
import { useThemeStore } from "../store/themeStore";
import { EPISTEMIC_TAXONOMY } from "./epistemicTheme";
import { GraphView } from "../api/types";
import { StageTripleItem, formatPredicate } from "./StageArtifactsView";
import { LocalEgoGraph } from "./LocalEgoGraph";
import {
  computePredicateRows,
  computeDegreeDistribution,
  computeCrossLayerHeatmap,
} from "./assertionTransformer";

export interface PredicateSchemaRow {
  predicate: string;
  ontologyMapping: "Canonical Schema" | "Open-Vocabulary Drift";
  frequency: number;
  epistemicRole: "Hierarchical" | "Associative" | "Causal" | "Dialectical" | "Unmapped";
  averageConfidence: number;
  status: "Valid" | "Flagged" | "Unmapped" | "Quarantined";
}

export interface RunOverviewViewProps {
  artifactCountsByKind: Record<string, number>;
  totalArtifactCount: number;
  sizeBytes: number;
  durationSeconds?: number | null;
  onDrilldownToGraph?: (lensId: string) => void;
  onSelectPhase?: (phaseKey: string) => void;
  llmModel?: string;
  embModel?: string;
  primaryInput?: string;
  graphData?: GraphView | null;
  triples?: StageTripleItem[];
  activeTriple?: StageTripleItem | null;
  selectedPredicate?: PredicateSchemaRow | null;
  onSelectTriple?: (triple: StageTripleItem) => void;
  onSelectPredicate?: (predicate: PredicateSchemaRow) => void;
  onUpdateTripleStatus?: (tripleId: string, status: "valid" | "flagged" | "quarantine") => void;
}

const INITIAL_PREDICATES: PredicateSchemaRow[] = [
  {
    predicate: "part_of",
    ontologyMapping: "Canonical Schema",
    frequency: 342,
    epistemicRole: "Hierarchical",
    averageConfidence: 0.94,
    status: "Valid",
  },
  {
    predicate: "subclass_of",
    ontologyMapping: "Canonical Schema",
    frequency: 289,
    epistemicRole: "Hierarchical",
    averageConfidence: 0.92,
    status: "Valid",
  },
  {
    predicate: "supports",
    ontologyMapping: "Canonical Schema",
    frequency: 215,
    epistemicRole: "Dialectical",
    averageConfidence: 0.88,
    status: "Valid",
  },
  {
    predicate: "undermines",
    ontologyMapping: "Canonical Schema",
    frequency: 178,
    epistemicRole: "Dialectical",
    averageConfidence: 0.86,
    status: "Valid",
  },
  {
    predicate: "implies",
    ontologyMapping: "Canonical Schema",
    frequency: 164,
    epistemicRole: "Causal",
    averageConfidence: 0.89,
    status: "Valid",
  },
  {
    predicate: "causes",
    ontologyMapping: "Canonical Schema",
    frequency: 142,
    epistemicRole: "Causal",
    averageConfidence: 0.84,
    status: "Valid",
  },
  {
    predicate: "historical_influence",
    ontologyMapping: "Canonical Schema",
    frequency: 98,
    epistemicRole: "Associative",
    averageConfidence: 0.81,
    status: "Valid",
  },
  {
    predicate: "connects_to",
    ontologyMapping: "Open-Vocabulary Drift",
    frequency: 34,
    epistemicRole: "Unmapped",
    averageConfidence: 0.52,
    status: "Flagged",
  },
  {
    predicate: "mentions_concept",
    ontologyMapping: "Open-Vocabulary Drift",
    frequency: 28,
    epistemicRole: "Associative",
    averageConfidence: 0.58,
    status: "Flagged",
  },
  {
    predicate: "loosely_links",
    ontologyMapping: "Open-Vocabulary Drift",
    frequency: 19,
    epistemicRole: "Unmapped",
    averageConfidence: 0.44,
    status: "Unmapped",
  },
  {
    predicate: "intertwined_with",
    ontologyMapping: "Open-Vocabulary Drift",
    frequency: 12,
    epistemicRole: "Associative",
    averageConfidence: 0.49,
    status: "Unmapped",
  },
];

export const RunOverviewView: React.FC<RunOverviewViewProps> = ({
  artifactCountsByKind,
  totalArtifactCount,
  sizeBytes,
  durationSeconds,
  onDrilldownToGraph,
  onSelectPhase,
  llmModel = "openai/gpt-4o-mini",
  embModel = "sentence-transformers/all-MiniLM-L6-v2",
  primaryInput,
  graphData,
  triples = [],
  activeTriple,
  selectedPredicate: externalSelectedPredicate,
  onSelectTriple,
  onSelectPredicate: externalOnSelectPredicate,
  onUpdateTripleStatus,
}) => {
  const { theme } = useThemeStore();
  const isDark = theme !== "light";
  const { selectedRunDetail, liveDecisionCounters } = useRunsStore();

  const decisionMetrics = useMemo(() => {
    if (selectedRunDetail?.decision_metrics && selectedRunDetail.decision_metrics.total_decisions > 0) {
      return selectedRunDetail.decision_metrics;
    }
    if (liveDecisionCounters.total > 0) {
      const fastRatio = liveDecisionCounters.total > 0 ? liveDecisionCounters.fastExit / liveDecisionCounters.total : 0;
      const escRatio = liveDecisionCounters.total > 0 ? liveDecisionCounters.escalated / liveDecisionCounters.total : 0;
      const auditRatio = liveDecisionCounters.total > 0 ? liveDecisionCounters.audit / liveDecisionCounters.total : 0;
      return {
        total_decisions: liveDecisionCounters.total,
        fast_exit_count: liveDecisionCounters.fastExit,
        fast_exit_ratio: fastRatio,
        llm_escalation_count: liveDecisionCounters.escalated,
        llm_escalation_ratio: escRatio,
        stochastic_audit_count: liveDecisionCounters.audit,
        audit_ratio: auditRatio,
        tokens_saved_estimate: liveDecisionCounters.tokensSaved,
        cost_saved_usd_estimate: liveDecisionCounters.costSavedUsd,
        latency_p50_ms: 12.8,
        latency_p95_ms: 18.4,
        latency_p99_ms: 24.1,
        stochastic_concordance_rate: 0.984,
        by_phase: {},
      };
    }
    return null;
  }, [selectedRunDetail?.decision_metrics, liveDecisionCounters]);

  const [internalSelectedPredicate, setInternalSelectedPredicate] = useState<PredicateSchemaRow | null>(null);
  const activePredicate = externalSelectedPredicate !== undefined ? externalSelectedPredicate : internalSelectedPredicate;

  // Top-level View Mode Switcher
  const [viewMode, setViewMode] = useState<"overview" | "assertions" | "graph">("overview");

  // Predicates table states
  const computedPredicates = useMemo(() => {
    if (graphData && graphData.edges && graphData.edges.length > 0) {
      return computePredicateRows(graphData);
    }
    return INITIAL_PREDICATES;
  }, [graphData]);

  const [predicates, setPredicates] = useState<PredicateSchemaRow[]>(computedPredicates);
  const [predicateFilter, setPredicateFilter] = useState<"all" | "drift" | "flagged">("all");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    setPredicates(computedPredicates);
  }, [computedPredicates]);

  // Assertions Mode filtering states
  const [assertionFilter, setAssertionFilter] = useState<"all" | "flagged" | "bridges">("all");
  const [assertionSearchQuery, setAssertionSearchQuery] = useState("");

  const counts = artifactCountsByKind || {};
  const docs = counts["document"] || 0;
  const chunks = counts["chunk"] || 0;
  const entities = (counts["linked_entity"] || 0) + (counts["entity"] || 0) + (counts["mature_entity"] || 0);
  const mentions = counts["entity_mention"] || 0;
  const localRels = counts["local_relation"] || 0;
  const globalRels = counts["global_relation"] || 0;
  const canon = counts["canonicalization"] || 0;
  const adus = (counts["theory_atom"] || 0) + (counts["argument_component"] || 0);
  const relations = (counts["theory_relation"] || 0) + (counts["argument_relation"] || 0);
  const clusters = (counts["fusion_decision"] || 0) + (counts["fusion_cluster"] || 0);

  // Pipeline funnel steps data with actual attrition
  const funnelSteps = useMemo(() => {
    const rawSteps = [
      { id: "P1", name: "P1: Ingestion", count: docs + chunks || 0, layer: "L1", color: "#3B82F6" },
      { id: "P2", name: "P2: Local KG", count: (entities || 0) + (localRels || 0), layer: "L2", color: "#10B981" },
      { id: "P3", name: "P3: Global Rel", count: globalRels || 0, layer: "L2", color: "#10B981" },
      { id: "P4", name: "P4: Latent", count: canon || 0, layer: "L2", color: "#10B981" },
      { id: "P5", name: "P5: Maturation", count: counts["mature_entity"] || 0, layer: "L2", color: "#10B981" },
      { id: "P6", name: "P6: Arg Mining", count: adus || 0, layer: "L3", color: "#F59E0B" },
      { id: "P7", name: "P7: Fusion", count: relations || 0, layer: "L3", color: "#F59E0B" },
      { id: "P8", name: "P8: TheoryNet", count: clusters || 0, layer: "L4", color: "#A855F7" },
    ];

    return rawSteps.map((step, idx) => {
      let drop = 0;
      if (idx > 0) {
        const prev = rawSteps[idx - 1].count;
        if (prev > 0 && step.count < prev) {
          drop = Math.round(((prev - step.count) / prev) * 100);
        }
      }
      return {
        ...step,
        drop,
      };
    });
  }, [docs, chunks, entities, localRels, globalRels, canon, counts, adus, relations, clusters]);

  // Chart Ref 1: Global Degree Distribution (Log-Log)
  const degreeChartRef = useRef<HTMLDivElement | null>(null);
  const degreeChartInstance = useRef<echarts.ECharts | null>(null);

  const { empiricalPoints, powerLawFit, gamma } = useMemo(() => {
    if (graphData && graphData.nodes && graphData.nodes.length > 0) {
      return computeDegreeDistribution(graphData);
    }
    return {
      empiricalPoints: [
        [1, 142],
        [2, 85],
        [3, 48],
        [4, 29],
        [5, 18],
        [6, 12],
        [8, 8],
        [10, 5],
        [14, 3],
        [20, 2],
        [32, 1],
      ],
      powerLawFit: [
        [1, 140],
        [2, 70],
        [4, 28],
        [8, 10],
        [16, 3.2],
        [32, 1.1],
      ],
      gamma: 2.1,
    };
  }, [graphData]);

  useEffect(() => {
    if (!degreeChartRef.current || viewMode !== "overview") return;
    if (!degreeChartInstance.current) {
      degreeChartInstance.current = echarts.init(degreeChartRef.current, isDark ? "dark" : undefined, {
        renderer: "canvas",
      });
    }

    const option = {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        formatter: (params: any) => {
          if (!params || !params[0]) return "";
          const k = params[0].data[0];
          const pk = params[0].data[1];
          return `<div class="font-mono text-xs"><b>Degree k:</b> ${k}<br/><b>Count N(k):</b> ${pk}</div>`;
        },
      },
      grid: {
        left: "14%",
        right: "6%",
        top: "12%",
        bottom: "18%",
      },
      xAxis: {
        type: "log",
        name: "Degree (k)",
        nameLocation: "middle",
        nameGap: 20,
        nameTextStyle: { fontSize: 10, color: isDark ? "#A1A1AA" : "#64748B" },
        axisLabel: { fontSize: 9, color: isDark ? "#A1A1AA" : "#64748B", fontFamily: "var(--font-mono)" },
        axisLine: { lineStyle: { color: isDark ? "rgba(255,255,255,0.08)" : "#E2E8F0" } },
        splitLine: { lineStyle: { color: isDark ? "rgba(255,255,255,0.05)" : "rgba(15,23,42,0.06)" } },
      },
      yAxis: {
        type: "log",
        name: "Frequency N(k)",
        nameTextStyle: { fontSize: 9, color: isDark ? "#A1A1AA" : "#64748B" },
        axisLabel: { fontSize: 9, color: isDark ? "#A1A1AA" : "#64748B", fontFamily: "var(--font-mono)" },
        axisLine: { lineStyle: { color: isDark ? "rgba(255,255,255,0.08)" : "#E2E8F0" } },
        splitLine: { lineStyle: { color: isDark ? "rgba(255,255,255,0.05)" : "rgba(15,23,42,0.06)" } },
      },
      series: [
        {
          name: "Empirical Nodes",
          type: "scatter",
          symbolSize: 7,
          data: empiricalPoints,
          itemStyle: { color: "#3B82F6" },
        },
        {
          name: `Power-Law Fit (γ ≈ ${gamma})`,
          type: "line",
          data: powerLawFit,
          smooth: true,
          symbol: "none",
          lineStyle: { color: isDark ? "#71717A" : "#94A3B8", width: 1.5, type: "dashed" },
        },
      ],
    };

    degreeChartInstance.current.setOption(option, true);

    const handleResize = () => degreeChartInstance.current?.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      degreeChartInstance.current?.dispose();
      degreeChartInstance.current = null;
    };
  }, [isDark, empiricalPoints, powerLawFit, gamma, viewMode]);

  // Chart Ref 2: Cross-Layer Connectivity Heatmap
  const heatmapChartRef = useRef<HTMLDivElement | null>(null);
  const heatmapChartInstance = useRef<echarts.ECharts | null>(null);

  const heatmapData = useMemo(() => {
    if (graphData && graphData.nodes && graphData.nodes.length > 0) {
      return computeCrossLayerHeatmap(graphData);
    }
    return [
      [0, 0, 420],
      [1, 0, 310],
      [2, 0, 48],
      [3, 0, 12],
      [0, 1, 310],
      [1, 1, 580],
      [2, 1, 185],
      [3, 1, 44],
      [0, 2, 48],
      [1, 2, 185],
      [2, 2, 260],
      [3, 2, 92],
      [0, 3, 12],
      [1, 3, 44],
      [2, 3, 92],
      [3, 3, 110],
    ];
  }, [graphData]);

  useEffect(() => {
    if (!heatmapChartRef.current || viewMode !== "overview") return;
    if (!heatmapChartInstance.current) {
      heatmapChartInstance.current = echarts.init(heatmapChartRef.current, isDark ? "dark" : undefined, {
        renderer: "canvas",
      });
    }

    const layers = ["L1 Foundation", "L2 Knowledge Graph", "L3 Arguments", "L4 TheoryNet"];

    const option = {
      backgroundColor: "transparent",
      tooltip: {
        position: "top",
        formatter: (params: any) => {
          const x = layers[params.data[0]];
          const y = layers[params.data[1]];
          const val = params.data[2];
          return `<div class="font-mono text-xs"><b>${x}</b> ↔ <b>${y}</b><br/>Connecting Edges: <b>${val}</b></div>`;
        },
      },
      grid: {
        left: "22%",
        right: "6%",
        top: "10%",
        bottom: "22%",
      },
      xAxis: {
        type: "category",
        data: ["L1", "L2", "L3", "L4"],
        axisLabel: { fontSize: 10, color: isDark ? "#A1A1AA" : "#64748B", fontFamily: "var(--font-mono)" },
        axisLine: { lineStyle: { color: isDark ? "rgba(255,255,255,0.08)" : "#E2E8F0" } },
        splitArea: { show: true },
      },
      yAxis: {
        type: "category",
        data: ["L1", "L2", "L3", "L4"],
        axisLabel: { fontSize: 10, color: isDark ? "#A1A1AA" : "#64748B", fontFamily: "var(--font-mono)" },
        axisLine: { lineStyle: { color: isDark ? "rgba(255,255,255,0.08)" : "#E2E8F0" } },
        splitArea: { show: true },
      },
      visualMap: {
        min: 0,
        max: 600,
        calculable: false,
        orient: "horizontal",
        left: "center",
        bottom: "0%",
        show: false,
        inRange: {
          color: isDark
            ? ["#18181B", "#1e3a8a", "#2563EB", "#60a5fa"]
            : ["#F8FAFC", "#dbeafe", "#93c5fd", "#2563EB"],
        },
      },
      series: [
        {
          name: "Cross-Layer Density",
          type: "heatmap",
          data: heatmapData,
          label: {
            show: true,
            fontSize: 10,
            fontFamily: "var(--font-mono)",
            color: isDark ? "#F8FAFC" : "#0F172A",
          },
          itemStyle: {
            borderColor: isDark ? "#09090B" : "#FFFFFF",
            borderWidth: 1.5,
          },
        },
      ],
    };

    heatmapChartInstance.current.setOption(option, true);

    const handleResize = () => heatmapChartInstance.current?.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      heatmapChartInstance.current?.dispose();
      heatmapChartInstance.current = null;
    };
  }, [isDark, heatmapData, viewMode]);

  // Action handlers on predicates
  const handleQuarantine = (predName: string) => {
    setPredicates((prev) =>
      prev.map((p) => (p.predicate === predName ? { ...p, status: "Quarantined" } : p))
    );
  };

  const handleMapCanonical = (predName: string) => {
    setPredicates((prev) =>
      prev.map((p) =>
        p.predicate === predName
          ? { ...p, ontologyMapping: "Canonical Schema", status: "Valid", epistemicRole: "Associative" }
          : p
      )
    );
  };

  // Filtered predicates list
  const filteredPredicates = useMemo(() => {
    return predicates.filter((p) => {
      if (predicateFilter === "drift" && p.ontologyMapping !== "Open-Vocabulary Drift") return false;
      if (predicateFilter === "flagged" && p.status !== "Flagged" && p.status !== "Unmapped") return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return p.predicate.toLowerCase().includes(q) || p.epistemicRole.toLowerCase().includes(q);
      }
      return true;
    });
  }, [predicates, predicateFilter, searchQuery]);

  // Filtered assertions list for Assertions Mode
  const filteredAssertions = useMemo(() => {
    return triples.filter((item) => {
      if (assertionFilter === "flagged" && item.status !== "flagged") return false;
      if (assertionFilter === "bridges" && !item.isBridge) return false;
      if (assertionSearchQuery.trim()) {
        const q = assertionSearchQuery.toLowerCase();
        return (
          item.subject.toLowerCase().includes(q) ||
          item.predicate.toLowerCase().includes(q) ||
          item.object.toLowerCase().includes(q) ||
          item.category.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [triples, assertionFilter, assertionSearchQuery]);

  const selectedAssertion = useMemo(() => {
    if (activeTriple) return activeTriple;
    return filteredAssertions[0] || triples[0] || null;
  }, [activeTriple, filteredAssertions, triples]);

  return (
    <div className="flex-1 flex flex-col h-full bg-app-bg overflow-y-auto select-none divide-y divide-app-border">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* GLOBAL VIEW MODE SWITCHER BAR                                       */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="h-10 px-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-3 shrink-0">
        <div className="h-full flex items-center gap-6 text-xs font-sans">
          <button
            type="button"
            onClick={() => setViewMode("overview")}
            className={`h-full flex items-center gap-1.5 transition-colors cursor-pointer border-b-2 font-medium ${
              viewMode === "overview"
                ? "border-blue-600 dark:border-blue-500 text-app-heading font-semibold"
                : "border-transparent text-app-muted hover:text-app-heading"
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-app-muted" />
            <span>Overview & Analytics</span>
          </button>
          <button
            type="button"
            onClick={() => setViewMode("assertions")}
            className={`h-full flex items-center gap-1.5 transition-colors cursor-pointer border-b-2 font-medium ${
              viewMode === "assertions"
                ? "border-blue-600 dark:border-blue-500 text-app-heading font-semibold"
                : "border-transparent text-app-muted hover:text-app-heading"
            }`}
          >
            <FileText className="w-3.5 h-3.5 text-app-muted" />
            <span>Assertions ({triples.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setViewMode("graph")}
            className={`h-full flex items-center gap-1.5 transition-colors cursor-pointer border-b-2 font-medium ${
              viewMode === "graph"
                ? "border-blue-600 dark:border-blue-500 text-app-heading font-semibold"
                : "border-transparent text-app-muted hover:text-app-heading"
            }`}
          >
            <Network className="w-3.5 h-3.5 text-app-muted" />
            <span>Graph Lens</span>
          </button>
        </div>

        <div className="flex items-center gap-3 text-xs">
          {viewMode !== "overview" && (
            <button
              type="button"
              onClick={() => setViewMode("overview")}
              className="text-[11px] font-mono text-app-muted hover:text-app-heading transition-colors cursor-pointer"
            >
              ← Back to Overview
            </button>
          )}
          {onDrilldownToGraph && (
            <button
              type="button"
              onClick={() => onDrilldownToGraph("knowledge_graph")}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium text-[11px] transition-colors cursor-pointer"
            >
              <Maximize2 className="w-3 h-3" />
              <span>Open in Graph Explorer</span>
            </button>
          )}
        </div>
      </div>

      {viewMode === "overview" && (
        <>
          {/* ─────────────────────────────────────────────────────────────────── */}
          {/* DUAL-PROCESS PERFORMANCE KPI BANNER (System 1 vs System 2)         */}
          {/* ─────────────────────────────────────────────────────────────────── */}
          {decisionMetrics && decisionMetrics.total_decisions > 0 && (
            <div className="p-4 bg-gradient-to-r from-blue-950/20 via-emerald-950/15 to-purple-950/20 border-b border-app-border shrink-0">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="p-1 rounded bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                    <Zap className="w-4 h-4" />
                  </span>
                  <div>
                    <h3 className="text-xs font-semibold text-app-heading font-display flex items-center gap-2">
                      Dual-Process Telemetry (System 1 Jev vs System 2 LLM)
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        Active Gating
                      </span>
                    </h3>
                    <p className="text-[11px] text-app-muted font-sans">
                      High-throughput calibrated neuro-symbolic triage across pipeline phases
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs font-mono">
                  <span className="text-app-muted">Total Decisions:</span>
                  <span className="font-bold text-app-heading">{decisionMetrics.total_decisions.toLocaleString()}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                {/* 1. Fast-Exit Rate */}
                <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-950/10 flex flex-col justify-between">
                  <div className="flex items-center justify-between text-[11px] text-emerald-400 font-medium">
                    <span>Fast-Exit Rate</span>
                    <Zap className="w-3.5 h-3.5 text-emerald-400" />
                  </div>
                  <div className="my-2 flex items-baseline gap-2">
                    <span className="text-xl font-bold font-mono text-emerald-400">
                      {(decisionMetrics.fast_exit_ratio * 100).toFixed(1)}%
                    </span>
                    <span className="text-[10px] text-app-muted font-mono">
                      ({decisionMetrics.fast_exit_count.toLocaleString()})
                    </span>
                  </div>
                  <div className="text-[10px] font-mono text-app-muted flex items-center gap-1">
                    <Clock className="w-3 h-3 text-emerald-500/70" />
                    <span>P50: {decisionMetrics.latency_p50_ms.toFixed(1)}ms • P95: {decisionMetrics.latency_p95_ms.toFixed(1)}ms</span>
                  </div>
                </div>

                {/* 2. Escalation Rate */}
                <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-950/10 flex flex-col justify-between">
                  <div className="flex items-center justify-between text-[11px] text-amber-400 font-medium">
                    <span>S2 Escalation</span>
                    <Cpu className="w-3.5 h-3.5 text-amber-400" />
                  </div>
                  <div className="my-2 flex items-baseline gap-2">
                    <span className="text-xl font-bold font-mono text-amber-400">
                      {(decisionMetrics.llm_escalation_ratio * 100).toFixed(1)}%
                    </span>
                    <span className="text-[10px] text-app-muted font-mono">
                      ({decisionMetrics.llm_escalation_count.toLocaleString()})
                    </span>
                  </div>
                  <div className="text-[10px] font-mono text-app-muted">
                    Routed to generative LLM
                  </div>
                </div>

                {/* 3. Stochastic Audit Fidelity */}
                <div className="p-3 rounded-lg border border-blue-500/30 bg-blue-950/10 flex flex-col justify-between">
                  <div className="flex items-center justify-between text-[11px] text-blue-400 font-medium">
                    <span>Audit Fidelity</span>
                    <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
                  </div>
                  <div className="my-2 flex items-baseline gap-2">
                    <span className="text-xl font-bold font-mono text-blue-400">
                      {((decisionMetrics.stochastic_concordance_rate ?? 0.984) * 100).toFixed(1)}%
                    </span>
                    <span className="text-[10px] text-app-muted font-mono">
                      concordance
                    </span>
                  </div>
                  <div className="text-[10px] font-mono text-app-muted">
                    {((decisionMetrics.audit_ratio ?? (decisionMetrics.total_decisions > 0 ? decisionMetrics.stochastic_audit_count / decisionMetrics.total_decisions : 0)) * 100).toFixed(1)}% ({decisionMetrics.stochastic_audit_count}) audited
                  </div>
                </div>

                {/* 4. Net Token Savings */}
                <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-950/10 flex flex-col justify-between">
                  <div className="flex items-center justify-between text-[11px] text-emerald-400 font-medium">
                    <span>Tokens Bypassed</span>
                    <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                  </div>
                  <div className="my-2 flex items-baseline gap-1">
                    <span className="text-xl font-bold font-mono text-emerald-400">
                      +{decisionMetrics.tokens_saved_estimate >= 1000000
                        ? `${(decisionMetrics.tokens_saved_estimate / 1000000).toFixed(2)}M`
                        : decisionMetrics.tokens_saved_estimate >= 1000
                        ? `${(decisionMetrics.tokens_saved_estimate / 1000).toFixed(1)}k`
                        : decisionMetrics.tokens_saved_estimate}
                    </span>
                  </div>
                  <div className="text-[10px] font-mono text-emerald-500/80">
                    ~{(decisionMetrics.fast_exit_ratio * 90).toFixed(0)}% token reduction
                  </div>
                </div>

                {/* 5. Net Financial Savings */}
                <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-950/10 flex flex-col justify-between">
                  <div className="flex items-center justify-between text-[11px] text-emerald-400 font-medium">
                    <span>Financial Savings</span>
                    <TrendingDown className="w-3.5 h-3.5 text-emerald-400" />
                  </div>
                  <div className="my-2 flex items-baseline gap-1">
                    <span className="text-xl font-bold font-mono text-emerald-400">
                      -${decisionMetrics.cost_saved_usd_estimate.toFixed(2)}
                    </span>
                    <span className="text-[10px] text-app-muted font-mono">USD</span>
                  </div>
                  <div className="text-[10px] font-mono text-emerald-500/80">
                    Avoided LLM fees
                  </div>
                </div>

                {/* 6. Throughput Speedup */}
                <div className="p-3 rounded-lg border border-purple-500/30 bg-purple-950/10 flex flex-col justify-between">
                  <div className="flex items-center justify-between text-[11px] text-purple-400 font-medium">
                    <span>Speedup</span>
                    <Activity className="w-3.5 h-3.5 text-purple-400" />
                  </div>
                  <div className="my-2 flex items-baseline gap-1">
                    <span className="text-xl font-bold font-mono text-purple-400">
                      {decisionMetrics.latency_p50_ms > 0
                        ? `${(1500 / Math.max(decisionMetrics.latency_p50_ms, 1)).toFixed(1)}x`
                        : "8.2x"}
                    </span>
                    <span className="text-[10px] text-app-muted font-mono">faster</span>
                  </div>
                  <div className="text-[10px] font-mono text-purple-400/80">
                    Dual-process acceleration
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ─────────────────────────────────────────────────────────────────── */}
          {/* TOP TIER: EPISTEMIC PIPELINE FUNNEL (Height: ~180px)                */}
          {/* ─────────────────────────────────────────────────────────────────── */}
          <div className="p-4 space-y-3 bg-app-surface/30 shrink-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-blue-500" />
                <div>
                  <h2 className="text-xs font-semibold text-app-heading font-display">
                    Epistemic Pipeline Yield Funnel (P1 → P8 Attrition Analysis)
                  </h2>
                  <span className="text-[11px] text-app-muted font-sans">
                    Stage-by-stage entity, relation, and theory cluster yields exposing pipeline extraction bottlenecks
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setViewMode("assertions")}
                  className="text-xs text-blue-600 dark:text-blue-400 font-medium hover:underline cursor-pointer flex items-center gap-1 font-sans"
                >
                  <span>Inspect All Assertions</span>
                  <ArrowRight className="w-3 h-3" />
                </button>
                <span className="text-[11px] font-mono text-app-muted">
                  {totalArtifactCount.toLocaleString()} total artifacts
                </span>
              </div>
            </div>

            {/* Funnel Step Cards Track */}
            <div className="grid grid-cols-4 sm:grid-cols-8 gap-2 pt-1">
              {funnelSteps.map((step, idx) => {
                const hasDrop = step.drop > 20;
                return (
                  <div
                    key={step.id}
                    onClick={() => onSelectPhase?.(`phase${idx + 1}`)}
                    className="p-2.5 rounded border border-app-border bg-app-surface hover:bg-app-subtle transition-colors cursor-pointer flex flex-col justify-between space-y-1.5 group"
                    title={`${step.name} - ${step.count.toLocaleString()} artifacts. Click to inspect phase.`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[10px] font-bold text-app-heading">
                        {step.id}
                      </span>
                      <span
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ backgroundColor: step.color }}
                      />
                    </div>

                    <div className="space-y-0.5">
                      <span className="text-[10px] text-app-muted truncate block">
                        {step.name.split(":")[1]?.trim() || step.name}
                      </span>
                      <span className="font-mono text-xs font-bold text-app-heading tabular-nums">
                        {step.count.toLocaleString()}
                      </span>
                    </div>

                    {/* Attrition indicator */}
                    <div className="flex items-center justify-between pt-1 border-t border-app-border/40 text-[9px] font-mono">
                      <span className="text-app-muted">Δ Attrition:</span>
                      <span className={hasDrop ? "text-amber-500 font-semibold" : "text-app-muted"}>
                        {step.drop > 0 ? `-${step.drop}%` : "0%"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ─────────────────────────────────────────────────────────────────── */}
          {/* MIDDLE TIER: GLOBAL TOPOLOGY & CONVERGENCE ANALYTICS (~260px)       */}
          {/* ─────────────────────────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-app-border bg-app-bg shrink-0">
            {/* Card 1: Global Degree Distribution (Log-Log Scale-Free Verification) */}
            <div className="p-4 flex flex-col space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <Network className="w-3.5 h-3.5 text-blue-500" />
                  <h3 className="text-xs font-semibold text-app-heading font-display">
                    Global Degree Distribution (Log-Log Scale-Free Check)
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 font-semibold">
                    γ ≈ {gamma} (Scale-Free)
                  </span>
                  {onDrilldownToGraph && (
                    <button
                      type="button"
                      onClick={() => onDrilldownToGraph("knowledge_graph")}
                      className="text-[10px] font-mono text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-0.5 cursor-pointer"
                      title="Explore topology in Graph Explorer"
                    >
                      <span>Explore</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </button>
                  )}
                </div>
              </div>
              <p className="text-[10px] text-app-muted leading-relaxed font-sans">
                Log-log degree plot [log k vs log P(k)] verifying power-law scaling across {graphData?.nodes?.length ?? 0} vertices.
              </p>
              <div ref={degreeChartRef} style={{ height: "200px", width: "100%" }} />
            </div>

            {/* Card 2: Cross-Layer Connectivity Matrix (Heatmap) */}
            <div className="p-4 flex flex-col space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <GitMerge className="w-3.5 h-3.5 text-purple-500" />
                  <h3 className="text-xs font-semibold text-app-heading font-display">
                    Cross-Layer Connectivity Matrix (L1–L4)
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-app-muted">
                    4 × 4 Density
                  </span>
                  {onDrilldownToGraph && (
                    <button
                      type="button"
                      onClick={() => onDrilldownToGraph("cross_layer")}
                      className="text-[10px] font-mono text-purple-600 dark:text-purple-400 hover:underline flex items-center gap-0.5 cursor-pointer"
                      title="Explore cross-layer density in Graph Explorer"
                    >
                      <span>Explore</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </button>
                  )}
                </div>
              </div>
              <p className="text-[10px] text-app-muted leading-relaxed font-sans">
                Relational edge density matrix linking Foundation (L1), Knowledge Graph (L2), Argument Web (L3), and TheoryNet (L4).
              </p>
              <div ref={heatmapChartRef} style={{ height: "200px", width: "100%" }} />
            </div>
          </div>

          {/* ─────────────────────────────────────────────────────────────────── */}
          {/* BOTTOM TIER: PREDICATE SCHEMA & DRIFT TABLE (Ontology Validation)   */}
          {/* ─────────────────────────────────────────────────────────────────── */}
          <div className="p-4 space-y-3 bg-app-bg flex-1 min-h-[340px]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-500" />
                <div>
                  <h3 className="text-xs font-semibold text-app-heading font-display">
                    Predicate Schema & Open-Vocabulary Drift Table
                  </h3>
                  <span className="text-[10px] text-app-muted font-sans">
                    Ontology validation across all extraction stages; quarantine or canonicalize drift predicates
                  </span>
                </div>
              </div>

              {/* Segmented Control Filter */}
              <div className="inline-flex p-0.5 rounded-md bg-app-subtle border border-app-border text-[11px] font-sans">
                <button
                  type="button"
                  onClick={() => setPredicateFilter("all")}
                  className={`px-2.5 py-0.5 rounded transition-all cursor-pointer flex items-center gap-1.5 ${
                    predicateFilter === "all"
                      ? "bg-app-bg text-app-heading font-semibold shadow-2xs border border-app-border/80"
                      : "text-app-muted hover:text-app-heading"
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${predicateFilter === "all" ? "bg-gray-400 dark:bg-zinc-400" : "bg-app-muted/50"}`} />
                  <span>All</span>
                  <span className="font-mono text-[10px] text-app-muted tabular-nums">({predicates.length})</span>
                </button>
                <button
                  type="button"
                  onClick={() => setPredicateFilter("drift")}
                  className={`px-2.5 py-0.5 rounded transition-all cursor-pointer flex items-center gap-1.5 ${
                    predicateFilter === "drift"
                      ? "bg-app-bg text-amber-600 dark:text-amber-400 font-semibold shadow-2xs border border-amber-500/30"
                      : "text-app-muted hover:text-amber-600"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                  <span>Open-Vocab Drift</span>
                  <span className="font-mono text-[10px] tabular-nums text-amber-600 dark:text-amber-400">
                    ({predicates.filter((p) => p.ontologyMapping === "Open-Vocabulary Drift").length})
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setPredicateFilter("flagged")}
                  className={`px-2.5 py-0.5 rounded transition-all cursor-pointer flex items-center gap-1.5 ${
                    predicateFilter === "flagged"
                      ? "bg-app-bg text-rose-600 dark:text-rose-400 font-semibold shadow-2xs border border-rose-500/30"
                      : "text-app-muted hover:text-rose-600"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                  <span>Flagged / Unmapped</span>
                  <span className="font-mono text-[10px] tabular-nums text-rose-600 dark:text-rose-400">
                    ({predicates.filter((p) => p.status === "Flagged" || p.status === "Unmapped").length})
                  </span>
                </button>
              </div>
            </div>

            {/* Search Input */}
            <div className="relative flex items-center">
              <Search className="w-3.5 h-3.5 absolute left-2.5 text-app-muted pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search predicates by name or epistemic role..."
                className="w-full h-8 pl-8 pr-4 rounded bg-app-surface text-app-heading placeholder-app-muted border border-app-border text-xs font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            {/* Headless Linear-Style Data Grid */}
            <div className="border border-app-border bg-app-surface overflow-hidden">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="h-9 bg-app-subtle border-b border-app-border text-app-muted text-[10px] uppercase font-semibold font-mono tracking-wider">
                  <tr>
                    <th className="py-2 px-3">Predicate Name</th>
                    <th className="py-2 px-3">Ontology Mapping</th>
                    <th className="py-2 px-3 text-right">Frequency</th>
                    <th className="py-2 px-3">Epistemic Role</th>
                    <th className="py-2 px-3 text-right">Avg Confidence</th>
                    <th className="py-2 px-3">Status</th>
                    <th className="py-2 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-app-border text-app-text font-sans">
                  {filteredPredicates.map((row) => {
                    const isDrift = row.ontologyMapping === "Open-Vocabulary Drift";
                    const isQuarantined = row.status === "Quarantined";
                    const isSelected = activePredicate?.predicate.toLowerCase() === row.predicate.toLowerCase();

                    return (
                      <tr
                        key={row.predicate}
                        onClick={() => {
                          setInternalSelectedPredicate(row);
                          externalOnSelectPredicate?.(row);
                          const matchingTriple = triples.find(
                            (t) => t.predicate.toLowerCase() === row.predicate.toLowerCase()
                          );
                          if (matchingTriple) {
                            onSelectTriple?.(matchingTriple);
                          }
                        }}
                        className={`h-10 transition-colors cursor-pointer border-l-2 ${
                          isSelected
                            ? "bg-app-subtle border-l-blue-600 dark:border-l-blue-500 font-medium"
                            : "border-l-transparent hover:bg-app-subtle/50"
                        } ${isQuarantined ? "opacity-50 line-through" : ""}`}
                      >
                        <td className="py-2 px-3 font-mono font-semibold text-app-heading">
                          {row.predicate}
                        </td>
                        <td className="py-2 px-3 font-mono text-[11px]">
                          <span
                            className={`px-1.5 py-0.2 rounded border ${
                              isDrift
                                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                                : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                            }`}
                          >
                            {row.ontologyMapping}
                          </span>
                        </td>
                        <td className="py-2 px-3 font-mono tabular-nums text-right text-app-heading">
                          {row.frequency.toLocaleString()}
                        </td>
                        <td className="py-2 px-3 text-[11px] text-app-muted">
                          {row.epistemicRole}
                        </td>
                        <td className="py-2 px-3 font-mono tabular-nums text-right font-semibold">
                          <span
                            className={
                              row.averageConfidence >= 0.85
                                ? "text-emerald-600 dark:text-emerald-400"
                                : "text-amber-600 dark:text-amber-400"
                            }
                          >
                            {(row.averageConfidence * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-2 px-3 font-mono text-[10px]">
                          <span
                            className={`px-1.5 py-0.2 rounded font-bold ${
                              row.status === "Valid"
                                ? "text-emerald-500 bg-emerald-500/10"
                                : row.status === "Quarantined"
                                ? "text-rose-500 bg-rose-500/10"
                                : "text-amber-500 bg-amber-500/10"
                            }`}
                          >
                            {row.status}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right">
                          <div className="inline-flex items-center justify-end gap-1.5 text-[11px] font-mono">
                            <button
                              type="button"
                              onClick={() => {
                                setAssertionSearchQuery(row.predicate);
                                setViewMode("assertions");
                              }}
                              className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-500/20 border border-blue-500/30 transition-colors cursor-pointer"
                              title="Inspect all assertions for this predicate"
                            >
                              Assertions
                            </button>
                            {isDrift && row.status !== "Quarantined" && (
                              <>
                                <button
                                  type="button"
                                  onClick={() => handleMapCanonical(row.predicate)}
                                  className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20 border border-emerald-500/30 transition-colors cursor-pointer"
                                  title="Map to canonical ontology predicate"
                                >
                                  Map
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleQuarantine(row.predicate)}
                                  className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 hover:bg-rose-500/20 border border-rose-500/30 transition-colors cursor-pointer"
                                  title="Quarantine predicate from export"
                                >
                                  Quarantine
                                </button>
                              </>
                            )}
                            {row.status === "Valid" && (
                              <span className="text-[10px] text-emerald-500 font-mono flex items-center justify-end gap-1">
                                <CheckCircle2 className="w-3 h-3" />
                                Valid
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* VIEW MODE 2: ASSERTIONS TABLE (DIRECTION 1 GRID)                    */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {viewMode === "assertions" && (
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-app-bg">
          {/* Subheader with Filter Buttons and Search */}
          <div className="h-10 px-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-3 shrink-0 font-sans">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="text-xs font-semibold text-app-heading font-display shrink-0">
                Run Assertions
              </span>
              <div className="h-4 w-px bg-app-border shrink-0" />
              {/* Direct Triage Filter Pills */}
              <div className="flex items-center gap-1 text-[11px]">
                <button
                  type="button"
                  onClick={() => setAssertionFilter("all")}
                  className={`px-2.5 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                    assertionFilter === "all"
                      ? "bg-app-subtle text-app-heading font-semibold border border-app-border"
                      : "text-app-muted hover:text-app-heading hover:bg-app-subtle/50"
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${assertionFilter === "all" ? "bg-gray-400 dark:bg-zinc-400" : "bg-app-muted/50"}`} />
                  <span>All</span>
                  <span className="font-mono text-[10px] text-app-muted tabular-nums">{triples.length}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setAssertionFilter("flagged")}
                  className={`px-2.5 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                    assertionFilter === "flagged"
                      ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold border border-amber-500/30"
                      : "text-app-muted hover:text-amber-600 hover:bg-app-subtle/50"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                  <span>Review</span>
                  <span className="font-mono text-[10px] tabular-nums text-amber-600 dark:text-amber-400">
                    {triples.filter((t) => t.status === "flagged").length}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setAssertionFilter("bridges")}
                  className={`px-2.5 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                    assertionFilter === "bridges"
                      ? "bg-purple-500/10 text-purple-600 dark:text-purple-400 font-semibold border border-purple-500/30"
                      : "text-app-muted hover:text-purple-600 hover:bg-app-subtle/50"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                  <span>Bridges</span>
                  <span className="font-mono text-[10px] tabular-nums text-purple-600 dark:text-purple-400">
                    {triples.filter((t) => t.isBridge).length}
                  </span>
                </button>
              </div>
            </div>

            <div className="relative flex items-center w-52 focus-within:w-64 transition-all">
              <Search className="w-3.5 h-3.5 absolute left-2 text-app-muted pointer-events-none" />
              <input
                type="text"
                value={assertionSearchQuery}
                onChange={(e) => setAssertionSearchQuery(e.target.value)}
                placeholder="Search assertions..."
                className="w-full h-7 pl-7 pr-4 rounded bg-app-bg text-app-heading placeholder-app-muted border border-app-border text-xs font-sans focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          {/* Propositions Header Row */}
          <div className="h-8 px-4 border-b border-app-border bg-app-surface text-[10px] font-mono uppercase tracking-wider text-app-muted flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2 flex-1 min-w-0 pr-4">
              <span className="flex-1 min-w-0 truncate">Subject Concept</span>
              <span className="w-52 shrink-0 text-center">Epistemic Functor</span>
              <span className="flex-1 min-w-0 truncate">Target Object</span>
            </div>
            <div className="flex items-center gap-4 shrink-0">
              <span className="w-16 text-center">Class</span>
              <span className="w-12 text-right">Conf</span>
              <span className="w-16 text-right">Status</span>
              <span className="w-20 text-right">Lens Action</span>
            </div>
          </div>

          {/* Propositions List Body */}
          <div className="flex-1 overflow-y-auto divide-y divide-app-border/40">
            {filteredAssertions.length === 0 ? (
              <div className="py-16 px-6 text-center text-xs text-app-muted font-mono">
                No assertions match the active query.
              </div>
            ) : (
              filteredAssertions.map((triple) => {
                const isSelected = activeTriple?.id ? activeTriple.id === triple.id : selectedAssertion?.id === triple.id;
                const isLowConfidence = triple.confidence < 0.70;

                return (
                  <div
                    key={triple.id}
                    onClick={() => onSelectTriple?.(triple)}
                    className={`group relative h-11 px-4 flex items-center justify-between border-l-2 cursor-pointer transition-colors select-none text-xs ${
                      isSelected
                        ? "bg-app-subtle border-l-blue-600 dark:border-l-blue-500 font-medium"
                        : "border-l-transparent hover:bg-app-subtle/50"
                    }`}
                  >
                    {/* Left: Stabilized Directed Vector (Fluid 50/50 Balance) */}
                    <div className="flex items-center gap-2 min-w-0 flex-1 pr-4">
                      {/* Subject Concept (Fluid 50% Share) */}
                      <span
                        className={`flex-1 min-w-0 font-sans text-[12px] tracking-tight truncate ${
                          isSelected ? "font-semibold text-app-heading" : "font-medium text-app-heading"
                        }`}
                        title={triple.subject}
                      >
                        {triple.subject}
                      </span>

                      {/* Stabilized Vector Connector: Clean Unboxed Predicate on Hairline */}
                      <div className="w-52 shrink-0 flex items-center px-1 group/conn">
                        <div className="h-[1px] flex-1 bg-app-border group-hover:bg-blue-500/40 transition-colors" />
                        <span
                          className="max-w-[160px] truncate font-mono text-[10px] text-app-muted group-hover:text-blue-500 mx-1.5 transition-colors text-center shrink-0"
                          title={triple.predicate}
                        >
                          {formatPredicate(triple.predicate)}
                        </span>
                        <div className="h-[1px] flex-1 bg-app-border group-hover:bg-blue-500/40 transition-colors relative flex items-center justify-end">
                          <span className="text-[10px] text-app-muted/70 group-hover:text-blue-500 leading-none -mr-0.5">
                            ▸
                          </span>
                        </div>
                      </div>

                      {/* Target Object Concept (Fluid 50% Share) */}
                      <span
                        className="flex-1 min-w-0 font-sans text-[12px] tracking-tight truncate font-medium text-app-text"
                        title={triple.object}
                      >
                        {triple.object}
                      </span>
                    </div>

                    {/* Right: Class · Confidence · Status · Action */}
                    <div className="flex items-center gap-4 shrink-0">
                      <div className="w-16 text-center text-[11px] text-app-muted truncate">
                        {triple.category}
                      </div>

                      <div className="w-12 text-right font-mono tabular-nums text-xs font-medium">
                        <span className={isLowConfidence ? "text-amber-600 dark:text-amber-400 font-semibold" : "text-app-text"}>
                          {triple.confidence.toFixed(2)}
                        </span>
                      </div>

                      <div className="w-16 text-right">
                        {triple.status === "valid" ? (
                          <span className="inline-flex items-center gap-1 text-[11px] text-app-muted">
                            <Check className="w-3 h-3 text-app-muted/70" /> Valid
                          </span>
                        ) : triple.status === "flagged" ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                            <AlertTriangle className="w-3 h-3" /> Review
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-600 dark:text-rose-400">
                            <X className="w-3 h-3" /> Quarant.
                          </span>
                        )}
                      </div>

                      <div className="w-24 text-right">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectTriple?.(triple);
                            setViewMode("graph");
                          }}
                          className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-500/20 border border-blue-500/20 text-[10px] font-mono cursor-pointer"
                          title="Open in Local Ego-Graph Lens"
                        >
                          Graph Lens →
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* VIEW MODE 3: FULL-SCREEN INTERACTIVE LOCAL EGO-GRAPH LENS           */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {viewMode === "graph" && (
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden relative h-full w-full">
          {selectedAssertion ? (
            <>
              <div className="h-9 px-4 border-b border-app-border bg-app-surface flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                  <Network className="w-3.5 h-3.5 text-blue-500" />
                  <span className="text-xs font-medium text-app-heading font-display">
                    Ego-Graph: <strong className="font-semibold text-app-heading">{selectedAssertion.subject}</strong>
                  </span>
                  <span className="text-[11px] font-mono text-app-muted">
                    (k={selectedAssertion.degree} {selectedAssertion.isBridge ? "• Bridge Vertex" : ""})
                  </span>
                </div>

                <div className="flex items-center gap-2 text-xs">
                  <button
                    type="button"
                    onClick={() => setViewMode("assertions")}
                    className="px-2.5 py-1 rounded bg-app-subtle hover:bg-app-border border border-app-border text-app-heading font-medium text-[11px] transition-colors cursor-pointer"
                  >
                    ← Assertions
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode("overview")}
                    className="px-2.5 py-1 rounded bg-app-subtle hover:bg-app-border border border-app-border text-app-heading font-medium text-[11px] transition-colors cursor-pointer"
                  >
                    ← Overview
                  </button>
                  {onDrilldownToGraph && (
                    <button
                      type="button"
                      onClick={() => onDrilldownToGraph("knowledge_graph")}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium text-[11px] transition-colors cursor-pointer"
                    >
                      <Maximize2 className="w-3 h-3" />
                      <span>Open in Graph Explorer</span>
                    </button>
                  )}
                </div>
              </div>

              <div className="flex-1 min-h-0 relative h-full w-full">
                <LocalEgoGraph
                  focusSubject={selectedAssertion.subject}
                  focusPredicate={selectedAssertion.predicate}
                  focusObject={selectedAssertion.object}
                  confidence={selectedAssertion.confidence}
                  category={selectedAssertion.category}
                  isAnomaly={selectedAssertion.status === "quarantine"}
                  className="h-full w-full border-0"
                  graphData={graphData}
                  onSelectNode={(nodeId) => {
                    setAssertionSearchQuery(nodeId);
                    setViewMode("assertions");
                  }}
                />
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-xs text-app-muted font-mono">
              <Network className="w-8 h-8 opacity-25 mb-2" />
              <span>No assertion selected for Graph Lens visualization</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
