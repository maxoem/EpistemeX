import React, { useMemo } from "react";
import {
  AlertOctagon,
  CheckCircle2,
  ExternalLink,
  GitBranch,
  Layers,
  Network,
  Radio,
  RotateCw,
  Workflow,
  XCircle,
} from "lucide-react";
import { useEvaluationStore } from "../../../../store/evaluationStore";
import type { PosetEvaluationDetail } from "../../../../api/types";

export interface CycleViolation {
  id: string;
  path: string[];
  offendingEdge: {
    source: string;
    target: string;
    predicate: string;
  };
  description: string;
}

export const PosetDagViewer: React.FC = () => {
  const {
    activeReport,
    setActiveSubTab,
    setCycleHighlightNodeIds,
  } = useEvaluationStore();

  const posetDetail: PosetEvaluationDetail = useMemo(() => {
    if (activeReport?.poset_detail) {
      return activeReport.poset_detail;
    }
    // Synthetic fallback representing strict Bourbaki poset metrics
    return {
      is_dag: false,
      root_element: "str:T_CPM_Base",
      root_conformity: false,
      transitive_reduction_f1: 0.812,
      reachability_f1: 0.84,
      predicted_edge_count: 18,
      reference_edge_count: 22,
    };
  }, [activeReport]);

  // Detect cycle violations from activeReport violations or synthesis
  const detectedCycles: CycleViolation[] = useMemo(() => {
    const violations = activeReport?.violations || [];
    const cycleFromViolations = violations.filter(
      (v) =>
        v.type === "cycle" ||
        v.type === "cyclic" ||
        v.type === "poset_cycle" ||
        (typeof v.message === "string" && v.message.toLowerCase().includes("cycle"))
    );

    if (cycleFromViolations.length > 0) {
      return cycleFromViolations.map((v, i) => ({
        id: `cycle_${i + 1}`,
        path: v.cycle_nodes || [v.node_id || "Hyp_04", "Lem_12", "Ax_01", v.node_id || "Hyp_04"],
        offendingEdge: {
          source: v.offending_source || "Lem_12",
          target: v.offending_target || "Ax_01",
          predicate: v.predicate || "PROVES",
        },
        description:
          v.message ||
          "Inferential circular fallacy: derived lemma references foundational axiom in inverted dependency.",
      }));
    }

    // If posetDetail.is_dag is false, provide canonical cycle for inspection
    if (!posetDetail.is_dag) {
      return [
        {
          id: "cycle_01",
          path: ["Hyp_04", "Lem_12", "Ax_01", "Hyp_04"],
          offendingEdge: {
            source: "Lem_12",
            target: "Ax_01",
            predicate: "PROVES",
          },
          description:
            "Circular specialization back-edge: Lemma-12 forms cyclical entailment loop back to Axiom-01.",
        },
      ];
    }

    return [];
  }, [activeReport, posetDetail]);

  const handleIsolateCycle = (cycle: CycleViolation) => {
    // 1. Set cycle node IDs in Zustand store
    const uniqueNodeIds = Array.from(new Set(cycle.path));
    setCycleHighlightNodeIds(uniqueNodeIds);

    // 2. Switch sub-tab to Sub-View 3.1: Topological Canvas
    setActiveSubTab("canvas");
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-app-bg text-app-text select-none font-sans">
      {/* 40px Header Toolbar */}
      <div className="h-10 px-4 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <Workflow className="w-4 h-4 text-purple-500" />
          <h3 className="font-semibold text-app-heading">
            Specialization Poset Hierarchy
          </h3>
        </div>

        {/* Global Poset Status Badge */}
        {posetDetail.is_dag ? (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            STRICT DAG VERIFIED
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold bg-rose-500/10 text-rose-500 border border-rose-500/30 animate-pulse">
            <AlertOctagon className="w-3.5 h-3.5" />
            CYCLIC VIOLATION DETECTED
          </span>
        )}
      </div>

      {/* Main Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Poset Invariant KPI Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {/* Root Element Conformity */}
          <div className="p-3 rounded-lg border border-app-border bg-app-surface/60 flex flex-col justify-between">
            <span className="text-[10px] uppercase font-semibold text-app-muted">
              Root B(TN) = {"{T₀}"}
            </span>
            <div className="mt-2 flex items-center justify-between">
              <span
                className={`text-xs font-mono font-bold ${
                  posetDetail.root_conformity ? "text-emerald-500" : "text-rose-500"
                }`}
              >
                {posetDetail.root_conformity ? "CONFORMANT" : "VIOLATION"}
              </span>
              <span className="text-[10px] text-app-muted font-mono truncate max-w-[90px]">
                {posetDetail.root_element || "T_0"}
              </span>
            </div>
          </div>

          {/* Transitive Reduction F1 */}
          <div className="p-3 rounded-lg border border-app-border bg-app-surface/60 flex flex-col justify-between">
            <span className="text-[10px] uppercase font-semibold text-app-muted">
              Transitive Red. F₁
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-base font-bold font-mono tabular-nums text-app-heading">
                {posetDetail.transitive_reduction_f1.toFixed(3)}
              </span>
              <span className="text-[10px] text-app-muted font-mono">Hasse Diagram</span>
            </div>
          </div>

          {/* Transitive Reachability F1 */}
          <div className="p-3 rounded-lg border border-app-border bg-app-surface/60 flex flex-col justify-between">
            <span className="text-[10px] uppercase font-semibold text-app-muted">
              Reachability F₁
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-base font-bold font-mono tabular-nums text-app-heading">
                {posetDetail.reachability_f1.toFixed(3)}
              </span>
              <span className="text-[10px] text-app-muted font-mono">Closure Match</span>
            </div>
          </div>

          {/* Edge Count Alignment */}
          <div className="p-3 rounded-lg border border-app-border bg-app-surface/60 flex flex-col justify-between">
            <span className="text-[10px] uppercase font-semibold text-app-muted">
              Poset Edges
            </span>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-base font-bold font-mono tabular-nums text-app-heading">
                {posetDetail.predicted_edge_count}
                <span className="text-xs text-app-muted font-normal">
                  {" "}/ {posetDetail.reference_edge_count}
                </span>
              </span>
              <span className="text-[10px] text-emerald-500 font-mono">
                {Math.round(
                  (posetDetail.predicted_edge_count /
                    Math.max(1, posetDetail.reference_edge_count)) *
                    100
                )}
                %
              </span>
            </div>
          </div>
        </div>

        {/* Cyclical Edge Violations Section */}
        {detectedCycles.length > 0 ? (
          <div className="p-3.5 rounded-lg border border-rose-500/30 bg-rose-500/5 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <RotateCw className="w-4 h-4 text-rose-500 animate-spin" />
                <span className="text-xs font-bold text-rose-500 uppercase tracking-wide">
                  Circular Dependency Violations ({detectedCycles.length})
                </span>
              </div>
              <span className="text-[10px] font-mono text-rose-400">
                Acyclicity Axiom Failed
              </span>
            </div>

            <p className="text-xs text-app-muted leading-relaxed">
              The specialization hierarchy violates DAG acyclicity. A circular back-edge causes
              infinite inferential regress between base axioms and derived lemmas.
            </p>

            <div className="space-y-2">
              {detectedCycles.map((cycle) => (
                <div
                  key={cycle.id}
                  className="p-3 rounded border border-rose-500/20 bg-app-bg/80 space-y-2.5"
                >
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    {/* Cycle Path Chain */}
                    <div className="flex items-center gap-1.5 font-mono text-xs text-app-heading font-medium">
                      {cycle.path.map((node, idx) => (
                        <React.Fragment key={idx}>
                          <span
                            className={`px-1.5 py-0.5 rounded border text-[11px] ${
                              idx === 0 || idx === cycle.path.length - 1
                                ? "bg-rose-500/20 text-rose-400 border-rose-500/40 font-bold"
                                : "bg-app-surface text-app-text border-app-border"
                            }`}
                          >
                            {node}
                          </span>
                          {idx < cycle.path.length - 1 && (
                            <span className="text-rose-500 font-bold">→</span>
                          )}
                        </React.Fragment>
                      ))}
                    </div>

                    {/* Isolate Cycle Action Button */}
                    <button
                      onClick={() => handleIsolateCycle(cycle)}
                      className="px-2.5 py-1 rounded text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white transition-colors shadow-2xs flex items-center gap-1.5"
                    >
                      <Network className="w-3.5 h-3.5" />
                      <span>Isolate Cycle on Canvas</span>
                    </button>
                  </div>

                  <div className="text-[11px] text-app-muted flex items-center justify-between border-t border-app-border/40 pt-2">
                    <span>
                      Offending Edge:{" "}
                      <strong className="text-rose-400 font-mono">
                        {cycle.offendingEdge.source} ─[{cycle.offendingEdge.predicate}]→{" "}
                        {cycle.offendingEdge.target}
                      </strong>
                    </span>
                    <span className="text-[10px] text-app-muted italic">
                      Drives red pulse hazard on Sub-View 3.1
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-500/5 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
              <div>
                <h4 className="text-xs font-semibold text-emerald-500">
                  Strict DAG Acyclicity Preserved
                </h4>
                <p className="text-[11px] text-app-muted">
                  No circular dependencies or back-edges detected in the specialization poset.
                </p>
              </div>
            </div>
            <button
              onClick={() =>
                handleIsolateCycle({
                  id: "simulated_cycle",
                  path: ["T_Base", "T_Grav", "T_Kepler", "T_Base"],
                  offendingEdge: { source: "T_Kepler", target: "T_Base", predicate: "SPECIALIZES" },
                  description: "Simulated demonstration cycle",
                })
              }
              className="text-[10px] text-app-muted hover:text-app-text px-2 py-1 rounded border border-app-border hover:bg-app-subtle transition-colors"
            >
              Simulate Cycle
            </button>
          </div>
        )}

        {/* Poset Specialization DAG Visual Architecture */}
        <div className="p-3.5 rounded-lg border border-app-border bg-app-surface/40 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-app-heading">
              Poset Specialization Hierarchy Tree
            </span>
            <span className="text-[10px] text-app-muted font-mono">
              Level 0 (Foundation) → Level 2 (Application)
            </span>
          </div>

          {/* SVG Miniature Tree Diagram */}
          <div className="w-full h-32 rounded border border-app-border bg-app-bg flex items-center justify-center p-2 relative overflow-hidden">
            <svg className="w-full h-full" viewBox="0 0 400 100">
              <defs>
                <marker
                  id="dag-arrow"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="4"
                  markerHeight="4"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6" />
                </marker>
                <marker
                  id="cycle-arrow"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="4"
                  markerHeight="4"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                </marker>
              </defs>

              {/* Normal Specialization Edges */}
              <line
                x1="80"
                y1="50"
                x2="170"
                y2="30"
                stroke="#3b82f6"
                strokeWidth="1.5"
                markerEnd="url(#dag-arrow)"
              />
              <line
                x1="80"
                y1="50"
                x2="170"
                y2="70"
                stroke="#3b82f6"
                strokeWidth="1.5"
                markerEnd="url(#dag-arrow)"
              />
              <line
                x1="230"
                y1="30"
                x2="320"
                y2="50"
                stroke="#3b82f6"
                strokeWidth="1.5"
                markerEnd="url(#dag-arrow)"
              />

              {/* Circular Back Edge if cyclic */}
              {!posetDetail.is_dag && (
                <path
                  d="M 320 40 C 260 0, 140 0, 85 42"
                  fill="none"
                  stroke="#ef4444"
                  strokeWidth="2"
                  strokeDasharray="4,3"
                  markerEnd="url(#cycle-arrow)"
                />
              )}

              {/* Nodes */}
              {/* Root T0 */}
              <g transform="translate(50, 35)">
                <rect
                  width="60"
                  height="30"
                  rx="4"
                  fill="#3b82f6"
                  fillOpacity="0.2"
                  stroke="#3b82f6"
                  strokeWidth="1.5"
                />
                <text
                  x="30"
                  y="18"
                  textAnchor="middle"
                  fontSize="10"
                  fontWeight="bold"
                  fill="#93c5fd"
                  fontFamily="monospace"
                >
                  T₀ (Core)
                </text>
              </g>

              {/* T1 */}
              <g transform="translate(170, 15)">
                <rect
                  width="60"
                  height="30"
                  rx="4"
                  fill="#10b981"
                  fillOpacity="0.2"
                  stroke="#10b981"
                  strokeWidth="1.5"
                />
                <text
                  x="30"
                  y="18"
                  textAnchor="middle"
                  fontSize="10"
                  fontWeight="bold"
                  fill="#6ee7b7"
                  fontFamily="monospace"
                >
                  T₁ (Grav)
                </text>
              </g>

              {/* T2 */}
              <g transform="translate(170, 55)">
                <rect
                  width="60"
                  height="30"
                  rx="4"
                  fill="#10b981"
                  fillOpacity="0.2"
                  stroke="#10b981"
                  strokeWidth="1.5"
                />
                <text
                  x="30"
                  y="18"
                  textAnchor="middle"
                  fontSize="10"
                  fontWeight="bold"
                  fill="#6ee7b7"
                  fontFamily="monospace"
                >
                  T₂ (Harm)
                </text>
              </g>

              {/* T3 */}
              <g transform="translate(320, 35)">
                <rect
                  width="60"
                  height="30"
                  rx="4"
                  fill="#f59e0b"
                  fillOpacity="0.2"
                  stroke={!posetDetail.is_dag ? "#ef4444" : "#f59e0b"}
                  strokeWidth="1.5"
                />
                <text
                  x="30"
                  y="18"
                  textAnchor="middle"
                  fontSize="10"
                  fontWeight="bold"
                  fill={!posetDetail.is_dag ? "#fca5a5" : "#fcd34d"}
                  fontFamily="monospace"
                >
                  T₃ (Orb)
                </text>
              </g>
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
};
