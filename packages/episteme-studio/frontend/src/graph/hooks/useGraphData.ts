import {useCallback, useEffect, useRef, useState} from "react";
import {useRunsStore} from "../../store/runsStore";
import {useDiffStore} from "../../store/diffStore";
import {api} from "../../api/client";
import {GraphView} from "../../api/types";

export interface UseGraphDataOptions {
  onNotify?: (msg: string) => void;
}

export function useGraphData(options?: UseGraphDataOptions) {
  const { onNotify } = options || {};
  const {
    selectedRunId,
    capabilities,
    activeDataSource,
    setActiveDataSource,
  } = useRunsStore();

  const { isDiffActive, diffData } = useDiffStore();

  const isNeo4j = Boolean(capabilities?.neo4j);
  const dataSource: "artifacts" | "neo4j" =
    activeDataSource === "neo4j" && isNeo4j ? "neo4j" : "artifacts";

  const [graphData, setGraphData] = useState<GraphView | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isExpanding, setIsExpanding] = useState(false);
  const [neo4jError, setNeo4jError] = useState<string | null>(null);

  const loadGraphSeqRef = useRef(0);
  const dataSourceRef = useRef(dataSource);
  dataSourceRef.current = dataSource;

  // Sync diff graph data when diff mode is active
  useEffect(() => {
    if (isDiffActive && diffData) {
      setGraphData(diffData.union_graph);
    }
  }, [isDiffActive, diffData]);

  // Load graph data based on selected data source
  const loadGraph = useCallback(() => {
    if (isDiffActive) return;

    setNeo4jError(null);
    const seq = ++loadGraphSeqRef.current;

    if (dataSource === "artifacts") {
      if (!selectedRunId) {
        setGraphData(null);
        return;
      }
      setIsLoading(true);
      api
        .getRunGraph(selectedRunId, 500, false)
        .then((data) => {
          if (seq === loadGraphSeqRef.current) {
            setGraphData(data);
            setIsLoading(false);
          }
        })
        .catch((err) => {
          if (seq === loadGraphSeqRef.current) {
            console.error("Failed to load artifact graph data:", err);
            setIsLoading(false);
          }
        });
    } else {
      // Neo4j mode
      if (!capabilities?.neo4j) {
        setActiveDataSource("artifacts");
        return;
      }
      setIsLoading(true);
      api
        .getNeo4jGraphView(500)
        .then((data) => {
          if (seq !== loadGraphSeqRef.current) return;
          if (!data.nodes || data.nodes.length === 0) {
            onNotify?.("Neo4j database returned 0 nodes. Falling back to Artifact Store.");
            setActiveDataSource("artifacts");
            return;
          }
          setGraphData(data);
          setIsLoading(false);
        })
        .catch((err) => {
          if (seq !== loadGraphSeqRef.current) return;
          console.error("Failed to load Neo4j graph:", err);
          setNeo4jError(err?.detail || err?.title || "Failed to load graph from Neo4j.");
          onNotify?.("Failed to load graph from Neo4j. Falling back to Artifact Store.");
          setActiveDataSource("artifacts");
          setIsLoading(false);
        });
    }
  }, [dataSource, selectedRunId, capabilities?.neo4j, isDiffActive, onNotify, setActiveDataSource]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // Lazy k-hop expansion in Neo4j mode
  const handleExpandNode = useCallback(
    async (nodeId: string) => {
      if (dataSourceRef.current !== "neo4j") return;
      setIsExpanding(true);
      try {
        const expanded = await api.expandNeo4jGraph([nodeId], 1);
        setGraphData((prev) => {
          if (!prev) return expanded;
          const existingNodeIds = new Set(prev.nodes.map((n) => n.id));
          const existingEdgeIds = new Set(prev.edges.map((e) => e.id));

          const newNodes = expanded.nodes.filter((n) => !existingNodeIds.has(n.id));
          const newEdges = expanded.edges.filter((e) => !existingEdgeIds.has(e.id));

          if (newNodes.length === 0 && newEdges.length === 0) {
            onNotify?.("No additional neighbors found for node.");
            return prev;
          }

          const mergedNodes = [...prev.nodes, ...newNodes];
          const mergedEdges = [...prev.edges, ...newEdges];

          const layerCounts: Record<number, number> = { 1: 0, 2: 0, 3: 0 };
          for (const n of mergedNodes) {
            layerCounts[n.layer] = (layerCounts[n.layer] || 0) + 1;
          }

          onNotify?.(
            `Expanded ${newNodes.length} neighbor${newNodes.length === 1 ? "" : "s"} & ${newEdges.length} edge${newEdges.length === 1 ? "" : "s"}.`
          );

          return {
            ...prev,
            nodes: mergedNodes,
            edges: mergedEdges,
            layer_counts: layerCounts,
            graph_version: `neo4j-expanded-${Date.now()}`,
          };
        });
      } catch (err: any) {
        console.error("Failed to expand node:", err);
        onNotify?.(`Expansion failed: ${err?.detail || "Unknown error"}`);
      } finally {
        setIsExpanding(false);
      }
    },
    [onNotify]
  );

  return {
    graphData,
    setGraphData,
    isLoading,
    isExpanding,
    neo4jError,
    loadGraph,
    handleExpandNode,
    dataSource,
    isNeo4j,
  };
}
