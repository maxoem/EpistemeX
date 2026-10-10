import {useCallback, useEffect, useRef} from "react";
import {CanvasEvent, EdgeEvent, Graph, GraphEvent, NodeEvent} from "@antv/g6";
import {GraphView, MetricResult, StudioEdge, StudioNode} from "../../api/types";
import {GraphSettings} from "../../store/graphSettingsStore";
import {LayoutType} from "../GraphCanvasHud";
import {ComputedNodeStyle} from "../styling/nodeStyling";
import {ComputedEdgeStyle} from "../styling/edgeStyling";

export interface UseG6InstanceParams {
  graphData: GraphView | null;
  filteredNodes: StudioNode[];
  filteredEdges: StudioEdge[];
  getNodeStyle: (node: StudioNode) => ComputedNodeStyle;
  getEdgeStyle: (edge: StudioEdge) => ComputedEdgeStyle;
  layoutType: LayoutType;
  graphSettings: GraphSettings;
  isDark: boolean;
  selectedRunId: string | null;
  selectedNode: StudioNode | null;
  selectedEdge: StudioEdge | null;
  activeMetricResult: MetricResult | null;
  syncHullPlugins: () => void;
  onNodeClick: (node: StudioNode) => void;
  onEdgeClick: (edge: StudioEdge) => void;
  onNodeDblClick?: (nodeId: string) => void;
  onNodeContextMenu: (node: StudioNode, x: number, y: number) => void;
  onEdgeContextMenu: (edge: StudioEdge, x: number, y: number) => void;
  onCanvasClick: () => void;
}

