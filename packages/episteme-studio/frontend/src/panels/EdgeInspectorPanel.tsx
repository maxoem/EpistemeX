import React, { useState, useMemo } from "react";
import { StudioEdge, StudioNode, MetricResult } from "../api/types";
import {
  X,
  ArrowRight,
  Copy,
  Check,
  Database,
  Search,
  Code2,
  Table,
} from "lucide-react";
import { useEngineSchema } from "../store/engineSettingsStore";

interface EdgeInspectorPanelProps {
  edge: StudioEdge;
  allNodes: StudioNode[];
  allEdges?: StudioEdge[];
  activeMetricResult?: MetricResult | null;
  onClose: () => void;
  onSelectNode: (nodeId: string) => void;
  onNotify?: (msg: string) => void;
}

export const EdgeInspectorPanel: React.FC<EdgeInspectorPanelProps> = ({
  edge,
  allNodes,
  activeMetricResult,
  onClose,
  onSelectNode,
  onNotify,
}) => {
  const [copiedId, setCopiedId] = useState(false);
  const [copiedCypher, setCopiedCypher] = useState(false);
  const [copiedStatement, setCopiedStatement] = useState(false);
  const [copiedProps, setCopiedProps] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "props">("overview");

  const { getPolarity, getRelationDefinition } = useEngineSchema();
  const resolvedPolarity = getPolarity(edge.type) ?? edge.polarity ?? (edge.props as any)?.polarity ?? null;
  const relationDefinition = getRelationDefinition(edge.type);

  // Properties tab state
  const [propsSearchQuery, setPropsSearchQuery] = useState("");
  const [propsViewMode, setPropsViewMode] = useState<"table" | "json">("table");

  const sourceNode = allNodes.find((n) => n.id === edge.source);
  const targetNode = allNodes.find((n) => n.id === edge.target);

  const edgeTenability =
    edge.tenability ?? (edge.props as any)?.tenability ?? (edge.props as any)?.tenability_score;

  // Check if active metric result affects this edge
  const affectedMetricDetail = activeMetricResult?.affected_edges.find(
    (ae) =>
      ae.relationship_id === edge.id ||
      (ae.source_node_id === edge.source && ae.target_node_id === edge.target)
  );

  const statementText = useMemo(() => {
    return (
      edge.props?.statement ||
      edge.props?.text ||
      edge.props?.source_sentence ||
      edge.props?.quote ||
      null
    );
  }, [edge]);

  const handleCopyId = () => {
    navigator.clipboard.writeText(edge.id);
    setCopiedId(true);
    onNotify?.(`Copied Edge ID: ${edge.id}`);
    setTimeout(() => setCopiedId(false), 1800);
  };

  const handleCopyStatement = () => {
    if (!statementText) return;
    navigator.clipboard.writeText(statementText);
    setCopiedStatement(true);
    onNotify?.("Copied statement text");
    setTimeout(() => setCopiedStatement(false), 1800);
  };

  const handleCopyCypher = () => {
    const query = `MATCH (s)-[r:${edge.type}]->(t) WHERE s.id = '${edge.source}' AND t.id = '${edge.target}' RETURN s, r, t;`;
    navigator.clipboard.writeText(query);
    setCopiedCypher(true);
    onNotify?.("Copied Cypher match query to clipboard");
    setTimeout(() => setCopiedCypher(false), 1800);
  };

  const handleCopyPropsJson = () => {
    const payload = {
      id: edge.id,
      type: edge.type,
      source: edge.source,
      target: edge.target,
      layer: edge.layer,
      polarity: edge.polarity,
      weight: edge.weight,
      confidence: edge.confidence,
      tenability: edgeTenability,
      props: edge.props,
    };
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setCopiedProps(true);
    onNotify?.("Copied properties JSON to clipboard");
    setTimeout(() => setCopiedProps(false), 1800);
  };

  const getPolarityMarker = () => {
    if (resolvedPolarity === 1) {
      return (
        <span className="font-mono text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">
          support (+1)
        </span>
      );
    }
    if (resolvedPolarity === -1) {
      return (
        <span className="font-mono text-[10px] text-rose-600 dark:text-rose-400 font-medium">
          attack (-1)
        </span>
      );
    }
    if (resolvedPolarity === 0) {
      return (
        <span className="font-mono text-[10px] text-app-muted">
          neutral (0)
        </span>
      );
    }
    return (
      <span className="font-mono text-[10px] text-app-muted opacity-50">
        unmapped
      </span>
    );
  };

  const getLayerLabel = (layer: number) => {
    switch (layer) {
      case 1:
        return "L1 Evidence";
      case 2:
        return "L2 Relation";
      case 3:
        return "L3 TheoryNet";
      default:
        return `Layer ${layer}`;
    }
  };

  const propEntries = useMemo(() => {
    const raw = Object.entries(edge.props || {}).filter(([k]) => k !== "embedding");
    if (!propsSearchQuery.trim()) return raw;
    const q = propsSearchQuery.toLowerCase();
    return raw.filter(
      ([k, v]) => k.toLowerCase().includes(q) || String(v).toLowerCase().includes(q)
    );
  }, [edge.props, propsSearchQuery]);

  return (
    <div className="w-full h-full flex flex-col bg-app-surface text-xs text-app-text select-none">
      {/* Primary Entity Header */}
      <div className="px-4 py-3 border-b border-app-border bg-app-surface flex items-start justify-between gap-3 shrink-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 text-[11px] font-mono text-app-muted">
            <span className="text-app-heading font-medium">{getLayerLabel(edge.layer)}</span>
            <span>·</span>
            <span className="text-app-heading font-semibold">{edge.type}</span>
            <span>·</span>
            {getPolarityMarker()}
          </div>

          <h3
            className="text-sm font-semibold text-app-heading leading-snug break-words line-clamp-2 select-text"
            title={`${sourceNode?.label || edge.source} → ${targetNode?.label || edge.target}`}
          >
            {sourceNode?.label || edge.source} → {targetNode?.label || edge.target}
          </h3>

          <div className="flex items-center gap-1.5 mt-1 text-[11px] text-app-muted">
            <span className="font-mono text-[10px] text-app-muted/80 select-text truncate max-w-[210px]" title={edge.id}>
              {edge.id}
            </span>
            <button
              onClick={handleCopyId}
              className="p-0.5 text-app-muted hover:text-app-heading rounded transition-colors cursor-pointer"
              title="Copy Edge ID"
            >
              {copiedId ? (
                <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <Copy className="w-3 h-3" />
              )}
            </button>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer shrink-0"
          title="Close Inspector"
          aria-label="Close Inspector"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Tabbed Navigation */}
      <div className="flex border-b border-app-border bg-app-surface px-4 text-xs gap-6 shrink-0">
        <button
          onClick={() => setActiveTab("overview")}
          className={`py-2 text-xs transition-colors cursor-pointer relative ${
            activeTab === "overview"
              ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
              : "text-app-muted hover:text-app-heading"
          }`}
        >
          Overview & Causal
        </button>
        <button
          onClick={() => setActiveTab("props")}
          className={`py-2 text-xs transition-colors flex items-center gap-1.5 cursor-pointer relative ${
            activeTab === "props"
              ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
              : "text-app-muted hover:text-app-heading"
          }`}
        >
          <span>Properties</span>
          <span className="font-mono text-[10px] text-app-muted">
            ({Object.keys(edge.props || {}).length})
          </span>
        </button>
      </div>

      {/* Panel Body */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 text-xs select-text">
        {activeTab === "overview" && (
          <>
            {/* Quantitative Metrics Row: Tight line-based layout */}
            <div className="space-y-1.5">
              <div className="pb-1 border-b border-app-border">
                <span className="text-xs font-semibold text-app-heading">Quantitative Metrics</span>
              </div>

              <div className="flex items-baseline justify-between py-1.5 border-b border-app-border-subtle">
                <div className="flex flex-col">
                  <span className="text-[9px] uppercase font-mono tracking-widest text-app-muted">
                    Weight (φ)
                  </span>
                  <span className="font-mono text-sm font-semibold text-app-heading tabular-nums mt-0.5">
                    {edge.weight !== null && edge.weight !== undefined
                      ? Number(edge.weight).toFixed(3)
                      : "—"}
                  </span>
                </div>

                <div className="flex flex-col">
                  <span className="text-[9px] uppercase font-mono tracking-widest text-app-muted">
                    Confidence
                  </span>
                  <span className="font-mono text-sm font-semibold text-app-heading tabular-nums mt-0.5">
                    {edge.confidence !== null && edge.confidence !== undefined
                      ? `${(Number(edge.confidence) * 100).toFixed(0)}%`
                      : "—"}
                  </span>
                </div>

                {edgeTenability !== null && edgeTenability !== undefined && (
                  <div className="flex flex-col">
                    <span className="text-[9px] uppercase font-mono tracking-widest text-app-muted">
                      Tenability (TS)
                    </span>
                    <span className="font-mono text-sm font-semibold text-app-heading tabular-nums mt-0.5">
                      {Number(edgeTenability).toFixed(3)}
                    </span>
                  </div>
                )}

                <div className="flex flex-col">
                  <span className="text-[9px] uppercase font-mono tracking-widest text-app-muted">
                    Status
                  </span>
                  <span
                    className={`font-mono text-xs font-semibold mt-0.5 ${
                      edgeTenability !== null && edgeTenability !== undefined
                        ? edgeTenability >= 0.8
                          ? "text-emerald-600 dark:text-emerald-400"
                          : edgeTenability >= 0.5
                          ? "text-amber-600 dark:text-amber-400"
                          : "text-rose-600 dark:text-rose-400"
                        : "text-app-muted"
                    }`}
                  >
                    {edgeTenability !== null && edgeTenability !== undefined
                      ? edgeTenability >= 0.8
                        ? "Satisfied"
                        : edgeTenability >= 0.5
                        ? "Tension"
                        : "Violated"
                      : "Unassessed"}
                  </span>
                </div>
              </div>
            </div>

            {/* Dual-Process Decision Calibration & QBAF Inferential Metrics */}
            <div className="space-y-1.5 p-2.5 rounded-lg border border-app-border bg-app-surface/50">
              <div className="pb-1 border-b border-app-border flex items-center justify-between">
                <span className="text-xs font-semibold text-app-heading flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  Decision Calibration & QBAF
                </span>
                {edge.decision_tier && (
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {edge.decision_tier}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
                <div>
                  <span className="text-[9px] uppercase tracking-wider text-app-muted block">Empirical Acc (P)</span>
                  <span className="font-semibold text-emerald-500">
                    {edge.empirical_accuracy !== null && edge.empirical_accuracy !== undefined
                      ? `${(edge.empirical_accuracy * 100).toFixed(1)}%`
                      : "—"}
                  </span>
                </div>
                <div>
                  <span className="text-[9px] uppercase tracking-wider text-app-muted block">Inferential Force (I)</span>
                  <span className="font-semibold text-app-heading">
                    {edge.inferential_force !== null && edge.inferential_force !== undefined
                      ? edge.inferential_force.toFixed(3)
                      : "—"}
                  </span>
                </div>
                <div>
                  <span className="text-[9px] uppercase tracking-wider text-app-muted block">Active Weight (W_ji)</span>
                  <span className="text-app-text">
                    {edge.active_weight !== null && edge.active_weight !== undefined
                      ? edge.active_weight.toFixed(3)
                      : "—"}
                  </span>
                </div>
                <div>
                  <span className="text-[9px] uppercase tracking-wider text-app-muted block">Admissibility</span>
                  <span className={edge.is_admissible === false ? "text-amber-500" : "text-emerald-500"}>
                    {edge.is_admissible !== undefined ? (edge.is_admissible ? "Admissible" : "Filtered") : "Admissible"}
                  </span>
                </div>
                {edge.conformal_set_size !== null && edge.conformal_set_size !== undefined && (
                  <div className="col-span-2">
                    <span className="text-[9px] uppercase tracking-wider text-app-muted block">Conformal Set Size</span>
                    <span className="text-blue-400">|C(x)| = {edge.conformal_set_size}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Relational Endpoints: Flat list style */}
            <div className="space-y-1.5">
              <div className="pb-1 border-b border-app-border">
                <span className="text-xs font-semibold text-app-heading">Relationship Endpoints</span>
              </div>

              <div className="divide-y divide-app-border-subtle">
                <button
                  onClick={() => onSelectNode(edge.source)}
                  className="w-full py-1.5 text-left hover:bg-app-subtle/50 transition-colors cursor-pointer group px-1 -mx-1 rounded-xs"
                  title={`Inspect source node: ${edge.source}`}
                >
                  <div className="text-[10px] text-app-muted font-mono">
                    source
                  </div>
                  <div className="font-medium text-app-heading group-hover:text-blue-500 truncate text-xs">
                    {sourceNode?.label || edge.source}
                  </div>
                  <div className="font-mono text-[10px] text-app-muted truncate">{edge.source}</div>
                </button>

                <button
                  onClick={() => onSelectNode(edge.target)}
                  className="w-full py-1.5 text-left hover:bg-app-subtle/50 transition-colors cursor-pointer group px-1 -mx-1 rounded-xs"
                  title={`Inspect target node: ${edge.target}`}
                >
                  <div className="text-[10px] text-app-muted font-mono">
                    target
                  </div>
                  <div className="font-medium text-app-heading group-hover:text-blue-500 truncate text-xs">
                    {targetNode?.label || edge.target}
                  </div>
                  <div className="font-mono text-[10px] text-app-muted truncate">{edge.target}</div>
                </button>
              </div>
            </div>

            {/* Active Schema Epistemic Definition */}
            {relationDefinition && (
              <div className="space-y-1.5">
                <div className="pb-1 border-b border-app-border">
                  <span className="text-xs font-semibold text-app-heading">Schema Definition</span>
                </div>
                <div className="p-2.5 rounded bg-app-subtle/50 border border-app-border-subtle text-[11px] text-app-text leading-relaxed select-text">
                  {relationDefinition}
                </div>
              </div>
            )}

            {/* Active Metric Causal Analysis */}
            {affectedMetricDetail && (
              <div className="space-y-1.5">
                <div className="pb-1 border-b border-app-border">
                  <span className="text-xs font-semibold text-app-heading">
                    Causal Pathway: {activeMetricResult?.metric_id}
                  </span>
                </div>
                <div className="flex items-baseline gap-8 py-1 font-mono text-xs">
                  <div>
                    <span className="text-[9px] uppercase tracking-wider text-app-muted block">Role</span>
                    <span className="font-mono text-xs font-bold text-app-heading capitalize mt-0.5 block">
                      {affectedMetricDetail.role}
                    </span>
                  </div>
                  <div>
                    <span className="text-[9px] uppercase tracking-wider text-app-muted block">Contribution (Δ)</span>
                    <span className="font-mono text-xs font-bold text-app-heading tabular-nums mt-0.5 block">
                      {affectedMetricDetail.contribution !== null &&
                      affectedMetricDetail.contribution !== undefined
                        ? affectedMetricDetail.contribution > 0
                          ? `+${affectedMetricDetail.contribution.toFixed(4)}`
                          : affectedMetricDetail.contribution.toFixed(4)
                        : "—"}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Statement / Citation Evidence */}
            {statementText && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between pb-1 border-b border-app-border">
                  <span className="text-xs font-semibold text-app-heading">
                    Evidence / Statement
                  </span>
                  <button
                    onClick={handleCopyStatement}
                    className="flex items-center gap-1 text-[11px] text-app-muted hover:text-app-heading transition-colors cursor-pointer"
                    title="Copy statement text"
                  >
                    {copiedStatement ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                        <span className="text-emerald-600 dark:text-emerald-400 font-mono text-[10px]">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span className="font-mono text-[10px]">Copy</span>
                      </>
                    )}
                  </button>
                </div>
                <blockquote className="text-xs leading-relaxed text-app-heading select-text border-l border-app-border pl-3 py-0.5 font-normal">
                  "{statementText}"
                </blockquote>
              </div>
            )}

            {/* Quick Cypher Match Query Helper */}
            <div className="pt-2 border-t border-app-border-subtle flex items-center justify-between">
              <button
                onClick={handleCopyCypher}
                className="flex items-center gap-1.5 text-[11px] font-mono text-app-muted hover:text-app-heading transition-colors cursor-pointer"
              >
                {copiedCypher ? (
                  <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                ) : (
                  <Database className="w-3.5 h-3.5 text-app-muted" />
                )}
                <span>Copy Cypher Match Query</span>
              </button>
            </div>
          </>
        )}

        {/* Enhanced Properties Tab with 2-Column Key-Value Grid */}
        {activeTab === "props" && (
          <div className="space-y-3">
            {/* Search and View Mode Toolbar */}
            <div className="flex items-center justify-between gap-2 pb-1 border-b border-app-border-subtle">
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-app-muted" />
                <input
                  type="text"
                  placeholder="Filter properties..."
                  value={propsSearchQuery}
                  onChange={(e) => setPropsSearchQuery(e.target.value)}
                  className="w-full pl-7 pr-2 py-1 text-xs bg-transparent border-b border-app-border text-app-heading placeholder:text-app-muted focus:outline-none focus:border-app-muted"
                />
              </div>

              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPropsViewMode("table")}
                  className={`p-1 rounded cursor-pointer transition-colors ${
                    propsViewMode === "table"
                      ? "text-app-heading font-medium bg-app-subtle"
                      : "text-app-muted hover:text-app-heading"
                  }`}
                  title="Table View"
                >
                  <Table className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setPropsViewMode("json")}
                  className={`p-1 rounded cursor-pointer transition-colors ${
                    propsViewMode === "json"
                      ? "text-app-heading font-medium bg-app-subtle"
                      : "text-app-muted hover:text-app-heading"
                  }`}
                  title="JSON View"
                >
                  <Code2 className="w-3.5 h-3.5" />
                </button>
              </div>

              <button
                onClick={handleCopyPropsJson}
                className="flex items-center gap-1 text-[11px] text-app-muted hover:text-app-heading transition-colors cursor-pointer shrink-0 font-mono"
                title="Copy edge properties as JSON"
              >
                {copiedProps ? (
                  <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                ) : (
                  <Copy className="w-3 h-3 text-app-muted" />
                )}
                <span>JSON</span>
              </button>
            </div>

            {propsViewMode === "table" ? (
              propEntries.length === 0 ? (
                <div className="py-4 text-center text-xs text-app-muted italic">
                  No properties match "{propsSearchQuery}".
                </div>
              ) : (
                <div className="divide-y divide-app-border-subtle font-mono text-[11px] select-text">
                  {propEntries.map(([k, v]) => (
                    <div
                      key={k}
                      className="grid grid-cols-12 gap-3 py-1.5 items-start"
                    >
                      <span
                        className="col-span-5 text-right text-app-muted truncate font-mono text-[11px]"
                        title={k}
                      >
                        {k}
                      </span>
                      <div className="col-span-7 text-left break-all text-app-heading font-mono select-text text-[11px]">
                        {typeof v === "object" && v !== null ? (
                          <pre className="p-1 text-[10px] font-mono overflow-x-auto whitespace-pre-wrap bg-app-subtle/50">
                            {JSON.stringify(v, null, 2)}
                          </pre>
                        ) : typeof v === "boolean" ? (
                          <span className={v ? "text-emerald-600 dark:text-emerald-400 font-semibold" : "text-rose-600 dark:text-rose-400 font-semibold"}>
                            {String(v)}
                          </span>
                        ) : typeof v === "number" ? (
                          <span className="tabular-nums font-semibold">{v}</span>
                        ) : (
                          <span>{String(v)}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )
            ) : (
              /* Raw JSON Mode */
              <pre className="p-2 text-[11px] font-mono text-app-text overflow-x-auto whitespace-pre-wrap select-text bg-transparent">
                {JSON.stringify(
                  {
                    id: edge.id,
                    type: edge.type,
                    source: edge.source,
                    target: edge.target,
                    layer: edge.layer,
                    polarity: edge.polarity,
                    weight: edge.weight,
                    confidence: edge.confidence,
                    tenability: edgeTenability,
                    props: edge.props,
                  },
                  null,
                  2
                )}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
