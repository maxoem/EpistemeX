import React, {useCallback, useEffect, useMemo, useState} from "react";
import {useRunsStore} from "../store/runsStore";
import {useThemeStore} from "../store/themeStore";
import {useGraphSettingsStore} from "../store/graphSettingsStore";
import {useDiffStore} from "../store/diffStore";
import {useViewOverlayStore} from "../store/viewOverlayStore";
import {useMetricsStore} from "../store/metricsStore";
import {useEngineSchema} from "../store/engineSettingsStore";
import {StudioEdge, StudioNode} from "../api/types";
import {AlertCircle, Check, Database, HardDrive, Info, Loader2,} from "lucide-react";
import {UnmappedPredicatesPanel} from "../panels/UnmappedPredicatesPanel";
import {NodeInspectorPanel} from "../panels/NodeInspectorPanel";
import {MetricsDrawer} from "../panels/MetricsDrawer";
import {NodeContextMenu} from "./NodeContextMenu";
import {EdgeContextMenu} from "./EdgeContextMenu";
import {EdgeInspectorModal} from "../panels/EdgeInspectorModal";
import {EdgeInspectorPanel} from "../panels/EdgeInspectorPanel";
import {GraphCanvasHud, LayoutType} from "./GraphCanvasHud";
import {ConfigDiffDrawer} from "../panels/ConfigDiffDrawer";
import {PolarityInversionModal} from "../panels/PolarityInversionModal";
import {ViewOverlayDrawer} from "../panels/ViewOverlayDrawer";
import {ResizablePanel} from "../panels/ResizablePanel";
import {exportGraphImage, exportGraphToGexf, exportGraphToGraphML, exportGraphToJson,} from "./exportUtils";

// Modular Domain Hooks & Pure Styling Pipeline
import {useGraphData} from "./hooks/useGraphData";
import {useGraphFiltering} from "./hooks/useGraphFiltering";
import {useG6Instance} from "./hooks/useG6Instance";
import {useHullClustering} from "./hooks/useHullClustering";
import {computeNodeStyle} from "./styling/nodeStyling";
import {computeEdgeStyle} from "./styling/edgeStyling";
import {EdgeStyleContext, NodeStyleContext} from "./styling/types";

