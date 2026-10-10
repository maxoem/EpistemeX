import React from "react";
import {AlertTriangle, Cpu, Database, ShieldCheck, Sparkles,} from "lucide-react";
import {EPISTEMIC_TAXONOMY, getEpistemicLayerForPhase} from "./epistemicTheme";

export interface StageContractDef {
  inputInvariants: string[];
  hyperparameters: Array<{ name: string; value: string; hint?: string }>;
  outputSignature: {
    nodes: string[];
    edges: string[];
    format: string;
  };
}

export const STAGE_CONTRACTS: Record<string, StageContractDef> = {
  phase1: {
    inputInvariants: [
      "Raw Scientific Corpus (PDF, EPUB, TXT, LaTeX)",
      "Corpus Bibliography & Metadata (BibTeX / DOIs)",
    ],
    hyperparameters: [
      { name: "chunk_size", value: "1024 tokens", hint: "Target semantic segmentation bound" },
      { name: "chunk_overlap", value: "128 tokens", hint: "Boundary continuity buffer" },
      { name: "splitter", value: "recursive_academic", hint: "Structural section boundary awareness" },
    ],
    outputSignature: {
      nodes: ["Document (L1)", "Chunk (L1)"],
      edges: ["CONTAINS_CHUNK", "SEQUENTIAL_NEXT"],
      format: "L1Chunk / L1Document with token span coordinate offsets",
    },
  },
  phase2: {
    inputInvariants: [
      "Requires: L1 Foundation & Ingestion [P1] (Tokenized semantic chunks)",
      "Epistemic Schema: schema.node_types & schema.relation_types",
    ],
    hyperparameters: [
      { name: "decoding_strategy", value: "nl_to_format", hint: "Constrained JSON grammar parsing" },
      { name: "max_gleanings", value: "k=2 passes", hint: "Recursive entity recall extraction" },
      { name: "confidence_cut", value: "0.0 (unfiltered)", hint: "Expose entire initial extraction envelope" },
    ],
    outputSignature: {
      nodes: ["Concept", "Person", "Work", "Theory", "Institution"],
      edges: ["RELATED_TO", "INSTANCE_OF", "PART_OF", "SUPPORTS", "REFUTES"],
      format: "L2Entity & L2Triple with evidence span bindings",
    },
  },
  phase3: {
    inputInvariants: [
      "Requires: L1 Text Chunks [P1]",
      "Requires: L2 Local Entities & Mentions [P2]",
    ],
    hyperparameters: [
      { name: "subgraph_depth", value: "k=2 hops", hint: "Contextual envelope radius" },
      { name: "dense_similarity_threshold", value: "0.80", hint: "Cosine cutoff for candidate retrieval" },
      { name: "reranker_threshold", value: "0.60", hint: "Cross-encoder scoring cutoff" },
      { name: "max_candidates", value: "200 pairs", hint: "Candidate evaluation ceiling" },
    ],
    outputSignature: {
      nodes: ["Verified Canonical Entities (L2)"],
      edges: ["GLOBAL_RELATION", "CROSS_DOCUMENT_RELATION"],
      format: "L2GlobalTriple with cross-document bibliographic anchors",
    },
  },
  phase3b: {
    inputInvariants: [
      "Requires: L2 Global Relations [P3]",
      "Requires: L2 Local Entities & Centroids [P2]",
    ],
    hyperparameters: [
      { name: "transitivity_hop_limit", value: "k=2 hops", hint: "Maximum latent traversal depth" },
      { name: "dense_similarity_threshold", value: "0.85", hint: "Embedding cosine cutoff" },
      { name: "relation_overlap_threshold", value: "0.80", hint: "Jaccard neighborhood similarity" },
    ],
    outputSignature: {
      nodes: ["Consolidated Entity Clusters", "Latent Synsets"],
      edges: ["SAME_AS", "TRANSITIVE_BRIDGE"],
      format: "L2LatentTriple with transitive confidence metric",
    },
  },
  phase4_maturation: {
    inputInvariants: [
      "Requires: L2 Consolidated Graph [P3/P3b]",
    ],
    hyperparameters: [
      { name: "maturation_top_k", value: "5 envelopes", hint: "Textual contexts closest to geometric centroid" },
      { name: "batch_size", value: "10 entities", hint: "Concurrent synthesis batch envelope" },
      { name: "decoding_strategy", value: "direct_constrained", hint: "Strict academic summary structure" },
    ],
    outputSignature: {
      nodes: ["MatureEntity (L2) with canonical academic descriptions"],
      edges: ["CANONICAL_BINDING"],
      format: "MatureEntity profile with centroid distance metrics",
    },
  },
  phase4: {
    inputInvariants: [
      "Requires: L1 Document Segments [P1]",
      "Requires: L2 Named Entity Mentions [P2]",
    ],
    hyperparameters: [
      { name: "adu_confidence_threshold", value: "0.70", hint: "Minimum proposition confidence" },
      { name: "relation_threshold", value: "0.65", hint: "Dialectical edge inference cutoff" },
      { name: "context_window", value: "3 chunks", hint: "Multi-premise dialectical window" },
    ],
    outputSignature: {
      nodes: ["TheoryAtom (ObservationUnit, EmpiricalStatement, TheoreticalHypothesis)"],
      edges: ["SUPPORTS_ARG", "ATTACKS", "UNDERCUTS", "SPECIALIZES"],
      format: "TheoryAtom & TheoryRelation with Dung AF compatibility",
    },
  },
  phase5: {
    inputInvariants: [
      "Requires: L2 Knowledge Graph [P3b/P4_maturation]",
      "Requires: L3 Argument Units & Relations [P4]",
    ],
    hyperparameters: [
      { name: "fusion_similarity_threshold", value: "0.75", hint: "Inter-tradition alignment cut" },
      { name: "polarity_consistency", value: "strict (Dung)", hint: "Cycle and defeat contradiction check" },
    ],
    outputSignature: {
      nodes: ["FusionCluster (L3)", "Inter-Tradition Web"],
      edges: ["WEB_RELATION", "INTER_DOC_RELATION"],
      format: "Consolidated argumentative web with stable extensions",
    },
  },
  phase6: {
    inputInvariants: [
      "Requires: L3 Argument Webs & Fusion Clusters [P5]",
    ],
    hyperparameters: [
      { name: "partition_algorithm", value: "Schurz-M_pp", hint: "Empirical M_pp vs theoretical M core" },
      { name: "k_core_min", value: "k >= 3", hint: "Dense structural theory component cut" },
    ],
    outputSignature: {
      nodes: ["TheoryNetCore (L4)", "Metatheory Bridges"],
      edges: ["THEORETICAL_BRIDGES", "PARTITION_COUPLING"],
      format: "TheoryNet metatheoretical graph with Lakatosian research cores",
    },
  },
};

