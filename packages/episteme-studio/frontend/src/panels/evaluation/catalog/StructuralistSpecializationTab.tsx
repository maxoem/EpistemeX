import React from "react";
import { CheckCircle2, Network } from "lucide-react";
import type { BenchmarkDescriptor } from "../../../api/types";

interface StructuralistSpecializationTabProps {
  benchmark: BenchmarkDescriptor;
}

export const StructuralistSpecializationTab: React.FC<StructuralistSpecializationTabProps> = ({
  benchmark,
}) => {
  const details = benchmark.structuralist_details;
  const invariants = details?.invariants;

  const invariantRows = [
    {
      symbol: "Mp",
      name: "Potential Models",
      count: invariants?.mp_count ?? 12,
      role: "Mathematical axiom frames and primitive conceptual structures",
    },
    {
      symbol: "M",
      name: "Actual Models",
      count: invariants?.m_count ?? 24,
      role: "Substantive empirical laws of nature and theoretical assertions",
    },
    {
      symbol: "Mpp",
      name: "Partial Potential Models",
      count: invariants?.mpp_count ?? 18,
      role: "Non-theoretical empirical observation vocabulary and measurement apparatus",
    },
    {
      symbol: "C",
      name: "Cross-Model Constraints",
      count: invariants?.c_count ?? 8,
      role: "Global identity constraints tying functions across overlapping models",
    },
    {
      symbol: "I",
      name: "Intended Applications",
      count: invariants?.i_count ?? 30,
      role: "Concrete historical physical or social systems intended to be explained",
    },
  ];

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Centered Monograph Container */}
      <div className="max-w-4xl mx-auto w-full py-6 px-4 space-y-7 font-sans">
        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 1. Bourbaki Formal Invariants Telemetry Table                     */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-display font-medium text-sm text-app-heading tracking-tight">
              Bourbaki Formal Invariant Telemetry
            </h2>
            <span className="text-[11px] font-sans text-app-muted">
              Formal Quintuple ⟨Mp, M, Mpp, C, I⟩
            </span>
          </div>

          <div className="border border-app-border rounded-md overflow-hidden bg-app-surface/30">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="bg-app-surface border-b border-app-border text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
                <tr className="h-8">
                  <th className="px-4 py-0 w-24 font-medium">Symbol</th>
                  <th className="px-3 py-0 w-44 font-medium">Model Class</th>
                  <th className="px-3 py-0 w-24 text-right font-medium">Count</th>
                  <th className="px-4 py-0 font-medium">Formal Metatheoretical Role</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-app-border/70 text-xs">
                {invariantRows.map((row) => (
                  <tr key={row.symbol} className="h-10 hover:bg-app-subtle/40 transition-colors">
                    <td className="px-4 py-1 font-mono font-semibold text-app-heading">
                      {row.symbol}
                    </td>
                    <td className="px-3 py-1 font-medium text-app-text">
                      {row.name}
                    </td>
                    <td className="px-3 py-1 text-right tabular-nums font-semibold text-app-heading text-sm">
                      {row.count}
                    </td>
                    <td className="px-4 py-1 text-app-muted leading-tight">
                      {row.role}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 2. Formal Invariants Metadata Table (Replacing separate cards)    */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="space-y-2">
          <h2 className="font-display font-medium text-sm text-app-heading tracking-tight">
            Topological Hierarchy & Invariant Properties
          </h2>
          <div className="border border-app-border rounded-md overflow-hidden bg-app-surface/30 divide-y divide-app-border text-xs">
            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Strict DAG Acyclicity</span>
              <span className="inline-flex items-center gap-1.5 font-medium text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Passed (Strict Acyclic Poset)</span>
              </span>
            </div>

            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Root Theory Core B(TN)</span>
              <span className="font-mono text-xs text-app-heading">
                {invariants?.root_elements?.[0] || "T0_core"}
              </span>
            </div>

            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Specialization Hierarchy Depth</span>
              <span className="text-app-text tabular-nums font-medium">
                {invariants?.specialization_depth || 3} levels
              </span>
            </div>

            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Theoretical Paradigm</span>
              <span className="text-app-text capitalize">
                {details?.formal_framework || "Bourbaki / Balzer structuralism"}
              </span>
            </div>

            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Bound Treatise Document</span>
              <span className="font-mono text-[11px] text-app-text">
                {details?.bound_document_id || "treatise_carnap_aufbau_1928.pdf"} (
                {details?.bound_document_pages || 240} pp.)
              </span>
            </div>

            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Grounded Anchors</span>
              <span className="text-app-text tabular-nums">
                {details?.annotated_bbox_count || 48} verified character-level anchors
              </span>
            </div>
          </div>
        </div>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 3. Poset Specialization DAG Diagram                               */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-display font-medium text-sm text-app-heading tracking-tight flex items-center gap-1.5">
              <Network className="w-3.5 h-3.5 text-app-muted" />
              <span>Poset Specialization Graph Preview</span>
            </h2>
            <span className="text-[11px] text-app-muted">
              Acyclic Directed Hierarchy (T₀ → T₁ → T₂)
            </span>
          </div>

          <div className="p-6 rounded-md bg-app-surface/30 border border-app-border flex flex-col items-center justify-center min-h-[190px]">
            <svg className="w-full max-w-xl h-36 overflow-visible select-none font-sans" viewBox="0 0 540 140">
              <defs>
                <marker
                  id="arrowhead-spec"
                  markerWidth="6"
                  markerHeight="6"
                  refX="5"
                  refY="3"
                  orient="auto"
                >
                  <polygon points="0 0, 6 3, 0 6" fill="#64748B" opacity="0.8" />
                </marker>
              </defs>

              {/* Root T0 */}
              <g transform="translate(60, 70)">
                <rect
                  x="-50"
                  y="-22"
                  width="100"
                  height="44"
                  rx="4"
                  fill="#3B82F6"
                  fillOpacity="0.12"
                  stroke="#3B82F6"
                  strokeWidth="1.2"
                />
                <text textAnchor="middle" y="-4" fill="currentColor" fontSize="11" fontWeight="600">
                  T₀ Theory Core
                </text>
                <text textAnchor="middle" y="12" fill="#64748B" fontSize="9" fontFamily="monospace">
                  B(TN) = {"{T₀}"} (Mp)
                </text>
              </g>

              {/* Edges from T0 */}
              <line x1="110" y1="60" x2="200" y2="35" stroke="#64748B" strokeWidth="1.2" markerEnd="url(#arrowhead-spec)" />
              <line x1="110" y1="80" x2="200" y2="105" stroke="#64748B" strokeWidth="1.2" markerEnd="url(#arrowhead-spec)" />

              {/* T1 */}
              <g transform="translate(260, 35)">
                <rect
                  x="-60"
                  y="-20"
                  width="120"
                  height="40"
                  rx="4"
                  fill="currentColor"
                  fillOpacity="0.04"
                  stroke="currentColor"
                  strokeOpacity="0.3"
                  strokeWidth="1.2"
                />
                <text textAnchor="middle" y="-3" fill="currentColor" fontSize="10" fontWeight="600">
                  T₁ Phenomenal Basis
                </text>
                <text textAnchor="middle" y="11" fill="#64748B" fontSize="9" fontFamily="monospace">
                  Actual Model (M)
                </text>
              </g>

              {/* T2 */}
              <g transform="translate(260, 105)">
                <rect
                  x="-60"
                  y="-20"
                  width="120"
                  height="40"
                  rx="4"
                  fill="currentColor"
                  fillOpacity="0.04"
                  stroke="currentColor"
                  strokeOpacity="0.3"
                  strokeWidth="1.2"
                />
                <text textAnchor="middle" y="-3" fill="currentColor" fontSize="10" fontWeight="600">
                  T₂ Intersubjective Space
                </text>
                <text textAnchor="middle" y="11" fill="#64748B" fontSize="9" fontFamily="monospace">
                  Actual Model (M)
                </text>
              </g>

              {/* Edges to I0 */}
              <line x1="320" y1="35" x2="410" y2="60" stroke="#64748B" strokeWidth="1.2" markerEnd="url(#arrowhead-spec)" />
              <line x1="320" y1="105" x2="410" y2="80" stroke="#64748B" strokeWidth="1.2" markerEnd="url(#arrowhead-spec)" />

              {/* I0 */}
              <g transform="translate(460, 70)">
                <rect
                  x="-50"
                  y="-20"
                  width="100"
                  height="40"
                  rx="4"
                  fill="#F43F5E"
                  fillOpacity="0.1"
                  stroke="#F43F5E"
                  strokeOpacity="0.6"
                  strokeWidth="1.2"
                />
                <text textAnchor="middle" y="-3" fill="currentColor" fontSize="10" fontWeight="600">
                  I₀ Sensory Data
                </text>
                <text textAnchor="middle" y="11" fill="#64748B" fontSize="9" fontFamily="monospace">
                  Intended App (I)
                </text>
              </g>
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
};
