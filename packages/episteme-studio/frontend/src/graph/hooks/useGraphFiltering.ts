import {useMemo} from "react";
import {GraphDiffView, GraphView, StudioEdge, StudioNode} from "../../api/types";
import {SubgraphMask} from "../../store/viewOverlayStore";
import {DiffFilter, DiffScrubMode} from "../../store/diffStore";

export interface UseGraphFilteringParams {
  graphData: GraphView | null;
  showL1: boolean;
  showL2: boolean;
  showL3: boolean;
  activeMask: SubgraphMask;
  searchTerm: string;
  isDiffActive: boolean;
  diffData: GraphDiffView | null;
  scrubMode: DiffScrubMode;
  activeFilter: DiffFilter;
  getPolarity: (relationType: string) => number | null;
  getPartition: (componentType: string) => "B" | "A" | null;
}

export function useGraphFiltering({
  graphData,
  showL1,
  showL2,
  showL3,
  activeMask,
  searchTerm,
  isDiffActive,
  diffData,
  scrubMode,
  activeFilter,
  getPolarity,
  getPartition,
}: UseGraphFilteringParams) {
  // Compute filtered nodes based on layer toggles, active mask, search query, and diff state
  const filteredNodes = useMemo<StudioNode[]>(() => {
    if (!graphData) return [];
    return graphData.nodes.filter((node) => {
      if (node.layer === 1 && !showL1) return false;
      if (node.layer === 2 && !showL2) return false;
      if (node.layer === 3 && !showL3) return false;

      // Active Subgraph Mask layer filter
      if (activeMask.layerFilter && !activeMask.layerFilter.includes(node.layer as 1 | 2 | 3)) {
        return false;
      }

      // Active Subgraph Mask allowed node types
      if (activeMask.allowedNodeTypes && activeMask.allowedNodeTypes.length > 0) {
        if (!activeMask.allowedNodeTypes.includes(node.type)) {
          return false;
        }
      }

      // Active Subgraph Mask partition filter ("B" for empirical base, "A" for theoretical core)
      if (activeMask.partitionFilter) {
        const p = node.partition || (node.props as any)?.partition || getPartition(node.type);
        if (p && p !== activeMask.partitionFilter) {
          return false;
        }
      }

      // Active Subgraph Mask dynamic theory element filter (Phi_spec dynamic projection)
      if (activeMask.theoryId) {
        const nodeTheoryId =
          node.props?.theory_id ||
          node.tenability?.theory_id ||
          (node.props?.tenability as any)?.theory_id;
        if (nodeTheoryId !== activeMask.theoryId) {
          return false;
        }
      }

      // Diff-aware filtering
      if (isDiffActive && diffData) {
        const nodeStatus = diffData.node_diff[node.id];
        // 3-state scrub filter:
        if (scrubMode === "run_a" && nodeStatus === "gained") return false;
        if (scrubMode === "run_b" && nodeStatus === "lost") return false;

        // Specific category filter
        if (activeFilter === "gained" && nodeStatus !== "gained") return false;
        if (activeFilter === "lost" && nodeStatus !== "lost") return false;
        if (activeFilter === "polarity_inversions") {
          const isInvEndpoint = diffData.polarity_inversions.some(
            (inv) => inv.source === node.id || inv.target === node.id
          );
          if (!isInvEndpoint) return false;
        }
        if (activeFilter === "arg_drift") {
          const dRho = diffData.rho_deltas[node.id];
          if (dRho === undefined || Math.abs(dRho) < 0.05) return false;
        }
      }

      if (searchTerm.trim()) {
        const term = searchTerm.toLowerCase();
        const matchesLabel = (node.label || "").toLowerCase().includes(term);
        const matchesId = node.id.toLowerCase().includes(term);
        const matchesType = node.type.toLowerCase().includes(term);
        if (!matchesLabel && !matchesId && !matchesType) return false;
      }
      return true;
    });
  }, [
    graphData,
    showL1,
    showL2,
    showL3,
    activeMask,
    searchTerm,
    isDiffActive,
    diffData,
    scrubMode,
    activeFilter,
    getPartition,
  ]);

  // Compute filtered edges connecting visible nodes and passing mask filters
  const filteredEdges = useMemo<StudioEdge[]>(() => {
    if (!graphData) return [];
    const visibleIds = new Set(filteredNodes.map((n) => n.id));
    return graphData.edges.filter((e) => {
      if (!visibleIds.has(e.source) || !visibleIds.has(e.target)) return false;

      // Active Subgraph Mask allowed edge types
      if (activeMask.allowedEdgeTypes && activeMask.allowedEdgeTypes.length > 0) {
        if (!activeMask.allowedEdgeTypes.includes(e.type)) {
          return false;
        }
      }

      // Active Subgraph Mask allowed polarities: schema/alias resolution takes precedence
      if (activeMask.allowedPolarities && activeMask.allowedPolarities.length > 0) {
        const pol = getPolarity(e.type) ?? e.polarity ?? (e.props as any)?.polarity ?? null;
        if (!activeMask.allowedPolarities.includes(pol)) {
          return false;
        }
      }

      if (isDiffActive && diffData) {
        const edgeStatus = diffData.edge_diff[e.id];
        if (scrubMode === "run_a" && edgeStatus === "gained") return false;
        if (scrubMode === "run_b" && edgeStatus === "lost") return false;
        if (activeFilter === "polarity_inversions" && edgeStatus !== "polarity_inverted") {
          return false;
        }
      }
      return true;
    });
  }, [
    graphData,
    filteredNodes,
    activeMask,
    isDiffActive,
    diffData,
    scrubMode,
    activeFilter,
    getPolarity,
  ]);

  return {
    filteredNodes,
    filteredEdges,
  };
}
