import React, { useState, useMemo, useEffect } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Database,
  Filter,
  Layers,
  ShieldAlert,
  Sparkles,
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

  // If props are provided, use them; otherwise use store
  const selectedElement =
    propSelectedElement !== undefined ? propSelectedElement : selectedBourbakiElement;

  const handleSelectElement = (el: BourbakiSubElement | null) => {
    if (propOnSelectElement) {
      propOnSelectElement(el);
    } else {
      setSelectedBourbakiElement(el);
    }
  };

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
      // Fallback synthetic summary if not seeded
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

  // Hierarchical elements with Conditional Cascade Masking & theoretical models
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

  const stagedCount = stagedAdjudications.size;

  return (
    <div className="flex flex-col h-full overflow-hidden bg-app-bg text-app-text select-none font-sans">
      {/* 40px Header Toolbar */}
      <div className="h-10 px-4 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-blue-500" />
          <h3 className="font-semibold text-app-heading">
            Bourbaki Structuralist Completeness
          </h3>
          <span className="text-[11px] text-app-muted font-mono hidden md:inline">
            ⟨Mp → M → I⟩ Cascading Decomposition
          </span>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1">
          <Filter className="w-3 h-3 text-app-muted mr-1" />
          {[
            { id: "all", label: "All Items" },
            { id: "active", label: "Verified" },
            { id: "masked", label: "Cascade Masked" },
            { id: "omission", label: "Root Omissions" },
          ].map((f) => (
            <button
              key={f.id}
              onClick={() => setStatusFilter(f.id as any)}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                statusFilter === f.id
                  ? "bg-blue-600 text-white font-semibold"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Staging Buffer Status Notice */}
      {stagedCount > 0 && (
        <div className="px-4 py-2 bg-amber-500/10 dark:bg-amber-500/15 border-b border-amber-500/30 flex items-center justify-between text-xs text-amber-600 dark:text-amber-400">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-amber-500" />
            <span>
              <strong>{stagedCount} Staged Adjudications</strong> pending batch commit (⌘⏎).
              Structural DAG topology and reachability invariants remain frozen until explicit
              server synchronization.
            </span>
          </div>
          {optimisticScalarDeltas.f1 !== 0 && (
            <span className="font-mono tabular-nums text-[11px] font-semibold bg-amber-500/20 px-2 py-0.5 rounded">
              ΔF₁ Preview: {optimisticScalarDeltas.f1 > 0 ? "+" : ""}
              {optimisticScalarDeltas.f1.toFixed(3)}
            </span>
          )}
        </div>
      )}

      {/* Main Table Grid Container (Full vertical space, unencumbered by bottom drawer) */}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-left border-collapse text-xs">
          {/* Sticky Table Header (Lean 5-Column Schema) */}
          <thead className="sticky top-0 bg-app-surface/90 backdrop-blur-xs border-b border-app-border z-10">
            <tr className="text-app-muted text-[11px] font-medium tracking-wide">
              <th className="py-2.5 px-4 font-medium w-[44%]">Component (Gold Entity)</th>
              <th className="py-2.5 px-3 text-center tabular-nums font-medium w-[14%]">Match / Gold</th>
              <th className="py-2.5 px-3 text-center tabular-nums font-medium w-[12%]">Impact (↓)</th>
              <th className="py-2.5 px-3 text-center font-medium w-[14%]">Gold Polarity</th>
              <th className="py-2.5 px-4 text-center font-medium w-[16%]">Verdict</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-app-border">
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
                  {/* Category Class Row */}
                  <tr
                    onClick={() => toggleClassExpand(clsKey)}
                    className="hover:bg-app-subtle cursor-pointer transition-colors bg-app-surface/40 group font-medium"
                  >
                    <td className="py-2.5 px-4">
                      <div className="flex items-center gap-2">
                        <button className="text-app-muted group-hover:text-app-text transition-colors">
                          {isExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5" />
                          )}
                        </button>
                        <span
                          className={`px-1.5 py-0.5 rounded font-mono text-[10px] font-medium border ${meta.bg} ${meta.color} ${meta.border}`}
                        >
                          {meta.symbol}
                        </span>
                        <span className="font-medium text-app-heading">{meta.label}</span>
                        <span className="text-[11px] text-app-muted hidden sm:inline truncate max-w-xs">
                          — {meta.description}
                        </span>
                      </div>
                    </td>

                    {/* Category Match / Gold */}
                    <td className="py-2.5 px-3 text-center tabular-nums text-[11px]">
                      <span className="font-medium text-app-heading">
                        {summary.matched_count} / {summary.reference_count}
                      </span>
                      <span className="text-[10px] text-app-muted ml-1">
                        ({coveragePct.toFixed(0)}%)
                      </span>
                    </td>

                    {/* Category Impact */}
                    <td className="py-2.5 px-3 text-center tabular-nums text-[11px]">
                      {categoryImpact > 0 ? (
                        <span className="font-medium text-purple-600 dark:text-purple-400">
                          ↓ {categoryImpact}
                        </span>
                      ) : (
                        <span className="text-app-muted/50">—</span>
                      )}
                    </td>

                    {/* Category Polarity */}
                    <td className="py-2.5 px-3 text-center text-[11px]">
                      {classChildren.some(
                        (c) => c.inferentialPolarity?.concordance === "CRITICAL_INVERSION"
                      ) ? (
                        <span className="inline-flex items-center gap-1 text-rose-500/90 dark:text-rose-400/90 font-medium">
                          <AlertTriangle className="w-3 h-3" />
                          Inverted
                        </span>
                      ) : (
                        <span className="text-zinc-400 font-medium">Agreed</span>
                      )}
                    </td>

                    {/* Category Verdict */}
                    <td className="py-2.5 px-4 text-center">
                      {summary.reference_count === 0 ? (
                        <span className="inline-flex items-center gap-1.5 text-[11px] text-zinc-400">
                          <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 shrink-0" />
                          Conformant
                        </span>
                      ) : coveragePct >= 85 ? (
                        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Pass
                        </span>
                      ) : coveragePct > 0 ? (
                        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                          Partial
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-rose-500/90 dark:text-rose-400/90">
                          <XCircle className="w-3.5 h-3.5" />
                          Fail
                        </span>
                      )}
                    </td>
                  </tr>

                  {/* Hierarchical Sub-Elements */}
                  {isExpanded &&
                    classChildren.map((el) => {
                      const isSelected = selectedElement?.id === el.id;
                      const isMasked = el.status === "cascade_masked_orphan";
                      const isOmission = el.status === "root_cause_omission";

                      return (
                        <tr
                          key={el.id}
                          onClick={() => handleSelectElement(el)}
                          className={`cursor-pointer transition-colors border-l-3 ${
                            isSelected
                              ? "bg-blue-600/15 border-blue-600 text-app-heading font-medium"
                              : isMasked
                              ? "bg-app-bg text-app-muted/60 hover:bg-app-subtle border-transparent"
                              : isOmission
                              ? "bg-rose-500/5 hover:bg-rose-500/10 border-rose-500/40 text-app-heading"
                              : "hover:bg-app-subtle border-transparent text-app-text"
                          }`}
                        >
                          <td className="py-2 pl-10 pr-4">
                            <div className="flex items-center gap-2">
                              {el.parentAxiomId && (
                                <Link2 className="w-3 h-3 text-app-muted/60 shrink-0" />
                              )}
                              <span
                                className={`font-mono text-[10px] font-medium ${
                                  isSelected
                                    ? "text-blue-500 dark:text-blue-400"
                                    : isMasked
                                    ? "text-app-muted"
                                    : "text-app-text"
                                }`}
                              >
                                {el.symbol}
                              </span>
                              <span
                                className={`font-normal text-app-text ${
                                  isMasked ? "line-through opacity-70" : ""
                                }`}
                              >
                                {el.name}
                              </span>
                              {isSelected && (
                                <span className="ml-auto text-[9px] px-1 py-0.2 rounded bg-blue-600 text-white font-medium tracking-wider">
                                  INSPECTING
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Match / Gold */}
                          <td className="py-2 px-3 text-center tabular-nums text-[11px]">
                            <span
                              className={`font-medium ${
                                el.matched_count >= el.reference_count
                                  ? "text-app-heading"
                                  : "text-rose-500/90 dark:text-rose-400/90"
                              }`}
                            >
                              {el.matched_count} / {el.reference_count}
                            </span>
                            {el.predicted_count > el.matched_count && (
                              <span
                                className="text-[10px] text-amber-500 ml-1"
                                title={`${
                                  el.predicted_count - el.matched_count
                                } extra predicted instances (over-generation)`}
                              >
                                (+{el.predicted_count - el.matched_count})
                              </span>
                            )}
                          </td>

                          {/* Impact (↓) */}
                          <td className="py-2 px-3 text-center tabular-nums text-[11px]">
                            {el.dependents && el.dependents.length > 0 ? (
                              <span
                                className="font-medium text-purple-600 dark:text-purple-400"
                                title={`${el.dependents.length} downstream gold components depend on this node`}
                              >
                                ↓ {el.dependents.length}
                              </span>
                            ) : (
                              <span className="text-app-muted/40">—</span>
                            )}
                          </td>

                          {/* Gold Polarity */}
                          <td className="py-2 px-3 text-center text-[11px]">
                            {isOmission || (el.coverage === 0 && !el.inferentialPolarity) ? (
                              <span className="text-app-muted/40">—</span>
                            ) : el.inferentialPolarity?.concordance === "CRITICAL_INVERSION" ? (
                              <span
                                className="inline-flex items-center gap-1 text-rose-500/90 dark:text-rose-400/90 font-medium"
                                title={`Predicted ${el.inferentialPolarity.predicate} conflicts with Gold ${el.inferentialPolarity.goldPredicate}`}
                              >
                                <AlertTriangle className="w-3 h-3" />
                                Inverted
                              </span>
                            ) : (
                              <span className="text-zinc-400 font-medium">Agreed</span>
                            )}
                          </td>

                          {/* Verdict */}
                          <td className="py-2 px-4 text-center">
                            {isMasked ? (
                              <span
                                title="Parent axiom failed in Mp. Dependent model masked under Bourbaki cascade doctrine."
                                className="inline-flex items-center gap-1.5 text-[11px] text-zinc-400 font-medium"
                              >
                                <span className="w-1.5 h-1.5 rounded-full border border-zinc-400 shrink-0" />
                                Cascade Masked
                              </span>
                            ) : isOmission ? (
                              <span
                                title="Root axiom missing in extraction! Causes downstream cascade masking."
                                className="inline-flex items-center gap-1.5 text-[11px] font-medium text-rose-500/90 dark:text-rose-400/90"
                              >
                                <span className="w-1.5 h-1.5 rounded-full bg-rose-400 dark:bg-rose-500 shrink-0" />
                                Root Omission
                              </span>
                            ) : el.coverage === 0 && el.reference_count > 0 ? (
                              <span
                                title="Unmatched reference axiom."
                                className="inline-flex items-center gap-1.5 text-[11px] font-medium text-rose-500/90 dark:text-rose-400/90"
                              >
                                <span className="w-1.5 h-1.5 rounded-full bg-rose-400 dark:bg-rose-500 shrink-0" />
                                Missing
                              </span>
                            ) : el.coverage >= 0.85 || (el.matched_count > 0 && el.coverage > 0) ? (
                              <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                Pass
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-amber-600 dark:text-amber-400">
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
    </div>
  );
};
