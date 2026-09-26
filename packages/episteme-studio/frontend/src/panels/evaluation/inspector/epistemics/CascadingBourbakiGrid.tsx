import React, { useState, useMemo } from "react";
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

export interface BourbakiSubElement {
  id: string;
  name: string;
  symbol: string;
  classType: "Mp" | "M" | "Mpp" | "C" | "I";
  parentAxiomId?: string;
  reference_count: number;
  predicted_count: number;
  matched_count: number;
  coverage: number;
  status: "pass" | "root_cause_omission" | "cascade_masked_orphan" | "active";
  rationale?: string;
}

const CLASS_METADATA: Record<
  string,
  { label: string; symbol: string; color: string; bg: string; border: string; description: string }
> = {
  Mp: {
    label: "Potential Models",
    symbol: "Mp",
    color: "text-blue-500 dark:text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
    description: "Mathematical frame structures and foundational axioms of the theory.",
  },
  M: {
    label: "Actual Models",
    symbol: "M",
    color: "text-emerald-500 dark:text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    description: "Core physical laws and domain axioms fulfilling the potential models.",
  },
  Mpp: {
    label: "Partial Potential Models",
    symbol: "Mpp",
    color: "text-amber-500 dark:text-amber-400",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    description: "Empirical basis and non-theoretical conceptual structures.",
  },
  C: {
    label: "Constraints",
    symbol: "C",
    color: "text-purple-500 dark:text-purple-400",
    bg: "bg-purple-500/10",
    border: "border-purple-500/30",
    description: "Cross-model constraints ensuring parameter consistency (e.g. constant masses).",
  },
  I: {
    label: "Intended Applications",
    symbol: "I",
    color: "text-orange-500 dark:text-orange-400",
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
    description: "Concrete empirical paradigms and target systems (e.g. planetary orbits, pendulums).",
  },
};

