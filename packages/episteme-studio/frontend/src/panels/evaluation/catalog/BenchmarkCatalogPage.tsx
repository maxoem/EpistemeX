import React, { useState, useMemo } from "react";
import {
  Award,
  BookOpen,
  CheckCircle2,
  Copy,
  ExternalLink,
  GitBranch,
  Layers,
  Network,
  Plus,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEvaluationStore } from "../../../store/evaluationStore";
import { PreFlightLinterRail } from "./PreFlightLinterRail";
import { PromoteToGoldModal } from "./PromoteToGoldModal";
import { RegisterBenchmarkModal } from "./RegisterBenchmarkModal";
import type { BenchmarkDescriptor } from "../../../api/types";

interface BenchmarkCatalogPageProps {
  onSelectRunToEvaluate?: (benchmarkId: string) => void;
}

export const BenchmarkCatalogPage: React.FC<BenchmarkCatalogPageProps> = ({
  onSelectRunToEvaluate,
}) => {
  const {
    benchmarks,
    selectedBenchmarkId,
    setSelectedBenchmarkId,
    setActiveMode,
  } = useEvaluationStore();

  const [isPromoteModalOpen, setIsPromoteModalOpen] = useState(false);
  const [isRegisterModalOpen, setIsRegisterModalOpen] = useState(false);
  const [clonedNotice, setClonedNotice] = useState<string | null>(null);

  // Active benchmark
  const activeBenchmark: BenchmarkDescriptor | undefined = useMemo(() => {
    if (!benchmarks.length) return undefined;
    if (!selectedBenchmarkId) return benchmarks[0];
    return benchmarks.find((b) => b.id === selectedBenchmarkId) || benchmarks[0];
  }, [benchmarks, selectedBenchmarkId]);

  const handleClone = () => {
    if (!activeBenchmark) return;
    setClonedNotice(`Cloned ${activeBenchmark.name} as draft revision`);
    setTimeout(() => setClonedNotice(null), 3000);
  };

  return (
    <div className="flex-1 flex h-full w-full overflow-hidden bg-app-bg text-app-text font-sans">
      {/* Center Fluid: Specification Vitrine */}
      <div className="flex-1 flex flex-col h-full overflow-y-auto border-r border-app-border">
        {activeBenchmark ? (
          <div className="flex-1 flex flex-col p-6 space-y-6 max-w-5xl">
            {/* Header Strip */}
            <div className="flex items-start justify-between gap-4 pb-4 border-b border-app-border">
              <div className="space-y-1">
                <div className="flex items-center gap-2.5">
                  <h1 className="text-lg font-bold text-app-heading tracking-tight">
                    {activeBenchmark.name}
                  </h1>
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-amber-500/10 text-amber-500 border border-amber-500/30">
                    v1.0-gold
                  </span>
                  {activeBenchmark.available ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/30">
                      <CheckCircle2 className="w-3 h-3" />
                      Verified
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-500/10 text-zinc-400 border border-zinc-500/30">
                      Draft
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2 text-xs text-app-muted">
                  <span className="font-mono text-[11px] text-app-muted">
                    id: {activeBenchmark.id}
                  </span>
                  <span>·</span>
                  <span className="capitalize">Task: {activeBenchmark.task_type}</span>
                  <span>·</span>
                  <span>Bourbaki Structuralist TheoryNet</span>
                </div>

                <p className="text-xs text-app-text/90 leading-relaxed pt-1 max-w-3xl">
                  {activeBenchmark.description ||
                    "Authoritative philosophical and scientific knowledge graph gold standard dataset."}
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={handleClone}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-app-surface text-app-text border border-app-border hover:bg-app-subtle transition-colors cursor-pointer"
                >
                  <Copy className="w-3.5 h-3.5 text-app-muted" />
                  <span>Clone Benchmark</span>
                </button>
                <button
                  onClick={() => setIsPromoteModalOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-amber-600 hover:bg-amber-700 text-white transition-colors cursor-pointer"
                >
                  <Award className="w-3.5 h-3.5" />
                  <span>+ Promote from Run</span>
                </button>
              </div>
            </div>

            {clonedNotice && (
              <div className="p-2.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs flex items-center gap-2 animate-in fade-in">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{clonedNotice}</span>
              </div>
            )}

            {/* Structural Invariants Summary */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-app-muted">
                  Bourbaki structural invariants
                </h3>
                <span className="text-[11px] font-mono text-app-muted">
                  Formal Quintuple ⟨Mp, M, Mpp, C, I⟩
                </span>
              </div>

              <div className="border border-app-border rounded-md overflow-hidden bg-app-surface/40 divide-x divide-app-border grid grid-cols-5 text-xs">
                {/* Mp: Potential Models */}
                <div className="p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-semibold text-blue-500">Mp</span>
                    <span className="text-[10px] text-app-muted">Potential Models</span>
                  </div>
                  <div className="text-base font-bold text-app-heading font-mono tabular-nums">
                    12
                  </div>
                  <p className="text-[10px] text-app-muted leading-tight">
                    Mathematical axiom frames & primitive concepts
                  </p>
                </div>

                {/* M: Actual Models */}
                <div className="p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-semibold text-emerald-500">M</span>
                    <span className="text-[10px] text-app-muted">Actual Models</span>
                  </div>
                  <div className="text-base font-bold text-app-heading font-mono tabular-nums">
                    24
                  </div>
                  <p className="text-[10px] text-app-muted leading-tight">
                    Laws of nature & substantive theoretical claims
                  </p>
                </div>

                {/* Mpp: Partial Potential */}
                <div className="p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-semibold text-purple-500">Mpp</span>
                    <span className="text-[10px] text-app-muted">Partial Pot.</span>
                  </div>
                  <div className="text-base font-bold text-app-heading font-mono tabular-nums">
                    18
                  </div>
                  <p className="text-[10px] text-app-muted leading-tight">
                    Non-theoretical empirical observation vocabulary
                  </p>
                </div>

                {/* C: Constraints */}
                <div className="p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-semibold text-amber-500">C</span>
                    <span className="text-[10px] text-app-muted">Constraints</span>
                  </div>
                  <div className="text-base font-bold text-app-heading font-mono tabular-nums">
                    8
                  </div>
                  <p className="text-[10px] text-app-muted leading-tight">
                    Cross-model identity & coordinate constraints
                  </p>
                </div>

                {/* I: Intended Applications */}
                <div className="p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-semibold text-rose-500">I</span>
                    <span className="text-[10px] text-app-muted">Intended App.</span>
                  </div>
                  <div className="text-base font-bold text-app-heading font-mono tabular-nums">
                    30
                  </div>
                  <p className="text-[10px] text-app-muted leading-tight">
                    Empirical data systems intended to be explained
                  </p>
                </div>
              </div>
            </div>

            {/* Poset Specialization Hierarchy SVG Preview */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Network className="w-4 h-4 text-blue-500" />
                  <h3 className="text-xs font-semibold text-app-heading">
                    Poset specialization graph preview
                  </h3>
                </div>
                <span className="text-[11px] font-mono text-app-muted">
                  Acyclic Directed Poset Hierarchy (T₀ → T₁ → T₂)
                </span>
              </div>

              <div className="p-4 rounded-md bg-app-surface/30 border border-app-border flex flex-col items-center justify-center min-h-[190px]">
                <svg
                  className="w-full max-w-xl h-36 overflow-visible select-none"
                  viewBox="0 0 540 140"
                >
                  <defs>
                    <marker
                      id="arrowhead"
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
                      rx="6"
                      fill="#3B82F6"
                      fillOpacity="0.15"
                      stroke="#3B82F6"
                      strokeWidth="1.5"
                    />
                    <text
                      textAnchor="middle"
                      y="-4"
                      fill="currentColor"
                      fontSize="11"
                      fontWeight="600"
                    >
                      T₀ Aufbau Core
                    </text>
                    <text
                      textAnchor="middle"
                      y="12"
                      fill="#64748B"
                      fontSize="9"
                      fontFamily="monospace"
                    >
                      B(TN) = {"{T₀}"} (Mp)
                    </text>
                  </g>

                  {/* Edges from T0 */}
                  <line
                    x1="110"
                    y1="60"
                    x2="200"
                    y2="35"
                    stroke="#64748B"
                    strokeWidth="1.2"
                    markerEnd="url(#arrowhead)"
                  />
                  <line
                    x1="110"
                    y1="80"
                    x2="200"
                    y2="105"
                    stroke="#64748B"
                    strokeWidth="1.2"
                    markerEnd="url(#arrowhead)"
                  />

                  {/* T1: Sensory Constitution */}
                  <g transform="translate(260, 35)">
                    <rect
                      x="-60"
                      y="-20"
                      width="120"
                      height="40"
                      rx="6"
                      fill="#10B981"
                      fillOpacity="0.12"
                      stroke="#10B981"
                      strokeWidth="1.5"
                    />
                    <text
                      textAnchor="middle"
                      y="-3"
                      fill="currentColor"
                      fontSize="10"
                      fontWeight="600"
                    >
                      T₁ Phenomenal Basis
                    </text>
                    <text
                      textAnchor="middle"
                      y="11"
                      fill="#64748B"
                      fontSize="9"
                      fontFamily="monospace"
                    >
                      Actual Model (M)
                    </text>
                  </g>

                  {/* T2: Intersubjective Space */}
                  <g transform="translate(260, 105)">
                    <rect
                      x="-60"
                      y="-20"
                      width="120"
                      height="40"
                      rx="6"
                      fill="#10B981"
                      fillOpacity="0.12"
                      stroke="#10B981"
                      strokeWidth="1.5"
                    />
                    <text
                      textAnchor="middle"
                      y="-3"
                      fill="currentColor"
                      fontSize="10"
                      fontWeight="600"
                    >
                      T₂ Intersubjective Space
                    </text>
                    <text
                      textAnchor="middle"
                      y="11"
                      fill="#64748B"
                      fontSize="9"
                      fontFamily="monospace"
                    >
                      Actual Model (M)
                    </text>
                  </g>

                  {/* Edges to Empirical Application */}
                  <line
                    x1="320"
                    y1="35"
                    x2="410"
                    y2="60"
                    stroke="#64748B"
                    strokeWidth="1.2"
                    markerEnd="url(#arrowhead)"
                  />
                  <line
                    x1="320"
                    y1="105"
                    x2="410"
                    y2="80"
                    stroke="#64748B"
                    strokeWidth="1.2"
                    markerEnd="url(#arrowhead)"
                  />

                  {/* T3: Empirical Claims */}
                  <g transform="translate(460, 70)">
                    <rect
                      x="-50"
                      y="-20"
                      width="100"
                      height="40"
                      rx="6"
                      fill="#F43F5E"
                      fillOpacity="0.12"
                      stroke="#F43F5E"
                      strokeWidth="1.5"
                    />
                    <text
                      textAnchor="middle"
                      y="-3"
                      fill="currentColor"
                      fontSize="10"
                      fontWeight="600"
                    >
                      I₀ Sensory Data
                    </text>
                    <text
                      textAnchor="middle"
                      y="11"
                      fill="#64748B"
                      fontSize="9"
                      fontFamily="monospace"
                    >
                      Intended App (I)
                    </text>
                  </g>
                </svg>
              </div>
            </div>

            {/* Primary Source Anchor & Provenance */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-app-muted">
                Primary source grounding provenance
              </h3>
              <div className="divide-y divide-app-border/60 border-t border-app-border/60 text-xs">
                <div className="py-2.5 flex items-center justify-between">
                  <span className="text-app-muted">Bound Treatise Document</span>
                  <span className="font-mono text-app-text font-medium">
                    doc_carnap_aufbau_de_1928.pdf (240 pp.)
                  </span>
                </div>
                <div className="py-2.5 flex items-center justify-between">
                  <span className="text-app-muted">Gold Standard Path</span>
                  <span className="font-mono text-app-muted text-[11px] truncate max-w-md">
                    {activeBenchmark.gold_standard_path}
                  </span>
                </div>
                {activeBenchmark.queries_path && (
                  <div className="py-2.5 flex items-center justify-between">
                    <span className="text-app-muted">Competency Queries Path</span>
                    <span className="font-mono text-app-muted text-[11px] truncate max-w-md">
                      {activeBenchmark.queries_path}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-app-muted">
            <BookOpen className="w-10 h-10 text-app-muted/50 mb-3" />
            <h3 className="text-sm font-semibold text-app-heading mb-1">
              No Benchmark Selected
            </h3>
            <p className="text-xs max-w-xs mb-4">
              Select a benchmark from the left catalog rail or register a new reference gold standard.
            </p>
            <button
              onClick={() => setIsRegisterModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Register New Benchmark</span>
            </button>
          </div>
        )}
      </div>

      {/* Right 380px Dock: Pre-Flight Linter Rail */}
      <PreFlightLinterRail
        benchmarkName={activeBenchmark?.name}
        className="shrink-0"
      />

      {/* Modals */}
      <PromoteToGoldModal
        isOpen={isPromoteModalOpen}
        onClose={() => setIsPromoteModalOpen(false)}
      />

      <RegisterBenchmarkModal
        isOpen={isRegisterModalOpen}
        onClose={() => setIsRegisterModalOpen(false)}
      />
    </div>
  );
};
