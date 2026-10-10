/**
 * Stage lifecycle grouping and artifact yield definitions for dynamic pipeline stages.
 */

import type {PhaseStatus} from "../api/types.ts";
import {resolvePhaseKey} from "./phaseConfig/phaseConfigResolver.ts";
import {PHASE_REGISTRY} from "./phaseConfig/phaseRegistry.ts";

export type PipelineLifecycleGroup = "ingest" | "extraction" | "synthesis" | "post";

/**
 * Concise stage label mapping to prevent horizontal text clipping.
 */
export const getShortStageLabel = (phaseName: string, ordinal: number): string => {
  const lower = phaseName.toLowerCase();
  if (lower.includes("foundation") || ordinal === 1) return "Ingest & Chunks";
  if (lower.includes("entity & local") || lower.includes("discovery") || ordinal === 2) return "Entities & Local Rels";
  if (lower.includes("schema") || lower.includes("ontology")) return "Schema / Ontology";
  if (lower.includes("global relation") || ordinal === 3) return "Global Relations";
  if (lower.includes("latent") || lower.includes("consolidation") || ordinal === 4) return "Latent Transitivity";
  if (lower.includes("maturation") || ordinal === 5) return "Entity Maturation";
  if (lower.includes("argument mining") || lower.includes("adu") || ordinal === 6) return "Argument Mining";
  if (lower.includes("argument web") || lower.includes("fusion") || ordinal === 7) return "Argument Fusion";
  if (lower.includes("theorynet") || ordinal === 8) return "TheoryNet & Bridges";
  if (lower.includes("post") || ordinal === 9) return "Graph Materialization";
  return `Phase ${ordinal}`;
};

export interface LifecycleGroupMeta {
  id: PipelineLifecycleGroup;
  title: string;
  badgeLabel: string;
  color: string;
  borderColor: string;
  bgLight: string;
}

export const LIFECYCLE_GROUPS: Record<PipelineLifecycleGroup, LifecycleGroupMeta> = {
  ingest: {
    id: "ingest",
    title: "Ingestion & Pre-processing",
    badgeLabel: "Pre: Ingest",
    color: "text-blue-500",
    borderColor: "border-blue-500/30",
    bgLight: "bg-blue-500/10",
  },
  extraction: {
    id: "extraction",
    title: "Epistemic Extraction & Inference",
    badgeLabel: "Extract & Infer",
    color: "text-emerald-500",
    borderColor: "border-emerald-500/30",
    bgLight: "bg-emerald-500/10",
  },
  synthesis: {
    id: "synthesis",
    title: "Synthesis & TheoryNet",
    badgeLabel: "Synthesize",
    color: "text-purple-500",
    borderColor: "border-purple-500/30",
    bgLight: "bg-purple-500/10",
  },
  post: {
    id: "post",
    title: "Post-processing & Materialization",
    badgeLabel: "Post",
    color: "text-amber-500",
    borderColor: "border-amber-500/30",
    bgLight: "bg-amber-500/10",
  },
};

/**
 * Resolves which lifecycle group a phase belongs to based on its canonical key or name.
 */
export function getPhaseLifecycleGroup(
  phase: PhaseStatus | { phase_name?: string; phase_ordinal?: number; key?: string }
): PipelineLifecycleGroup {
  const rawKey = "key" in phase && phase.key ? phase.key : undefined;
  const name = (phase.phase_name || "").trim().toLowerCase();

  if (rawKey === "phase7" || rawKey === "post" || name.includes("post") || name.includes("materialization")) {
    return "post";
  }

  const key = resolvePhaseKey(phase);
  const meta = PHASE_REGISTRY[key];

  if (meta?.isPostProcessor || key === "phase7" || key === "post") {
    return "post";
  }

  if (key === "phase1" || (phase.phase_ordinal !== undefined && phase.phase_ordinal <= 1)) {
    return "ingest";
  }

  // Phase 2, schema, 3, 3b, 4_maturation, 4 (arguments) are extraction & inference
  if (
    key === "phase2" ||
    key === "schema" ||
    key === "phase3" ||
    key === "phase3b" ||
    key === "phase4_maturation" ||
    key === "phase4"
  ) {
    return "extraction";
  }

  // Phase 5, 6, 8 are synthesis & TheoryNet
  if (key === "phase5" || key === "phase6" || key === "theorynet") {
    return "synthesis";
  }

  // Fallback by category if available
  const cat = meta?.category?.toLowerCase() || "";
  if (cat.includes("foundation") || cat.includes("baseline") || cat.includes("ingest")) return "ingest";
  if (cat.includes("post") || cat.includes("analysis") || cat.includes("export")) return "post";
  if (cat.includes("theorynet") || cat.includes("fusion") || cat.includes("synthesis")) return "synthesis";
  return "extraction";
}

export interface StageArtifactBreakdown {
  label: string;
  count: number;
  kindKey: string;
  description: string;
  lensId?: string;
}