export interface StageExecutionContractCardProps {
  stageKey: string;
  stageName: string;
  stageOrdinal: number;
  status?: string;
  className?: string;
}

export const StageExecutionContractCard: React.FC<StageExecutionContractCardProps> = ({
  stageKey,
  stageName,
  stageOrdinal,
  status = "planned",
  className = "",
}) => {
  const layerKey = getEpistemicLayerForPhase(stageKey, stageOrdinal);
  const epistemic = EPISTEMIC_TAXONOMY[layerKey];
  const contract = STAGE_CONTRACTS[stageKey] || {
    inputInvariants: [`Requires upstream computation from Stage P${Math.max(1, stageOrdinal - 1)}`],
    hyperparameters: [{ name: "execution_mode", value: "standard", hint: "Default parameter baseline" }],
    outputSignature: {
      nodes: [`Projected ${stageName} vertices`],
      edges: ["Projected relational edges"],
      format: "Contracted domain artifacts",
    },
  };

  const isAborted = status === "aborted";
  const isFailed = status === "failed";

  return (
    <div
      className={`rounded-[4px] border border-app-border bg-app-bg overflow-hidden text-xs ${className}`}
    >
      {/* Header Banner */}
      <div className="px-4 py-3 bg-app-surface border-b border-app-border flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <ShieldCheck className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-app-heading font-display text-xs">
                Epistemic Transformation Contract
              </h4>
              <span className="font-mono text-[10px] px-1.5 py-0.2 rounded bg-app-subtle text-app-muted">
                P{stageOrdinal} Spec
              </span>
            </div>
            <p className="text-[10px] text-app-muted font-sans">
              Algorithmic directives, input invariants, and expected ontological graph signature
            </p>
          </div>
        </div>

        <div>
          {isAborted ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/30">
              <AlertTriangle className="w-3 h-3" />
              Cancelled (Upstream Abort)
            </span>
          ) : isFailed ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-500/10 text-rose-700 dark:text-rose-400 border border-rose-500/30">
              Execution Halted
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-500/20">
              Contract Verified // Ready
            </span>
          )}
        </div>
      </div>

      {/* Contract 3-Column Diagnostic Matrix */}
      <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-app-border">
        {/* Column 1: Input Invariants */}
        <div className="p-3.5 space-y-2">
          <div className="flex items-center gap-1.5 font-semibold text-app-text text-[11px] font-display">
            <Database className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 shrink-0" />
            <span>Input Invariants</span>
          </div>
          <p className="text-[10px] text-app-muted">
            Mandatory upstream artifact collections & schema bindings:
          </p>
          <ul className="space-y-1.5 pt-1">
            {contract.inputInvariants.map((inv, idx) => (
              <li
                key={idx}
                className="flex items-start gap-1.5 font-mono text-[11px] text-app-heading leading-snug"
              >
                <span className="text-blue-600 dark:text-blue-400 font-bold shrink-0">↳</span>
                <span>{inv}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Column 2: Hyperparameters & Algorithmic Directives */}
        <div className="p-3.5 space-y-2">
          <div className="flex items-center gap-1.5 font-semibold text-app-text text-[11px] font-display">
            <Cpu className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400 shrink-0" />
            <span>Algorithmic Directives</span>
          </div>
          <p className="text-[10px] text-app-muted">
            Calibrated numerical thresholds and traversal bounds:
          </p>
          <div className="space-y-1.5 pt-1">
            {contract.hyperparameters.map((param, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between gap-2 font-mono text-[11px] py-0.5 border-b border-app-border last:border-0"
              >
                <span className="text-app-muted truncate" title={param.hint}>
                  {param.name}:
                </span>
                <span className="font-semibold text-app-heading tabular-nums shrink-0">
                  {param.value}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Column 3: Expected Output Graph Signature */}
        <div className="p-3.5 space-y-2">
          <div className="flex items-center gap-1.5 font-semibold text-app-text text-[11px] font-display">
            <Sparkles className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span>Projected Graph Signature</span>
          </div>
          <p className="text-[10px] text-app-muted">
            Epistemic vertices and relation types materialized upon execution:
          </p>
          <div className="space-y-2 pt-1 font-mono text-[11px]">
            <div>
              <span className="text-[10px] uppercase tracking-wider text-app-muted block mb-0.5">
                Target Nodes:
              </span>
              <div className="flex flex-wrap gap-1">
                {contract.outputSignature.nodes.map((n, idx) => (
                  <span
                    key={idx}
                    className="px-1.5 py-0.5 rounded bg-app-subtle text-app-text text-[10px] border border-app-border"
                  >
                    {n}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <span className="text-[10px] uppercase tracking-wider text-app-muted block mb-0.5">
                Target Edges:
              </span>
              <div className="flex flex-wrap gap-1">
                {contract.outputSignature.edges.map((e, idx) => (
                  <span
                    key={idx}
                    className="px-1.5 py-0.5 rounded bg-blue-50/80 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 text-[10px] border border-blue-200 dark:border-blue-800/60"
                  >
                    {e}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Status Bar */}
      <div className="px-4 py-2 bg-app-surface/90 border-t border-app-border flex items-center justify-between text-[10px] font-mono text-app-muted">
        <span>Format: {contract.outputSignature.format}</span>
        <span>Epistemic Domain: {epistemic.name}</span>
      </div>
    </div>
  );
};
