import React, { useState, useMemo, useEffect, useCallback } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Filter,
  Layers,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Link2,
} from "lucide-react";
import { useEvaluationStore } from "../../../../store/evaluationStore";
import type { ModelDecompositionEntry } from "../../../../api/types";
import type { BourbakiSubElement } from "./types";
import { CLASS_METADATA, getBourbakiSubElements } from "./types";

export interface CascadingBourbakiGridProps {
  selectedElement?: BourbakiSubElement | null;
  onSelectElement?: (el: BourbakiSubElement | null) => void;
  onElementsCalculated?: (elements: BourbakiSubElement[]) => void;
}

/**
 * Headless Linear-Style Data Grid for Bourbaki Structuralist Completeness.
 *
 * Implements design.md §9 & §11:
 * - Fixed 40px (h-10) table rows
 * - Active selection: solid 2px left border in primary blue (#2563EB) + bg-app-subtle
 * - Strict typography roles: JetBrains Mono for symbols/IDs, Inter for labels, tabular-nums for ratios
 * - Full keyboard triage (j/k and arrow keys step through sub-element rows)
 */
export const CascadingBourbakiGrid: React.FC<CascadingBourbakiGridProps> = ({
  selectedElement: propSelectedElement,
  onSelectElement: propOnSelectElement,
  onElementsCalculated,
}) => {
  const {
    activeReport,
    stagedAdjudications,
    optimisticScalarDeltas,
    selectedBourbakiElement,
    setSelectedBourbakiElement,
  } = useEvaluationStore();

  const selectedElement =
    propSelectedElement !== undefined ? propSelectedElement : selectedBourbakiElement;

  const handleSelectElement = useCallback(
    (el: BourbakiSubElement | null) => {
      if (propOnSelectElement) {
        propOnSelectElement(el);
      } else {
        setSelectedBourbakiElement(el);
      }
    },
    [propOnSelectElement, setSelectedBourbakiElement]
  );

  const [expandedClasses, setExpandedClasses] = useState<Set<string>>(
    new Set(["Mp", "M", "Mpp", "C", "I"])
  );
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "masked" | "omission">("all");

  const toggleClassExpand = (cls: string) => {
    setExpandedClasses((prev) => {
      const next = new Set(prev);
      if (next.has(cls)) {
        next.delete(cls);
      } else {
        next.add(cls);
      }
      return next;
    });
  };

  // Normalize model decomposition entries from activeReport
  const decompositionEntries = useMemo(() => {
    if (!activeReport?.model_decomposition || activeReport.model_decomposition.length === 0) {
      return [
        {
          class_name: "potential_models",
          symbol: "Mp",
          reference_count: 12,
          predicted_count: 11,
          matched_count: 10,
          completeness: 0.833,
        },
        {
          class_name: "actual_models",
          symbol: "M",
          reference_count: 24,
          predicted_count: 20,
          matched_count: 18,
          completeness: 0.75,
        },
        {
          class_name: "partial_potential_models",
          symbol: "Mpp",
          reference_count: 18,
          predicted_count: 17,
          matched_count: 17,
          completeness: 0.944,
        },
        {
          class_name: "constraints",
          symbol: "C",
          reference_count: 8,
          predicted_count: 7,
          matched_count: 7,
          completeness: 0.875,
        },
        {
          class_name: "intended_applications",
          symbol: "I",
          reference_count: 30,
          predicted_count: 24,
          matched_count: 22,
          completeness: 0.733,
        },
      ] as ModelDecompositionEntry[];
    }
    return activeReport.model_decomposition;
  }, [activeReport]);

  // Hierarchical elements with Conditional Cascade Masking
  const subElements = useMemo(() => {
    return getBourbakiSubElements(activeReport, decompositionEntries);
  }, [activeReport, decompositionEntries]);

  useEffect(() => {
    if (onElementsCalculated) {
      onElementsCalculated(subElements);
    }
  }, [subElements, onElementsCalculated]);

  // Filtered sub-elements
  const filteredSubElements = useMemo(() => {
    return subElements.filter((el) => {
      if (statusFilter === "active") return el.status === "pass" || el.status === "active";
      if (statusFilter === "masked") return el.status === "cascade_masked_orphan";
      if (statusFilter === "omission") return el.status === "root_cause_omission";
      return true;
    });
  }, [subElements, statusFilter]);

  // Flattened visible elements list for j/k keyboard triage
  const visibleSubElements = useMemo(() => {
    const list: BourbakiSubElement[] = [];
    for (const clsKey of ["Mp", "M", "Mpp", "C", "I"]) {
      if (expandedClasses.has(clsKey)) {
        const children = filteredSubElements.filter((el) => el.classType === clsKey);
        list.push(...children);
      }
    }
    return list;
  }, [expandedClasses, filteredSubElements]);

  // Keyboard Triage (§11)
  const activeIndex = useMemo(() => {
    if (!selectedElement) return -1;
    return visibleSubElements.findIndex((el) => el.id === selectedElement.id);
  }, [visibleSubElements, selectedElement]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
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
        if (visibleSubElements.length === 0) return;
        const nextIndex = activeIndex < visibleSubElements.length - 1 ? activeIndex + 1 : 0;
        handleSelectElement(visibleSubElements[nextIndex]);
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        if (visibleSubElements.length === 0) return;
        const prevIndex = activeIndex > 0 ? activeIndex - 1 : visibleSubElements.length - 1;
        handleSelectElement(visibleSubElements[prevIndex]);
      }
    },
    [activeIndex, visibleSubElements, handleSelectElement]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const stagedCount = stagedAdjudications.size;

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-hidden bg-app-bg text-app-text select-none font-sans">
      {/* 44px Contextual Sub-Bar (design.md §8: Breadcrumbs, Scope pills, Filter pills) */}
      <div className="h-11 px-4 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs gap-3">
        <div className="flex items-center gap-2">
          <Layers className="w-3.5 h-3.5 text-blue-500" />
          <h3 className="type-caption font-semibold text-app-heading uppercase tracking-wider">
            Bourbaki Decomposition Grid
          </h3>
          <span className="type-mono text-[11px] text-app-muted hidden md:inline">
            ⟨Mp → M → I⟩
          </span>
        </div>

        {/* Filter Pills (Segmented Pill Track) */}
        <div className="flex items-center gap-1 bg-app-bg p-0.5 rounded border border-app-border text-[11px]">
          <Filter className="w-3 h-3 text-app-muted ml-1 mr-0.5" />
          {[
            { id: "all", label: "All Nodes" },
            { id: "active", label: "Verified" },
            { id: "masked", label: "Cascade Masked" },
            { id: "omission", label: "Root Omissions" },
          ].map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setStatusFilter(f.id as any)}
              className={`px-2 py-0.5 rounded transition-colors cursor-pointer ${
                statusFilter === f.id
                  ? "bg-app-surface text-app-heading font-medium border border-app-border/80"
                  : "text-app-muted hover:text-app-text"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Staging Buffer Notice */}
      {stagedCount > 0 && (
        <div className="px-4 py-2 bg-amber-500/10 border-b border-amber-500/30 flex items-center justify-between text-xs text-amber-600 dark:text-amber-400">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-500" />
            <span>
              <strong>{stagedCount} Staged Adjudications</strong> pending commit (⌘⏎).
            </span>
          </div>
          {optimisticScalarDeltas.f1 !== 0 && (
            <span className="type-mono tabular-nums text-[11px] font-semibold bg-amber-500/20 px-2 py-0.5 rounded">
              ΔF₁: {optimisticScalarDeltas.f1 > 0 ? "+" : ""}
              {optimisticScalarDeltas.f1.toFixed(3)}
            </span>
          )}
        </div>
      )}

      {/* Edge-to-Edge Data Table */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <table className="w-full text-left text-xs border-collapse">
          {/* Sticky Table Header (design.md §9: surface-light/dark, border-b 1px, Inter 11px uppercase tracking-[0.05em]) */}
          <thead className="sticky top-0 bg-app-surface border-b border-app-border text-[11px] text-app-muted font-semibold tracking-[0.05em] uppercase z-10">
            <tr className="h-9">
              <th className="px-4 font-semibold w-[44%]">Structural Component</th>
              <th className="px-3 text-center tabular-nums font-semibold w-[14%]">Match / Gold</th>
              <th className="px-3 text-center tabular-nums font-semibold w-[12%]">Impact (↓)</th>
              <th className="px-3 text-center font-semibold w-[14%]">Gold Polarity</th>
              <th className="px-4 text-center font-semibold w-[16%]">Verdict</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-app-border font-sans">
            {["Mp", "M", "Mpp", "C", "I"].map((clsKey) => {
              const meta = CLASS_METADATA[clsKey];
              const summary = decompositionEntries.find(
                (d) =>
                  d.symbol === clsKey ||
                  d.class_name.toLowerCase().startsWith(clsKey.toLowerCase()) ||
                  (clsKey === "Mp" && d.class_name.includes("potential") && !d.class_name.includes("partial")) ||
                  (clsKey === "M" && d.class_name.includes("actual")) ||
                  (clsKey === "Mpp" && d.class_name.includes("partial")) ||
                  (clsKey === "C" && d.class_name.includes("constraint")) ||
                  (clsKey === "I" && d.class_name.includes("intended"))
              ) || {
                class_name: meta.label,
                symbol: meta.symbol,
                reference_count: 1,
                predicted_count: 1,
                matched_count: 1,
                completeness: 1.0,
              };

              const isExpanded = expandedClasses.has(clsKey);
              const classChildren = filteredSubElements.filter((el) => el.classType === clsKey);
              const coveragePct = Math.round(summary.completeness * 1000) / 10;
              const categoryImpact = classChildren.reduce(
                (sum, c) => sum + (c.dependents?.length || 0),
                0
              );

              return (
                <React.Fragment key={clsKey}>
                  {/* Category Class Row (Fixed 40px h-10) */}
                  <tr
                    onClick={() => toggleClassExpand(clsKey)}
                    className="h-10 hover:bg-app-subtle cursor-pointer transition-colors bg-app-surface/50 font-medium"
                  >
                    <td className="px-4">
                      <div className="flex items-center gap-2">
                        <span className="text-app-muted">
                          {isExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5" />
                          )}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded type-mono text-[10px] font-semibold border ${meta.bg} ${meta.color} ${meta.border}`}
                        >
                          {meta.symbol}
                        </span>
                        <span className="font-semibold text-app-heading text-xs">{meta.label}</span>
                        <span className="type-caption text-app-muted hidden sm:inline truncate max-w-xs">
                          — {meta.description}
                        </span>
                      </div>
                    </td>

                    {/* Category Match / Gold */}
                    <td className="px-3 text-center type-mono tabular-nums text-xs">
                      <span className="font-semibold text-app-heading">
                        {summary.matched_count} / {summary.reference_count}
                      </span>
                      <span className="text-[10px] text-app-muted ml-1">
                        ({coveragePct.toFixed(0)}%)
                      </span>
                    </td>

                    {/* Category Impact */}
                    <td className="px-3 text-center type-mono tabular-nums text-xs">
                      {categoryImpact > 0 ? (
                        <span className="font-semibold text-purple-600 dark:text-purple-400">
                          ↓ {categoryImpact}
                        </span>
                      ) : (
                        <span className="text-app-muted/50">—</span>
                      )}
                    </td>

                    {/* Category Polarity */}
                    <td className="px-3 text-center text-xs">
                      {classChildren.some(
                        (c) => c.inferentialPolarity?.concordance === "CRITICAL_INVERSION"
                      ) ? (
                        <span className="inline-flex items-center gap-1 text-rose-500 font-medium text-[11px]">
                          <AlertTriangle className="w-3 h-3" />
                          Inverted
                        </span>
                      ) : (
                        <span className="text-app-muted font-medium text-[11px]">Agreed</span>
                      )}
                    </td>

                    {/* Category Verdict */}
                    <td className="px-4 text-center">
                      {summary.reference_count === 0 ? (
                        <span className="inline-flex items-center gap-1.5 text-[11px] text-zinc-400">
                          Conformant
                        </span>
                      ) : coveragePct >= 85 ? (
                        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Pass
                        </span>
                      ) : coveragePct > 0 ? (
                        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-amber-600 dark:text-amber-400">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                          Partial
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-rose-500">
                          <XCircle className="w-3.5 h-3.5" />
                          Fail
                        </span>
                      )}
                    </td>
                  </tr>

                  {/* Hierarchical Sub-Elements (Fixed 40px h-10) */}
                  {isExpanded &&
                    classChildren.map((el) => {
                      const isSelected = selectedElement?.id === el.id;
                      const isMasked = el.status === "cascade_masked_orphan";
                      const isOmission = el.status === "root_cause_omission";

                      return (
                        <tr
                          key={el.id}
                          onClick={() => handleSelectElement(el)}
                          className={`h-10 cursor-pointer transition-colors ${
                            isSelected
                              ? "bg-app-subtle border-l-2 border-blue-600 text-app-heading font-medium"
                              : isMasked
                              ? "border-l-2 border-transparent text-app-muted/60 hover:bg-app-subtle/50"
                              : isOmission
                              ? "border-l-2 border-rose-500/50 bg-rose-500/5 hover:bg-rose-500/10 text-app-heading"
                              : "border-l-2 border-transparent hover:bg-app-subtle/50 text-app-text"
                          }`}
                        >
                          <td className="px-4 pl-9">
                            <div className="flex items-center gap-2">
                              {el.parentAxiomId && (
                                <Link2 className="w-3 h-3 text-app-muted/60 shrink-0" />
                              )}
                              <span className="type-mono text-[11px] font-semibold text-app-heading shrink-0">
                                {el.symbol}
                              </span>
                              <span
                                className={`type-body text-xs text-app-heading truncate ${
                                  isMasked ? "line-through opacity-70" : ""
                                }`}
                              >
                                {el.name}
                              </span>
                            </div>
                          </td>

                          {/* Match / Gold */}
                          <td className="px-3 text-center type-mono tabular-nums text-xs">
                            <span
                              className={`font-semibold ${
                                el.matched_count >= el.reference_count
                                  ? "text-app-heading"
                                  : "text-rose-500"
                              }`}
                            >
                              {el.matched_count} / {el.reference_count}
                            </span>
                            {el.predicted_count > el.matched_count && (
                              <span
                                className="text-[10px] text-amber-500 ml-1"
                                title={`${
                                  el.predicted_count - el.matched_count
                                } extra predicted instances`}
                              >
                                (+{el.predicted_count - el.matched_count})
                              </span>
                            )}
                          </td>

                          {/* Impact (↓) */}
                          <td className="px-3 text-center type-mono tabular-nums text-xs">
                            {el.dependents && el.dependents.length > 0 ? (
                              <span className="font-semibold text-purple-600 dark:text-purple-400">
                                ↓ {el.dependents.length}
                              </span>
                            ) : (
                              <span className="text-app-muted/40">—</span>
                            )}
                          </td>

                          {/* Gold Polarity */}
                          <td className="px-3 text-center text-xs">
                            {isOmission || (el.coverage === 0 && !el.inferentialPolarity) ? (
                              <span className="text-app-muted/40">—</span>
                            ) : el.inferentialPolarity?.concordance === "CRITICAL_INVERSION" ? (
                              <span className="inline-flex items-center gap-1 text-rose-500 font-semibold text-[11px]">
                                <AlertTriangle className="w-3 h-3" />
                                Inverted
                              </span>
                            ) : (
                              <span className="text-app-muted font-medium text-[11px]">Agreed</span>
                            )}
                          </td>

                          {/* Verdict */}
                          <td className="px-4 text-center">
                            {isMasked ? (
                              <span className="inline-flex items-center gap-1.5 text-[11px] text-app-muted font-medium">
                                <span className="w-1.5 h-1.5 rounded-full border border-app-muted shrink-0" />
                                Masked
                              </span>
                            ) : isOmission ? (
                              <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-rose-500">
                                <span className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0" />
                                Root Omission
                              </span>
                            ) : el.coverage === 0 && el.reference_count > 0 ? (
                              <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-rose-500">
                                Missing
                              </span>
                            ) : el.coverage >= 0.85 || (el.matched_count > 0 && el.coverage > 0) ? (
                              <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                Pass
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-amber-600 dark:text-amber-400">
                                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                                Partial
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer Instructions */}
      <div className="h-8 px-4 border-t border-app-border bg-app-surface/60 shrink-0 flex items-center justify-between text-[11px] text-app-muted">
        <span>
          Showing <strong className="type-mono text-app-heading">{visibleSubElements.length}</strong> active sub-elements
        </span>
        <span className="hidden sm:inline text-app-muted/70">
          Use <kbd className="px-1 py-0.5 rounded bg-app-bg border border-app-border text-[10px] type-mono">j</kbd> /{" "}
          <kbd className="px-1 py-0.5 rounded bg-app-bg border border-app-border text-[10px] type-mono">k</kbd> to step through nodes
        </span>
      </div>
    </div>
  );
};
