import {useCallback, useEffect} from "react";
import {Graph, GraphEvent} from "@antv/g6";
import {MetricResult, Overlay, StudioNode} from "../../api/types";

const HULL_PALETTE = [
  { fill: "#3b82f6", stroke: "#2563eb" }, // Blue
  { fill: "#10b981", stroke: "#059669" }, // Emerald
  { fill: "#f59e0b", stroke: "#d97706" }, // Amber
  { fill: "#ec4899", stroke: "#db2777" }, // Pink
  { fill: "#8b5cf6", stroke: "#7c3aed" }, // Violet
  { fill: "#06b6d4", stroke: "#0891b2" }, // Cyan
  { fill: "#f97316", stroke: "#ea580c" }, // Orange
  { fill: "#14b8a6", stroke: "#0d9488" }, // Teal
  { fill: "#6366f1", stroke: "#4f46e5" }, // Indigo
  { fill: "#84cc16", stroke: "#65a30d" }, // Lime
];

export interface UseHullClusteringParams {
  graphRef: React.RefObject<Graph | null>;
  activeMetricResult: MetricResult | null;
  activeOverlay: Overlay | null;
  filteredNodes: StudioNode[];
  isDark: boolean;
}

export function useHullClustering({
  graphRef,
  activeMetricResult,
  activeOverlay,
  filteredNodes,
  isDark,
}: UseHullClusteringParams) {
  const syncHullPlugins = useCallback(() => {
    const graph = graphRef.current;
    if (!graph || (graph as any).destroyed) return;

    const isLeidenResult = Boolean(activeMetricResult && activeMetricResult.metric_id.includes("leiden"));
    const isLeidenOverlay = Boolean(activeOverlay && activeOverlay.kind === "leiden");
    const isTenabilityResult = Boolean(activeMetricResult && activeMetricResult.metric_id.includes("tenability"));
    const isTenabilityOverlay = Boolean(activeOverlay && activeOverlay.kind === "tenability");

    if (!isLeidenResult && !isLeidenOverlay && !isTenabilityResult && !isTenabilityOverlay) {
      try {
        graph.setPlugins([]);
        graph.draw().catch(() => {});
      } catch (e) {}
      return;
    }

    const clusters: Record<string, string[]> = {};
    if (isLeidenResult && activeMetricResult) {
      for (const [nodeId, detail] of Object.entries(activeMetricResult.affected_nodes)) {
        const comm = detail.metadata?.community ?? detail.metadata?.cluster;
        if (comm !== undefined && comm !== null) {
          const commKey = String(comm);
          if (!clusters[commKey]) clusters[commKey] = [];
          clusters[commKey].push(nodeId);
        }
      }
    } else if (isLeidenOverlay && activeOverlay) {
      for (const [nodeId, val] of Object.entries(activeOverlay.node_values)) {
        if (val !== undefined && val !== null) {
          const commKey = String(val);
          if (!clusters[commKey]) clusters[commKey] = [];
          clusters[commKey].push(nodeId);
        }
      }
    } else if (isTenabilityResult || isTenabilityOverlay) {
      for (const node of filteredNodes) {
        const clusterId =
          node.tenability?.cluster_id ||
          activeMetricResult?.affected_nodes[node.id]?.metadata?.cluster_id ||
          (node as any).cluster_id ||
          (node.props as any)?.cluster_id;
        if (clusterId) {
          const commKey = String(clusterId);
          if (!clusters[commKey]) clusters[commKey] = [];
          clusters[commKey].push(node.id);
        }
      }
    }

    const renderedNodeIds = new Set(filteredNodes.map((n) => n.id));

    const hullPlugins = Object.entries(clusters)
      .map(([commKey, members], idx) => {
        const validMembers = members.filter((id) => renderedNodeIds.has(id));
        if (validMembers.length === 0) return null;
        const palette = HULL_PALETTE[idx % HULL_PALETTE.length];
        return {
          key: `hull-${commKey}`,
          type: "hull",
          members: validMembers,
          padding: 18,
          corner: "smooth" as const,
          fill: palette.fill,
          stroke: palette.stroke,
          fillOpacity: isDark ? 0.18 : 0.12,
          strokeOpacity: 0.7,
          lineWidth: 2,
          labelText:
            isTenabilityResult || isTenabilityOverlay
              ? `Empirical Cluster ${commKey} (${validMembers.length})`
              : `Community ${commKey} (${validMembers.length})`,
          labelFill: isDark ? "#f1f5f9" : "#1e293b",
          labelFontSize: 11,
          labelBackground: true,
          labelBackgroundFill: isDark ? "#0f172a" : "#ffffff",
          labelBackgroundOpacity: 0.8,
          labelBackgroundPadding: [2, 6],
        };
      })
      .filter(Boolean);

    try {
      graph.setPlugins(hullPlugins as any);
      graph.draw().catch(() => {});
      graph.emit(GraphEvent.AFTER_RENDER, {});
    } catch (err) {
      console.warn("Failed to update G6 Hull plugins:", err);
    }
  }, [graphRef, activeMetricResult, activeOverlay, filteredNodes, isDark]);

  useEffect(() => {
    syncHullPlugins();
  }, [syncHullPlugins]);

  return { syncHullPlugins };
}
