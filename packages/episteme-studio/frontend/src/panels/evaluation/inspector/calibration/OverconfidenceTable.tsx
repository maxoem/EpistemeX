import React, { useState, useMemo } from "react";
import {
  AlertTriangle,
  Search,
  Wrench,
  Sparkles,
  ExternalLink,
  Info,
  ShieldAlert,
} from "lucide-react";
import type { MiscalibratedAssertionItem } from "../../../../api/types";
import { ActionableHookPill } from "../../components/ActionableHookPill";

export interface OverconfidenceTableProps {
  assertions: MiscalibratedAssertionItem[];
  onOpenConfigEditor?: () => void;
}

export const OverconfidenceTable: React.FC<OverconfidenceTableProps> = ({
  assertions,
  onOpenConfigEditor,
}) => {
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(
    assertions.length > 0 ? assertions[0].assertion_id : null
  );

  const filtered = useMemo(() => {
    if (!search.trim()) return assertions;
    const q = search.toLowerCase();
    return assertions.filter((item) => {
      return (
        item.assertion_id.toLowerCase().includes(q) ||
        item.descriptor.toLowerCase().includes(q) ||
        item.assertion_type.toLowerCase().includes(q) ||
        (item.rationale && item.rationale.toLowerCase().includes(q))
      );
    });
  }, [assertions, search]);

  const selectedItem = useMemo(() => {
    return filtered.find((i) => i.assertion_id === selectedId) || filtered[0] || null;
  }, [filtered, selectedId]);

  return (
    <div className="flex-1 flex flex-col h-full bg-app-surface border border-app-border rounded-lg overflow-hidden select-none">
      {/* Header & Search */}
      <div className="p-3 border-b border-app-border space-y-2 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1 rounded bg-rose-500/10 text-rose-500">
              <AlertTriangle className="w-3.5 h-3.5" />
            </div>
            <div>
              <h3 className="text-xs font-semibold text-app-heading">
                High-Confidence Hallucinations
              </h3>
              <p className="text-[11px] text-app-muted">
                Assertions with confidence &gt; 0.85 that failed empirical verification
              </p>
            </div>
          </div>
          <span className="font-mono text-xs tabular-nums px-2 py-0.5 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/25 font-semibold">
            {assertions.length} Flagged
          </span>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-app-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search miscalibrated assertions or predicates..."
            className="w-full pl-8 pr-2.5 py-1 text-xs rounded-md bg-app-bg border border-app-border focus:border-blue-500 focus:outline-hidden text-app-text placeholder-app-muted font-sans"
          />
        </div>
      </div>

      {/* Table Container */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <table className="w-full text-left text-xs border-collapse">
          <thead className="sticky top-0 bg-app-surface border-b border-app-border text-[11px] text-app-muted font-medium select-none z-10">
            <tr className="h-8">
              <th className="px-3">Assertion ID</th>
              <th className="px-2 text-right">Conf</th>
              <th className="px-2">Type</th>
              <th className="px-3">Descriptor</th>
              <th className="px-2 text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-app-border/40 font-mono text-[11px]">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-app-muted font-sans text-xs">
                  <ShieldAlert className="w-6 h-6 opacity-30 mx-auto mb-1.5" />
                  No high-confidence hallucinations found.
                </td>
              </tr>
            ) : (
              filtered.map((item) => {
                const isSelected = item.assertion_id === selectedItem?.assertion_id;
                return (
                  <tr
                    key={item.assertion_id}
                    onClick={() => setSelectedId(item.assertion_id)}
                    className={`h-10 cursor-pointer transition-colors ${
                      isSelected
                        ? "border-l-2 border-rose-500 bg-rose-500/10 text-app-heading font-medium"
                        : "hover:bg-app-subtle text-app-muted hover:text-app-text"
                    }`}
                  >
                    <td className="py-2 px-3 truncate max-w-[120px] text-app-text">
                      {item.assertion_id}
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums text-rose-500 font-bold">
                      {(item.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="py-2 px-2 uppercase text-[10px] text-app-muted">
                      {item.assertion_type}
                    </td>
                    <td className="py-2 px-3 truncate max-w-[200px] text-app-text" title={item.descriptor}>
                      {item.descriptor}
                    </td>
                    <td className="py-2 px-2 text-center">
                      <span className="px-1.5 py-0.2 rounded text-[10px] bg-rose-500/15 text-rose-600 dark:text-rose-400 font-sans font-medium">
                        FP
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Selected Hallucination Diagnostic Drawer / Bottom Pane */}
      {selectedItem && (
        <div className="p-3.5 border-t border-app-border bg-app-bg space-y-2.5 shrink-0">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-app-muted">
              Selected Hallucination Diagnostic
            </span>
            <span className="font-mono text-xs text-rose-500 font-bold">
              Discrepancy: +{selectedItem.discrepancy.toFixed(2)}
            </span>
          </div>

          <div className="py-2 px-3 rounded-md bg-app-surface border border-app-border font-mono text-xs text-app-text">
            {selectedItem.descriptor}
          </div>

          {selectedItem.evidence_text && (
            <div className="space-y-1">
              <span className="text-[10px] text-app-muted uppercase font-semibold">
                Source Context / Text Grounding:
              </span>
              <blockquote className="text-xs text-app-muted italic bg-app-surface/60 p-2.5 rounded border-l-2 border-blue-500 font-serif leading-relaxed">
                &ldquo;{selectedItem.evidence_text}&rdquo;
              </blockquote>
            </div>
          )}

          {selectedItem.rationale && (
            <div className="space-y-1">
              <span className="text-[10px] text-app-muted uppercase font-semibold">
                Failure Mode Rationale:
              </span>
              <div className="text-xs text-rose-600 dark:text-rose-400 bg-rose-500/10 p-2.5 rounded border-l-2 border-rose-500 leading-relaxed font-sans">
                {selectedItem.rationale}
              </div>
            </div>
          )}

          {/* Action Trigger: Cross-module prompt tuning hook */}
          <div className="pt-1 flex justify-end">
            <ActionableHookPill
              type="overconfidence"
              sourceText={selectedItem.evidence_text || selectedItem.descriptor}
              assertionId={selectedItem.assertion_id}
              phaseKey="phase2"
              onClick={onOpenConfigEditor}
            />
          </div>
        </div>
      )}
    </div>
  );
};
