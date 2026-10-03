import React, { useEffect, useState, useMemo } from "react";
import { StudioNode, StudioEdge, EvidenceTrail, Overlay } from "../api/types";
import { api } from "../api/client";
import {
  X,
  Copy,
  Check,
  Network,
  Activity,
  AlertCircle,
  Search,
  Code2,
  Table,
  ChevronDown,
  ChevronRight,
  Database,
  ArrowRight,
} from "lucide-react";
import { useEngineSchema } from "../store/engineSettingsStore";

interface NodeInspectorPanelProps {
  node: StudioNode;
  runId?: string | null;
  allNodes: StudioNode[];
  edges: StudioEdge[];
  activeOverlay?: Overlay | null;
  isNeo4j?: boolean;
  onExpand?: (nodeId: string) => void;
  onCalculateMetrics?: (node: StudioNode) => void;
  onClose: () => void;
  onSelectNode: (nodeId: string) => void;
  onNotify?: (msg: string) => void;
}

export const NodeInspectorPanel: React.FC<NodeInspectorPanelProps> = ({
  node,
  runId,
  allNodes,
  edges,
  activeOverlay,
  isNeo4j = false,
  onExpand,
  onCalculateMetrics,
  onClose,
  onSelectNode,
  onNotify,
}) => {
  const [copiedId, setCopiedId] = useState(false);
  const [copiedStatement, setCopiedStatement] = useState(false);
  const [copiedProps, setCopiedProps] = useState(false);
  const [copiedCypher, setCopiedCypher] = useState(false);
  const [evidence, setEvidence] = useState<EvidenceTrail | null>(null);
  const [isLoadingEvidence, setIsLoadingEvidence] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "evidence" | "props">("overview");

  // Accordion open/close states for relational topology
  const [incomingOpen, setIncomingOpen] = useState(true);
  const [outgoingOpen, setOutgoingOpen] = useState(true);

  // Properties tab view controls
  const [propsSearchQuery, setPropsSearchQuery] = useState("");
  const [propsViewMode, setPropsViewMode] = useState<"table" | "json">("table");

  // Inbound / outbound edge filters
  const [inboundTypeFilter, setInboundTypeFilter] = useState<string>("all");
  const [outboundTypeFilter, setOutboundTypeFilter] = useState<string>("all");

  const nodesMap = useMemo(() => new Map(allNodes.map((n) => [n.id, n])), [allNodes]);

  const nodeTenability = node.tenability || (node.props as any)?.tenability;
  const nodeParameters = node.parameters || (node.props as any)?.parameters;

  const { getPartition, getNodeDefinition } = useEngineSchema();
  const partition = node.partition || (node.props as any)?.partition || getPartition(node.type);
  const nodeDefinition = getNodeDefinition(node.type);

  // Inbound & outbound edges connected to this node
  const inboundEdges = useMemo(() => edges.filter((e) => e.target === node.id), [edges, node.id]);
  const outboundEdges = useMemo(() => edges.filter((e) => e.source === node.id), [edges, node.id]);

  // Unique edge types for filtering
  const inboundEdgeTypes = useMemo(
    () => Array.from(new Set(inboundEdges.map((e) => e.type))),
    [inboundEdges]
  );
  const outboundEdgeTypes = useMemo(
    () => Array.from(new Set(outboundEdges.map((e) => e.type))),
    [outboundEdges]
  );

  const filteredInboundEdges = useMemo(() => {
    if (inboundTypeFilter === "all") return inboundEdges;
    return inboundEdges.filter((e) => e.type === inboundTypeFilter);
  }, [inboundEdges, inboundTypeFilter]);

  const filteredOutboundEdges = useMemo(() => {
    if (outboundTypeFilter === "all") return outboundEdges;
    return outboundEdges.filter((e) => e.type === outboundTypeFilter);
  }, [outboundEdges, outboundTypeFilter]);

  // Extract statement text from various common attributes
  const statementText = useMemo(() => {
    return (
      node.props?.text ||
      node.props?.statement ||
      node.props?.claim_text ||
      node.props?.argument_statement ||
      (node.props?.label !== node.label ? node.props?.label : null) ||
      null
    );
  }, [node]);

  useEffect(() => {
    if (!runId) {
      setEvidence(null);
      setIsLoadingEvidence(false);
      return;
    }
    let isMounted = true;
    setIsLoadingEvidence(true);
    setEvidence(null);

    api
      .getEvidence(runId, node.id)
      .then((data: EvidenceTrail) => {
        if (isMounted) {
          setEvidence(data);
          setIsLoadingEvidence(false);
        }
      })
      .catch((err) => {
        console.warn("Could not load evidence for node:", node.id, err);
        if (isMounted) {
          setIsLoadingEvidence(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [runId, node.id]);

  const handleCopyId = () => {
    navigator.clipboard.writeText(node.id);
    setCopiedId(true);
    onNotify?.(`Copied Node ID: ${node.id}`);
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
    const query = `MATCH (n) WHERE n.id = '${node.id}' RETURN n;`;
    navigator.clipboard.writeText(query);
    setCopiedCypher(true);
    onNotify?.("Copied Cypher match query to clipboard");
    setTimeout(() => setCopiedCypher(false), 1800);
  };

  const handleCopyPropsJson = () => {
    const payload = {
      id: node.id,
      label: node.label,
      layer: node.layer,
      type: node.type,
      props: node.props,
      parameters: nodeParameters,
      tenability: nodeTenability,
    };
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setCopiedProps(true);
    onNotify?.("Copied properties JSON to clipboard");
    setTimeout(() => setCopiedProps(false), 1800);
  };

  const getLayerLabel = (layer: number) => {
    switch (layer) {
      case 1:
        return "L1 Chunk";
      case 2:
        return "L2 Entity";
      case 3:
        return "L3 TheoryNet";
      default:
        return `Layer ${layer}`;
    }
  };

  const getPolarityMarker = (polarity?: number | null) => {
    if (polarity === 1) {
      return (
        <span className="font-mono text-[10px] text-emerald-600 dark:text-emerald-400 font-medium" title="Support (+1)">
          +1 sup
        </span>
      );
    }
    if (polarity === -1) {
      return (
        <span className="font-mono text-[10px] text-rose-600 dark:text-rose-400 font-medium" title="Attack (-1)">
          -1 att
        </span>
      );
    }
    if (polarity === 0) {
      return (
        <span className="font-mono text-[10px] text-app-muted" title="Neutral (0)">
          0 neu
        </span>
      );
    }
    return (
      <span className="font-mono text-[10px] text-app-muted opacity-50" title="Unspecified">
        ·
      </span>
    );
  };

  const overlayValue = activeOverlay?.node_values?.[node.id];

  // Calculated metrics
  const degreeVal = node.degree ?? (inboundEdges.length + outboundEdges.length);
  const betweennessProp =
    (node.props as any)?.betweenness ??
    (node.props as any)?.betweenness_centrality ??
    (node.props as any)?.node_betweenness;

  // Flattened and categorized properties list
  const propertyEntries = useMemo(() => {
    const rawProps = node.props || {};
    const entries: { key: string; value: any; category: string }[] = [];

    // Core Props
    for (const [k, v] of Object.entries(rawProps)) {
      if (k === "embedding") continue; // Exclude massive vector embeddings
      entries.push({ key: k, value: v, category: "Core Properties" });
    }

    // Parameters if present
    if (nodeParameters) {
      for (const [k, v] of Object.entries(nodeParameters)) {
        entries.push({ key: `param:${k}`, value: v, category: "Parameters (Φ)" });
      }
    }

    // Tenability if present
    if (nodeTenability) {
      for (const [k, v] of Object.entries(nodeTenability)) {
        entries.push({ key: `tenability:${k}`, value: v, category: "Tenability" });
      }
    }

    if (!propsSearchQuery.trim()) return entries;

    const q = propsSearchQuery.toLowerCase();
    return entries.filter(
      (entry) =>
        entry.key.toLowerCase().includes(q) ||
        String(entry.value).toLowerCase().includes(q) ||
        entry.category.toLowerCase().includes(q)
    );
  }, [node.props, nodeParameters, nodeTenability, propsSearchQuery]);

  // Group properties by category for structured scanning
  const categorizedProperties = useMemo(() => {
    const groups: Record<string, typeof propertyEntries> = {};
    for (const entry of propertyEntries) {
      if (!groups[entry.category]) {
        groups[entry.category] = [];
      }
      groups[entry.category].push(entry);
    }
    return groups;
  }, [propertyEntries]);

  // Qualitative attributes from node.props for the overview tab
  const qualitativeAttributes = useMemo(() => {
    const ignoredKeys = new Set([
      "text",
      "statement",
      "claim_text",
      "argument_statement",
      "label",
      "description",
      "embedding",
      "betweenness",
      "betweenness_centrality",
      "node_betweenness",
    ]);

    const result: [string, any][] = [];
    for (const [k, v] of Object.entries(node.props || {})) {
      if (ignoredKeys.has(k)) continue;
      if (typeof v === "object" && v !== null && Object.keys(v).length > 6) continue;
      result.push([k, v]);
    }
    return result;
  }, [node.props]);

  return (
    <div className="w-full h-full flex flex-col bg-app-surface text-xs text-app-text select-none">
      {/* Primary Entity Header */}
      <div className="px-4 py-3 border-b border-app-border bg-app-surface flex items-start justify-between gap-3 shrink-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 text-[11px] font-mono text-app-muted">
            <span className="text-app-heading font-medium">{getLayerLabel(node.layer)}</span>
            <span>·</span>
            <span>{node.type}</span>
            {node.synthetic && (
              <>
                <span>·</span>
                <span>synthetic</span>
              </>
            )}
            {!node.resolved && (
              <>
                <span>·</span>
                <span className="text-amber-600 dark:text-amber-400">unresolved</span>
              </>
            )}
            {partition && (
              <>
                <span>·</span>
                <span title={partition === "A" ? "Theoretical Core (A)" : "Empirical Base (B)"}>
                  part. {partition}
                </span>
              </>
            )}
          </div>

          <h3
            className="text-sm font-semibold text-app-heading leading-snug break-words select-text"
            title={node.label || node.id}
          >
            {node.label || node.id}
          </h3>

          <div className="flex items-center gap-1.5 mt-1 text-[11px] text-app-muted">
            <span className="font-mono text-[10px] text-app-muted select-text truncate max-w-[210px]" title={node.id}>
              {node.id}
            </span>
            <button
              onClick={handleCopyId}
              className="p-0.5 text-app-muted hover:text-app-heading rounded transition-colors cursor-pointer"
              title="Copy Node ID"
            >
              {copiedId ? (
                <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <Copy className="w-3 h-3" />
              )}
            </button>
          </div>
        </div>

        {/* Action Toolbar */}
        <div className="flex items-center space-x-1 shrink-0 pt-0.5">
          {isNeo4j && onExpand && (
            <button
              onClick={() => onExpand(node.id)}
              className="p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
              title="Expand 1-hop neighborhood from Neo4j"
            >
              <Network className="w-3.5 h-3.5" />
            </button>
          )}

          {onCalculateMetrics && (
            <button
              onClick={() => onCalculateMetrics(node)}
              className="p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
              title="Open Metrics Calculator for this focus node"
            >
              <Activity className="w-3.5 h-3.5" />
            </button>
          )}

          <button
            onClick={onClose}
            className="p-1 text-app-muted hover:text-app-heading hover:bg-app-subtle rounded transition-colors cursor-pointer"
            title="Close Inspector"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
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
          Overview & Relations
        </button>
        <button
          onClick={() => setActiveTab("evidence")}
          className={`py-2 text-xs transition-colors flex items-center gap-1.5 cursor-pointer relative ${
            activeTab === "evidence"
              ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
              : "text-app-muted hover:text-app-heading"
          }`}
        >
          <span>Evidence</span>
          <span className="font-mono text-[10px] text-app-muted">({evidence?.chunks?.length || 0})</span>
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
          <span className="font-mono text-[10px] text-app-muted">({propertyEntries.length})</span>
        </button>
      </div>

      {/* Panel Body */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {activeTab === "overview" && (
          <>
            {/* Quantitative Metrics Row: Tight line-based layout with strict alignment */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between pb-1 border-b border-app-border">
                <span className="text-xs font-semibold text-app-heading">Quantitative Metrics</span>
                {onCalculateMetrics && (
                  <button
                    onClick={() => onCalculateMetrics(node)}
                    className="flex items-center gap-1 text-[11px] font-mono text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
                    title="Compute / recalculate metrics for this focus node"
                  >
                    <Activity className="w-3 h-3" />
                    <span>Compute</span>
                  </button>
                )}
              </div>

              <div className="flex items-baseline justify-between py-1.5 border-b border-app-border-subtle">
                <div className="flex flex-col">
                  <span className="text-[9px] uppercase font-mono tracking-widest text-app-muted">Degree</span>
                  <span className="font-mono text-sm font-semibold text-app-heading tabular-nums mt-0.5">
                    {degreeVal}
                  </span>
                  <span className="font-mono text-[9px] text-app-muted tabular-nums">
                    {inboundEdges.length}↓ / {outboundEdges.length}↑
                  </span>
                </div>

                <div className="flex flex-col">
                  <span className="text-[9px] uppercase font-mono tracking-widest text-app-muted">Confidence</span>
                  <span className="font-mono text-sm font-semibold text-app-heading tabular-nums mt-0.5">
                    {node.confidence !== null && node.confidence !== undefined
                      ? `${(node.confidence * 100).toFixed(0)}%`
                      : "—"}
                  </span>
                </div>

                <div className="flex flex-col">
                  <span className="text-[9px] uppercase font-mono tracking-widest text-app-muted">Plausibility</span>
                  <span className="font-mono text-sm font-semibold text-app-heading tabular-nums mt-0.5">
                    {node.plausibility !== null && node.plausibility !== undefined
                      ? node.plausibility.toFixed(2)
                      : "—"}
                  </span>
                </div>

                <div className="flex flex-col">
                  <span
                    className="text-[9px] uppercase font-mono tracking-widest text-app-muted truncate max-w-[80px]"
                    title={activeOverlay && overlayValue !== undefined ? activeOverlay.kind : "Betweenness"}
                  >
                    {activeOverlay && overlayValue !== undefined ? activeOverlay.kind : "Betweenness"}
                  </span>
                  <span className="font-mono text-sm font-semibold text-app-heading tabular-nums mt-0.5">
                    {activeOverlay && overlayValue !== undefined && overlayValue !== null
                      ? typeof overlayValue === "number"
                        ? overlayValue.toFixed(3)
                        : String(overlayValue)
                      : betweennessProp !== undefined && betweennessProp !== null
                      ? Number(betweennessProp).toFixed(3)
                      : "—"}
                  </span>
                </div>
              </div>
            </div>

            {/* Dual-Process Decision Calibration & QBAF Epistemic Properties */}
            <div className="space-y-2 p-2.5 rounded-lg border border-app-border bg-app-surface/50">
              <div className="pb-1 border-b border-app-border flex items-center justify-between">
                <span className="text-xs font-semibold text-app-heading flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  Epistemic Modal Strength & QBAF Semantics
                </span>
                <div className="flex items-center gap-1.5">
                  {node.decision_tier && (
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {node.decision_tier}
                    </span>
                  )}
                  {((node.is_modal_clamped ?? (node.props as any)?.is_modal_clamped ?? (node.props as any)?.clamped)) && (
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold bg-amber-500/10 text-amber-500 border border-amber-500/20" title="Clamped by structuralist syntax bounds [M_min, M_max]">
                      Clamped Bounds
                    </span>
                  )}
                </div>
              </div>

              {/* Structuralist Syntax & Scope Classification (Schurz 2014) */}
              {((node.scope_type || (node.props as any)?.scope_type || node.epistemic_status || (node.props as any)?.epistemic_status)) && (
                <div className="flex flex-wrap items-center gap-1.5 pt-0.5 pb-1">
                  {(node.scope_type || (node.props as any)?.scope_type) && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                      <span className="text-[9px] text-app-muted uppercase">Scope:</span>
                      <strong className="font-semibold">{node.scope_type || (node.props as any)?.scope_type}</strong>
                    </span>
                  )}
                  {(node.epistemic_status || (node.props as any)?.epistemic_status) && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
                      <span className="text-[9px] text-app-muted uppercase">Status:</span>
                      <strong className="font-semibold">{node.epistemic_status || (node.props as any)?.epistemic_status}</strong>
                    </span>
                  )}
                  {(node.modal_resolver || (node.props as any)?.modal_resolver) && (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono text-app-muted bg-app-subtle border border-app-border">
                      {node.modal_resolver || (node.props as any)?.modal_resolver}
                    </span>
                  )}
                </div>
              )}

              <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
                <div>
                  <span className="text-[9px] uppercase tracking-wider text-app-muted block">Modal Strength M(φ)</span>
                  <div className="flex items-baseline gap-1.5">
                    <span className="font-semibold text-emerald-500 text-xs">
                      {node.modal_strength !== null && node.modal_strength !== undefined
                        ? node.modal_strength.toFixed(3)
                        : "—"}
                    </span>
                    {(node.raw_modal_score !== null && node.raw_modal_score !== undefined || (node.props as any)?.raw_modal_score !== undefined || (node.props as any)?.raw_engine_score !== undefined) && (
                      <span className="text-[9px] text-app-muted font-normal" title="Raw unconstrained System 1 score">
                        (raw: {Number(node.raw_modal_score ?? (node.props as any)?.raw_modal_score ?? (node.props as any)?.raw_engine_score).toFixed(2)})
                      </span>
                    )}
                  </div>
                </div>
                <div>
                  <span className="text-[9px] uppercase tracking-wider text-app-muted block">Base Score (τ_0)</span>
                  <span className="font-semibold text-app-heading">
                    {node.base_score !== null && node.base_score !== undefined
                      ? node.base_score.toFixed(3)
                      : "—"}
                  </span>
                </div>
                <div>
                  <span className="text-[9px] uppercase tracking-wider text-app-muted block">QBAF Equilibrium (τ*)</span>
                  <span className="font-semibold text-purple-400">
                    {node.qbaf_tau !== null && node.qbaf_tau !== undefined
                      ? node.qbaf_tau.toFixed(3)
                      : "—"}
                  </span>
                </div>
                <div>
                  <span className="text-[9px] uppercase tracking-wider text-app-muted block">Evidence Total (E)</span>
                  <span className="text-app-text">
                    {node.total_weight_of_evidence !== null && node.total_weight_of_evidence !== undefined
                      ? node.total_weight_of_evidence.toFixed(2)
                      : "—"}
                  </span>
                </div>
                {node.conformal_set_size !== null && node.conformal_set_size !== undefined && (
                  <div className="col-span-2">
                    <span className="text-[9px] uppercase tracking-wider text-app-muted block">Conformal Set Size</span>
                    <span className="text-blue-400">|C(x)| = {node.conformal_set_size}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Asserted Statement Section */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between pb-1 border-b border-app-border">
                <span className="text-xs font-semibold text-app-heading">Asserted Statement</span>
                <div className="flex items-center gap-2">
                  {evidence && evidence.chunks && evidence.chunks.length > 0 && (
                    <button
                      onClick={() => setActiveTab("evidence")}
                      className="flex items-center gap-1 text-[11px] font-mono text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
                      title="View source evidence chunks"
                    >
                      <ArrowRight className="w-3 h-3" />
                      <span>{evidence.chunks.length} Evidence</span>
                    </button>
                  )}
                  {statementText && (
                    <button
                      onClick={handleCopyStatement}
                      className="flex items-center gap-1 text-[11px] text-app-muted hover:text-app-heading transition-colors cursor-pointer"
                      title="Copy argument statement text"
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
                  )}
                </div>
              </div>

              {statementText ? (
                <div className="space-y-1 pt-0.5">
                  <blockquote className="text-xs leading-relaxed text-app-heading select-text border-l border-app-border pl-3 py-0.5 font-normal">
                    "{statementText}"
                  </blockquote>
                  <div className="flex items-center gap-3 text-[10px] text-app-muted font-mono pl-3">
                    <span>{statementText.length} chars</span>
                    <span>·</span>
                    <span>{statementText.trim().split(/\s+/).length} words</span>
                  </div>
                </div>
              ) : (
                <div className="text-[11px] text-app-muted/60 italic py-0.5 select-none font-normal">
                  No distinct asserted statement attached.
                </div>
              )}
            </div>

            {/* Epistemic Description Section */}
            {node.props?.description && (
              <div className="space-y-1.5">
                <div className="pb-1 border-b border-app-border">
                  <span className="text-xs font-semibold text-app-heading">Epistemic Description</span>
                </div>
                <p className="text-xs leading-relaxed text-app-text select-text border-l border-app-border pl-3 py-0.5 font-normal">
                  "{node.props.description}"
                </p>
              </div>
            )}

            {/* Active Schema Epistemic Definition */}
            {nodeDefinition && (
              <div className="space-y-1.5">
                <div className="pb-1 border-b border-app-border">
                  <span className="text-xs font-semibold text-app-heading">Schema Definition ({node.type})</span>
                </div>
                <div className="p-2.5 rounded bg-app-subtle/50 border border-app-border-subtle text-[11px] text-app-text leading-relaxed select-text">
                  {nodeDefinition}
                </div>
              </div>
            )}

            {/* Theoretical Evaluation (Φ) */}
            {(nodeTenability || nodeParameters) && (
              <div className="space-y-2">
                <div className="flex items-center justify-between pb-1 border-b border-app-border">
                  <span className="text-xs font-semibold text-app-heading">Theoretical Evaluation (Φ)</span>
                  {nodeTenability && (
                    <span
                      className={`font-mono text-[10px] font-medium ${
                        nodeTenability.is_tenable !== false && (nodeTenability.local_tenability_score ?? 1) >= 0.5
                          ? "text-emerald-600 dark:text-emerald-400"
                          : "text-rose-600 dark:text-rose-400"
                      }`}
                    >
                      {nodeTenability.is_tenable !== false && (nodeTenability.local_tenability_score ?? 1) >= 0.5
                        ? "Tenable (TS)"
                        : "Untenable"}
                    </span>
                  )}
                </div>

                {nodeTenability && (
                  <div className="flex items-baseline gap-8 py-1 font-mono text-xs">
                    <div>
                      <span className="text-[9px] uppercase tracking-wider text-app-muted block">Local Tenability</span>
                      <span className="font-mono text-xs font-bold text-app-heading tabular-nums mt-0.5 block">
                        {typeof nodeTenability.local_tenability_score === "number"
                          ? nodeTenability.local_tenability_score.toFixed(3)
                          : "—"}
                      </span>
                    </div>
                    <div>
                      <span className="text-[9px] uppercase tracking-wider text-app-muted block">Blur Bound (δ*)</span>
                      <span className="font-mono text-xs font-bold text-app-heading tabular-nums mt-0.5 block">
                        {typeof nodeTenability.delta_star === "number"
                          ? nodeTenability.delta_star.toFixed(3)
                          : "—"}
                      </span>
                    </div>
                  </div>
                )}

                {/* Postulated Parameters */}
                {nodeParameters && Object.keys(nodeParameters).length > 0 && (
                  <div className="space-y-1">
                    <span className="text-[10px] uppercase font-mono tracking-wider font-semibold text-app-muted block">
                      Postulated Parameters (Φ_spec)
                    </span>
                    <div className="divide-y divide-app-border-subtle font-mono text-[11px]">
                      {Object.entries(nodeParameters).map(([paramKey, paramVal]) => (
                        <div key={paramKey} className="grid grid-cols-12 gap-2 py-1 text-[11px]">
                          <span className="col-span-6 text-right text-app-muted truncate" title={paramKey}>
                            {paramKey}
                          </span>
                          <span className="col-span-6 text-left text-app-heading font-semibold tabular-nums">
                            {typeof paramVal === "number" ? Number(paramVal).toFixed(2) : String(paramVal)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Anomalies Alert */}
                {nodeTenability?.anomalies && nodeTenability.anomalies.length > 0 && (
                  <div className="py-1 space-y-1 text-rose-600 dark:text-rose-400">
                    <span className="font-mono text-[9px] uppercase tracking-wider block font-semibold">
                      Anomalies ({nodeTenability.anomalies.length})
                    </span>
                    <ul className="space-y-0.5 font-mono text-[10px]">
                      {nodeTenability.anomalies.map((anom: string, idx: number) => (
                        <li key={idx} className="truncate" title={anom}>
                          · {anom}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Categorized Qualitative Properties Grid */}
            {qualitativeAttributes.length > 0 && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between pb-1 border-b border-app-border">
                  <span className="text-xs font-semibold text-app-heading">Key Attributes</span>
                  <button
                    onClick={() => setActiveTab("props")}
                    className="font-mono text-[10px] text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
                  >
                    All ({propertyEntries.length})
                  </button>
                </div>

                <div className="divide-y divide-app-border-subtle text-[11px]">
                  {qualitativeAttributes.slice(0, 8).map(([key, value]) => (
                    <div key={key} className="grid grid-cols-12 gap-2 py-1 items-baseline">
                      <span className="col-span-5 text-right text-app-muted font-mono truncate" title={key}>
                        {key}
                      </span>
                      <div className="col-span-7 text-left text-app-heading font-mono truncate select-text" title={String(value)}>
                        {typeof value === "boolean" ? (
                          <span className={value ? "text-emerald-600 dark:text-emerald-400 font-semibold" : "text-rose-600 dark:text-rose-400 font-semibold"}>
                            {String(value)}
                          </span>
                        ) : typeof value === "number" ? (
                          <span className="tabular-nums font-semibold">{value}</span>
                        ) : (
                          <span>{String(value)}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Relational Topology: Clean divide-y lists */}
            <div className="space-y-3 pt-1">
              {/* Incoming Connections */}
              <div className="space-y-1.5">
                <button
                  onClick={() => setIncomingOpen(!incomingOpen)}
                  className="w-full flex items-center justify-between py-1 text-left cursor-pointer select-none group"
                >
                  <div className="flex items-center gap-1.5">
                    {incomingOpen ? (
                      <ChevronDown className="w-3.5 h-3.5 text-app-muted" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-app-muted" />
                    )}
                    <span className="text-xs font-semibold text-app-heading group-hover:text-blue-500 transition-colors">
                      Incoming Relations
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-app-muted tabular-nums">
                    ({filteredInboundEdges.length}/{inboundEdges.length})
                  </span>
                </button>

                {incomingOpen && (
                  <div className="space-y-1">
                    {/* Filter Links */}
                    {inboundEdgeTypes.length > 1 && (
                      <div className="flex items-center gap-2 overflow-x-auto py-0.5 text-[10px] font-mono scrollbar-none">
                        <button
                          onClick={() => setInboundTypeFilter("all")}
                          className={`cursor-pointer ${
                            inboundTypeFilter === "all"
                              ? "text-app-heading font-bold underline"
                              : "text-app-muted hover:text-app-heading"
                          }`}
                        >
                          ALL
                        </button>
                        {inboundEdgeTypes.map((t) => (
                          <button
                            key={t}
                            onClick={() => setInboundTypeFilter(t)}
                            className={`cursor-pointer shrink-0 ${
                              inboundTypeFilter === t
                                ? "text-app-heading font-bold underline"
                                : "text-app-muted hover:text-app-heading"
                            }`}
                          >
                            {t}
                          </button>
                        ))}
                      </div>
                    )}

                    {filteredInboundEdges.length === 0 ? (
                      <div className="text-[11px] text-app-muted/60 italic py-1 select-none font-normal">
                        No incoming relations found.
                      </div>
                    ) : (
                      <div className="divide-y divide-app-border-subtle">
                        {filteredInboundEdges.map((edge) => {
                          const srcNode = nodesMap.get(edge.source);
                          return (
                            <div
                              key={edge.id}
                              onClick={() => onSelectNode(edge.source)}
                              className="py-1.5 hover:bg-app-subtle/50 transition-colors cursor-pointer group px-1 -mx-1 rounded-xs"
                              title={`Select connected source: ${srcNode?.label || edge.source}`}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-app-heading text-xs font-medium group-hover:text-blue-500 transition-colors truncate">
                                  {srcNode?.label || edge.source}
                                </span>
                                {edge.weight !== null && edge.weight !== undefined && (
                                  <span className="text-[9px] font-mono text-app-muted tabular-nums shrink-0">
                                    w: {edge.weight.toFixed(2)}
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-2 mt-0.5 text-[10px] font-mono text-app-muted">
                                {getPolarityMarker(edge.polarity)}
                                <span className="truncate">{edge.type}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Outgoing Connections */}
              <div className="space-y-1.5 pt-1 border-t border-app-border-subtle">
                <button
                  onClick={() => setOutgoingOpen(!outgoingOpen)}
                  className="w-full flex items-center justify-between py-1 text-left cursor-pointer select-none group"
                >
                  <div className="flex items-center gap-1.5">
                    {outgoingOpen ? (
                      <ChevronDown className="w-3.5 h-3.5 text-app-muted" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-app-muted" />
                    )}
                    <span className="text-xs font-semibold text-app-heading group-hover:text-blue-500 transition-colors">
                      Outgoing Relations
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-app-muted tabular-nums">
                    ({filteredOutboundEdges.length}/{outboundEdges.length})
                  </span>
                </button>

                {outgoingOpen && (
                  <div className="space-y-1">
                    {/* Filter Links */}
                    {outboundEdgeTypes.length > 1 && (
                      <div className="flex items-center gap-2 overflow-x-auto py-0.5 text-[10px] font-mono scrollbar-none">
                        <button
                          onClick={() => setOutboundTypeFilter("all")}
                          className={`cursor-pointer ${
                            outboundTypeFilter === "all"
                              ? "text-app-heading font-bold underline"
                              : "text-app-muted hover:text-app-heading"
                          }`}
                        >
                          ALL
                        </button>
                        {outboundEdgeTypes.map((t) => (
                          <button
                            key={t}
                            onClick={() => setOutboundTypeFilter(t)}
                            className={`cursor-pointer shrink-0 ${
                              outboundTypeFilter === t
                                ? "text-app-heading font-bold underline"
                                : "text-app-muted hover:text-app-heading"
                            }`}
                          >
                            {t}
                          </button>
                        ))}
                      </div>
                    )}

                    {filteredOutboundEdges.length === 0 ? (
                      <div className="text-[11px] text-app-muted/60 italic py-1 select-none font-normal">
                        No outgoing relations found.
                      </div>
                    ) : (
                      <div className="divide-y divide-app-border-subtle">
                        {filteredOutboundEdges.map((edge) => {
                          const tgtNode = nodesMap.get(edge.target);
                          return (
                            <div
                              key={edge.id}
                              onClick={() => onSelectNode(edge.target)}
                              className="py-1.5 hover:bg-app-subtle/50 transition-colors cursor-pointer group px-1 -mx-1 rounded-xs"
                              title={`Select connected target: ${tgtNode?.label || edge.target}`}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-app-heading text-xs font-medium group-hover:text-blue-500 transition-colors truncate">
                                  {tgtNode?.label || edge.target}
                                </span>
                                {edge.weight !== null && edge.weight !== undefined && (
                                  <span className="text-[9px] font-mono text-app-muted tabular-nums shrink-0">
                                    w: {edge.weight.toFixed(2)}
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-2 mt-0.5 text-[10px] font-mono text-app-muted">
                                {getPolarityMarker(edge.polarity)}
                                <span className="truncate">{edge.type}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

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

        {/* Evidence Trail Tab */}
        {activeTab === "evidence" && (
          <div className="space-y-4">
            {isLoadingEvidence ? (
              <div className="py-4 text-center text-app-muted text-xs">Loading evidence trail...</div>
            ) : !evidence || evidence.chunks.length === 0 ? (
              <div className="py-4 text-center text-app-muted text-xs italic">
                No source text chunks attached to this node.
              </div>
            ) : (
              <div className="divide-y divide-app-border-subtle space-y-3">
                {evidence.chunks.map((chunk, idx) => (
                  <div
                    key={chunk.chunk_id || idx}
                    className="pt-2 first:pt-0 space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-[10px] text-app-muted font-mono">
                      <span className="font-mono text-app-heading font-medium truncate max-w-[200px]" title={chunk.chunk_id}>
                        {chunk.chunk_id}
                      </span>
                      <div className="flex items-center gap-1">
                        {chunk.spans.map((s, sIdx) => (
                          <span
                            key={sIdx}
                            className="font-mono text-[10px] text-app-muted"
                            title={
                              s.mode === "exact"
                                ? `Exact Character Span (${s.start_char ?? 0}..${s.end_char ?? 0})`
                                : s.mode === "substring"
                                ? "Substring Match in Chunk"
                                : "Whole Chunk Reference"
                            }
                          >
                            {s.mode === "exact"
                              ? `(${s.start_char}..${s.end_char})`
                              : s.mode === "substring"
                              ? "substring"
                              : "full"}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Render chunk text with highlight */}
                    <div className="text-app-text text-xs leading-relaxed border-l border-app-border pl-3 py-0.5 select-text">
                      {chunk.spans && chunk.spans.length > 0 && chunk.spans[0].mode === "exact" && chunk.spans[0].start_char !== null && chunk.spans[0].end_char !== null ? (
                        (() => {
                          const start = Math.max(0, chunk.spans[0].start_char!);
                          const end = Math.min(chunk.text.length, chunk.spans[0].end_char!);
                          const prefix = chunk.text.slice(0, start);
                          const match = chunk.text.slice(start, end);
                          const suffix = chunk.text.slice(end);
                          return (
                            <>
                              {prefix}
                              <mark className="bg-amber-400/25 text-amber-900 dark:text-amber-200 px-0.5 font-medium">
                                {match}
                              </mark>
                              {suffix}
                            </>
                          );
                        })()
                      ) : chunk.spans && chunk.spans.length > 0 && chunk.spans[0].mode === "substring" && chunk.spans[0].text ? (
                        (() => {
                          const sub = chunk.spans[0].text;
                          const idx = chunk.text.toLowerCase().indexOf(sub.toLowerCase());
                          if (idx !== -1) {
                            const prefix = chunk.text.slice(0, idx);
                            const match = chunk.text.slice(idx, idx + sub.length);
                            const suffix = chunk.text.slice(idx + sub.length);
                            return (
                              <>
                                {prefix}
                                <mark className="bg-app-subtle text-app-heading px-0.5 font-medium">
                                  {match}
                                </mark>
                                {suffix}
                              </>
                            );
                          }
                          return chunk.text;
                        })()
                      ) : (
                        <div>{chunk.text}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Enhanced Structured Properties Tab with 2-Column Key-Value Grid */}
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
                title="Copy all properties as JSON"
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
              propertyEntries.length === 0 ? (
                <div className="py-4 text-center text-xs text-app-muted italic">
                  No properties match "{propsSearchQuery}".
                </div>
              ) : (
                <div className="space-y-4">
                  {Object.entries(categorizedProperties).map(([category, items]) => (
                    <div key={category} className="space-y-1">
                      <div className="pb-1 border-b border-app-border-subtle flex items-center justify-between">
                        <span className="text-xs font-semibold text-app-heading">{category}</span>
                        <span className="font-mono text-[10px] text-app-muted">({items.length})</span>
                      </div>
                      <div className="divide-y divide-app-border-subtle font-mono text-[11px] select-text">
                        {items.map((entry) => (
                          <div
                            key={entry.key}
                            className="grid grid-cols-12 gap-3 py-1.5 items-start"
                          >
                            <span
                              className="col-span-5 text-right text-app-muted truncate font-mono text-[11px]"
                              title={entry.key}
                            >
                              {entry.key}
                            </span>
                            <div className="col-span-7 text-left break-all text-app-heading font-mono select-text text-[11px]">
                              {typeof entry.value === "object" && entry.value !== null ? (
                                <pre className="p-1 text-[10px] font-mono overflow-x-auto whitespace-pre-wrap bg-app-subtle/50">
                                  {JSON.stringify(entry.value, null, 2)}
                                </pre>
                              ) : typeof entry.value === "boolean" ? (
                                <span className={entry.value ? "text-emerald-600 dark:text-emerald-400 font-semibold" : "text-rose-600 dark:text-rose-400 font-semibold"}>
                                  {String(entry.value)}
                                </span>
                              ) : typeof entry.value === "number" ? (
                                <span className="tabular-nums font-semibold">{entry.value}</span>
                              ) : (
                                <span>{String(entry.value)}</span>
                              )}
                            </div>
                          </div>
                        ))}
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
                    id: node.id,
                    label: node.label,
                    layer: node.layer,
                    type: node.type,
                    props: node.props,
                    parameters: nodeParameters,
                    tenability: nodeTenability,
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
