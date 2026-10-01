import React, { useState, useMemo, useEffect } from "react";
import {
  BookOpen,
  ChevronRight,
  Copy,
  Play,
  Plus,
} from "lucide-react";
import { useEvaluationStore } from "../../../store/evaluationStore";
import type { BenchmarkDescriptor } from "../../../api/types";

interface BenchmarkRegistryTableProps {
  benchmarks: BenchmarkDescriptor[];
  selectedBenchmarkId: string | null;
  onSelectBenchmark: (id: string) => void;
  onInspectBenchmark: (id: string) => void;
  onEvaluateBenchmark: (benchmark: BenchmarkDescriptor) => void;
  onRegisterClick?: () => void;
  onPromoteClick?: () => void;
}

export const BenchmarkRegistryTable: React.FC<BenchmarkRegistryTableProps> = ({
  benchmarks,
  selectedBenchmarkId,
  onSelectBenchmark,
  onInspectBenchmark,
  onEvaluateBenchmark,
  onRegisterClick,
  onPromoteClick,
}) => {
  const { catalogSearchQuery, catalogTaskFilter } = useEvaluationStore();
  const [copyFeedbackId, setCopyFeedbackId] = useState<string | null>(null);

  // Filter benchmarks based on store catalog filters
  const filteredBenchmarks = useMemo(() => {
    return benchmarks.filter((b) => {
      if (catalogTaskFilter !== "all" && b.task_type.toLowerCase() !== catalogTaskFilter.toLowerCase()) {
        return false;
      }
      if (!catalogSearchQuery.trim()) return true;
      const q = catalogSearchQuery.toLowerCase();
      return (
        b.name.toLowerCase().includes(q) ||
        b.id.toLowerCase().includes(q) ||
        (b.domain && b.domain.toLowerCase().includes(q)) ||
        (b.description && b.description.toLowerCase().includes(q))
      );
    });
  }, [benchmarks, catalogSearchQuery, catalogTaskFilter]);

  // Keyboard triage (design.md §11: j/k navigation, Enter to inspect)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "TEXTAREA"
      ) {
        return;
      }

      if (filteredBenchmarks.length === 0) return;

      const currentIndex = filteredBenchmarks.findIndex(
        (b) => b.id === selectedBenchmarkId
      );

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        const nextIndex =
          currentIndex < filteredBenchmarks.length - 1 ? currentIndex + 1 : 0;
        onSelectBenchmark(filteredBenchmarks[nextIndex].id);
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        const prevIndex =
          currentIndex > 0 ? currentIndex - 1 : filteredBenchmarks.length - 1;
        onSelectBenchmark(filteredBenchmarks[prevIndex].id);
      } else if (e.key === "Enter") {
        if (selectedBenchmarkId) {
          e.preventDefault();
          onInspectBenchmark(selectedBenchmarkId);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [filteredBenchmarks, selectedBenchmarkId, onSelectBenchmark, onInspectBenchmark]);

  const handleCopyId = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopyFeedbackId(id);
    setTimeout(() => setCopyFeedbackId(null), 1500);
  };

  return (
    <div className="flex-1 flex flex-col h-full w-full bg-app-bg text-app-text font-sans overflow-hidden">
      {/* Edge-to-Edge Data Grid (design.md §9 Headless Linear-Style Grid) */}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-left border-collapse select-none font-sans">
          {/* Table Header: Inter 11px, weight 600, uppercase, tracking-[0.05em] */}
          <thead className="sticky top-0 z-10 bg-app-surface border-b border-app-border font-sans">
            <tr className="h-9 text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
              <th className="px-4 py-0 font-medium">Benchmark Specification</th>
              <th className="px-3 py-0 font-medium w-40">Task & Level</th>
              <th className="px-3 py-0 font-medium w-52">Domain / Area</th>
              <th className="px-3 py-0 font-medium w-44">Elements & Splits</th>
              <th className="px-3 py-0 font-medium w-48">Recommended Metrics</th>
              <th className="px-4 py-0 font-medium w-36 text-right">Actions</th>
            </tr>
          </thead>

          {/* Table Body */}
          <tbody className="divide-y divide-app-border/70 text-xs">
            {filteredBenchmarks.length > 0 ? (
              filteredBenchmarks.map((b) => {
                const isSelected = b.id === selectedBenchmarkId;

                // Scale info in clean human format
                const goldSplit = b.splits?.["gold"];
                const queriesSplit = b.splits?.["queries"];
                const scaleLabel =
                  b.task_type === "structuralist" && b.structuralist_details
                    ? `${b.structuralist_details.invariants.total_atoms} atoms · ${b.structuralist_details.invariants.total_relations} rels`
                    : b.task_type === "retrieval" && b.retrieval_details
                    ? `${b.retrieval_details.query_count} queries`
                    : b.task_type === "extraction" && b.extraction_details
                    ? `${b.extraction_details.document_count} docs · ${b.extraction_details.sentence_count} sents`
                    : goldSplit?.item_count
                    ? `${goldSplit.item_count} items`
                    : "Reference gold";

                return (
                  <tr
                    key={b.id}
                    onClick={() => onSelectBenchmark(b.id)}
                    onDoubleClick={() => onInspectBenchmark(b.id)}
                    className={`h-11 transition-colors cursor-pointer group ${
                      isSelected
                        ? "bg-app-subtle border-l-[2px] border-l-blue-500"
                        : "border-l-[2px] border-l-transparent hover:bg-app-subtle/50"
                    }`}
                  >
                    {/* 1. Name (Manrope font-display) & Machine Slug (JetBrains Mono) */}
                    <td className="px-4 py-1.5">
                      <div className="flex flex-col">
                        <span className="font-display font-medium text-sm text-app-heading group-hover:text-blue-500 transition-colors">
                          {b.name}
                        </span>
                        <div className="flex items-center gap-1.5 text-[11px] text-app-muted pt-0.5">
                          <span className="font-mono text-[11px] text-app-muted">
                            {b.id}
                          </span>
                          <button
                            type="button"
                            onClick={(e) => handleCopyId(e, b.id)}
                            className="opacity-0 group-hover:opacity-100 hover:text-app-text transition-opacity cursor-pointer"
                            title="Copy benchmark ID"
                          >
                            <Copy className="w-3 h-3" />
                          </button>
                          {copyFeedbackId === b.id && (
                            <span className="text-[10px] text-app-muted font-sans">copied</span>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* 2. Task Category & Level (Neutral Inter badges, no loud colors) */}
                    <td className="px-3 py-1.5">
                      <div className="flex items-center gap-1.5 font-sans">
                        <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-app-subtle border border-app-border text-app-text">
                          {b.task_type === "structuralist"
                            ? "TheoryNet"
                            : b.task_type === "retrieval"
                            ? "Retrieval"
                            : b.task_type === "extraction"
                            ? "Extraction"
                            : b.task_type}
                        </span>
                        <span className="text-[11px] text-app-muted">
                          L{b.level || (b.task_type === "structuralist" ? 4 : 2)}
                        </span>
                      </div>
                    </td>

                    {/* 3. Scientific Domain */}
                    <td className="px-3 py-1.5 font-sans">
                      <span className="text-xs text-app-text/90 truncate block max-w-[200px]" title={b.domain}>
                        {b.domain || "General Science"}
                      </span>
                    </td>

                    {/* 4. Scale & Splits (Tabular numerals, not mono) */}
                    <td className="px-3 py-1.5 font-sans">
                      <div className="flex flex-col">
                        <span className="text-xs font-medium tabular-nums text-app-heading">
                          {scaleLabel}
                        </span>
                        <span className="text-[11px] text-app-muted">
                          {[
                            goldSplit && "gold",
                            queriesSplit && "queries",
                          ].filter(Boolean).join(", ") || "gold reference"}
                        </span>
                      </div>
                    </td>

                    {/* 5. Recommended Metrics (Neutral tags) */}
                    <td className="px-3 py-1.5 font-sans">
                      <div className="flex flex-wrap gap-1">
                        {(b.target_metrics || ["MCC", "PFS"]).slice(0, 3).map((m) => (
                          <span
                            key={m}
                            className="px-1.5 py-0.2 rounded text-[10px] font-medium bg-app-subtle/60 border border-app-border text-app-muted"
                          >
                            {m}
                          </span>
                        ))}
                      </div>
                    </td>

                    {/* 6. Action Buttons */}
                    <td className="px-4 py-1.5 text-right font-sans">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onInspectBenchmark(b.id);
                          }}
                          className="px-2.5 py-1 rounded text-xs font-medium bg-app-surface hover:bg-app-subtle text-app-text border border-app-border transition-colors cursor-pointer flex items-center gap-1"
                        >
                          <span>Inspect</span>
                          <ChevronRight className="w-3 h-3 text-app-muted" />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onEvaluateBenchmark(b);
                          }}
                          className="px-2.5 py-1 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer flex items-center gap-1"
                          title="Evaluate a pipeline run against this benchmark"
                        >
                          <Play className="w-3 h-3" />
                          <span>Eval</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-app-muted font-sans">
                  <div className="flex flex-col items-center justify-center space-y-2">
                    <BookOpen className="w-8 h-8 text-app-muted/40" />
                    <p className="font-display text-sm font-medium text-app-heading">No Benchmarks Found</p>
                    <p className="text-xs max-w-sm text-app-muted">
                      No registered reference datasets match your search or filter criteria.
                    </p>
                    <button
                      onClick={onRegisterClick}
                      className="mt-2 flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Register Benchmark</span>
                    </button>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
