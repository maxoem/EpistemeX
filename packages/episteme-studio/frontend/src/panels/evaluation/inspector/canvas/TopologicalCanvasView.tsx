import React, { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { Graph, NodeEvent, EdgeEvent, CanvasEvent } from "@antv/g6";
import {
  Focus,
  Maximize2,
  Minimize2,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Layers,
  Sparkles,
} from "lucide-react";
import { useEvaluationStore } from "../../../../store/evaluationStore";
import { CanvasEvaluationHud } from "./CanvasEvaluationHud";
import { TopologicalErrorQuad } from "./TopologicalErrorQuad";
import { AmbiguousAliasDrawer } from "./AmbiguousAliasDrawer";
import type {
  EvaluationEdgeOverlay,
  EvaluationNodeOverlay,
} from "../../../../api/types";

const BOURBAKI_HULL_PALETTE: Record<string, { fill: string; stroke: string; label: string }> = {
  Mp: { fill: "#3b82f6", stroke: "#2563eb", label: "Mp: Potential Models" },
  M: { fill: "#10b981", stroke: "#059669", label: "M: Actual Models" },
  Mpp: { fill: "#f59e0b", stroke: "#d97706", label: "Mpp: Partial Potential" },
  C: { fill: "#8b5cf6", stroke: "#7c3aed", label: "C: Constraints" },
  I: { fill: "#f97316", stroke: "#ea580c", label: "I: Intended Applications" },
  potential_models: { fill: "#3b82f6", stroke: "#2563eb", label: "Mp: Potential Models" },
  actual_models: { fill: "#10b981", stroke: "#059669", label: "M: Actual Models" },
  intended_applications: { fill: "#f97316", stroke: "#ea580c", label: "I: Intended Applications" },
  constraints: { fill: "#8b5cf6", stroke: "#7c3aed", label: "C: Constraints" },
  partial_potential_models: { fill: "#f59e0b", stroke: "#d97706", label: "Mpp: Partial Potential" },
};

export const TopologicalCanvasView: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);

  const {
    activeReport,
    graphOverlay,
    isLoadingOverlay,
    fetchGraphOverlay,
    selectedOverlayItem,
    setSelectedOverlayItem,
    alignmentFilters,
    ghostOpacity,
    bourbakiHullEnabled,
    selectedBourbakiClasses,
    cycleHighlightNodeIds,
  } = useEvaluationStore();

  const [layoutMode, setLayoutMode] = useState<"d3-force" | "dagre" | "circular">("d3-force");

  // Determine dark mode
  const isDark =
    typeof document !== "undefined" &&
    document.documentElement.classList.contains("dark");

  // Fetch overlay if not present
  useEffect(() => {
    if (activeReport && !graphOverlay && !isLoadingOverlay) {
      fetchGraphOverlay(activeReport.evaluation_id);
    }
  }, [activeReport, graphOverlay, isLoadingOverlay, fetchGraphOverlay]);

  // Normalize Bourbaki class of a node
  const getNodeClassCategory = useCallback((node: EvaluationNodeOverlay): string => {
    if (node.symbol) {
      if (node.symbol.startsWith("Mp")) return "Mp";
      if (node.symbol.startsWith("Mpp")) return "Mpp";
      if (node.symbol.startsWith("M")) return "M";
      if (node.symbol.startsWith("C")) return "C";
      if (node.symbol.startsWith("I")) return "I";
    }
    const c = (node.class_name || "").toLowerCase();
    if (c.includes("potential_model") || c.includes("potential")) return "Mp";
    if (c.includes("partial")) return "Mpp";
    if (c.includes("actual")) return "M";
    if (c.includes("constraint")) return "C";
    if (c.includes("intended") || c.includes("application")) return "I";
    return "M";
  }, []);

  // Filter nodes based on alignment filters and Bourbaki class selection
  const filteredNodes = useMemo(() => {
    if (!graphOverlay?.nodes) return [];
    return graphOverlay.nodes.filter((node) => {
      // 1. Alignment filter
      if (node.is_ghost || node.alignment_status === "false_negative") {
        if (!alignmentFilters.fn) return false;
      } else if (node.alignment_status === "true_positive") {
        if (!alignmentFilters.tp) return false;
      } else if (node.alignment_status === "false_positive") {
        if (!alignmentFilters.fp) return false;
      } else if (node.alignment_status === "borderline") {
        if (!alignmentFilters.borderline) return false;
      }

      // 2. Bourbaki class filter
      const cat = getNodeClassCategory(node);
      if (!selectedBourbakiClasses.has(cat)) {
        return false;
      }

      return true;
    });
  }, [graphOverlay, alignmentFilters, selectedBourbakiClasses, getNodeClassCategory]);

  const filteredNodeIds = useMemo(
    () => new Set(filteredNodes.map((n) => n.id)),
    [filteredNodes]
  );

  // Filter edges based on visible nodes and edge alignment filters
  const filteredEdges = useMemo(() => {
    if (!graphOverlay?.edges) return [];
    return graphOverlay.edges.filter((edge) => {
      // Must connect visible nodes
      if (!filteredNodeIds.has(edge.source) || !filteredNodeIds.has(edge.target)) {
        return false;
      }

      // Alignment filter
      if (edge.is_ghost || edge.alignment_status === "false_negative") {
        if (!alignmentFilters.fn) return false;
      } else if (edge.alignment_status === "true_positive") {
        if (!alignmentFilters.tp) return false;
      } else if (edge.alignment_status === "false_positive") {
        if (!alignmentFilters.fp) return false;
      } else if (edge.alignment_status === "polarity_conflict") {
        if (!alignmentFilters.polarity) return false;
      }

      return true;
    });
  }, [graphOverlay, filteredNodeIds, alignmentFilters]);

  // Compute borderline count
  const borderlineCount = useMemo(() => {
    if (!graphOverlay?.nodes) return 0;
    return graphOverlay.nodes.filter(
      (n) =>
        n.alignment_status === "borderline" ||
        (n.similarity_score >= 0.75 && n.similarity_score <= 0.88 && !n.is_ghost)
    ).length;
  }, [graphOverlay]);

  // Compute node visual styles
  const getNodeStyle = useCallback(
    (node: EvaluationNodeOverlay) => {
      const isSelected =
        selectedOverlayItem?.type === "node" && selectedOverlayItem.item.id === node.id;
      const isCycleNode = cycleHighlightNodeIds?.includes(node.id);
      const isCycleActive = Boolean(cycleHighlightNodeIds && cycleHighlightNodeIds.length > 0);

      // Base colors based on alignment
      let fill = isDark ? "#064e3b" : "#ecfdf5";
      let stroke = isDark ? "#10b981" : "#059669";
      let lineDash: number[] | undefined = undefined;
      let opacity = 1.0;
      let halo = isSelected;
      let haloStroke = "#38bdf8";

      if (node.is_ghost || node.alignment_status === "false_negative") {
        fill = isDark ? "#27272a" : "#f1f5f9";
        stroke = isDark ? "#71717a" : "#94a3b8";
        lineDash = [4, 4];
        opacity = ghostOpacity;
      } else if (node.alignment_status === "false_positive") {
        fill = isDark ? "#450a0a" : "#fef2f2";
        stroke = isDark ? "#f87171" : "#dc2626";
      } else if (node.alignment_status === "borderline") {
        fill = isDark ? "#2e1065" : "#f5f3ff";
        stroke = isDark ? "#a78bfa" : "#7c3aed";
        halo = true;
        haloStroke = "#a78bfa";
      }

      // Cycle highlight override
      if (isCycleActive) {
        if (isCycleNode) {
          halo = true;
          haloStroke = "#ef4444";
          stroke = "#ef4444";
          opacity = 1.0;
        } else {
          opacity = 0.25;
        }
      }

      // Selected override
      if (isSelected) {
        halo = true;
        haloStroke = "#38bdf8";
        stroke = "#38bdf8";
      }

      return {
        size: 38,
        fill,
        stroke,
        lineWidth: isSelected ? 3 : 2,
        lineDash,
        opacity,
        halo,
        haloStroke,
        haloLineWidth: isSelected ? 8 : 5,
        haloOpacity: 0.4,
        labelText: node.label,
        labelFill: isDark ? "#f1f5f9" : "#1e293b",
        labelFontSize: 11,
        labelFontWeight: isSelected ? "600" : "500",
        labelBackground: true,
        labelBackgroundFill: isDark ? "#09090b" : "#ffffff",
        labelBackgroundOpacity: 0.85,
        labelBackgroundPadding: [2, 5],
        labelBackgroundRadius: 4,
        badgeText: node.symbol || undefined,
        badgeFill: stroke,
        badgeFontSize: 9,
      };
    },
    [selectedOverlayItem, ghostOpacity, cycleHighlightNodeIds, isDark]
  );

  // Compute edge visual styles
  const getEdgeStyle = useCallback(
    (edge: EvaluationEdgeOverlay) => {
      const isSelected =
        selectedOverlayItem?.type === "edge" && selectedOverlayItem.item.id === edge.id;
      const isCycleEdge =
        cycleHighlightNodeIds &&
        cycleHighlightNodeIds.includes(edge.source) &&
        cycleHighlightNodeIds.includes(edge.target);
      const isCycleActive = Boolean(cycleHighlightNodeIds && cycleHighlightNodeIds.length > 0);

      let stroke = isDark ? "#10b981" : "#059669";
      let lineWidth = 2;
      let lineDash: number[] | undefined = undefined;
      let opacity = 0.9;
      let halo = isSelected;

      if (edge.is_ghost || edge.alignment_status === "false_negative") {
        stroke = isDark ? "#71717a" : "#94a3b8";
        lineDash = [5, 4];
        opacity = ghostOpacity;
      } else if (edge.alignment_status === "false_positive") {
        stroke = isDark ? "#f87171" : "#dc2626";
        lineWidth = 2.5;
        lineDash = [6, 3];
      } else if (edge.alignment_status === "polarity_conflict") {
        stroke = isDark ? "#fbbf24" : "#d97706";
        lineWidth = 3.5;
      }

      // Cycle highlight override
      if (isCycleActive) {
        if (isCycleEdge) {
          stroke = "#ef4444";
          lineWidth = 4;
          opacity = 1.0;
        } else {
          opacity = 0.15;
        }
      }

      if (isSelected) {
        stroke = "#38bdf8";
        lineWidth = 3.5;
        halo = true;
      }

      return {
        stroke,
        lineWidth,
        lineDash,
        opacity,
        halo,
        haloStroke: "#38bdf8",
        haloLineWidth: 6,
        haloOpacity: 0.35,
        endArrow: {
          path: "M 0,0 L 8,4 L 8,-4 Z",
          fill: stroke,
        },
        labelText: edge.alignment_status === "polarity_conflict" ? `⚡ ${edge.predicate}` : edge.predicate,
        labelFill: isDark ? "#cbd5e1" : "#475569",
        labelFontSize: 10,
        labelBackground: true,
        labelBackgroundFill: isDark ? "#09090b" : "#ffffff",
        labelBackgroundOpacity: 0.85,
        labelBackgroundPadding: [1, 4],
        labelBackgroundRadius: 3,
      };
    },
    [selectedOverlayItem, ghostOpacity, cycleHighlightNodeIds, isDark]
  );

  // Sync Bourbaki Hull Plugins
  const syncHullPlugins = useCallback(() => {
    const graph = graphRef.current;
    if (!graph || (graph as any).destroyed) return;

    if (!bourbakiHullEnabled) {
      try {
        graph.setPlugins([]);
        graph.draw().catch(() => {});
      } catch (e) {}
      return;
    }

    // Group nodes by Bourbaki category
    const clusters: Record<string, string[]> = {};
    for (const node of filteredNodes) {
      const cat = getNodeClassCategory(node);
      if (!clusters[cat]) clusters[cat] = [];
      clusters[cat].push(node.id);
    }

    const hullPlugins = Object.entries(clusters)
      .map(([catKey, members]) => {
        if (members.length === 0) return null;
        const palette = BOURBAKI_HULL_PALETTE[catKey] || {
          fill: "#3b82f6",
          stroke: "#2563eb",
          label: catKey,
        };
        return {
          key: `hull-bourbaki-${catKey}`,
          type: "hull",
          members,
          padding: 22,
          corner: "smooth" as const,
          fill: palette.fill,
          stroke: palette.stroke,
          fillOpacity: isDark ? 0.15 : 0.1,
          strokeOpacity: 0.65,
          lineWidth: 2,
          labelText: `${palette.label} (${members.length})`,
          labelFill: isDark ? "#f1f5f9" : "#1e293b",
          labelFontSize: 11,
          labelBackground: true,
          labelBackgroundFill: isDark ? "#09090b" : "#ffffff",
          labelBackgroundOpacity: 0.85,
          labelBackgroundPadding: [2, 6],
        };
      })
      .filter(Boolean);

    try {
      graph.setPlugins(hullPlugins as any);
      graph.draw().catch(() => {});
    } catch (err) {
      console.warn("Failed to set Bourbaki hull plugins:", err);
    }
  }, [bourbakiHullEnabled, filteredNodes, getNodeClassCategory, isDark]);

  // Initialize and maintain G6 instance
  useEffect(() => {
    if (!containerRef.current) return;

    containerRef.current.innerHTML = "";

    const initialG6Data = {
      nodes: filteredNodes.map((node) => ({
        id: node.id,
        data: { ...node },
        style: getNodeStyle(node),
      })),
      edges: filteredEdges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        data: { ...edge },
        style: getEdgeStyle(edge),
      })),
    };

    const graph = new Graph({
      container: containerRef.current,
      autoFit: "view",
      autoResize: true,
      theme: isDark ? "dark" : "light",
      data: initialG6Data as any,
      layout:
        layoutMode === "dagre"
          ? {
              type: "dagre",
              rankdir: "TB",
              nodesep: 50,
              ranksep: 70,
            }
          : layoutMode === "circular"
          ? {
              type: "circular",
            }
          : {
              type: "d3-force",
              preventOverlap: true,
              linkDistance: 130,
              nodeStrength: -280,
            },
      behaviors: [
        "drag-canvas",
        "zoom-canvas",
        "drag-element",
        "click-select",
      ],
    });

    graphRef.current = graph;

    // Attach click listeners
    graph.on(NodeEvent.CLICK, (e: any) => {
      const targetId = e.target?.id;
      if (targetId && graphOverlay?.nodes) {
        const found = graphOverlay.nodes.find((n) => n.id === targetId);
        if (found) {
          setSelectedOverlayItem({ type: "node", item: found });
        }
      }
    });

    graph.on(EdgeEvent.CLICK, (e: any) => {
      const targetId = e.target?.id || e.target?.parentElement?.id;
      if (targetId && graphOverlay?.edges) {
        const found = graphOverlay.edges.find((edge) => edge.id === targetId);
        if (found) {
          setSelectedOverlayItem({ type: "edge", item: found });
        }
      }
    });

    graph.on(CanvasEvent.CLICK, () => {
      setSelectedOverlayItem(null);
    });

    graph
      .render()
      .then(() => {
        syncHullPlugins();
      })
      .catch((err) => {
        console.warn("G6 render error:", err);
      });

    return () => {
      try {
        graph.destroy();
      } catch (e) {}
      graphRef.current = null;
    };
  }, [layoutMode, isDark]);

  // Update G6 data when filtered elements or styles change
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || (graph as any).destroyed) return;

    const g6Data = {
      nodes: filteredNodes.map((node) => ({
        id: node.id,
        data: { ...node },
        style: getNodeStyle(node),
      })),
      edges: filteredEdges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        data: { ...edge },
        style: getEdgeStyle(edge),
      })),
    };

    graph.setData(g6Data as any);
    graph
      .render()
      .then(() => {
        syncHullPlugins();
      })
      .catch(() => {});
  }, [filteredNodes, filteredEdges, getNodeStyle, getEdgeStyle, syncHullPlugins]);

  // Auto-focus cycle nodes if cycleHighlightNodeIds changes
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || !cycleHighlightNodeIds || cycleHighlightNodeIds.length === 0) return;
    try {
      graph.focusElement(cycleHighlightNodeIds);
    } catch (e) {}
  }, [cycleHighlightNodeIds]);

  // Zoom controls
  const handleZoomIn = () => {
    graphRef.current?.zoomBy(1.25);
  };

  const handleZoomOut = () => {
    graphRef.current?.zoomBy(0.8);
  };

  const handleFitView = () => {
    graphRef.current?.fitView();
  };

  return (
    <div className="relative flex-1 w-full h-full overflow-hidden flex bg-app-bg select-none">
      {/* Center Graph Canvas */}
      <div className="relative flex-1 h-full overflow-hidden">
        {/* Floating Top-Left Canvas HUD */}
        <div className="absolute left-4 top-4 z-20">
          <CanvasEvaluationHud borderlineCount={borderlineCount} />
        </div>

        {/* Floating Bottom-Left Canvas Controls */}
        <div className="absolute left-4 bottom-4 z-20 flex items-center gap-1.5 p-1.5 rounded-lg bg-app-surface/90 backdrop-blur-md border border-app-border">
          <button
            onClick={handleFitView}
            className="p-1.5 rounded hover:bg-app-subtle text-app-muted hover:text-app-text transition-colors"
            title="Fit to Canvas"
          >
            <Focus className="w-4 h-4" />
          </button>
          <div className="h-4 w-px bg-app-border" />
          <button
            onClick={handleZoomIn}
            className="p-1.5 rounded hover:bg-app-subtle text-app-muted hover:text-app-text transition-colors"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            className="p-1.5 rounded hover:bg-app-subtle text-app-muted hover:text-app-text transition-colors"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <div className="h-4 w-px bg-app-border" />
          {/* Layout Selector */}
          <select
            value={layoutMode}
            onChange={(e) => setLayoutMode(e.target.value as any)}
            className="text-[11px] bg-app-bg text-app-text px-2 py-0.5 rounded border border-app-border focus:outline-hidden cursor-pointer"
          >
            <option value="d3-force">Force Directed</option>
            <option value="dagre">Dagre Hierarchy</option>
            <option value="circular">Circular</option>
          </select>
        </div>

        {/* Cycle Isolation Notice Bar if active */}
        {cycleHighlightNodeIds && cycleHighlightNodeIds.length > 0 && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 px-3 py-1.5 rounded-md bg-rose-600/90 text-white border border-rose-500/50 backdrop-blur-xs text-xs font-medium animate-pulse">
            <span>Cycle Path Isolated: {cycleHighlightNodeIds.join(" → ")}</span>
            <button
              onClick={() => useEvaluationStore.getState().setCycleHighlightNodeIds(null)}
              className="ml-2 underline text-[11px] hover:text-rose-100"
            >
              Reset Filter
            </button>
          </div>
        )}

        {/* The G6 DOM Container */}
        <div ref={containerRef} className="w-full h-full" />

        {/* Non-blocking Slide-out Ambiguous Alias Drawer */}
        <AmbiguousAliasDrawer />
      </div>

      {/* Docked Right Topological Error Quad (360px Fixed Dock) */}
      <TopologicalErrorQuad />
    </div>
  );
};