export function useG6Instance({
  graphData,
  filteredNodes,
  filteredEdges,
  getNodeStyle,
  getEdgeStyle,
  layoutType,
  graphSettings,
  isDark,
  selectedRunId,
  selectedNode,
  selectedEdge,
  activeMetricResult,
  syncHullPlugins,
  onNodeClick,
  onEdgeClick,
  onNodeDblClick,
  onNodeContextMenu,
  onEdgeContextMenu,
  onCanvasClick,
}: UseG6InstanceParams) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const isGraphReadyRef = useRef(false);

  // Position caching to avoid layout resets and enable warm restarts
  const positionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());
  const prevRunIdRef = useRef<string | null>(selectedRunId || null);
  const renderedTopologyKeyRef = useRef<string>("");

  const syncElementStatesRef = useRef<() => void>(() => {});
  const syncHullPluginsRef = useRef(syncHullPlugins);
  syncHullPluginsRef.current = syncHullPlugins;

  const graphDataRef = useRef(graphData);
  graphDataRef.current = graphData;

  const saveNodePositions = useCallback(() => {
    const graph = graphRef.current;
    if (!graph || (graph as any).destroyed) return;
    try {
      const nodes = graph.getNodeData();
      for (const n of nodes) {
        const sx = (n.style as any)?.x;
        const sy = (n.style as any)?.y;
        if (typeof sx === "number" && !isNaN(sx) && typeof sy === "number" && !isNaN(sy)) {
          positionsRef.current.set(n.id, { x: sx, y: sy });
        }
      }
    } catch (e) {}
  }, []);

  // Clear position cache if selected run changes
  useEffect(() => {
    if (selectedRunId !== prevRunIdRef.current) {
      prevRunIdRef.current = selectedRunId || null;
      positionsRef.current.clear();
      renderedTopologyKeyRef.current = "";
    }
  }, [selectedRunId]);

  const getLayoutConfig = useCallback(
    (type: LayoutType) => {
      switch (type) {
        case "d3-force":
          return {
            type: "d3-force",
            preventOverlap: true,
            linkDistance: graphSettings.linkDistance,
            nodeStrength: graphSettings.nodeRepulsion,
            animation: graphSettings.forceLayoutAnimated,
            iterations: graphSettings.forceIterations,
            alphaDecay: 0.05,
            velocityDecay: 0.6,
          };
        case "concentric":
          return {
            type: "concentric",
            preventOverlap: true,
          };
        case "radial":
          return {
            type: "radial",
            preventOverlap: true,
          };
        case "circular":
          return {
            type: "circular",
          };
        case "grid":
          return {
            type: "grid",
          };
        case "antv-dagre":
          return {
            type: "antv-dagre",
            rankdir: "LR",
            ranksep: graphSettings.hierarchicalRankSep,
          };
        default:
          return { type: "d3-force" };
      }
    },
    [
      graphSettings.linkDistance,
      graphSettings.nodeRepulsion,
      graphSettings.hierarchicalRankSep,
      graphSettings.forceLayoutAnimated,
      graphSettings.forceIterations,
    ]
  );

  // Synchronize composite element states (selected + metric overlay) with G6
  const syncElementStates = useCallback(() => {
    const graph = graphRef.current;
    if (!graph || (graph as any).destroyed) return;

    try {
      const affectedNodes = activeMetricResult?.affected_nodes || {};
      const affectedEdges = activeMetricResult?.affected_edges || [];
      const stateMap: Record<string, string[]> = {};

      for (const node of filteredNodes) {
        const states: string[] = [];
        if (selectedNode && node.id === selectedNode.id) {
          states.push("selected");
        }

        if (activeMetricResult) {
          if (node.id === activeMetricResult.focus_node_id) {
            states.push("metric-focus");
          } else if (affectedNodes[node.id]) {
            states.push("metric-affected");
            const roles = affectedNodes[node.id].roles;
            roles.forEach((r) => states.push(`metric-role-${r}`));
          } else {
            states.push("metric-dimmed");
          }
        }
        stateMap[node.id] = states;
      }

      for (const edge of filteredEdges) {
        const states: string[] = [];
        if (selectedEdge && edge.id === selectedEdge.id) {
          states.push("selected");
        }

        if (activeMetricResult) {
          const aff = affectedEdges.find(
            (ae) =>
              ae.relationship_id === edge.id ||
              (ae.source_node_id === edge.source && ae.target_node_id === edge.target)
          );
          if (aff) {
            states.push("metric-affected");
            states.push(`metric-${aff.role}`);
          } else {
            states.push("metric-dimmed");
          }
        }
        stateMap[edge.id] = states;
      }

      if (Object.keys(stateMap).length > 0) {
        graph.setElementState(stateMap).catch((err) => {
          console.debug("G6 setElementState notice:", err);
        });
      }
    } catch (err) {
      console.debug("Error preparing element states:", err);
    }
  }, [selectedNode, selectedEdge, filteredNodes, filteredEdges, activeMetricResult]);

  syncElementStatesRef.current = syncElementStates;

  // Mount and initialize G6 Graph instance
  useEffect(() => {
    if (!containerRef.current || !graphData) return;

    let isDestroyed = false;
    isGraphReadyRef.current = false;

    // Clear previous DOM canvas if any to avoid StrictMode double-mounting leaks
    containerRef.current.innerHTML = "";

    // Build initial data payload with cached coordinate preservation
    const initialG6Data = {
      nodes: filteredNodes.map((node) => {
        const cachedPos = positionsRef.current.get(node.id);
        const baseStyle = getNodeStyle(node);
        return {
          id: node.id,
          data: { ...(node as any) } as Record<string, unknown>,
          style: {
            ...baseStyle,
            ...(cachedPos ? { x: cachedPos.x, y: cachedPos.y } : {}),
          },
        };
      }),
      edges: filteredEdges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        data: { ...(edge as any) } as Record<string, unknown>,
        style: getEdgeStyle(edge),
      })),
    };

    const graph = new Graph({
      container: containerRef.current,
      autoFit: "view",
      autoResize: true,
      theme: isDark ? "dark" : "light",
      data: initialG6Data as any,
      layout: getLayoutConfig(layoutType),
      behaviors: [
        "drag-canvas",
        "zoom-canvas",
        "drag-element",
        "click-select",
        {
          type: "optimize-viewport-transform",
          key: "optimize-viewport-transform-1",
          debounce: 150,
        },
        ...(graphSettings.autoAdaptLabels
          ? [
              {
                type: "auto-adapt-label",
                key: "auto-adapt-label-1",
                sortNode: { type: "degree" as const },
                padding: [2, 4],
              },
            ]
          : []),
      ],
      node: {
        state: {
          selected: {
            stroke: "#38bdf8",
            lineWidth: 3.5,
          },
          "metric-focus": {
            stroke: "#06b6d4",
            lineWidth: 4,
          },
          "metric-affected": {
            lineWidth: 2.5,
          },
          "metric-role-support": {
            stroke: "#10b981",
            lineWidth: 3,
          },
          "metric-role-attack": {
            stroke: "#ef4444",
            lineWidth: 3,
          },
          "metric-dimmed": {
            opacity: 0.3,
          },
        },
      },
      edge: {
        state: {
          selected: {
            stroke: "#38bdf8",
            lineWidth: 4,
            halo: true,
            haloStroke: "#38bdf8",
            haloOpacity: 0.35,
            haloLineWidth: 12,
          },
          "metric-affected": {
            lineWidth: 2.5,
          },
          "metric-support": {
            stroke: "#10b981",
            lineWidth: 3,
            lineDash: undefined,
          },
          "metric-attack": {
            stroke: "#ef4444",
            lineWidth: 3,
            lineDash: [6, 4],
          },
          "metric-undercut": {
            stroke: "#f59e0b",
            lineWidth: 3,
            lineDash: [4, 4],
          },
          "metric-dimmed": {
            opacity: 0.2,
          },
        },
      },
    });

    graphRef.current = graph;

    // Register event listeners
    graph.on(NodeEvent.CLICK, (e: any) => {
      const targetId = e.target?.id;
      if (targetId && graphDataRef.current) {
        const found = graphDataRef.current.nodes.find((n) => n.id === targetId);
        if (found) onNodeClick(found);
      }
    });

    graph.on(EdgeEvent.CLICK, (e: any) => {
      const targetId = e.target?.id || e.target?.parentElement?.id || e.target?.attributes?.id;
      if (targetId && graphDataRef.current) {
        const found = graphDataRef.current.edges.find((edge) => edge.id === targetId);
        if (found) onEdgeClick(found);
      }
    });

    graph.on(NodeEvent.DBLCLICK, (e: any) => {
      const targetId = e.target?.id;
      if (targetId && onNodeDblClick) onNodeDblClick(targetId);
    });

    graph.on(NodeEvent.CONTEXT_MENU, (e: any) => {
      if (e.preventDefault) e.preventDefault();
      const targetId = e.target?.id;
      if (targetId && graphDataRef.current) {
        const found = graphDataRef.current.nodes.find((n) => n.id === targetId);
        if (found) {
          const clientX = e.client?.x ?? e.viewport?.x ?? 250;
          const clientY = e.client?.y ?? e.viewport?.y ?? 200;
          onNodeContextMenu(found, clientX, clientY);
        }
      }
    });

    graph.on(EdgeEvent.CONTEXT_MENU, (e: any) => {
      if (e.preventDefault) e.preventDefault();
      const targetId = e.target?.id;
      if (targetId && graphDataRef.current) {
        const found = graphDataRef.current.edges.find((edge) => edge.id === targetId);
        if (found) {
          const clientX = e.client?.x ?? e.viewport?.x ?? 250;
          const clientY = e.client?.y ?? e.viewport?.y ?? 200;
          onEdgeContextMenu(found, clientX, clientY);
        }
      }
    });

    graph.on(CanvasEvent.CLICK, () => {
      onCanvasClick();
    });

    graph.on(GraphEvent.AFTER_LAYOUT, () => {
      saveNodePositions();
      syncHullPluginsRef.current();
    });

    graph
      .render()
      .then(() => {
        if (!isDestroyed) {
          isGraphReadyRef.current = true;
          saveNodePositions();
          graph.fitView();
          syncElementStatesRef.current();
          syncHullPluginsRef.current();
        }
      })
      .catch((err) => {
        console.warn("G6 render warning:", err);
      });

    // Resize observer to keep canvas responsive when side panels toggle
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0 && graphRef.current && isGraphReadyRef.current && !isDestroyed) {
          try {
            graphRef.current.resize(width, height);
          } catch (e) {}
        }
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      isDestroyed = true;
      isGraphReadyRef.current = false;
      resizeObserver.disconnect();
      try {
        graph.destroy();
      } catch (err) {
        // ignore cleanup errors on unmount
      }
      graphRef.current = null;
    };
  }, [graphData, layoutType]); // Re-mount when graph data or layout type changes

  // Update theme dynamically on graph when theme toggle is clicked
  useEffect(() => {
    if (!graphRef.current || !isGraphReadyRef.current || (graphRef.current as any).destroyed) return;
    try {
      graphRef.current.setTheme(isDark ? "dark" : "light");
    } catch (err) {
      console.warn("Error updating G6 theme:", err);
    }
  }, [isDark]);

  // Dynamically update layout when layout parameters change
  useEffect(() => {
    if (!graphRef.current || !isGraphReadyRef.current || (graphRef.current as any).destroyed) return;
    try {
      const cfg = getLayoutConfig(layoutType);
      graphRef.current
        .layout(cfg)
        .then(() => {
          saveNodePositions();
          syncHullPluginsRef.current();
        })
        .catch((err) => {
          console.warn("Error applying dynamic G6 layout:", err);
        });
    } catch (err) {
      console.warn("Error updating G6 layout:", err);
    }
  }, [getLayoutConfig, layoutType, saveNodePositions]);

  // Update data dynamically: use draw() for visual/overlay changes, and render() only when topology changes
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || !isGraphReadyRef.current || (graph as any).destroyed) return;

    try {
      const currentTopologyKey =
        filteredNodes.map((n) => n.id).join(",") +
        "|" +
        filteredEdges.map((e) => e.id).join(",");

      const isTopologyUnchanged =
        renderedTopologyKeyRef.current !== "" &&
        renderedTopologyKeyRef.current === currentTopologyKey;

      renderedTopologyKeyRef.current = currentTopologyKey;

      const g6Data = {
        nodes: filteredNodes.map((node) => {
          const cachedPos = positionsRef.current.get(node.id);
          const baseStyle = getNodeStyle(node);
          return {
            id: node.id,
            data: { ...(node as any) } as Record<string, unknown>,
            style: {
              ...baseStyle,
              ...(cachedPos ? { x: cachedPos.x, y: cachedPos.y } : {}),
            },
          };
        }),
        edges: filteredEdges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          data: { ...(edge as any) } as Record<string, unknown>,
          style: getEdgeStyle(edge),
        })),
      };

      graph.setData(g6Data as any);

      if (isTopologyUnchanged) {
        // Pure visual / overlay / style update: redraw without re-running force simulation!
        graph
          .draw()
          .then(() => {
            syncElementStatesRef.current();
            syncHullPluginsRef.current();
          })
          .catch((err) => {
            console.warn("Error drawing G6 dynamically:", err);
          });
      } else {
        // Topology changed (filtering or expansion): run layout
        graph
          .render()
          .then(() => {
            saveNodePositions();
            syncElementStatesRef.current();
            syncHullPluginsRef.current();
          })
          .catch((err) => {
            console.warn("Error rendering G6 dynamically:", err);
          });
      }
    } catch (err) {
      console.warn("Error updating G6 data dynamically:", err);
    }
  }, [filteredNodes, filteredEdges, getNodeStyle, getEdgeStyle, saveNodePositions]);

  // Update composite element states when selection or metrics change
  useEffect(() => {
    syncElementStates();
  }, [syncElementStates]);

  // Camera actions
  const handleZoomIn = useCallback(() => {
    if (isGraphReadyRef.current && graphRef.current) {
      graphRef.current.zoomBy(1.25).catch(() => {});
    }
  }, []);

  const handleZoomOut = useCallback(() => {
    if (isGraphReadyRef.current && graphRef.current) {
      graphRef.current.zoomBy(0.8).catch(() => {});
    }
  }, []);

  const handleFitView = useCallback(() => {
    if (isGraphReadyRef.current && graphRef.current) {
      graphRef.current.fitView().catch(() => {});
    }
  }, []);

  const handleFitCenter = useCallback(() => {
    if (isGraphReadyRef.current && graphRef.current) {
      graphRef.current.fitCenter().catch(() => {});
    }
  }, []);

  const focusElement = useCallback(async (id: string, options?: any) => {
    if (isGraphReadyRef.current && graphRef.current) {
      try {
        await graphRef.current.focusElement(id, options);
      } catch (err) {
        console.warn("Could not focus element in G6:", err);
      }
    }
  }, []);

  const resetPositions = useCallback(() => {
    positionsRef.current.clear();
    renderedTopologyKeyRef.current = "";
  }, []);

  return {
    containerRef,
    graphRef,
    isGraphReadyRef,
    handleZoomIn,
    handleZoomOut,
    handleFitView,
    handleFitCenter,
    focusElement,
    resetPositions,
    syncElementStates,
  };
}
