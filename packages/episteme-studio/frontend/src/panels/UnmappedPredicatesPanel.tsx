import React, {useMemo, useState} from "react";
import {GraphView, StudioEdge, StudioNode} from "../api/types";
import {AlertCircle, ArrowRight, Check, Copy, HelpCircle} from "lucide-react";

interface UnmappedPredicatesPanelProps {
  graphView: GraphView | null;
  onSelectEdge?: (edge: StudioEdge) => void;
}

export const UnmappedPredicatesPanel: React.FC<UnmappedPredicatesPanelProps> = ({
  graphView,
  onSelectEdge,
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  const nodesById = useMemo(() => {
    if (!graphView) return new Map<string, StudioNode>();
    return new Map(graphView.nodes.map((n) => [n.id, n]));
  }, [graphView]);

  // Rank predicates by frequency
  const rankedPredicates = useMemo(() => {
    if (!graphView || !graphView.unmapped_predicates) return [];
    const entries = Object.entries(graphView.unmapped_predicates);
    entries.sort((a, b) => b[1] - a[1]);
    return entries.filter(([pred]) =>
      pred.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [graphView, searchTerm]);

  // Find example edge for each unmapped predicate
  const exampleEdges = useMemo(() => {
    if (!graphView) return new Map<string, StudioEdge>();
    const map = new Map<string, StudioEdge>();
    for (const edge of graphView.edges) {
      if (edge.polarity === null && !map.has(edge.type)) {
        map.set(edge.type, edge);
      }
    }
    return map;
  }, [graphView]);

  const totalUnmapped = useMemo(() => {
    if (!graphView?.unmapped_predicates) return 0;
    return Object.values(graphView.unmapped_predicates).reduce((a, b) => a + b, 0);
  }, [graphView]);

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const getNodeLabel = (nodeId: string): string => {
    const node = nodesById.get(nodeId);
    if (!node) return nodeId;
    return node.label || node.id;
  };

  if (!graphView) {
    return (
      <div className="p-8 text-center text-app-muted text-xs">
        Load a graph view to inspect unmapped predicates.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-app-surface border border-app-border rounded-xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-app-subtle border-b border-app-border">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-amber-500 dark:text-amber-400" />
          <span className="text-sm font-semibold text-app-heading">Unmapped Predicates</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30 font-mono">
            {rankedPredicates.length} distinct ({totalUnmapped} occurrences)
          </span>
        </div>

        <div className="relative">
          <input
            type="text"
            placeholder="Filter predicates..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="px-2.5 py-1 text-xs bg-app-bg border border-app-border rounded text-app-text placeholder-app-muted focus:outline-none focus:border-amber-500/70 w-44"
          />
        </div>
      </div>

      {/* Explanatory Banner (D-15) */}
      <div className="px-4 py-2 bg-app-subtle/50 border-b border-app-border text-[11px] text-app-muted flex items-start gap-2">
        <HelpCircle className="w-3.5 h-3.5 text-app-muted shrink-0 mt-0.5" />
        <p>
          Extracted relations missing from <code className="text-app-heading font-mono">RELATION_POLARITIES</code> render with neutral polarity (<code className="text-app-heading font-mono">null</code>). This panel exposes the open-vocabulary German predicates for curation.
        </p>
      </div>

      {/* Predicate List */}
      <div className="flex-1 overflow-auto divide-y divide-app-border">
        {rankedPredicates.length === 0 ? (
          <div className="p-8 text-center text-app-muted text-xs">
            {searchTerm ? "No predicates match the filter." : "No unmapped predicates in the current projection."}
          </div>
        ) : (
          rankedPredicates.map(([pred, count]) => {
            const exampleEdge = exampleEdges.get(pred);
            const isCopied = copiedKey === pred;

            return (
              <div
                key={pred}
                className="p-3.5 hover:bg-app-hover transition-colors flex flex-col gap-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-amber-700 dark:text-amber-300 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/30">
                      {pred}
                    </span>
                    <span className="text-xs text-app-muted font-mono">
                      {count} {count === 1 ? "edge" : "edges"}
                    </span>
                  </div>

                  <button
                    onClick={() => handleCopy(pred, pred)}
                    className="px-2 py-0.5 text-[11px] text-app-muted hover:text-app-heading hover:bg-app-hover rounded border border-app-border flex items-center gap-1 transition-colors"
                  >
                    {isCopied ? <Check className="w-3 h-3 text-emerald-500 dark:text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>{isCopied ? "Copied" : "Copy"}</span>
                  </button>
                </div>

                {/* Example Edge Card */}
                {exampleEdge && (
                  <div
                    onClick={() => onSelectEdge && onSelectEdge(exampleEdge)}
                    className={`mt-1 px-3 py-2 bg-app-bg border border-app-border rounded-lg flex items-center justify-between text-xs font-mono text-app-text ${
                      onSelectEdge ? "cursor-pointer hover:border-app-muted" : ""
                    }`}
                  >
                    <div className="flex items-center gap-2 max-w-md truncate">
                      <span className="text-app-muted truncate max-w-[140px]" title={exampleEdge.source}>
                        {getNodeLabel(exampleEdge.source)}
                      </span>
                      <ArrowRight className="w-3 h-3 text-app-muted shrink-0" />
                      <span className="text-amber-600 dark:text-amber-400 font-medium">{pred}</span>
                      <ArrowRight className="w-3 h-3 text-app-muted shrink-0" />
                      <span className="text-app-muted truncate max-w-[140px]" title={exampleEdge.target}>
                        {getNodeLabel(exampleEdge.target)}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-[11px] text-app-muted shrink-0">
                      <span>L{exampleEdge.layer}</span>
                      {exampleEdge.confidence !== null && exampleEdge.confidence !== undefined && (
                        <span>conf: {(exampleEdge.confidence * 100).toFixed(0)}%</span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