export const CascadingBourbakiGrid: React.FC = () => {
  const { activeReport, stagedAdjudications, optimisticScalarDeltas } = useEvaluationStore();

  const [expandedClasses, setExpandedClasses] = useState<Set<string>>(
    new Set(["Mp", "M", "Mpp", "C", "I"])
  );
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "masked" | "omission">("all");
  const [selectedElement, setSelectedElement] = useState<BourbakiSubElement | null>(null);

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

  // Hierarchical elements with Conditional Cascade Masking
  // Rule: If parent axiom in Mp fails (e.g. Axiom-02), downstream models in M and I are labeled [CASCADE_MASKED_ORPHAN]
  const subElements = useMemo(() => {
    const omitted = activeReport?.omitted_components || [];
    const hasMpOmission =
      omitted.some((c) => c.toLowerCase().includes("axiom") || c.toLowerCase().includes("mp")) ||
      (decompositionEntries.find((d) => d.symbol === "Mp" || d.class_name.includes("potential"))?.completeness ?? 1) < 1.0;

    const list: BourbakiSubElement[] = [
      // Mp Elements (Foundational Axioms)
      {
        id: "ax_01_space_metric",
        name: "Axiom-01 (Spatiotemporal Kinematics)",
        symbol: "Mp.1",
        classType: "Mp",
        reference_count: 1,
        predicted_count: 1,
        matched_count: 1,
        coverage: 1.0,
        status: "pass",
        rationale: "Topology and metric spaces accurately grounded in primary text.",
      },
      {
        id: "ax_02_dynamical_conservation",
        name: "Axiom-02 (Conservation of Momentum/Force)",
        symbol: "Mp.2",
        classType: "Mp",
        reference_count: 1,
        predicted_count: 0,
        matched_count: 0,
        coverage: 0.0,
        status: hasMpOmission ? "root_cause_omission" : "pass",
        rationale: hasMpOmission
          ? "Extraction failed to extract foundational conservation condition from Chapter II, §4."
          : "Verified in primary source text.",
      },
      {
        id: "ax_03_inertial_frames",
        name: "Axiom-03 (Inertial Frame Equivalence)",
        symbol: "Mp.3",
        classType: "Mp",
        reference_count: 1,
        predicted_count: 1,
        matched_count: 1,
        coverage: 1.0,
        status: "pass",
        rationale: "Extracted and mapped to Galilean relativity schema.",
      },

      // M Elements (Actual Models)
      {
        id: "m_01_inertial_dynamics",
        name: "Sub-Model 01-A (Inertial Force Equations)",
        symbol: "M.1",
        classType: "M",
        parentAxiomId: "ax_01_space_metric",
        reference_count: 1,
        predicted_count: 1,
        matched_count: 1,
        coverage: 1.0,
        status: "pass",
        rationale: "F = m*a derived successfully from Spatiotemporal frame.",
      },
      {
        id: "m_02_gravitational_law",
        name: "Sub-Model 02-A (Gravitational Force Balance)",
        symbol: "M.2",
        classType: "M",
        parentAxiomId: "ax_02_dynamical_conservation",
        reference_count: 1,
        predicted_count: 0,
        matched_count: 0,
        coverage: 0.0,
        status: hasMpOmission ? "cascade_masked_orphan" : "pass",
        rationale: hasMpOmission
          ? "Orphaned due to missing parent Axiom-02. Masked to prevent double-penalization."
          : "Verified against Keplerian reduction.",
      },
      {
        id: "m_03_harmonic_spring",
        name: "Sub-Model 03-C (Hookean Elastic Restoring Force)",
        symbol: "M.3",
        classType: "M",
        parentAxiomId: "ax_03_inertial_frames",
        reference_count: 1,
        predicted_count: 1,
        matched_count: 1,
        coverage: 1.0,
        status: "pass",
        rationale: "Linear oscillator laws mapped with correct parameters.",
      },

      // Mpp Elements (Partial Potential Models)
      {
        id: "mpp_01_kinematic_particles",
        name: "Kinematic Positions & Velocities",
        symbol: "Mpp.1",
        classType: "Mpp",
        reference_count: 1,
        predicted_count: 1,
        matched_count: 1,
        coverage: 1.0,
        status: "pass",
        rationale: "Empirical observation base successfully matched to text tokens.",
      },
      {
        id: "mpp_02_time_measurement",
        name: "Chronometric Standard Clock Intervals",
        symbol: "Mpp.2",
        classType: "Mpp",
        reference_count: 1,
        predicted_count: 1,
        matched_count: 1,
        coverage: 1.0,
        status: "pass",
        rationale: "Temporal measure concepts verified.",
      },

      // C Elements (Constraints)
      {
        id: "c_01_mass_equality",
        name: "Invariance of Gravitational & Inertial Mass",
        symbol: "C.1",
        classType: "C",
        reference_count: 1,
        predicted_count: 1,
        matched_count: 1,
        coverage: 1.0,
        status: "pass",
        rationale: "Equivalence constraint verified across multiple model instances.",
      },

      // I Elements (Intended Applications / Empirical Paradigms)
      {
        id: "i_01_planetary_orbits",
        name: "Paradigm I-01 (Keplerian Planetary Orbits)",
        symbol: "I.1",
        classType: "I",
        parentAxiomId: "ax_01_space_metric",
        reference_count: 1,
        predicted_count: 1,
        matched_count: 1,
        coverage: 1.0,
        status: "pass",
        rationale: "Solar system orbit paradigm grounded in historical corpus.",
      },
      {
        id: "i_02_lunar_perturbation",
        name: "Empirical Claim 08 (Lunar Perturbation & Tides)",
        symbol: "I.2",
        classType: "I",
        parentAxiomId: "ax_02_dynamical_conservation",
        reference_count: 1,
        predicted_count: 0,
        matched_count: 0,
        coverage: 0.0,
        status: hasMpOmission ? "cascade_masked_orphan" : "pass",
        rationale: hasMpOmission
          ? "Dependent on Sub-Model 02-A (Gravitation). Masked under Bourbaki cascade doctrine."
          : "Verified against empirical tide observations.",
      },
      {
        id: "i_03_terrestrial_free_fall",
        name: "Paradigm I-03 (Terrestrial Free Fall in Vacuum)",
        symbol: "I.3",
        classType: "I",
        parentAxiomId: "ax_03_inertial_frames",
        reference_count: 1,
        predicted_count: 1,
        matched_count: 1,
        coverage: 1.0,
        status: "pass",
        rationale: "Galilean inclined plane and tower drop experiments grounded.",
      },
    ];

    return list;
  }, [activeReport, decompositionEntries]);

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
          <span className="text-[11px] text-app-muted font-mono">
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
                  ? "bg-blue-600 text-white"
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

      {/* Main Table Grid Container */}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-left border-collapse text-xs">
          {/* Sticky Table Header */}
          <thead className="sticky top-0 bg-app-surface/90 backdrop-blur-xs border-b border-app-border z-10">
            <tr className="text-app-muted text-[11px] font-medium tracking-wide">
              <th className="py-2.5 px-4 font-semibold w-[42%]">Component Class / Axiom</th>
              <th className="py-2.5 px-3 text-right font-mono tabular-nums w-[10%]">Ref</th>
              <th className="py-2.5 px-3 text-right font-mono tabular-nums w-[10%]">Pred</th>
              <th className="py-2.5 px-3 text-right font-mono tabular-nums w-[10%]">Match</th>
              <th className="py-2.5 px-3 text-right font-mono tabular-nums w-[12%]">Coverage</th>
              <th className="py-2.5 px-4 text-center font-semibold w-[16%]">Status</th>
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
                          className={`px-1.5 py-0.5 rounded font-mono text-[10px] font-bold border ${meta.bg} ${meta.color} ${meta.border}`}
                        >
                          {meta.symbol}
                        </span>
                        <span className="font-semibold text-app-heading">{meta.label}</span>
                        <span className="text-[11px] text-app-muted hidden sm:inline truncate max-w-xs">
                          — {meta.description}
                        </span>
                      </div>
                    </td>

                    <td className="py-2.5 px-3 text-right font-mono tabular-nums text-app-muted">
                      {summary.reference_count}
                    </td>
                    <td className="py-2.5 px-3 text-right font-mono tabular-nums text-app-muted">
                      {summary.predicted_count}
                    </td>
                    <td className="py-2.5 px-3 text-right font-mono tabular-nums font-semibold text-app-text">
                      {summary.matched_count}
                    </td>

                    <td className="py-2.5 px-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-12 h-1.5 bg-app-subtle rounded-full overflow-hidden shrink-0 hidden md:block">
                          <div
                            className={`h-full rounded-full ${
                              coveragePct >= 90
                                ? "bg-emerald-500"
                                : coveragePct >= 70
                                ? "bg-blue-500"
                                : "bg-amber-500"
                            }`}
                            style={{ width: `${Math.min(100, coveragePct)}%` }}
                          />
                        </div>
                        <span className="font-mono tabular-nums text-[11px] font-semibold">
                          {coveragePct.toFixed(1)}%
                        </span>
                      </div>
                    </td>

                    <td className="py-2.5 px-4 text-center">
                      {coveragePct >= 85 ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/30">
                          <CheckCircle2 className="w-3 h-3" />
                          [PASS]
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/10 text-blue-500 border border-blue-500/30">
                          Active
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
                          onClick={() => setSelectedElement(el)}
                          className={`cursor-pointer transition-colors border-l-2 ${
                            isSelected
                              ? "bg-blue-600/10 border-blue-600 text-app-heading"
                              : isMasked
                              ? "bg-app-bg text-app-muted/60 hover:bg-app-subtle border-transparent"
                              : isOmission
                              ? "bg-rose-500/5 hover:bg-rose-500/10 border-rose-500 text-app-heading"
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
                                  isMasked ? "text-app-muted" : "text-app-text"
                                }`}
                              >
                                {el.symbol}
                              </span>
                              <span
                                className={`font-medium ${
                                  isMasked ? "line-through opacity-70" : ""
                                }`}
                              >
                                {el.name}
                              </span>
                            </div>
                          </td>

                          <td className="py-2 px-3 text-right font-mono tabular-nums text-app-muted">
                            {el.reference_count}
                          </td>
                          <td className="py-2 px-3 text-right font-mono tabular-nums text-app-muted">
                            {el.predicted_count}
                          </td>
                          <td className="py-2 px-3 text-right font-mono tabular-nums text-app-muted font-medium">
                            {el.matched_count}
                          </td>

                          <td className="py-2 px-3 text-right font-mono tabular-nums text-[11px]">
                            {(el.coverage * 100).toFixed(0)}%
                          </td>

                          <td className="py-2 px-4 text-center">
                            {isMasked ? (
                              <span
                                title="Parent axiom failed in Mp. Dependent model masked under Bourbaki cascade doctrine to avoid duplicate penalization."
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-zinc-500/10 dark:bg-zinc-500/20 text-zinc-400 border border-zinc-500/30"
                              >
                                [CASCADE_MASKED_ORPHAN]
                              </span>
                            ) : isOmission ? (
                              <span
                                title="Root axiom missing in extraction! Causes downstream cascade masking."
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/10 text-rose-500 border border-rose-500/30"
                              >
                                <XCircle className="w-3 h-3" />
                                [ROOT_CAUSE_OMISSION]
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/30">
                                <CheckCircle2 className="w-3 h-3" />
                                [PASS]
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

      {/* Selected Element Insight Card at Bottom */}
      {selectedElement && (
        <div className="p-3 border-t border-app-border bg-app-surface/90 shrink-0 text-xs flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-app-heading">{selectedElement.name}</span>
              <span className="font-mono text-[10px] text-app-muted">({selectedElement.id})</span>
              {selectedElement.status === "cascade_masked_orphan" && (
                <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-zinc-500/20 text-zinc-400">
                  Conditional Cascade Mask Active
                </span>
              )}
            </div>
            <p className="text-[11px] text-app-muted leading-relaxed">
              {selectedElement.rationale}
            </p>
          </div>

          <button
            onClick={() => setSelectedElement(null)}
            className="text-[11px] text-app-muted hover:text-app-text px-2 py-1 rounded hover:bg-app-subtle shrink-0"
          >
            Close
          </button>
        </div>
      )}
    </div>
  );
};
