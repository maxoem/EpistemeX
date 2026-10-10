import React, {useEffect, useMemo, useRef, useState} from "react";
import {AlertTriangle, Check, FileText, Maximize2, Network, Search, X,} from "lucide-react";

import {StageArtifactsReport} from "./stageModel";
import {LocalEgoGraph} from "./LocalEgoGraph";
import {GraphView} from "../api/types";

export function formatPredicate(predicate: string): string {
  if (!predicate) return "";
  return predicate.replace(/_/g, " ").replace(/\band\b/g, "&");
}

export interface ProvenanceChunkDisplay {
  chunkId: string;
  docId?: string;
  tokenCount?: number;
  label?: string;
  textBefore: string;
  highlightedText: string;
  highlightType: "subject" | "object";
  textMiddle?: string;
  relationText?: string;
  textMiddleAfterRelation?: string;
  secondHighlightedText?: string;
  secondHighlightType?: "subject" | "object";
  textAfter: string;
  hasMiddleEllipsis?: boolean;
}

export interface StageTripleItem {
  id: string;
  subject: string;
  predicate: string;
  object: string;
  category: "Hierarchical" | "Associative" | "Causal" | "Dialectical" | "Unmapped";
  confidence: number;
  status: "valid" | "flagged" | "quarantine";
  degree: number;
  isOrphan: boolean;
  isBridge: boolean;
  sourceChunkId: string;
  chunkTokens: number;
  sourceTextBefore: string;
  sourceSubjectText: string;
  sourcePredicateText: string;
  sourceObjectText: string;
  sourceTextAfter: string;
  phaseKey?: string;
  sourceNodeId?: string;
  targetNodeId?: string;
  provenanceMode?: "single_chunk" | "multi_chunk";
  provenanceChunks?: ProvenanceChunkDisplay[];
  documentName?: string;
  scope?: "local" | "global" | "theory";
}