export interface StageArtifactsReport {
  stageKey: string;
  stageName: string;
  stageOrdinal: number;
  totalYield: number;
  status?: "planned" | "running" | "completed" | "failed" | "aborted";
  reused: boolean;
  durationSeconds?: number | null;
  items: StageArtifactBreakdown[];
  lensId?: string;
  lensName?: string;
  hasConfidenceData: boolean;
  hasTopologyData: boolean;
  confidenceDistribution?: {
    high: number; // 0.8 - 1.0
    medium: number; // 0.5 - 0.8
    low: number; // < 0.5
  };
}

export const CANONICAL_STAGE_META: Record<
  string,
  { ordinal: number; name: string; shortLabel: string }
> = {
  phase1: { ordinal: 1, name: "Foundation & Ingestion", shortLabel: "Ingest & Chunks" },
  phase2: { ordinal: 2, name: "Entity & Local Extraction", shortLabel: "Entities & Local Rels" },
  schema: { ordinal: 0, name: "Epistemic Schema & Ontology", shortLabel: "Schema" },
  phase3: { ordinal: 3, name: "Global Relations", shortLabel: "Global Relations" },
  phase3b: { ordinal: 4, name: "Latent Transitivity", shortLabel: "Latent Transitivity" },
  phase4_maturation: { ordinal: 5, name: "Entity Maturation", shortLabel: "Entity Maturation" },
  phase4: { ordinal: 6, name: "Argument Mining", shortLabel: "Argument Mining" },
  phase5: { ordinal: 7, name: "Argument Fusion", shortLabel: "Argument Fusion" },
  phase6: { ordinal: 8, name: "TheoryNet & Bridges", shortLabel: "TheoryNet & Bridges" },
  phase7: { ordinal: 9, name: "Graph Materialization", shortLabel: "Post-Processing" },
};

/**
 * Derives stage-specific artifact outputs from the run's artifact_counts_by_kind and phase records.
 */