interface GraphCanvasProps {
  onNavigateToCypher?: () => void;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({ onNavigateToCypher }) => {
  // Global Store Subscriptions
  const {
    selectedRunId,
    setSearchableNodes,
    focusedNodeId,
    setFocusedNodeId,
  } = useRunsStore();
  const { theme } = useThemeStore();
  const isDark = theme !== "light";
  const { settings: graphSettings } = useGraphSettingsStore();

  const {
    isDiffActive,
    diffData,
    scrubMode,
    activeFilter,
  } = useDiffStore();

  const {
    activeMask,
    activeOverlay,
    setActiveOverlay,
    isDrawerOpen: isViewOverlayDrawerOpen,
    openDrawer: openViewOverlayDrawer,
    closeDrawer: closeViewOverlayDrawer,
  } = useViewOverlayStore();

  const {
    activeMetricResult,
    instances: metricInstances,
    stylingVersion,
    scaleMode,
    isDrawerOpen: isMetricsDrawerOpen,
    openDrawer: openMetricsDrawer,
    closeDrawer: closeMetricsDrawer,
    clearMetricResult,
  } = useMetricsStore();

  // Engine Schema dynamic domain resolution
  const {
    getPolarity,
    getPartition,
    getNodeDefinition,
    getRelationDefinition,
  } = useEngineSchema();

  // Local UI State
  const [notification, setNotification] = useState<string | null>(null);
  const [showUnmapped, setShowUnmapped] = useState(false);
  const [selectedNode, setSelectedNode] = useState<StudioNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<StudioEdge | null>(null);

  // Layer visibility toggles (D-20: L1 defaults to off on cardinality grounds)
  const [showL1, setShowL1] = useState(false);
  const [showL2, setShowL2] = useState(true);
  const [showL3, setShowL3] = useState(true);

  // Graph layout and controls
  const [layoutType, setLayoutType] = useState<LayoutType>("d3-force");
  const [searchTerm, setSearchTerm] = useState("");
  const [showLegend, setShowLegend] = useState(true);

  // Context menus and inspectors
  const [nodeContextMenu, setNodeContextMenu] = useState<{
    node: StudioNode;
    x: number;
    y: number;
  } | null>(null);

  const [edgeContextMenu, setEdgeContextMenu] = useState<{
    edge: StudioEdge;
    x: number;
    y: number;
  } | null>(null);

  const [inspectedEdge, setInspectedEdge] = useState<StudioEdge | null>(null);

  // 1. Data Layer: Graph Data loading, expansion & fallback
  const {
    graphData,
    isLoading,
    isExpanding,
    neo4jError,
    loadGraph,
    handleExpandNode,
    dataSource,
    isNeo4j,
  } = useGraphData({ onNotify: setNotification });

  // 2. Filter Layer: Pure multi-layer, subgraph mask, diff & search filtering
  const { filteredNodes, filteredEdges } = useGraphFiltering({
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
  });

  // Type aggregates for HUD & lens dropdowns
  const nodeTypesInGraph = useMemo(() => {
    if (!graphData) return [];
    return Array.from(new Set(graphData.nodes.map((n) => n.type))).sort();
  }, [graphData]);

  const edgeTypesInGraph = useMemo(() => {
    if (!graphData) return [];
    return Array.from(new Set(graphData.edges.map((e) => e.type))).sort();
  }, [graphData]);

  // 3. Styling Layer: Pure functions consuming domain contexts
  // Decoupled from idle cards and drawer UI state via stylingVersion
  const activeCompletedMetricInstances = useMemo(() => {
    return metricInstances.filter(
      (inst) => inst.status === "completed" && inst.result && inst.styling?.enabled !== false
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stylingVersion]);

  const nodeStyleCtx = useMemo<NodeStyleContext>(
    () => ({
      isDark,
      activeOverlay,
      activeMetricResult,
      metricInstances: activeCompletedMetricInstances,
      scaleMode,
      isDiffActive,
      diffData,
      graphSettings,
      getPartition,
      getNodeDefinition,
    }),
    [
      isDark,
      activeOverlay,
      activeMetricResult,
      activeCompletedMetricInstances,
      scaleMode,
      isDiffActive,
      diffData,
      graphSettings,
      getPartition,
      getNodeDefinition,
    ]
  );

  const edgeStyleCtx = useMemo<EdgeStyleContext>(
    () => ({
      isDark,
      activeOverlay,
      activeMetricResult,
      metricInstances: activeCompletedMetricInstances,
      isDiffActive,
      diffData,
      graphSettings,
      getPolarity,
      getRelationDefinition,
    }),
    [
      isDark,
      activeOverlay,
      activeMetricResult,
      activeCompletedMetricInstances,
      isDiffActive,
      diffData,
      graphSettings,
      getPolarity,
      getRelationDefinition,
    ]
  );

  const getNodeStyle = useCallback(
    (node: StudioNode) => computeNodeStyle(node, nodeStyleCtx),
    [nodeStyleCtx]
  );

  const getEdgeStyle = useCallback(
    (edge: StudioEdge) => computeEdgeStyle(edge, edgeStyleCtx),
    [edgeStyleCtx]
  );

  // 4. Clustering & Hull Plugin Layer
  // (graphRef will be assigned by useG6Instance)
  const graphRefHolder = React.useRef<any>(null);

  const { syncHullPlugins } = useHullClustering({
    graphRef: graphRefHolder,
    activeMetricResult,
    activeOverlay,
    filteredNodes,
    isDark,
  });

  // 5. Canvas Engine Layer: G6 lifecycle, camera, coordinate caching & state sync
  const {
    containerRef,
    graphRef,
    isGraphReadyRef,
    handleZoomIn,
    handleZoomOut,
    handleFitView,
    handleFitCenter,
    focusElement,
    resetPositions,
  } = useG6Instance({
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
    onNodeClick: (node) => {
      setSelectedNode(node);
      setSelectedEdge(null);
      setShowUnmapped(false);
      setNodeContextMenu(null);
      setEdgeContextMenu(null);
    },
    onEdgeClick: (edge) => {
      setSelectedEdge(edge);
      setSelectedNode(null);
      setShowUnmapped(false);
      setNodeContextMenu(null);
      setEdgeContextMenu(null);
    },
    onNodeDblClick: (nodeId) => {
      if (dataSource === "neo4j") {
        handleExpandNode(nodeId);
      }
    },
    onNodeContextMenu: (node, x, y) => {
      setNodeContextMenu({ node, x, y });
      setEdgeContextMenu(null);
    },
    onEdgeContextMenu: (edge, x, y) => {
      setEdgeContextMenu({ edge, x, y });
      setNodeContextMenu(null);
    },
    onCanvasClick: () => {
      setSelectedNode(null);
      setSelectedEdge(null);
      setNodeContextMenu(null);
      setEdgeContextMenu(null);
    },
  });

  // Keep holder in sync with graphRef
  graphRefHolder.current = graphRef.current;

  // Sync searchable nodes to global header search
  useEffect(() => {
    if (graphData?.nodes) {
      setSearchableNodes(graphData.nodes);
    }
  }, [graphData?.nodes, setSearchableNodes]);

  // Handle global search focus from header
  useEffect(() => {
    if (!focusedNodeId || !graphData) return;
    const target = graphData.nodes.find((n) => n.id === focusedNodeId);
    if (target) {
      setSelectedNode(target);
      setSelectedEdge(null);
      if (isGraphReadyRef.current) {
        focusElement(target.id);
      }
    }
    setFocusedNodeId(null);
  }, [focusedNodeId, graphData, setFocusedNodeId, focusElement, isGraphReadyRef]);

  // Auto-dismiss notification toast
  useEffect(() => {
    if (!notification) return;
    const t = setTimeout(() => setNotification(null), 3500);
    return () => clearTimeout(t);
  }, [notification]);

  // Export handlers
  const handleExportFormat = useCallback(
    async (format: "json" | "graphml" | "gexf" | "png" | "svg") => {
      if (!graphData) {
        setNotification("No active graph data to export.");
        return;
      }
      try {
        if (format === "json") {
          exportGraphToJson(graphData, selectedRunId);
          setNotification("Exported raw graph topology to JSON.");
        } else if (format === "graphml") {
          exportGraphToGraphML(graphData, selectedRunId);
          setNotification("Exported scientific GraphML topology.");
        } else if (format === "gexf") {
          exportGraphToGexf(graphData, selectedRunId);
          setNotification("Exported GEXF network model.");
        } else if (format === "png" || format === "svg") {
          await exportGraphImage(graphRef.current, containerRef.current, format, selectedRunId);
          setNotification(`Exported high-resolution ${format.toUpperCase()} render.`);
        }
      } catch (err: any) {
        setNotification(`Export failed: ${err.message || err}`);
      }
    },
    [graphData, selectedRunId, graphRef, containerRef]
  );

  useEffect(() => {
    const handleExport = (e: Event) => {
      const format = (e as CustomEvent).detail?.format ?? "json";
      handleExportFormat(format);
    };
    window.addEventListener("glp-export-graph", handleExport);
    return () => window.removeEventListener("glp-export-graph", handleExport);
  }, [handleExportFormat]);

  const handleLayoutChange = useCallback(
    (newLayout: LayoutType) => {
      resetPositions();
      setLayoutType(newLayout);
    },
    [resetPositions]
  );

  const handleClearMetric = useCallback(() => {
    if (
      activeMetricResult &&
      activeOverlay?.id === `metric-overlay-${activeMetricResult.execution_id}`
    ) {
      setActiveOverlay(null);
    }
    clearMetricResult();
  }, [activeMetricResult, activeOverlay, clearMetricResult, setActiveOverlay]);

  const handleToggleMetricsDrawer = useCallback(() => {
    if (isMetricsDrawerOpen) {
      closeMetricsDrawer();
    } else {
      closeViewOverlayDrawer();
      openMetricsDrawer(selectedNode ? "single_node" : "global", undefined, selectedNode?.id);
    }
  }, [isMetricsDrawerOpen, closeMetricsDrawer, closeViewOverlayDrawer, openMetricsDrawer, selectedNode]);

  const handleToggleViewOverlayDrawer = useCallback(() => {
    if (isViewOverlayDrawerOpen) {
      closeViewOverlayDrawer();
    } else {
      closeMetricsDrawer();
      openViewOverlayDrawer();
    }
  }, [isViewOverlayDrawerOpen, closeViewOverlayDrawer, closeMetricsDrawer, openViewOverlayDrawer]);

  return (
    <div className="flex-1 flex h-full bg-app-bg overflow-hidden relative">
      {/* Interactive Canvas Container */}
      <div className="flex-1 bg-app-surface relative overflow-hidden flex flex-col">
        <ConfigDiffDrawer />

        {/* Floating Canvas HUD: Layout, Viewport, Layers, Overlay & Metrics */}
        <GraphCanvasHud
          layoutType={layoutType}
          onLayoutChange={handleLayoutChange}
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onFitView={handleFitView}
          onFitCenter={handleFitCenter}
          onRefresh={loadGraph}
          isLoading={isLoading}
          isExpanding={isExpanding}
          showL1={showL1}
          showL2={showL2}
          showL3={showL3}
          layerCounts={graphData?.layer_counts}
          onToggleL1={() => setShowL1(!showL1)}
          onToggleL2={() => setShowL2(!showL2)}
          onToggleL3={() => setShowL3(!showL3)}
          onResetLayers={() => {
            setShowL1(false);
            setShowL2(true);
            setShowL3(true);
          }}
          onShowAllLayers={() => {
            setShowL1(true);
            setShowL2(true);
            setShowL3(true);
          }}
          runId={selectedRunId}
          graphVersion={graphData?.graph_version}
          activeOverlay={activeOverlay}
          onOverlayChange={setActiveOverlay}
          nodeTypesInGraph={nodeTypesInGraph}
          edgeTypesInGraph={edgeTypesInGraph}
          onNavigateToCypher={onNavigateToCypher}
          isViewOverlayDrawerOpen={isViewOverlayDrawerOpen}
          onToggleViewOverlayDrawer={handleToggleViewOverlayDrawer}
          isMetricsDrawerOpen={isMetricsDrawerOpen}
          activeMetricResult={activeMetricResult}
          activeMetricInstancesCount={metricInstances.filter((i) => i.status === "completed").length}
          onToggleMetricsDrawer={handleToggleMetricsDrawer}
          onClearMetric={handleClearMetric}
        />

        {/* Notification Toast */}
        {notification && (
          <div className="absolute top-3 right-3 z-30 flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40 rounded-lg shadow-lg text-xs backdrop-blur-xs">
            <Check className="w-3.5 h-3.5" />
            <span>{notification}</span>
          </div>
        )}

        {/* Canvas Display & Empty States */}
        {!isNeo4j && !selectedRunId ? (
          <div className="flex-1 flex flex-col items-center justify-center text-xs text-app-muted space-y-3 p-6 text-center">
            <HardDrive className="w-8 h-8 text-app-muted/50 mb-1" />
            <div className="font-semibold text-app-heading">No Pipeline Run Selected</div>
            <p className="max-w-md">
              Select a run from the left panel to visualize its immutable artifact graph snapshot, or connect Neo4j in the Cypher Console for live cross-run exploration.
            </p>
            {onNavigateToCypher && (
              <button
                onClick={onNavigateToCypher}
                className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition-colors shadow-xs cursor-pointer flex items-center gap-1.5"
              >
                <Database className="w-3.5 h-3.5" />
                Connect Neo4j in Cypher Console
              </button>
            )}
          </div>
        ) : isLoading ? (
          <div className="flex-1 flex flex-col items-center justify-center text-xs text-app-muted space-y-2">
            <Loader2 className="w-6 h-6 animate-spin text-blue-500 dark:text-blue-400" />
            <div>
              {dataSource === "neo4j"
                ? "Querying live graph projection from Neo4j..."
                : "Materializing graph projection from artifacts..."}
            </div>
          </div>
        ) : neo4jError && dataSource === "neo4j" ? (
          <div className="flex-1 flex flex-col items-center justify-center text-xs text-red-500 dark:text-red-400 space-y-2 p-6 text-center">
            <AlertCircle className="w-6 h-6 mb-1" />
            <div className="font-semibold text-app-heading">Failed to load graph from Neo4j</div>
            <p className="max-w-md text-xs">{neo4jError}</p>
            <div className="flex gap-2 mt-2">
              <button
                onClick={loadGraph}
                className="px-3 py-1 bg-app-surface text-app-heading rounded border border-app-border hover:bg-app-subtle cursor-pointer"
              >
                Retry Query
              </button>
              {onNavigateToCypher && (
                <button
                  onClick={onNavigateToCypher}
                  className="px-3 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-500 cursor-pointer"
                >
                  Reconfigure in Cypher Console
                </button>
              )}
            </div>
          </div>
        ) : filteredNodes.length === 0 && graphData ? (
          <div className="flex-1 flex flex-col items-center justify-center text-xs text-app-muted space-y-2">
            <div>No nodes match the current layer filters or search term.</div>
            <button
              onClick={() => {
                setShowL1(true);
                setShowL2(true);
                setShowL3(true);
                setSearchTerm("");
              }}
              className="px-3 py-1 bg-blue-600/20 text-blue-500 dark:text-blue-400 rounded border border-blue-500/30 hover:bg-blue-600/30 cursor-pointer"
            >
              Reset Layer Filters
            </button>
          </div>
        ) : (
          <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />
        )}

        {/* Floating Metadata & Legend Plane */}
        {showLegend ? (
          <div className="absolute bottom-3 left-3 bg-app-surface/90 backdrop-blur-md border border-app-border rounded-lg p-2.5 text-[11px] text-app-muted shadow-xl space-y-2 pointer-events-auto max-w-xs z-10 select-none">
            <div className="flex items-center justify-between font-semibold text-app-heading text-[10px] uppercase border-b border-app-border-subtle pb-1.5">
              <span className="flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5 text-app-muted" />
                Metadata & Legend
              </span>
              <button
                onClick={() => setShowLegend(false)}
                className="text-app-muted hover:text-app-heading text-[10px] cursor-pointer"
              >
                Hide
              </button>
            </div>

            {/* Live Telemetry Stats & Unmapped Predicates Alert */}
            {graphData && (
              <div className="flex items-center justify-between gap-2 border-b border-app-border-subtle pb-1.5">
                <div className="flex items-center space-x-1.5 text-[11px] text-app-muted font-mono">
                  <span>
                    <strong className="text-app-heading font-semibold">{filteredNodes.length}</strong> nodes
                  </span>
                  <span>·</span>
                  <span>
                    <strong className="text-app-heading font-semibold">{filteredEdges.length}</strong> edges
                  </span>
                </div>

                {graphData.unmapped_predicates && Object.keys(graphData.unmapped_predicates).length > 0 && (
                  <button
                    onClick={() => {
                      setShowUnmapped(!showUnmapped);
                      if (!showUnmapped) setSelectedNode(null);
                    }}
                    className={`flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-mono transition-colors cursor-pointer ${
                      showUnmapped
                        ? "bg-amber-500/20 text-amber-600 dark:text-amber-300 border-amber-500/40 font-medium"
                        : "bg-app-bg text-amber-600 dark:text-amber-400 border-amber-500/30 hover:bg-amber-500/10"
                    }`}
                    title="View unmapped open-vocabulary predicates"
                  >
                    <AlertCircle className="w-2.5 h-2.5 shrink-0" />
                    <span>{Object.keys(graphData.unmapped_predicates).length} unmapped</span>
                  </button>
                )}
              </div>
            )}

            <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[10px]">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block" />
                <span>L1 Chunks</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-purple-500 inline-block" />
                <span>L2 Entities</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
                <span>L3 TheoryNet</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-600 border border-dashed border-amber-400 inline-block" />
                <span>Unresolved (D-16)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 bg-emerald-500 dark:bg-emerald-400 inline-block" />
                <span>Support (+1)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 bg-red-500 dark:bg-red-400 inline-block" />
                <span>Attack (-1)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 bg-slate-400 inline-block" />
                <span>Neutral (0)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 border-b border-dashed border-slate-500 inline-block" />
                <span>Unmapped (null)</span>
              </div>

              {activeMetricResult && (
                <>
                  <div className="flex items-center gap-1.5 col-span-2 border-t border-app-border-subtle pt-1 mt-0.5 text-app-heading font-medium">
                    <span>Causal Traversal Indicators</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">[▲]</span>
                    <span>Support Path</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[10px] text-red-600 dark:text-red-400 font-semibold">[▼]</span>
                    <span>Attack Path</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[10px] text-purple-600 dark:text-purple-400 font-semibold">[▲/▼]</span>
                    <span>Multi-role (±)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full border border-app-heading inline-block" />
                    <span>Focus Target</span>
                  </div>
                </>
              )}
            </div>
            <div className="text-[10px] text-app-muted border-t border-app-border-subtle pt-1">
              {dataSource === "neo4j" ? (
                <span>
                  Click to inspect. <strong>Double-click or right-click</strong> node to expand 1-hop neighborhood.
                </span>
              ) : (
                <span>Click node to inspect evidence trail and attributes.</span>
              )}
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowLegend(true)}
            className="absolute bottom-3 left-3 bg-app-surface/90 backdrop-blur-md border border-app-border rounded-md px-2.5 py-1 text-[11px] text-app-muted hover:text-app-heading shadow-md flex items-center gap-1.5 cursor-pointer z-10"
            title="Show Metadata & Legend"
          >
            <Info className="w-3.5 h-3.5 text-app-muted" />
            <span>Metadata & Legend</span>
            {graphData && (
              <span className="text-[10px] font-mono text-app-muted border-l border-app-border pl-1.5 ml-0.5">
                {filteredNodes.length} nodes
              </span>
            )}
          </button>
        )}
      </div>

      {/* Docked Right Metrics Panel */}
      {isMetricsDrawerOpen && (
        <ResizablePanel storageKey="glp-studio-panel-metrics-width">
          <MetricsDrawer
            selectedNode={selectedNode}
            onSelectNode={(nodeId) => {
              const target = graphData?.nodes.find((n) => n.id === nodeId);
              if (target) setSelectedNode(target);
            }}
            dataSource={dataSource}
            runId={selectedRunId}
            graphVersion={graphData?.graph_version}
            nodeTypesInGraph={nodeTypesInGraph}
            edgeTypesInGraph={edgeTypesInGraph}
          />
        </ResizablePanel>
      )}

      {/* Docked Right Views & Overlays Panel */}
      {isViewOverlayDrawerOpen && !isMetricsDrawerOpen && (
        <ResizablePanel storageKey="glp-studio-panel-viewoverlay-width">
          <ViewOverlayDrawer
            graphData={graphData}
            runId={dataSource === "artifacts" ? selectedRunId : null}
            graphVersion={graphData?.graph_version}
            dataSource={dataSource}
            nodeTypesInGraph={nodeTypesInGraph}
            edgeTypesInGraph={edgeTypesInGraph}
            onNavigateToCypher={onNavigateToCypher}
            onClose={closeViewOverlayDrawer}
          />
        </ResizablePanel>
      )}

      {/* Docked Right Node Inspector Panel */}
      {selectedNode && graphData && !isMetricsDrawerOpen && !isViewOverlayDrawerOpen && (
        <ResizablePanel storageKey="glp-studio-panel-nodeinspector-width">
          <NodeInspectorPanel
            node={selectedNode}
            runId={dataSource === "artifacts" ? selectedRunId : null}
            allNodes={graphData.nodes}
            edges={graphData.edges}
            activeOverlay={activeOverlay}
            isNeo4j={dataSource === "neo4j"}
            onExpand={handleExpandNode}
            onCalculateMetrics={(n) => openMetricsDrawer("single_node", undefined, n.id)}
            onClose={() => setSelectedNode(null)}
            onSelectNode={(nodeId) => {
              const target = graphData.nodes.find((n) => n.id === nodeId);
              if (target) setSelectedNode(target);
            }}
            onNotify={setNotification}
          />
        </ResizablePanel>
      )}

      {/* Docked Right Edge Inspector Panel */}
      {selectedEdge && graphData && !isMetricsDrawerOpen && !isViewOverlayDrawerOpen && (
        <ResizablePanel storageKey="glp-studio-panel-edgeinspector-width">
          <EdgeInspectorPanel
            edge={selectedEdge}
            allNodes={graphData.nodes}
            allEdges={graphData.edges}
            activeMetricResult={activeMetricResult}
            onClose={() => setSelectedEdge(null)}
            onSelectNode={(nodeId) => {
              const target = graphData.nodes.find((n) => n.id === nodeId);
              if (target) {
                setSelectedEdge(null);
                setSelectedNode(target);
              }
            }}
            onNotify={setNotification}
          />
        </ResizablePanel>
      )}

      {/* Docked Right Unmapped Predicates Panel */}
      {showUnmapped && !selectedNode && !selectedEdge && !isMetricsDrawerOpen && !isViewOverlayDrawerOpen && (
        <ResizablePanel storageKey="glp-studio-panel-unmapped-width">
          <UnmappedPredicatesPanel graphView={graphData} />
        </ResizablePanel>
      )}

      {/* Node Context Menu */}
      {nodeContextMenu && (
        <NodeContextMenu
          node={nodeContextMenu.node}
          x={nodeContextMenu.x}
          y={nodeContextMenu.y}
          onExpand={(nodeId) => {
            if (dataSource === "neo4j") {
              handleExpandNode(nodeId);
            } else {
              setNotification("Neighborhood expansion requires live Neo4j store.");
            }
          }}
          onCalculateMetrics={(node) => {
            setSelectedNode(node);
            setSelectedEdge(null);
            openMetricsDrawer("single_node", undefined, node.id);
          }}
          onInspect={(node) => {
            setSelectedNode(node);
            setSelectedEdge(null);
            setShowUnmapped(false);
          }}
          onClose={() => setNodeContextMenu(null)}
          onNotify={setNotification}
        />
      )}

      {/* Edge Context Menu */}
      {edgeContextMenu && (
        <EdgeContextMenu
          edge={edgeContextMenu.edge}
          x={edgeContextMenu.x}
          y={edgeContextMenu.y}
          onInspect={(edge) => {
            setSelectedEdge(edge);
            setSelectedNode(null);
            setShowUnmapped(false);
          }}
          onFilterPath={(edge) => {
            const src = graphData?.nodes.find((n) => n.id === edge.source);
            if (src) setSelectedNode(src);
            setNotification(`Focusing path around edge: ${edge.source} → ${edge.target}`);
          }}
          onClose={() => setEdgeContextMenu(null)}
          onNotify={setNotification}
        />
      )}

      {/* Edge Inspector Modal */}
      {inspectedEdge && graphData && (
        <EdgeInspectorModal
          edge={inspectedEdge}
          allNodes={graphData.nodes}
          onClose={() => setInspectedEdge(null)}
          onSelectNode={(nodeId) => {
            const target = graphData.nodes.find((n) => n.id === nodeId);
            if (target) setSelectedNode(target);
            setInspectedEdge(null);
          }}
          onNotify={setNotification}
        />
      )}

      {/* Polarity Inversion Modal */}
      <PolarityInversionModal
        onFocusEndpoints={(sourceId) => {
          const target = graphData?.nodes.find((n) => n.id === sourceId);
          if (target) {
            setSelectedNode(target);
            if (isGraphReadyRef.current) {
              focusElement(target.id);
            }
          }
        }}
      />
    </div>
  );
};