export const INITIAL_STAGE_TRIPLES: StageTripleItem[] = [
  {
    id: "trip-001",
    subject: "Hegel's Dialectic",
    predicate: "immanently_critiques",
    object: "Kantian Dualism",
    category: "Dialectical",
    confidence: 0.94,
    status: "valid",
    degree: 14,
    isOrphan: false,
    isBridge: true,
    sourceChunkId: "chunk_042",
    chunkTokens: 384,
    sourceTextBefore: "In the introductory remarks to the Science of Logic, Hegel argues that ",
    sourceSubjectText: "the dialectical progression",
    sourcePredicateText: " immanently overcomes and critiques ",
    sourceObjectText: "the rigid transcendental dualism postulated by Kant",
    sourceTextAfter: ", demonstrating that the thing-in-itself cannot remain permanently separated from phenomenal manifestation.",
  },
  {
    id: "trip-002",
    subject: "Sublation (Aufhebung)",
    predicate: "preserves_and_negates",
    object: "Determinate Being",
    category: "Dialectical",
    confidence: 0.91,
    status: "valid",
    degree: 9,
    isOrphan: false,
    isBridge: false,
    sourceChunkId: "chunk_043",
    chunkTokens: 412,
    sourceTextBefore: "Crucially, the operation of ",
    sourceSubjectText: "sublation (Aufhebung)",
    sourcePredicateText: " simultaneous preserves and negates ",
    sourceObjectText: "determinate being (Dasein)",
    sourceTextAfter: " within the higher structural unification of the Absolute Idea.",
  },
  {
    id: "trip-003",
    subject: "Phenomenology of Spirit",
    predicate: "articulates_stages_of",
    object: "Consciousness Evolution",
    category: "Hierarchical",
    confidence: 0.88,
    status: "valid",
    degree: 12,
    isOrphan: false,
    isBridge: true,
    sourceChunkId: "chunk_018",
    chunkTokens: 320,
    sourceTextBefore: "Historically, the 1807 treatise ",
    sourceSubjectText: "Phenomenology of Spirit",
    sourcePredicateText: " methodically articulates the progressive stages of ",
    sourceObjectText: "consciousness evolution",
    sourceTextAfter: " from primitive sense-certainty up to self-conscious recognition in sociality.",
  },
  {
    id: "trip-004",
    subject: "Epistemic Justification",
    predicate: "correlates_with",
    object: "Empirical Coherence",
    category: "Associative",
    confidence: 0.68,
    status: "flagged",
    degree: 4,
    isOrphan: false,
    isBridge: false,
    sourceChunkId: "chunk_088",
    chunkTokens: 290,
    sourceTextBefore: "It has been suggested that modern ",
    sourceSubjectText: "epistemic justification models",
    sourcePredicateText: " loosely correlate with ",
    sourceObjectText: "empirical coherence across isolated observation networks",
    sourceTextAfter: ", though this alignment requires substantial formal qualification.",
  },
  {
    id: "trip-005",
    subject: "Synthetic A Priori",
    predicate: "conditions_possibility_of",
    object: "Geometric Judgment",
    category: "Causal",
    confidence: 0.86,
    status: "valid",
    degree: 8,
    isOrphan: false,
    isBridge: true,
    sourceChunkId: "chunk_009",
    chunkTokens: 450,
    sourceTextBefore: "Under the transcendental aesthetic, the ",
    sourceSubjectText: "synthetic a priori intuition of pure space",
    sourcePredicateText: " uniquely conditions the possibility of ",
    sourceObjectText: "Euclidean geometric judgments",
    sourceTextAfter: " without relying upon posterior sensory induction.",
  },
  {
    id: "trip-006",
    subject: "Transcendental Idealism",
    predicate: "delimits_scope_of",
    object: "Pure Reason",
    category: "Hierarchical",
    confidence: 0.82,
    status: "valid",
    degree: 16,
    isOrphan: false,
    isBridge: false,
    sourceChunkId: "chunk_012",
    chunkTokens: 512,
    sourceTextBefore: "Through the antinomies, ",
    sourceSubjectText: "transcendental idealism",
    sourcePredicateText: " strictly delimits the cognitive scope of ",
    sourceObjectText: "pure speculative reason",
    sourceTextAfter: " to guard against dogmatic cosmological overreach.",
  },
  {
    id: "trip-007",
    subject: "Nominal Entity Alpha",
    predicate: "unmapped_relation_vector",
    object: "Quasi Concept Beta",
    category: "Unmapped",
    confidence: 0.54,
    status: "quarantine",
    degree: 1,
    isOrphan: true,
    isBridge: false,
    sourceChunkId: "chunk_104",
    chunkTokens: 210,
    sourceTextBefore: "The passage vaguely connects ",
    sourceSubjectText: "Nominal Entity Alpha",
    sourcePredicateText: " with ",
    sourceObjectText: "Quasi Concept Beta",
    sourceTextAfter: " without formalizing any explicit logical or causal functor in the argument tree.",
  },
  {
    id: "trip-008",
    subject: "Hermeneutic Circle",
    predicate: "presupposes_wholeness_of",
    object: "Textual Horizon",
    category: "Associative",
    confidence: 0.76,
    status: "flagged",
    degree: 5,
    isOrphan: false,
    isBridge: false,
    sourceChunkId: "chunk_071",
    chunkTokens: 380,
    sourceTextBefore: "Gadamer emphasizes that the iterative movement of the ",
    sourceSubjectText: "hermeneutic circle",
    sourcePredicateText: " fundamentally presupposes the wholeness of ",
    sourceObjectText: "the historical textual horizon",
    sourceTextAfter: " prior to specific semantic part-resolution.",
  },
  {
    id: "trip-009",
    subject: "Dung Argumentation Framework",
    predicate: "resolves_conflict_in",
    object: "Defeasible Inference",
    category: "Causal",
    confidence: 0.95,
    status: "valid",
    degree: 11,
    isOrphan: false,
    isBridge: true,
    sourceChunkId: "chunk_064",
    chunkTokens: 410,
    sourceTextBefore: "In multi-agent reasoning, the formal ",
    sourceSubjectText: "Dung argumentation framework",
    sourcePredicateText: " methodically resolves structural conflict in ",
    sourceObjectText: "defeasible inference graphs",
    sourceTextAfter: " by computing stable and preferred extensions over attack relations.",
  },
  {
    id: "trip-010",
    subject: "Isolated Lemma Lambda",
    predicate: "hypothesizes_parallel_to",
    object: "Unreferenced Claim Xi",
    category: "Unmapped",
    confidence: 0.49,
    status: "quarantine",
    degree: 1,
    isOrphan: true,
    isBridge: false,
    sourceChunkId: "chunk_119",
    chunkTokens: 180,
    sourceTextBefore: "In an obscure footnote, the author introduces ",
    sourceSubjectText: "Isolated Lemma Lambda",
    sourcePredicateText: " as a tentative parallel to ",
    sourceObjectText: "Unreferenced Claim Xi",
    sourceTextAfter: ", neither of which receives downstream defense or corroboration.",
  },
];