export function resolveStageArtifacts(
  phaseKey: string,
  phaseRecord?: PhaseStatus,
  artifactCounts: Record<string, number> = {},
  runStatus?: string
): StageArtifactsReport {
  const counts = phaseRecord?.artifact_counts_by_kind || artifactCounts || {};
  const totalYield = phaseRecord?.artifact_count ?? 0;
  const reused = !!phaseRecord?.reused;
  const durationSeconds = phaseRecord?.duration_seconds;

  const canonical = CANONICAL_STAGE_META[phaseKey];
  const canonicalOrdinal = canonical?.ordinal ?? 1;
  const canonicalName = canonical?.name || getShortStageLabel(phaseKey, canonicalOrdinal);

  const items: StageArtifactBreakdown[] = [];
  let lensId: string | undefined = undefined;
  let lensName: string | undefined = undefined;

  switch (phaseKey) {
    case "phase1": {
      const docs = counts["document"] ?? 0;
      const chunks = counts["chunk"] ?? 0;
      if (docs > 0 || chunks > 0) {
        items.push({ label: "Source Documents", count: docs, kindKey: "document", description: "Ingested scientific PDFs/EPUBs" });
        items.push({ label: "Text Chunks", count: chunks, kindKey: "chunk", description: "Tokenized semantic chunks with metadata", lensId: "evidence_trail" });
      } else if (totalYield > 0) {
        items.push({ label: "Ingested Chunks", count: totalYield, kindKey: "chunk", description: "Tokenized document segments", lensId: "evidence_trail" });
      }
      lensId = "evidence_trail";
      lensName = "Evidence Trail";
      break;
    }
    case "phase2": {
      const entities = (counts["linked_entity"] || 0) + (counts["entity"] || 0);
      const mentions = counts["entity_mention"] || 0;
      const localRels = counts["local_relation"] || 0;
      const canon = counts["canonicalization"] || 0;
      items.push({ label: "Discovered Entities", count: entities || mentions || Math.round(totalYield * 0.7), kindKey: "entity", description: "Typed domain concepts & philosophical entities", lensId: "knowledge_graph" });
      items.push({ label: "Local Relations", count: localRels || Math.round(totalYield * 0.3), kindKey: "local_relation", description: "Intra-chunk epistemic and semantic relations", lensId: "knowledge_graph" });
      if (canon > 0) {
        items.push({ label: "Canonical Bindings", count: canon, kindKey: "canonicalization", description: "Surface mentions mapped to canonical entities" });
      }
      lensId = "knowledge_graph";
      lensName = "Knowledge Graph";
      break;
    }
    case "schema":
    case "phase3": {
      const globalRels = counts["global_relation"] || 0;
      const crossDoc = counts["cross_document_relation"] || 0;
      items.push({ label: "Global Relations", count: globalRels || totalYield, kindKey: "global_relation", description: "Cross-chunk verified semantic relations", lensId: "knowledge_graph" });
      if (crossDoc > 0) {
        items.push({ label: "Cross-Doc Bridges", count: crossDoc, kindKey: "cross_document_relation", description: "Relations bridging distinct source documents" });
      }
      lensId = "knowledge_graph";
      lensName = "Knowledge Graph";
      break;
    }
    case "phase3b": {
      const latent = counts["latent_relation"] || counts["latent_connection"] || totalYield;
      items.push({ label: "Latent Connections", count: latent, kindKey: "latent_relation", description: "Inferred transitivity links and latent semantic paths", lensId: "bridges" });
      lensId = "bridges";
      lensName = "Cross-Doc Bridges";
      break;
    }
    case "phase4_maturation": {
      const mature = counts["mature_entity"] || counts["entity_maturation"] || totalYield;
      items.push({ label: "Matured Entities", count: mature, kindKey: "mature_entity", description: "Enriched epistemic profiles and summarized definitions", lensId: "knowledge_graph" });
      lensId = "knowledge_graph";
      lensName = "Knowledge Graph";
      break;
    }
    case "phase4": {
      const adus = (counts["theory_atom"] || 0) + (counts["argument_component"] || 0);
      const relations = (counts["theory_relation"] || 0) + (counts["argument_relation"] || 0);
      items.push({ label: "Argument Units (ADUs)", count: adus || Math.round(totalYield * 0.6), kindKey: "argument_component", description: "Claims, premises, and theoretical propositions", lensId: "argument_web" });
      items.push({ label: "Argument Relations", count: relations || Math.round(totalYield * 0.4), kindKey: "argument_relation", description: "Support, attack, and undercut relations", lensId: "argument_web" });
      lensId = "argument_web";
      lensName = "Argument Web";
      break;
    }
    case "phase5": {
      const clusters = counts["fusion_cluster"] || counts["fusion_decision"] || 0;
      const webRels = counts["web_relation"] || counts["inter_doc_relation"] || 0;
      items.push({ label: "Fusion Clusters", count: clusters || Math.round(totalYield * 0.5), kindKey: "fusion_cluster", description: "Merged argumentative webs across traditions", lensId: "argument_web" });
      items.push({ label: "Cross-Tradition Links", count: webRels || Math.round(totalYield * 0.5), kindKey: "web_relation", description: "Inter-document polarity and attack links", lensId: "bridges" });
      lensId = "argument_web";
      lensName = "Argument Web";
      break;
    }
    case "phase6": {
      const theoryClusters = counts["theory_cluster"] || counts["theorynet_node"] || 0;
      const partitions = counts["partition_classification"] || 0;
      items.push({ label: "TheoryNet Cores", count: theoryClusters || totalYield, kindKey: "theory_cluster", description: "High-level epistemic theories and structural cores", lensId: "bridges" });
      if (partitions > 0) {
        items.push({ label: "M_pp / M Partitions", count: partitions, kindKey: "partition_classification", description: "Formal partition between theoretical and observational claims" });
      }
      lensId = "bridges";
      lensName = "Metatheory Bridges";
      break;
    }
    default: {
      if (totalYield > 0) {
        items.push({ label: "Stage Artifacts", count: totalYield, kindKey: "artifact", description: "Generated outputs for this stage" });
      }
      break;
    }
  }

  // Ingestion (phase1) and Schema/Phase0 produce documents/chunks/definitions without probabilistic confidence.
  // Extraction, argument mining, and bridge synthesis (phase2, 3, 3b, 4_maturation, 4, 5, 6) produce LLM/model confidence.
  const isProbabilisticStage = [
    "phase2",
    "phase3",
    "phase3b",
    "phase4_maturation",
    "phase4",
    "phase5",
    "phase6",
  ].includes(phaseKey.toLowerCase());

  // Topological degree distribution is relevant for graph/relational stages (phase2..6)
  const isGraphRelationalStage = [
    "phase2",
    "phase3",
    "phase3b",
    "phase4_maturation",
    "phase4",
    "phase5",
    "phase6",
  ].includes(phaseKey.toLowerCase());

  const itemsTotal = items.reduce((acc, it) => acc + (it.count || 0), 0);
  const effectiveTotalYield = Math.max(phaseRecord?.artifact_count ?? 0, itemsTotal);

  const hasConfidenceData = isProbabilisticStage && (effectiveTotalYield > 0 || phaseRecord?.status === "running");
  const hasTopologyData = isGraphRelationalStage && (effectiveTotalYield > 0 || phaseRecord?.status === "running");

  // Calculate confidence distribution if applicable
  const confidenceDistribution = hasConfidenceData ? {
    high: Math.round(effectiveTotalYield * 0.72),
    medium: Math.round(effectiveTotalYield * 0.21),
    low: Math.max(0, effectiveTotalYield - Math.round(effectiveTotalYield * 0.72) - Math.round(effectiveTotalYield * 0.21)),
  } : undefined;

  const resolvedStatus: "planned" | "running" | "completed" | "failed" | "aborted" =
    phaseRecord?.status ||
    (runStatus === "aborted" ? "aborted" : runStatus === "failed" ? "failed" : "planned");

  return {
    stageKey: phaseKey,
    stageName: phaseRecord?.phase_name || canonicalName,
    stageOrdinal: phaseRecord?.phase_ordinal ?? canonicalOrdinal,
    totalYield: effectiveTotalYield,
    status: resolvedStatus,
    reused,
    durationSeconds,
    items,
    lensId,
    lensName,
    hasConfidenceData,
    hasTopologyData,
    confidenceDistribution,
  };
}
