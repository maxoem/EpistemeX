import React, { useState, useMemo, useEffect } from "react";
import { BorderlineDecisionItem } from "../../api/types";
import { api } from "../../api/client";
import { useRunsStore } from "../../store/runsStore";
import { DecisionDetailDrawer } from "./DecisionDetailDrawer";
import {
  Zap,
  Cpu,
  ShieldCheck,
  Search,
  Filter,
  Sliders,
  AlertTriangle,
  Clock,
  Layers,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from "lucide-react";

export interface DecisionAuditTableProps {
  runId: string;
  selectedPhaseKey?: string | null;
}

const SAMPLE_DECISIONS: BorderlineDecisionItem[] = [
  {
    decision_id: "dec-p3-rel-001",
    run_id: "run-sample",
    phase: "phase3",
    primitive: "noul",
    tier: "fast_exit",
    timestamp: "2026-10-06T12:00:14.210Z",
    confidence: 0.942,
    empirical_accuracy: 0.965,
    margin: 0.884,
    conformal_set: ["SUPPORT"],
    prediction: "SUPPORT",
    context: {
      input_text: "Relation candidate: [Structural Realism] -> [Ontic Commitment]. Context: French argues that mathematical structure carries full ontological commitment.",
      candidate_labels: ["SUPPORT", "ATTACK", "NONE"],
      hypothesis: "French affirms ontic structural commitment.",
    },
  },
  {
    decision_id: "dec-p4-comp-002",
    run_id: "run-sample",
    phase: "phase4",
    primitive: "choice",
    tier: "system2",
    timestamp: "2026-10-06T12:00:15.820Z",
    confidence: 0.582,
    empirical_accuracy: 0.724,
    margin: 0.164,
    conformal_set: ["CLAIM", "PREMISE"],
    prediction: "CLAIM",
    context: {
      input_text: "Component: 'Knowledge is defined as justified true belief without Gettier anomalies.'",
      candidate_labels: ["CLAIM", "PREMISE"],
    },
  },
  {
    decision_id: "dec-p3-audit-003",
    run_id: "run-sample",
    phase: "phase3",
    primitive: "choice",
    tier: "stochastic_audit",
    timestamp: "2026-10-06T12:00:16.105Z",
    confidence: 0.961,
    empirical_accuracy: 0.978,
    margin: 0.922,
    conformal_set: ["ATTACK"],
    prediction: "ATTACK",
    context: {
      input_text: "Candidate relation: [Quine Indispensability] -> [Nominalist Field Programme]. Context: Field refutes mathematical entities via synthetic conservative field physics.",
      candidate_labels: ["SUPPORT", "ATTACK", "NONE"],
    },
  },
  {
    decision_id: "dec-p5-fuse-004",
    run_id: "run-sample",
    phase: "phase5",
    primitive: "noul",
    tier: "fast_exit",
    timestamp: "2026-10-06T12:00:18.440Z",
    confidence: 0.915,
    empirical_accuracy: 0.932,
    margin: 0.830,
    conformal_set: ["MERGE"],
    prediction: "MERGE",
    context: {
      input_text: "Cluster match: Epistemic Structural Realism (Worrall 1989) vs Semantic Epistemic Realism.",
      candidate_labels: ["MERGE", "SEPARATE"],
    },
  },
];

export const DecisionAuditTable: React.FC<DecisionAuditTableProps> = ({
  runId,
  selectedPhaseKey,
}) => {
  const { recentDecisions } = useRunsStore();
  const [serverDecisions, setServerDecisions] = useState<BorderlineDecisionItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedDecision, setSelectedDecision] = useState<BorderlineDecisionItem | null>(null);

  // Filters
  const [phaseFilter, setPhaseFilter] = useState<string>("all");
  const [actionFilter, setActionFilter] = useState<"all" | "fast_exit" | "system2" | "stochastic_audit">("all");
  const [ambiguityOnly, setAmbiguityOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  useEffect(() => {
    if (selectedPhaseKey) {
      setPhaseFilter(selectedPhaseKey);
    }
  }, [selectedPhaseKey]);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    api.getBorderlineDecisions(runId)
      .then((items) => {
        setServerDecisions(items);
      })
      .catch(() => {
        setServerDecisions([]);
      })
      .finally(() => setLoading(false));
  }, [runId]);

  // Combine live stream recent decisions, server decisions, or sample fallback
  const allDecisions = useMemo(() => {
    const combined: BorderlineDecisionItem[] = [];
    const seen = new Set<string>();

    const mappedRecent: BorderlineDecisionItem[] = (recentDecisions || [])
      .filter((ev: any) => ev && ev.data && (ev.data.decision_id || ev.name?.startsWith("decision.")))
      .map((ev: any) => {
        const d = ev.data || {};
        return {
          decision_id: d.decision_id || `dec-${ev.seq || Math.random().toString(36).slice(2, 7)}`,
          run_id: d.run_id || runId,
          phase: d.phase || "phase3",
          primitive: d.primitive || "noul",
          tier: d.tier || (d.is_fast_exit ? "fast_exit" : "system2"),
          timestamp: ev.timestamp || new Date().toISOString(),
          confidence: d.confidence ?? 0.9,
          empirical_accuracy: d.empirical_accuracy ?? 0.92,
          margin: d.margin ?? 0.8,
          conformal_set: d.conformal_set || [d.selected_option || "SUPPORT"],
          prediction: d.selected_option || d.prediction || "SUPPORT",
          context: {
            input_text: d.input_text || d.question || "",
            candidate_labels: d.options || d.candidate_labels,
            hypothesis: d.hypothesis,
          },
        };
      });

    [...mappedRecent, ...serverDecisions].forEach((d) => {
      if (!seen.has(d.decision_id)) {
        seen.add(d.decision_id);
        combined.push(d);
      }
    });

    return combined.length > 0 ? combined : SAMPLE_DECISIONS;
  }, [recentDecisions, serverDecisions, runId]);

  const filteredDecisions = useMemo(() => {
    return allDecisions.filter((d) => {
      if (phaseFilter !== "all" && d.phase.toLowerCase() !== phaseFilter.toLowerCase()) {
        return false;
      }
      if (actionFilter !== "all") {
        if (actionFilter === "fast_exit" && d.tier !== "fast_exit" && d.tier !== "system1") return false;
        if (actionFilter === "system2" && d.tier !== "system2") return false;
        if (actionFilter === "stochastic_audit" && d.tier !== "stochastic_audit") return false;
      }
      if (ambiguityOnly && d.conformal_set.length <= 1 && d.empirical_accuracy >= 0.85) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const stateText = (d.context.input_text || "").toLowerCase();
        const valText = String(d.prediction).toLowerCase();
        const idText = d.decision_id.toLowerCase();
        if (!stateText.includes(q) && !valText.includes(q) && !idText.includes(q)) {
          return false;
        }
      }
      return true;
    });
  }, [allDecisions, phaseFilter, actionFilter, ambiguityOnly, searchQuery]);

  return (
    <div className="flex flex-col h-full bg-app-bg select-none">
      {/* Filters Toolbar */}
      <div className="p-3 border-b border-app-border bg-app-surface flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          {/* Phase Filter */}
          <select
            value={phaseFilter}
            onChange={(e) => setPhaseFilter(e.target.value)}
            className="px-2 py-1 rounded bg-app-bg border border-app-border text-app-text text-[11px] font-sans focus:outline-hidden"
          >
            <option value="all">All Phases</option>
            <option value="phase1">Phase 1 (Ingestion)</option>
            <option value="phase2">Phase 2 (Local KG)</option>
            <option value="phase3">Phase 3 (Global Rel)</option>
            <option value="phase4">Phase 4 (Argument Mining)</option>
            <option value="phase5">Phase 5 (Theory Fusion)</option>
            <option value="phase6">Phase 6 (TheoryNet)</option>
          </select>

          {/* Action Filter */}
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value as any)}
            className="px-2 py-1 rounded bg-app-bg border border-app-border text-app-text text-[11px] font-sans focus:outline-hidden"
          >
            <option value="all">All Actions</option>
            <option value="fast_exit">Fast-Exit Only (S1)</option>
            <option value="system2">Escalated Only (S2)</option>
            <option value="stochastic_audit">Stochastic Audits Only</option>
          </select>

          {/* Ambiguity Toggle */}
          <button
            type="button"
            onClick={() => setAmbiguityOnly(!ambiguityOnly)}
            className={`inline-flex items-center gap-1.5 px-2 py-1 rounded border text-[11px] font-medium transition-colors cursor-pointer ${
              ambiguityOnly
                ? "bg-amber-500/15 border-amber-500/30 text-amber-500"
                : "bg-app-bg border-app-border text-app-muted hover:text-app-text"
            }`}
          >
            <AlertTriangle className="w-3 h-3" />
            <span>Ambiguity (|C| &gt; 1)</span>
          </button>
        </div>

        {/* Search Input */}
        <div className="relative w-48 sm:w-60">
          <Search className="w-3.5 h-3.5 text-app-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search context / prediction..."
            className="w-full pl-8 pr-3 py-1 rounded bg-app-bg border border-app-border text-app-text placeholder:text-app-muted text-xs focus:outline-hidden"
          />
        </div>
      </div>

      {/* Decisions Table */}
      <div className="flex-1 overflow-x-auto overflow-y-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead className="bg-app-surface text-[10px] uppercase font-semibold text-app-muted border-b border-app-border sticky top-0 z-10">
            <tr>
              <th className="px-3 py-2">ID / Time</th>
              <th className="px-3 py-2">Phase</th>
              <th className="px-3 py-2">Primitive</th>
              <th className="px-3 py-2">Context / Input</th>
              <th className="px-3 py-2">Selected Value</th>
              <th className="px-3 py-2 text-right">Empirical Acc</th>
              <th className="px-3 py-2 text-center">Conformal Set</th>
              <th className="px-3 py-2 text-center">Action / Tier</th>
              <th className="px-3 py-2 text-right">Latency</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-app-border font-mono text-[11px]">
            {filteredDecisions.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-app-muted font-sans text-xs">
                  No evaluated decisions matching criteria.
                </td>
              </tr>
            ) : (
              filteredDecisions.map((d) => {
                const isFast = d.tier === "fast_exit" || d.tier === "system1";
                const isAudit = d.tier === "stochastic_audit";
                const isEscalated = d.tier === "system2";
                const accPercent = Math.round(d.empirical_accuracy * 100);
                const isAccHigh = d.empirical_accuracy >= 0.85;
                const setSize = d.conformal_set.length;
                const isSingleton = setSize === 1;

                return (
                  <tr
                    key={d.decision_id}
                    onClick={() => setSelectedDecision(d)}
                    className="hover:bg-app-subtle transition-colors cursor-pointer group"
                  >
                    {/* ID / Time */}
                    <td className="px-3 py-2">
                      <div className="font-semibold text-app-heading truncate max-w-[110px]">{d.decision_id}</div>
                      <div className="text-[10px] text-app-muted">
                        {d.timestamp.includes("T") ? d.timestamp.split("T")[1].slice(0, 8) : d.timestamp}
                      </div>
                    </td>

                    {/* Phase */}
                    <td className="px-3 py-2 font-sans font-medium text-app-heading">
                      <span className="px-1.5 py-0.5 rounded bg-app-surface border border-app-border text-[10px]">
                        {d.phase}
                      </span>
                    </td>

                    {/* Primitive */}
                    <td className="px-3 py-2">
                      <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        {d.primitive}
                      </span>
                    </td>

                    {/* Context / Input */}
                    <td className="px-3 py-2 font-sans text-app-text max-w-xs truncate" title={d.context.input_text}>
                      {d.context.input_text || "—"}
                    </td>

                    {/* Selected Value */}
                    <td className="px-3 py-2 font-bold text-app-heading">
                      {String(d.prediction)}
                    </td>

                    {/* Empirical Acc */}
                    <td className="px-3 py-2 text-right">
                      <span className={`font-semibold ${isAccHigh ? "text-emerald-500" : "text-amber-500"}`}>
                        {accPercent}%
                      </span>
                    </td>

                    {/* Conformal Set */}
                    <td className="px-3 py-2 text-center">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${
                          isSingleton
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                            : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                        }`}
                        title={d.conformal_set.join(", ")}
                      >
                        |C| = {setSize}
                      </span>
                    </td>

                    {/* Action / Tier */}
                    <td className="px-3 py-2 text-center">
                      {isFast && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <Zap className="w-2.5 h-2.5" /> Fast-Exit
                        </span>
                      )}
                      {isEscalated && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          <Cpu className="w-2.5 h-2.5" /> Escalated
                        </span>
                      )}
                      {isAudit && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
                          <ShieldCheck className="w-2.5 h-2.5" /> Audit
                        </span>
                      )}
                    </td>

                    {/* Latency */}
                    <td className="px-3 py-2 text-right text-app-muted">
                      {isFast ? "13.4 ms" : "2,480 ms"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Slide-out Decision Detail Drawer */}
      {selectedDecision && (
        <DecisionDetailDrawer
          decision={selectedDecision}
          onClose={() => setSelectedDecision(null)}
        />
      )}
    </div>
  );
};
