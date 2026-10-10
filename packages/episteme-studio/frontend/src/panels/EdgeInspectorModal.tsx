import React, {useEffect} from "react";
import {StudioEdge, StudioNode} from "../api/types";
import {ArrowRight, Copy, Scale, X} from "lucide-react";
import {useEngineSchema} from "../store/engineSettingsStore";

interface EdgeInspectorModalProps {
  edge: StudioEdge | null;
  allNodes: StudioNode[];
  onClose: () => void;
  onSelectNode?: (nodeId: string) => void;
  onNotify?: (msg: string) => void;
}

export const EdgeInspectorModal: React.FC<EdgeInspectorModalProps> = ({
  edge,
  allNodes,
  onClose,
  onSelectNode,
  onNotify,
}) => {
  const { getPolarity, getRelationDefinition } = useEngineSchema();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!edge) return null;

  const sourceNode = allNodes.find((n) => n.id === edge.source);
  const targetNode = allNodes.find((n) => n.id === edge.target);

  const resolvedPolarity = getPolarity(edge.type) ?? edge.polarity ?? (edge.props as any)?.polarity ?? null;
  const relationDefinition = getRelationDefinition(edge.type);

  const polarityBadge = () => {
    if (resolvedPolarity === 1) {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
          Support (+1)
        </span>
      );
    }
    if (resolvedPolarity === -1) {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/30">
          Attack (-1)
        </span>
      );
    }
    if (resolvedPolarity === 0) {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-app-subtle text-app-muted border border-app-border">
          Neutral (0)
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/30">
        Unmapped (null)
      </span>
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-app-surface border border-app-border rounded-xl shadow-2xl overflow-hidden flex flex-col text-xs text-app-text animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-app-border bg-app-subtle">
          <div className="flex items-center gap-2">
            <Scale className="w-4 h-4 text-app-muted" />
            <span className="font-semibold text-app-heading text-sm font-mono">{edge.type}</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-surface transition-colors cursor-pointer"
            aria-label="Close Inspector"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4 max-h-[75vh] overflow-y-auto">
          {/* Endpoints Flow Card */}
          <div className="p-3 bg-app-bg rounded border border-app-border space-y-2">
            <div className="text-[10px] text-app-muted uppercase font-semibold">
              Relationship Endpoints
            </div>
            <div className="flex items-center justify-between gap-2">
              <button
                onClick={() => {
                  onSelectNode?.(edge.source);
                  onClose();
                }}
                className="flex-1 p-2 rounded bg-app-surface border border-app-border hover:border-app-heading text-left transition-colors cursor-pointer"
                title={`Select source node: ${edge.source}`}
              >
                <div className="text-[10px] text-app-muted">Source</div>
                <div className="font-semibold text-app-heading truncate">
                  {sourceNode?.label || edge.source}
                </div>
                <div className="font-mono text-[9px] text-app-muted truncate">{edge.source}</div>
              </button>

              <ArrowRight className="w-4 h-4 text-app-muted flex-shrink-0" />

              <button
                onClick={() => {
                  onSelectNode?.(edge.target);
                  onClose();
                }}
                className="flex-1 p-2 rounded bg-app-surface border border-app-border hover:border-app-heading text-left transition-colors cursor-pointer"
                title={`Select target node: ${edge.target}`}
              >
                <div className="text-[10px] text-app-muted">Target</div>
                <div className="font-semibold text-app-heading truncate">
                  {targetNode?.label || edge.target}
                </div>
                <div className="font-mono text-[9px] text-app-muted truncate">{edge.target}</div>
              </button>
            </div>
          </div>

          {/* Key Properties Grid */}
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2.5 rounded bg-app-bg border border-app-border space-y-1">
              <div className="text-[10px] text-app-muted uppercase font-semibold">Polarity</div>
              <div>{polarityBadge()}</div>
            </div>

            <div className="p-2.5 rounded bg-app-bg border border-app-border space-y-1">
              <div className="text-[10px] text-app-muted uppercase font-semibold">Weight (φ)</div>
              <div className="font-mono font-bold text-sm text-app-heading">
                {edge.weight !== null && edge.weight !== undefined
                  ? Number(edge.weight).toFixed(3)
                  : "—"}
              </div>
            </div>

            <div className="p-2.5 rounded bg-app-bg border border-app-border space-y-1">
              <div className="text-[10px] text-app-muted uppercase font-semibold">Confidence</div>
              <div className="font-mono font-bold text-sm text-app-heading">
                {edge.confidence !== null && edge.confidence !== undefined
                  ? Number(edge.confidence).toFixed(2)
                  : "—"}
              </div>
            </div>
          </div>

          {/* Active Schema Epistemic Definition */}
          {relationDefinition && (
            <div className="space-y-1.5">
              <div className="text-[10px] text-app-muted uppercase font-semibold">
                Schema Definition
              </div>
              <div className="p-2.5 rounded-lg border border-app-border bg-app-bg text-[11px] text-app-text leading-relaxed">
                {relationDefinition}
              </div>
            </div>
          )}

          {/* Supplemental Properties Table */}
          {edge.props && Object.keys(edge.props).length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[10px] text-app-muted uppercase font-semibold">
                Relationship Properties
              </div>
              <div className="rounded-lg border border-app-border overflow-hidden divide-y divide-app-border bg-app-bg font-mono text-[11px]">
                {Object.entries(edge.props).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between px-3 py-1.5">
                    <span className="text-app-muted">{k}</span>
                    <span className="text-app-heading truncate max-w-[240px]">
                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Edge ID */}
          <div className="pt-2 border-t border-app-border flex items-center justify-between text-app-muted">
            <span className="font-mono text-[10px]">ID: {edge.id}</span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(edge.id);
                onNotify?.(`Copied Edge ID: ${edge.id}`);
              }}
              className="flex items-center gap-1 text-[10px] hover:text-app-heading transition-colors cursor-pointer"
            >
              <Copy className="w-3 h-3" />
              <span>Copy ID</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