export interface StageArtifactsViewProps {
  report: StageArtifactsReport;
  onDrilldownToGraph?: (lensId: string) => void;
  primaryInputName?: string;
  isRunActive?: boolean;
  isStageRunning?: boolean;
  refreshIntervalSeconds?: number;
  onManualRefresh?: () => void;
  phaseViewMode?: "artifacts" | "config";
  onPhaseViewModeChange?: (mode: "artifacts" | "config") => void;
  selectedTripleId?: string;
  onSelectTripleId?: (id: string) => void;
  onActiveTripleChange?: (triple: StageTripleItem) => void;
  triples?: StageTripleItem[];
  onUpdateStatus?: (tripleId: string, nextStatus: "valid" | "flagged" | "quarantine") => void;
  graphData?: GraphView | null;
}

export const StageArtifactsView: React.FC<StageArtifactsViewProps> = ({
  report,
  onDrilldownToGraph,
  primaryInputName,
  isRunActive = false,
  isStageRunning = false,
  refreshIntervalSeconds = 30,
  onManualRefresh,
  phaseViewMode = "artifacts",
  onPhaseViewModeChange,
  selectedTripleId: externalSelectedTripleId,
  onSelectTripleId: externalOnSelectTripleId,
  onActiveTripleChange,
  triples: externalTriples,
  onUpdateStatus: externalOnUpdateStatus,
  graphData,
}) => {
  const { stageName, stageOrdinal, lensId } = report;

  // Triples state (managed locally or synchronized with parent)
  const [internalTriples, setInternalTriples] = useState<StageTripleItem[]>(INITIAL_STAGE_TRIPLES);
  const triples = externalTriples || internalTriples;

  // View mode for the center stage: "assertions" (Direction 1 grid) or "graph" (Full-Screen Graph Lens)
  const [centerViewMode, setCenterViewMode] = useState<"assertions" | "graph">("assertions");

  // Filtering states
  const [triageFilter, setTriageFilter] = useState<"all" | "flagged" | "orphans" | "schema">("all");
  const [textSearch, setTextSearch] = useState<string>("");

  const [internalSelectedId, setInternalSelectedId] = useState<string>(
    externalSelectedTripleId || INITIAL_STAGE_TRIPLES[0]?.id || ""
  );

  // Sync internal selection when externalSelectedTripleId changes
  useEffect(() => {
    if (externalSelectedTripleId) {
      setInternalSelectedId(externalSelectedTripleId);
    }
  }, [externalSelectedTripleId]);

  const selectedTripleId = internalSelectedId || externalSelectedTripleId;

  const setSelectedTripleId = (id: string) => {
    setInternalSelectedId(id);
    if (externalOnSelectTripleId) {
      externalOnSelectTripleId(id);
    }
    const found = triples.find((t) => t.id === id);
    if (found && onActiveTripleChange) {
      onActiveTripleChange(found);
    }
  };

  // Handler for immediate scientist triage validation
  const handleUpdateStatus = (tripleId: string, nextStatus: "valid" | "flagged" | "quarantine") => {
    if (externalOnUpdateStatus) {
      externalOnUpdateStatus(tripleId, nextStatus);
    } else {
      setInternalTriples((prev) =>
        prev.map((item) => (item.id === tripleId ? { ...item, status: nextStatus } : item))
      );
    }
  };

  // Filtered triples based on triage filter + text search
  const filteredTriples = useMemo(() => {
    return triples.filter((item) => {
      if (triageFilter === "flagged" && item.confidence >= 0.70) return false;
      if (triageFilter === "orphans" && !item.isOrphan) return false;
      if (triageFilter === "schema" && item.category !== "Unmapped") return false;

      if (textSearch.trim()) {
        const query = textSearch.toLowerCase();
        const matchesSubj = item.subject.toLowerCase().includes(query);
        const matchesPred = item.predicate.toLowerCase().includes(query);
        const matchesObj = item.object.toLowerCase().includes(query);
        if (!matchesSubj && !matchesPred && !matchesObj) return false;
      }

      return true;
    });
  }, [triples, triageFilter, textSearch]);

  // Ensure active selected triple is valid within filtered list
  useEffect(() => {
    if (filteredTriples.length > 0) {
      if (!filteredTriples.some((t) => t.id === selectedTripleId)) {
        setSelectedTripleId(filteredTriples[0].id);
      }
    }
  }, [filteredTriples, selectedTripleId]);

  const activeTriple = useMemo(() => {
    return filteredTriples.find((t) => t.id === selectedTripleId) || filteredTriples[0] || triples[0];
  }, [filteredTriples, selectedTripleId, triples]);

  // Notify parent of active triple change for right rail synchronization (guarded by ID ref)
  const prevActiveIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (activeTriple && activeTriple.id !== prevActiveIdRef.current) {
      prevActiveIdRef.current = activeTriple.id;
      onActiveTripleChange?.(activeTriple);
    }
  }, [activeTriple?.id]);

  // Keyboard navigation & quick triage shortcuts (j/k to navigate, v to validate, f to flag, q to quarantine)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
      if (filteredTriples.length === 0) return;
      const currentIndex = filteredTriples.findIndex((t) => t.id === selectedTripleId);

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        const nextIndex = Math.min(filteredTriples.length - 1, currentIndex >= 0 ? currentIndex + 1 : 0);
        const nextTriple = filteredTriples[nextIndex];
        if (nextTriple) {
          setSelectedTripleId(nextTriple.id);
          externalOnSelectTripleId?.(nextTriple.id);
          onActiveTripleChange?.(nextTriple);
        }
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        const prevIndex = Math.max(0, currentIndex >= 0 ? currentIndex - 1 : 0);
        const prevTriple = filteredTriples[prevIndex];
        if (prevTriple) {
          setSelectedTripleId(prevTriple.id);
          externalOnSelectTripleId?.(prevTriple.id);
          onActiveTripleChange?.(prevTriple);
        }
      } else if (e.key === "v" && activeTriple) {
        e.preventDefault();
        handleUpdateStatus(activeTriple.id, "valid");
      } else if (e.key === "f" && activeTriple) {
        e.preventDefault();
        handleUpdateStatus(activeTriple.id, "flagged");
      } else if (e.key === "q" && activeTriple) {
        e.preventDefault();
        handleUpdateStatus(activeTriple.id, "quarantine");
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [filteredTriples, selectedTripleId, activeTriple]);

  const flaggedCount = useMemo(() => triples.filter((t) => t.confidence < 0.70).length, [triples]);
  const orphanCount = useMemo(() => triples.filter((t) => t.isOrphan).length, [triples]);
  const schemaViolationCount = useMemo(() => triples.filter((t) => t.category === "Unmapped").length, [triples]);

  return (
    <div className="flex flex-col h-full bg-app-bg overflow-hidden select-none">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Sleek, Uncluttered 38px Stage Action Bar                            */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="h-[38px] min-h-[38px] px-3 border-b border-app-border flex items-center justify-between gap-3 bg-app-surface shrink-0 font-sans">
        {/* Left: View Mode Switcher + Concise Triage Filter Pills */}
        <div className="flex items-center gap-3 min-w-0 h-full">
          {/* Primary View Mode Tabs (Flush Underline Style, matches Inspector Rail) */}
          <div className="h-full flex items-center gap-4 text-xs font-sans shrink-0">
            <button
              type="button"
              onClick={() => setCenterViewMode("assertions")}
              className={`h-full flex items-center gap-1.5 transition-colors cursor-pointer border-b-2 font-medium ${
                centerViewMode === "assertions"
                  ? "border-blue-600 dark:border-blue-500 text-app-heading font-semibold"
                  : "border-transparent text-app-muted hover:text-app-heading"
              }`}
            >
              <FileText className="w-3.5 h-3.5 text-app-muted" />
              <span>Assertions</span>
            </button>
            <button
              type="button"
              onClick={() => setCenterViewMode("graph")}
              className={`h-full flex items-center gap-1.5 transition-colors cursor-pointer border-b-2 font-medium ${
                centerViewMode === "graph"
                  ? "border-blue-600 dark:border-blue-500 text-app-heading font-semibold"
                  : "border-transparent text-app-muted hover:text-app-heading"
              }`}
            >
              <Network className="w-3.5 h-3.5 text-app-muted" />
              <span>Graph Lens</span>
            </button>
          </div>

          {/* Hairline Divider */}
          {centerViewMode === "assertions" && (
            <div className="h-4 w-px bg-app-border shrink-0 mx-0.5" />
          )}

          {/* Direct Triage Filter Pills (Flattened, no heavy nested container) */}
          {centerViewMode === "assertions" && (
            <div className="flex items-center gap-1 text-[11px]">
              <button
                type="button"
                onClick={() => setTriageFilter("all")}
                className={`px-2.5 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                  triageFilter === "all"
                    ? "bg-app-subtle text-app-heading font-semibold border border-app-border"
                    : "text-app-muted hover:text-app-heading hover:bg-app-subtle/50"
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${triageFilter === "all" ? "bg-gray-400 dark:bg-zinc-400" : "bg-app-muted/50"}`} />
                <span>All</span>
                <span className="font-mono text-[10px] text-app-muted tabular-nums">{triples.length}</span>
              </button>
              <button
                type="button"
                onClick={() => setTriageFilter("flagged")}
                className={`px-2.5 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                  triageFilter === "flagged"
                    ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold border border-amber-500/30"
                    : "text-app-muted hover:text-amber-600 hover:bg-app-subtle/50"
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                <span>Review</span>
                <span className="font-mono text-[10px] tabular-nums text-amber-600 dark:text-amber-400">{flaggedCount}</span>
              </button>
              <button
                type="button"
                onClick={() => setTriageFilter("orphans")}
                className={`px-2.5 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                  triageFilter === "orphans"
                    ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 font-semibold border border-rose-500/30"
                    : "text-app-muted hover:text-rose-600 hover:bg-app-subtle/50"
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                <span>Orphans</span>
                <span className="font-mono text-[10px] tabular-nums text-rose-600 dark:text-rose-400">{orphanCount}</span>
              </button>
              <button
                type="button"
                onClick={() => setTriageFilter("schema")}
                className={`px-2.5 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                  triageFilter === "schema"
                    ? "bg-purple-500/10 text-purple-600 dark:text-purple-400 font-semibold border border-purple-500/30"
                    : "text-app-muted hover:text-purple-600 hover:bg-app-subtle/50"
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                <span>Unmapped</span>
                <span className="font-mono text-[10px] tabular-nums text-purple-600 dark:text-purple-400">{schemaViolationCount}</span>
              </button>
            </div>
          )}
        </div>

        {/* Right: Search Box with Integrated Keyboard Shortcut */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="relative flex items-center w-48 focus-within:w-60 transition-all">
            <Search className="w-3.5 h-3.5 absolute left-2 text-app-muted pointer-events-none" />
            <input
              type="text"
              value={textSearch}
              onChange={(e) => setTextSearch(e.target.value)}
              placeholder="Search assertions..."
              className="w-full h-7 pl-7 pr-12 rounded bg-app-bg text-app-heading placeholder-app-muted border border-app-border text-xs font-sans focus:outline-none focus:border-blue-500"
            />
            {textSearch ? (
              <button
                type="button"
                onClick={() => setTextSearch("")}
                className="absolute right-2 text-app-muted hover:text-app-heading cursor-pointer"
              >
                <X className="w-3 h-3" />
              </button>
            ) : (
              <kbd
                className="hidden sm:inline-flex items-center absolute right-2 px-1 py-0.2 rounded bg-app-subtle border border-app-border text-[9px] font-mono text-app-muted pointer-events-none"
                title="Traverse: j / k"
              >
                j / k
              </kbd>
            )}
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Fluid Center Workspace: Full Canvas Mode Switching                 */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-app-bg">
        {centerViewMode === "assertions" ? (
          /* ================================================================= */
          /* MODE 1: DIRECTION 1 DIRECTED VECTOR PROPOSITIONS (A ── rel ──► B) */
          /* ================================================================= */
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            {/* Header Row (Monospace Uppercase Tracking, Clean 32px) */}
            <div className="h-8 px-4 border-b border-app-border bg-app-surface text-[10px] font-mono uppercase tracking-wider text-app-muted flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2 flex-1 min-w-0 pr-4">
                <span className="flex-1 min-w-0 truncate">Subject Concept</span>
                <span className="w-52 shrink-0 text-center">Epistemic Functor</span>
                <span className="flex-1 min-w-0 truncate">Target Object</span>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <span className="w-16 text-center">Class</span>
                <span className="w-12 text-right">Conf</span>
                <span className="w-16 text-right">Status</span>
              </div>
            </div>

            {/* List Body (Scrollable Edge-to-Edge) */}
            <div className="flex-1 overflow-y-auto divide-y divide-app-border/40">
              {filteredTriples.length === 0 ? (
                <div className="py-16 px-6 text-center text-xs text-app-muted font-mono">
                  No stage assertions match the active filter criteria.
                </div>
              ) : (
                filteredTriples.map((triple) => {
                  const isSelected = triple.id === activeTriple?.id || triple.id === selectedTripleId;
                  const isLowConfidence = triple.confidence < 0.70;

                  return (
                    <div
                      key={triple.id}
                      onClick={() => {
                        setSelectedTripleId(triple.id);
                        externalOnSelectTripleId?.(triple.id);
                        onActiveTripleChange?.(triple);
                      }}
                      className={`group relative h-11 px-4 flex items-center justify-between border-l-2 cursor-pointer transition-colors select-none text-xs ${
                        isSelected
                          ? "bg-app-subtle border-l-blue-600 dark:border-l-blue-500 font-medium"
                          : "border-l-transparent hover:bg-app-subtle/50"
                      }`}
                    >
                      {/* Left: Stabilized Directed Vector (Fluid 50/50 Balance) */}
                      <div className="flex items-center gap-2 min-w-0 flex-1 pr-4">
                        {/* Subject Concept (Fluid 50% Share) */}
                        <span
                          className={`flex-1 min-w-0 font-sans text-[12px] tracking-tight truncate ${
                            isSelected ? "font-semibold text-app-heading" : "font-medium text-app-heading"
                          }`}
                          title={triple.subject}
                        >
                          {triple.subject}
                        </span>

                        {/* Stabilized Vector Connector: Clean Unboxed Predicate on Hairline */}
                        <div className="w-52 shrink-0 flex items-center px-1 group/conn">
                          <div className="h-[1px] flex-1 bg-app-border group-hover:bg-blue-500/40 transition-colors" />
                          <span
                            className="max-w-[160px] truncate font-mono text-[10px] text-app-muted group-hover:text-blue-500 mx-1.5 transition-colors text-center shrink-0"
                            title={triple.predicate}
                          >
                            {formatPredicate(triple.predicate)}
                          </span>
                          <div className="h-[1px] flex-1 bg-app-border group-hover:bg-blue-500/40 transition-colors relative flex items-center justify-end">
                            <span className="text-[10px] text-app-muted/70 group-hover:text-blue-500 leading-none -mr-0.5">
                              ▸
                            </span>
                          </div>
                        </div>

                        {/* Target Object Concept (Fluid 50% Share) */}
                        <span
                          className="flex-1 min-w-0 font-sans text-[12px] tracking-tight truncate font-medium text-app-text"
                          title={triple.object}
                        >
                          {triple.object}
                        </span>
                      </div>

                      {/* Right: Class · Confidence · Status */}
                      <div className="flex items-center gap-4 shrink-0">
                        {/* Class */}
                        <div className="w-16 text-center text-[11px] text-app-muted truncate">
                          {triple.category}
                        </div>

                        {/* Confidence Score (Neutral tabular numeral; colored only when anomaly) */}
                        <div className="w-12 text-right font-mono tabular-nums text-xs font-medium">
                          <span className={isLowConfidence ? "text-amber-600 dark:text-amber-400 font-semibold" : "text-app-text"}>
                            {triple.confidence.toFixed(2)}
                          </span>
                        </div>

                        {/* Operational Status (Valid is calm neutral; Review and Quarantine pop) */}
                        <div className="w-16 text-right">
                          {triple.status === "valid" ? (
                            <span className="inline-flex items-center gap-1 text-[11px] text-app-muted">
                              <Check className="w-3 h-3 text-app-muted/70" /> Valid
                            </span>
                          ) : triple.status === "flagged" ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                              <AlertTriangle className="w-3 h-3" /> Review
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-600 dark:text-rose-400">
                              <X className="w-3 h-3" /> Quarant.
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Master Footer Summary */}
            <div className="h-8 px-4 border-t border-app-border bg-app-surface text-[11px] font-mono text-app-muted flex items-center justify-between shrink-0">
              <span>
                Showing {filteredTriples.length} of {triples.length} stage assertions
              </span>
              <span className="truncate max-w-sm">
                {activeTriple ? (
                  <>
                    Selected: <strong className="text-app-heading">{activeTriple.id}</strong> ({activeTriple.subject})
                  </>
                ) : (
                  <span>No assertion selected</span>
                )}
              </span>
            </div>
          </div>
        ) : (
          /* ================================================================= */
          /* MODE 2: FULL-SCREEN INTERACTIVE LOCAL EGO-GRAPH LENS               */
          /* ================================================================= */
          activeTriple ? (
            <div className="flex-1 min-h-0 flex flex-col overflow-hidden relative h-full w-full">
              <div className="h-9 px-4 border-b border-app-border bg-app-surface flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                  <Network className="w-3.5 h-3.5 text-blue-500" />
                  <span className="text-xs font-medium text-app-heading font-display">
                    Ego-Graph: <strong className="font-semibold text-app-heading">{activeTriple.subject}</strong>
                  </span>
                  <span className="text-[11px] font-mono text-app-muted">
                    (k={activeTriple.degree} {activeTriple.isBridge ? "• Bridge Vertex" : ""})
                  </span>
                </div>

                <div className="flex items-center gap-2 text-xs">
                  <button
                    type="button"
                    onClick={() => setCenterViewMode("assertions")}
                    className="px-2.5 py-1 rounded bg-app-subtle hover:bg-app-border border border-app-border text-app-heading font-medium text-[11px] transition-colors cursor-pointer"
                  >
                    ← Back to Assertions
                  </button>
                  {lensId && onDrilldownToGraph && (
                    <button
                      type="button"
                      onClick={() => onDrilldownToGraph(lensId)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium text-[11px] transition-colors cursor-pointer"
                    >
                      <Maximize2 className="w-3 h-3" />
                      <span>Open in Graph Explorer</span>
                    </button>
                  )}
                </div>
              </div>

              <div className="flex-1 min-h-0 relative h-full w-full">
                <LocalEgoGraph
                  focusSubject={activeTriple.subject}
                  focusPredicate={activeTriple.predicate}
                  focusObject={activeTriple.object}
                  confidence={activeTriple.confidence}
                  category={activeTriple.category}
                  isAnomaly={activeTriple.status === "quarantine"}
                  className="h-full w-full border-0"
                  graphData={graphData}
                  onSelectNode={(nodeId) => {
                    setTextSearch(nodeId);
                  }}
                />
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-xs text-app-muted font-mono">
              <Network className="w-8 h-8 opacity-25 mb-2" />
              <span>No assertion selected for Graph Lens visualization</span>
            </div>
          )
        )}
      </div>
    </div>
  );
};
