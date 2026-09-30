import React, { useMemo, useEffect, useCallback } from "react";
import { AlertTriangle, ShieldAlert, ArrowUpDown, ChevronUp, ChevronDown } from "lucide-react";
import type { MiscalibratedAssertionItem } from "../../../../api/types";

export interface OverconfidenceTableProps {
  assertions: MiscalibratedAssertionItem[];
  selectedId: string | null;
  onSelectId: (id: string) => void;
  searchQuery?: string;
}

type SortField = "id" | "confidence" | "type" | "descriptor";
type SortDirection = "asc" | "desc";

/**
 * Headless Linear-Style Data Grid for Miscalibrated Assertions.
 *
 * Implements design.md §9 (Linear data grid specification):
 * - Fixed 40px (h-10) table rows
 * - Inset surface wash (bg-app-subtle) with 2px left border in primary blue (#2563EB)
 * - Click-to-sort column headers with Inter 11px uppercase tracking-[0.05em]
 * - Keyboard triage ergonomics (§11): j/k and arrow keys advance selection
 */
export const OverconfidenceTable: React.FC<OverconfidenceTableProps> = ({
  assertions,
  selectedId,
  onSelectId,
  searchQuery = "",
}) => {
  const [sortField, setSortField] = React.useState<SortField>("confidence");
  const [sortDirection, setSortDirection] = React.useState<SortDirection>("desc");

  // Filter assertions
  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return assertions;
    const q = searchQuery.toLowerCase();
    return assertions.filter((item) => {
      return (
        item.assertion_id.toLowerCase().includes(q) ||
        item.descriptor.toLowerCase().includes(q) ||
        item.assertion_type.toLowerCase().includes(q) ||
        (item.rationale && item.rationale.toLowerCase().includes(q))
      );
    });
  }, [assertions, searchQuery]);

  // Sort assertions
  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let valA: any = a.confidence;
      let valB: any = b.confidence;

      if (sortField === "id") {
        valA = a.assertion_id;
        valB = b.assertion_id;
      } else if (sortField === "type") {
        valA = a.assertion_type;
        valB = b.assertion_type;
      } else if (sortField === "descriptor") {
        valA = a.descriptor;
        valB = b.descriptor;
      }

      if (valA < valB) return sortDirection === "asc" ? -1 : 1;
      if (valA > valB) return sortDirection === "asc" ? 1 : -1;
      return 0;
    });
  }, [filtered, sortField, sortDirection]);

  // Active index
  const activeIndex = useMemo(() => {
    if (!selectedId) return 0;
    const idx = sorted.findIndex((i) => i.assertion_id === selectedId);
    return idx >= 0 ? idx : 0;
  }, [sorted, selectedId]);

  // Keyboard triage (§11)
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Ignore if focus is in an input or textarea
      const target = e.target as HTMLElement;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        if (activeIndex < sorted.length - 1) {
          onSelectId(sorted[activeIndex + 1].assertion_id);
        }
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        if (activeIndex > 0) {
          onSelectId(sorted[activeIndex - 1].assertion_id);
        }
      }
    },
    [activeIndex, sorted, onSelectId]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const handleToggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-hidden bg-app-bg select-none">
      {/* Edge-to-Edge Data Table */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <table className="w-full text-left text-xs border-collapse">
          {/* Table Header (design.md §9: surface-light/dark, border-b 1px, Inter 11px uppercase tracking-[0.05em]) */}
          <thead className="sticky top-0 bg-app-surface border-b border-app-border text-[11px] text-app-muted font-semibold tracking-[0.05em] uppercase z-10">
            <tr className="h-9">
              <th
                onClick={() => handleToggleSort("id")}
                className="px-4 cursor-pointer hover:text-app-text transition-colors w-[22%]"
              >
                <div className="flex items-center gap-1">
                  <span>Assertion ID</span>
                  {sortField === "id" &&
                    (sortDirection === "asc" ? (
                      <ChevronUp className="w-3 h-3 text-blue-500" />
                    ) : (
                      <ChevronDown className="w-3 h-3 text-blue-500" />
                    ))}
                </div>
              </th>
              <th
                onClick={() => handleToggleSort("confidence")}
                className="px-3 text-right cursor-pointer hover:text-app-text transition-colors w-[14%]"
              >
                <div className="flex items-center justify-end gap-1">
                  <span>Conf</span>
                  {sortField === "confidence" &&
                    (sortDirection === "asc" ? (
                      <ChevronUp className="w-3 h-3 text-blue-500" />
                    ) : (
                      <ChevronDown className="w-3 h-3 text-blue-500" />
                    ))}
                </div>
              </th>
              <th
                onClick={() => handleToggleSort("type")}
                className="px-3 cursor-pointer hover:text-app-text transition-colors w-[16%]"
              >
                <div className="flex items-center gap-1">
                  <span>Type</span>
                  {sortField === "type" &&
                    (sortDirection === "asc" ? (
                      <ChevronUp className="w-3 h-3 text-blue-500" />
                    ) : (
                      <ChevronDown className="w-3 h-3 text-blue-500" />
                    ))}
                </div>
              </th>
              <th
                onClick={() => handleToggleSort("descriptor")}
                className="px-4 cursor-pointer hover:text-app-text transition-colors w-[36%]"
              >
                <div className="flex items-center gap-1">
                  <span>Descriptor</span>
                  {sortField === "descriptor" &&
                    (sortDirection === "asc" ? (
                      <ChevronUp className="w-3 h-3 text-blue-500" />
                    ) : (
                      <ChevronDown className="w-3 h-3 text-blue-500" />
                    ))}
                </div>
              </th>
              <th className="px-3 text-center w-[12%]">Verdict</th>
            </tr>
          </thead>

          {/* Table Body (design.md §9: fixed height 40px h-10, px-6 / px-4) */}
          <tbody className="divide-y divide-app-border font-sans text-xs">
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-12 text-center text-app-muted">
                  <ShieldAlert className="w-7 h-7 opacity-30 mx-auto mb-2" />
                  <p className="type-body text-xs text-app-heading">No miscalibrated assertions found</p>
                  <p className="type-caption text-[11px] text-app-muted mt-0.5">
                    {searchQuery ? "Try refining your search filter." : "Model extractions are well calibrated."}
                  </p>
                </td>
              </tr>
            ) : (
              sorted.map((item) => {
                const isSelected = item.assertion_id === selectedId;

                return (
                  <tr
                    key={item.assertion_id}
                    onClick={() => onSelectId(item.assertion_id)}
                    className={`h-10 cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-app-subtle border-l-2 border-blue-600 text-app-heading font-medium"
                        : "border-l-2 border-transparent hover:bg-app-subtle/50 text-app-text"
                    }`}
                  >
                    {/* Machine ID (JetBrains Mono) */}
                    <td className="px-4 type-mono text-[11px] text-app-heading truncate max-w-[160px]">
                      {item.assertion_id}
                    </td>

                    {/* Confidence (Inter Tabular, right-aligned) */}
                    <td className="px-3 text-right type-mono font-semibold tabular-nums text-rose-500 text-xs">
                      {(item.confidence * 100).toFixed(1)}%
                    </td>

                    {/* Machine Class / Type */}
                    <td className="px-3 type-mono text-[10px] uppercase text-app-muted truncate">
                      {item.assertion_type}
                    </td>

                    {/* Descriptor */}
                    <td
                      className="px-4 type-body text-xs text-app-heading truncate max-w-[260px]"
                      title={item.descriptor}
                    >
                      {item.descriptor}
                    </td>

                    {/* Operational State Pill */}
                    <td className="px-3 text-center">
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] type-mono font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/25">
                        FP (+{item.discrepancy.toFixed(2)})
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Grid Footer Summary Bar */}
      <div className="h-8 px-4 border-t border-app-border bg-app-surface/60 shrink-0 flex items-center justify-between text-[11px] text-app-muted">
        <span>
          Showing <strong className="type-mono text-app-heading font-semibold">{sorted.length}</strong> of{" "}
          <strong className="type-mono text-app-heading font-semibold">{assertions.length}</strong> assertions
        </span>
        <span className="hidden sm:inline text-app-muted/70">
          Use <kbd className="px-1 py-0.5 rounded bg-app-bg border border-app-border text-[10px] type-mono">j</kbd> /{" "}
          <kbd className="px-1 py-0.5 rounded bg-app-bg border border-app-border text-[10px] type-mono">k</kbd> to step through items
        </span>
      </div>
    </div>
  );
};
