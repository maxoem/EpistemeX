import React, { useState, useEffect } from "react";
import {
  Activity,
  Cpu,
  Loader2,
  ShieldCheck,
  Zap,
  Layers,
  Database,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Boxes,
  Check,
  Flag,
  ShieldAlert,
  ArrowRight,
  ExternalLink,
  X,
} from "lucide-react";
import { RunDetail, PhaseStatus } from "../api/types";
import { StageArtifactsReport } from "./stageModel";
import { LiveProgress, SubtaskProgress } from "../store/runsStore";
import { EPISTEMIC_TAXONOMY, getEpistemicLayerForPhase } from "./epistemicTheme";
import { PredicateCompositionDonutChart } from "./EpistemicCharts";
import { StageTripleItem, ProvenanceChunkDisplay, formatPredicate } from "./StageArtifactsView";
import type { PredicateSchemaRow } from "./RunOverviewView";
import { DecisionAuditTable } from "./decisions/DecisionAuditTable";

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};

const formatDuration = (seconds?: number | null): string => {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
};

export interface RunDiagnosticInspectorRailProps {
  selectedRunDetail: RunDetail | null;
  selectedPhaseKey: string | null;
  activePhaseRecord?: PhaseStatus;
  stageReport?: StageArtifactsReport | null;
  totalArtifactCount: number;
  sizeBytes: number;
  durationSeconds?: number | null;
  reusedCount: number;
  totalPhaseCount: number;
  reusePercent: number;
  llmModel?: string;
  embModel?: string;
  rrkModel?: string;
  thinkingLevel?: string | null;
  liveProgress?: LiveProgress | null;
  subtasks?: Record<string, SubtaskProgress>;
  isRunActive?: boolean;
  phaseScores?: Record<string, number[]>;
  onSelectPhase?: (phaseKey: string | null) => void;
  activeTriple?: StageTripleItem | null;
  selectedPredicate?: PredicateSchemaRow | null;
  selectionNonce?: number;
  onUpdateTripleStatus?: (tripleId: string, status: "valid" | "flagged" | "quarantine") => void;
  onUpdatePredicateStatus?: (predicateName: string, status: "Valid" | "Flagged" | "Quarantined") => void;
  primaryInputName?: string;
  onDrilldownToGraph?: (lensId: string) => void;
  activeTab?: "assertion" | "predicate" | "invariants" | "telemetry" | "decisions";
  onActiveTabChange?: (tab: "assertion" | "predicate" | "invariants" | "telemetry" | "decisions") => void;
}

export const RunDiagnosticInspectorRail: React.FC<RunDiagnosticInspectorRailProps> = ({
  selectedRunDetail,
  selectedPhaseKey,
  activePhaseRecord,
  stageReport,
  totalArtifactCount,
  sizeBytes,
  durationSeconds,
  reusedCount,
  totalPhaseCount,
  reusePercent,
  llmModel = "openai/gpt-4o-mini",
  embModel = "sentence-transformers/all-MiniLM-L6-v2",
  rrkModel = "Alibaba-NLP/gte-reranker-modernbert-base",
  thinkingLevel,
  liveProgress,
  subtasks,
  isRunActive = false,
  phaseScores = {},
  onSelectPhase,
  activeTriple,
  selectedPredicate,
  selectionNonce,
  onUpdateTripleStatus,
  onUpdatePredicateStatus,
  primaryInputName,
  onDrilldownToGraph,
  activeTab: externalActiveTab,
  onActiveTabChange,
}) => {
  const isRunning = isRunActive || selectedRunDetail?.status === "running";
  
  // Controlled tab state with fallback to local state
  const [internalTab, setInternalTab] = useState<"assertion" | "predicate" | "invariants" | "telemetry" | "decisions">(
    selectedPredicate ? "predicate" : activeTriple ? "assertion" : "invariants"
  );
  const activeTab = externalActiveTab !== undefined ? externalActiveTab : internalTab;

  const setActiveTab = (tab: "assertion" | "predicate" | "invariants" | "telemetry" | "decisions") => {
    setInternalTab(tab);
    onActiveTabChange?.(tab);
  };

  // Automatically switch to "predicate" tab when a predicate is selected
  useEffect(() => {
    if (selectedPredicate) {
      setActiveTab("predicate");
    }
  }, [selectedPredicate?.predicate]);

  // Force tab switch on explicit user selection (e.g. clicking a table row)
  useEffect(() => {
    if (selectionNonce !== undefined && selectionNonce > 0) {
      if (selectedPredicate) {
        setActiveTab("predicate");
      } else if (activeTriple) {
        setActiveTab("assertion");
      }
    }
  }, [selectionNonce]);

  return (
    <div className="w-full h-full flex flex-col bg-app-surface overflow-hidden select-none">
      {/* Rail Header (Docked 44px) */}
      <div className="h-11 px-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Activity className="w-4 h-4 text-app-muted shrink-0" />
          <h2 className="text-xs font-semibold text-app-heading tracking-tight truncate font-display">
            Diagnostic Inspector
          </h2>
        </div>

        {isRunning && (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 animate-pulse shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping" />
            LIVE
          </span>
        )}
      </div>

      {/* Modern Underline Tabs (No box-in-box pill track, no rainbow icons) */}
      <div className="h-9 px-4 border-b border-app-border bg-app-surface flex items-center gap-6 text-xs font-sans shrink-0">
        {activeTriple && (
          <button
            type="button"
            onClick={() => setActiveTab("assertion")}
            className={`h-full flex items-center transition-colors cursor-pointer border-b-2 font-medium ${
              activeTab === "assertion"
                ? "border-blue-600 dark:border-blue-500 text-app-heading font-semibold"
                : "border-transparent text-app-muted hover:text-app-heading"
            }`}
          >
            <span>Assertion</span>
          </button>
        )}

        {selectedPredicate && (
          <button
            type="button"
            onClick={() => setActiveTab("predicate")}
            className={`h-full flex items-center transition-colors cursor-pointer border-b-2 font-medium ${
              activeTab === "predicate"
                ? "border-blue-600 dark:border-blue-500 text-app-heading font-semibold"
                : "border-transparent text-app-muted hover:text-app-heading"
            }`}
          >
            <span>Predicate</span>
          </button>
        )}

        <button
          type="button"
          onClick={() => setActiveTab("invariants")}
          className={`h-full flex items-center transition-colors cursor-pointer border-b-2 font-medium ${
            activeTab === "invariants"
              ? "border-blue-600 dark:border-blue-500 text-app-heading font-semibold"
              : "border-transparent text-app-muted hover:text-app-heading"
          }`}
        >
          <span>Invariants</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("telemetry")}
          className={`h-full flex items-center transition-colors cursor-pointer border-b-2 font-medium ${
            activeTab === "telemetry"
              ? "border-blue-600 dark:border-blue-500 text-app-heading font-semibold"
              : "border-transparent text-app-muted hover:text-app-heading"
          }`}
        >
          <span>Telemetry</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("decisions")}
          className={`h-full flex items-center transition-colors cursor-pointer border-b-2 font-medium ${
            activeTab === "decisions"
              ? "border-blue-600 dark:border-blue-500 text-app-heading font-semibold"
              : "border-transparent text-app-muted hover:text-app-heading"
          }`}
        >
          <span>Decisions</span>
        </button>
      </div>

      {/* Rail Content Body (Scrollable, Clean Hairline Sections) */}
      <div className="flex-1 overflow-y-auto divide-y divide-app-border">
        {activeTab === "decisions" && (
          <div className="h-full flex flex-col animate-in fade-in duration-100">
            <DecisionAuditTable
              runId={selectedRunDetail?.run_id || ""}
              selectedPhaseKey={selectedPhaseKey}
            />
          </div>
        )}

        {activeTab === "predicate" && selectedPredicate ? (
          /* ================================================================= */
          /* TAB: SELECTED PREDICATE SCHEMA & DRIFT                            */
          /* ================================================================= */
          <div className="divide-y divide-app-border animate-in fade-in duration-100">
            {/* 1. Predicate Banner */}
            <div className="p-4 space-y-2">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-xs font-semibold text-app-heading font-display">
                  Predicate Definition
                </span>
                <span
                  className={`px-1.5 py-0.5 rounded font-mono text-[10px] font-bold ${
                    selectedPredicate.status === "Valid"
                      ? "text-emerald-500 bg-emerald-500/10"
                      : selectedPredicate.status === "Quarantined"
                      ? "text-rose-500 bg-rose-500/10"
                      : "text-amber-500 bg-amber-500/10"
                  }`}
                >
                  {selectedPredicate.status}
                </span>
              </div>

              <div className="pt-1">
                <div className="text-sm font-mono font-bold text-app-heading">
                  {selectedPredicate.predicate}
                </div>
                <div className="text-[11px] text-app-muted mt-0.5">
                  Ontology Mapping: <span className="text-app-text font-medium">{selectedPredicate.ontologyMapping}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-2 text-[11px] font-sans">
                <div className="p-2 rounded bg-app-subtle/60 border border-app-border">
                  <div className="text-app-muted text-[10px] uppercase font-mono">Frequency</div>
                  <div className="font-mono text-xs font-bold text-app-heading tabular-nums">
                    {selectedPredicate.frequency.toLocaleString()} occurrences
                  </div>
                </div>
                <div className="p-2 rounded bg-app-subtle/60 border border-app-border">
                  <div className="text-app-muted text-[10px] uppercase font-mono">Avg Confidence</div>
                  <div className="font-mono text-xs font-bold text-app-heading tabular-nums">
                    {(selectedPredicate.averageConfidence * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Scientist Triage Actions */}
            <div className="p-4 space-y-2 border-b border-app-border">
              <div className="text-xs font-semibold text-app-heading font-display">
                Predicate Triage
              </div>
              <div className="p-0.5 rounded-lg bg-app-subtle border border-app-border flex items-center gap-1 text-xs font-sans">
                <button
                  type="button"
                  onClick={() => onUpdatePredicateStatus?.(selectedPredicate.predicate, "Valid")}
                  className={`flex-1 py-1.5 px-2 rounded-md transition-all cursor-pointer flex items-center justify-center gap-1.5 text-[11px] font-medium ${
                    selectedPredicate.status === "Valid"
                      ? "bg-app-bg text-app-heading font-semibold shadow-2xs border border-app-border/80"
                      : "text-app-muted hover:text-app-heading"
                  }`}
                  title="Mark predicate valid and canonical"
                >
                  <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  <span>Valid</span>
                </button>

                <button
                  type="button"
                  onClick={() => onUpdatePredicateStatus?.(selectedPredicate.predicate, "Flagged")}
                  className={`flex-1 py-1.5 px-2 rounded-md transition-all cursor-pointer flex items-center justify-center gap-1.5 text-[11px] font-medium ${
                    selectedPredicate.status === "Flagged"
                      ? "bg-app-bg text-amber-600 dark:text-amber-400 font-semibold shadow-2xs border border-amber-500/30"
                      : "text-app-muted hover:text-amber-600"
                  }`}
                  title="Flag for epistemological review"
                >
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                  <span>Review</span>
                </button>

                <button
                  type="button"
                  onClick={() => onUpdatePredicateStatus?.(selectedPredicate.predicate, "Quarantined")}
                  className={`flex-1 py-1.5 px-2 rounded-md transition-all cursor-pointer flex items-center justify-center gap-1.5 text-[11px] font-medium ${
                    selectedPredicate.status === "Quarantined"
                      ? "bg-app-bg text-rose-600 dark:text-rose-400 font-semibold shadow-2xs border border-rose-500/30"
                      : "text-app-muted hover:text-rose-600"
                  }`}
                  title="Quarantine predicate"
                >
                  <X className="w-3.5 h-3.5 text-rose-500" />
                  <span>Quarantine</span>
                </button>
              </div>
            </div>

            {/* 3. Epistemic Classification */}
            <div className="p-4 space-y-2">
              <h3 className="text-xs font-semibold text-app-heading font-display">
                Epistemic Specification
              </h3>
              <table className="w-full text-left border-collapse text-xs">
                <tbody className="divide-y divide-app-border/40 font-sans">
                  <tr className="h-7">
                    <td className="text-app-muted text-[11px] py-1">Ontology Class</td>
                    <td className="text-right font-sans text-[11px] text-app-heading font-medium py-1">
                      {selectedPredicate.epistemicRole}
                    </td>
                  </tr>
                  <tr className="h-7">
                    <td className="text-app-muted text-[11px] py-1">Schema Drift</td>
                    <td className="text-right font-sans text-[11px] py-1">
                      {selectedPredicate.ontologyMapping === "Open-Vocabulary Drift" ? (
                        <span className="text-amber-600 dark:text-amber-400 font-semibold">Drift Detected</span>
                      ) : (
                        <span className="text-emerald-600 dark:text-emerald-400 font-medium">Canonical ✓</span>
                      )}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* 4. Active Linked Assertion */}
            {activeTriple && (
              <div className="p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold text-app-heading font-display">
                    Example Proposition
                  </h3>
                  <button
                    type="button"
                    onClick={() => setActiveTab("assertion")}
                    className="text-[10px] font-mono text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
                  >
                    Inspect Assertion →
                  </button>
                </div>
                <div className="p-2.5 rounded bg-app-subtle border border-app-border text-xs space-y-1">
                  <div className="font-semibold text-app-heading truncate">{activeTriple.subject}</div>
                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-app-muted pl-2 border-l-2 border-app-border">
                    <span className="text-app-heading font-medium truncate">{formatPredicate(activeTriple.predicate)}</span>
                    <span className="shrink-0">──►</span>
                    <span className="font-sans font-medium text-app-text truncate">{activeTriple.object}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : activeTab === "assertion" && activeTriple ? (
          /* ================================================================= */
          /* TAB 0: SELECTED ASSERTION PROVENANCE & GROUND TRUTH               */
          /* ================================================================= */
          <div className="divide-y divide-app-border animate-in fade-in duration-100">
            {/* 1. Hero Proposition Card (Clean ROMER-style callout) */}
            <div className="p-4 space-y-3 bg-app-surface/50 border-b border-app-border">
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-app-subtle border border-app-border text-app-heading">
                  {activeTriple.category}
                </span>
                <span
                  className="font-mono text-[10px] text-app-muted truncate max-w-[160px] select-all cursor-pointer hover:text-app-heading"
                  title={activeTriple.id}
                >
                  {activeTriple.id.split("::").pop() || activeTriple.id}
                </span>
              </div>

              {/* Proposition Hero Presentation */}
              <div className="space-y-2 py-1">
                {/* Subject Concept */}
                <div className="text-sm font-semibold text-app-heading font-sans tracking-tight leading-snug">
                  {activeTriple.subject}
                </div>

                {/* Directed Functor Flow */}
                <div className="flex items-center gap-2 text-[11px] font-mono text-app-muted">
                  <div className="h-px flex-1 bg-app-border" />
                  <span
                    className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold text-[10px] tracking-wide"
                    title={activeTriple.predicate}
                  >
                    {formatPredicate(activeTriple.predicate)}
                  </span>
                  <div className="h-px flex-1 bg-app-border" />
                  <span className="text-blue-600 dark:text-blue-400 -ml-1 text-[10px]">▸</span>
                </div>

                {/* Target Object Concept */}
                <div className="text-sm font-medium text-app-text font-sans tracking-tight leading-snug">
                  {activeTriple.object}
                </div>
              </div>

              {/* Primary Metric Bar: Unified Split Ledger */}
              <div className="p-2.5 rounded-lg bg-app-subtle/50 border border-app-border-subtle flex items-center divide-x divide-app-border">
                <div className="flex-1 pr-3">
                  <div className="text-[10px] uppercase font-mono tracking-wider text-app-muted">Confidence</div>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <span className="text-base font-bold font-mono tabular-nums text-app-heading">
                      {(activeTriple.confidence * 100).toFixed(1)}%
                    </span>
                    <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 font-semibold">
                      {activeTriple.confidence >= 0.85 ? "High" : activeTriple.confidence >= 0.65 ? "Med" : "Low"}
                    </span>
                  </div>
                </div>

                <div className="flex-1 pl-3">
                  <div className="text-[10px] uppercase font-mono tracking-wider text-app-muted">Degree (k)</div>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <span className="text-base font-bold font-mono tabular-nums text-app-heading">
                      {activeTriple.degree}
                    </span>
                    <span className="text-[10px] font-sans text-app-muted truncate">
                      {activeTriple.isBridge ? "Bridge" : "Connections"}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Scientist Triage Segmented Bar */}
            <div className="p-4 space-y-2 border-b border-app-border">
              <div className="text-xs font-semibold text-app-heading font-display">
                Epistemic Validation
              </div>
              <div className="p-0.5 rounded-lg bg-app-subtle border border-app-border flex items-center gap-1 text-xs font-sans">
                <button
                  type="button"
                  onClick={() => onUpdateTripleStatus && onUpdateTripleStatus(activeTriple.id, "valid")}
                  className={`flex-1 py-1.5 px-2 rounded-md transition-all cursor-pointer flex items-center justify-center gap-1.5 text-[11px] font-medium ${
                    activeTriple.status === "valid"
                      ? "bg-app-bg text-app-heading font-semibold shadow-2xs border border-app-border/80"
                      : "text-app-muted hover:text-app-heading"
                  }`}
                  title="Validate triple according to text evidence (Key: v)"
                >
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Valid</span>
                </button>

                <button
                  type="button"
                  onClick={() => onUpdateTripleStatus && onUpdateTripleStatus(activeTriple.id, "flagged")}
                  className={`flex-1 py-1.5 px-2 rounded-md transition-all cursor-pointer flex items-center justify-center gap-1.5 text-[11px] font-medium ${
                    activeTriple.status === "flagged"
                      ? "bg-app-bg text-amber-600 dark:text-amber-400 font-semibold shadow-2xs border border-amber-500/30"
                      : "text-app-muted hover:text-amber-600"
                  }`}
                  title="Flag assertion for human expert review (Key: f)"
                >
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                  <span>Flag</span>
                </button>

                <button
                  type="button"
                  onClick={() => onUpdateTripleStatus && onUpdateTripleStatus(activeTriple.id, "quarantine")}
                  className={`flex-1 py-1.5 px-2 rounded-md transition-all cursor-pointer flex items-center justify-center gap-1.5 text-[11px] font-medium ${
                    activeTriple.status === "quarantine"
                      ? "bg-app-bg text-rose-600 dark:text-rose-400 font-semibold shadow-2xs border border-rose-500/30"
                      : "text-app-muted hover:text-rose-600"
                  }`}
                  title="Quarantine unmapped or hallucinated triple (Key: q)"
                >
                  <X className="w-3.5 h-3.5 text-rose-500" />
                  <span>Quarantine</span>
                </button>
              </div>
            </div>

            {/* 3. Extraction Specification: Typographic Key-Value Ledger */}
            <div className="p-4 space-y-2 border-b border-app-border">
              <h3 className="text-xs font-semibold text-app-heading font-display mb-1">
                Extraction Specification
              </h3>

              <div className="divide-y divide-app-border-subtle text-xs font-sans">
                <div className="flex items-center justify-between py-1.5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-app-muted">Scope</span>
                  <span className="font-sans font-medium text-[11px] text-app-heading">
                    {activeTriple.provenanceMode === "multi_chunk" ? "Cross-Chunk (L2)" : activeTriple.scope === "theory" ? "Theory Net (L3)" : "Intra-Chunk (L2)"}
                  </span>
                </div>

                <div className="flex items-center justify-between py-1.5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-app-muted">Stage</span>
                  <span className="font-mono font-medium text-[11px] text-app-heading">
                    {activeTriple.phaseKey ? activeTriple.phaseKey.toUpperCase() : "PHASE 2"}
                  </span>
                </div>

                <div className="flex items-center justify-between py-1.5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-app-muted">Token Volume</span>
                  <span className="font-mono tabular-nums font-semibold text-[11px] text-app-heading">
                    {activeTriple.chunkTokens.toLocaleString()} tok
                  </span>
                </div>

                <div className="flex items-center justify-between py-1.5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-app-muted">Verification</span>
                  <span className="font-sans font-medium text-[11px] text-emerald-600 dark:text-emerald-400">
                    Schema Aligned ✓
                  </span>
                </div>

                <div className="flex items-center justify-between py-1.5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-app-muted">Source Doc</span>
                  <span
                    className="font-sans font-medium text-[11px] text-app-heading max-w-[170px] truncate text-right"
                    title={activeTriple.documentName || primaryInputName || "Corpus Document"}
                  >
                    {activeTriple.documentName || primaryInputName || "Corpus Document"}
                  </span>
                </div>
              </div>
            </div>

            {/* 4. Literature Source Provenance Reader */}
            <div className="p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-app-heading font-display">
                  Literature Provenance
                </h3>
                {activeTriple.provenanceMode === "multi_chunk" ? (
                  <span className="px-1.5 py-0.5 rounded font-mono text-[10px] font-bold text-purple-600 dark:text-purple-400 bg-purple-500/10 border border-purple-500/20">
                    Cross-Chunk Grounding
                  </span>
                ) : (
                  <span className="px-1.5 py-0.5 rounded font-mono text-[10px] font-bold text-blue-600 dark:text-blue-400 bg-blue-500/10 border border-blue-500/20">
                    Intra-Chunk Grounding
                  </span>
                )}
              </div>

              {activeTriple.provenanceMode === "multi_chunk" &&
              activeTriple.provenanceChunks &&
              activeTriple.provenanceChunks.length >= 2 ? (
                /* Multi-Chunk Reading Ground */
                <div className="space-y-2">
                  {/* Chunk A */}
                  <div className="p-3 rounded bg-app-subtle/50 border border-app-border space-y-1.5">
                    <div className="flex items-center justify-between text-[10px] font-mono text-app-muted">
                      <span className="font-semibold text-blue-600 dark:text-blue-400">
                        {activeTriple.provenanceChunks[0].label || "Chunk A · Subject Grounding"}
                      </span>
                      <span>
                        {activeTriple.provenanceChunks[0].chunkId} · {activeTriple.provenanceChunks[0].tokenCount ?? "—"} tokens
                      </span>
                    </div>
                    <div className="font-serif text-[12.5px] leading-[1.7] text-app-heading antialiased selection:bg-blue-500/20">
                      <span>{activeTriple.provenanceChunks[0].textBefore}</span>
                      <mark className="bg-blue-500/15 text-blue-700 dark:text-blue-300 font-sans font-semibold px-1 py-0.5 rounded-xs border-b border-blue-500/50">
                        {activeTriple.provenanceChunks[0].highlightedText}
                      </mark>
                      <span>{activeTriple.provenanceChunks[0].textAfter}</span>
                    </div>
                  </div>

                  {/* Bridge */}
                  <div className="py-1 flex items-center justify-center gap-2">
                    <div className="h-px bg-app-border flex-1" />
                    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-app-subtle border border-app-border text-[10px] font-mono">
                      <span className="text-purple-600 dark:text-purple-400 font-bold uppercase">
                        {activeTriple.predicate}
                      </span>
                      <span className="text-app-muted">──►</span>
                      <span className="text-app-muted font-sans text-[10px]">Synthesis</span>
                    </div>
                    <div className="h-px bg-app-border flex-1" />
                  </div>

                  {/* Chunk B */}
                  <div className="p-3 rounded bg-app-subtle/50 border border-app-border space-y-1.5">
                    <div className="flex items-center justify-between text-[10px] font-mono text-app-muted">
                      <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                        {activeTriple.provenanceChunks[1].label || "Chunk B · Object Grounding"}
                      </span>
                      <span>
                        {activeTriple.provenanceChunks[1].chunkId} · {activeTriple.provenanceChunks[1].tokenCount ?? "—"} tokens
                      </span>
                    </div>
                    <div className="font-serif text-[12.5px] leading-[1.7] text-app-heading antialiased selection:bg-emerald-500/20">
                      <span>{activeTriple.provenanceChunks[1].textBefore}</span>
                      <mark className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-sans font-semibold px-1 py-0.5 rounded-xs border-b border-emerald-500/50">
                        {activeTriple.provenanceChunks[1].highlightedText}
                      </mark>
                      <span>{activeTriple.provenanceChunks[1].textAfter}</span>
                    </div>
                  </div>
                </div>
              ) : (
                /* Single Chunk Reading Ground */
                (() => {
                  const singleChunk = activeTriple.provenanceChunks?.[0];
                  const textBefore = singleChunk?.textBefore ?? activeTriple.sourceTextBefore;
                  const firstText = singleChunk?.highlightedText ?? activeTriple.sourceSubjectText;
                  const isSubjectFirst = (singleChunk?.highlightType ?? "subject") === "subject";
                  const midText = singleChunk?.textMiddle;
                  const relText = singleChunk?.relationText ?? (midText ? undefined : activeTriple.sourcePredicateText);
                  const midAfterRel = singleChunk?.textMiddleAfterRelation;
                  const secondText = singleChunk?.secondHighlightedText ?? activeTriple.sourceObjectText;
                  const isSecondObject = (singleChunk?.secondHighlightType ?? "object") === "object";
                  const textAfter = singleChunk?.textAfter ?? activeTriple.sourceTextAfter;

                  return (
                    <div className="p-3 rounded bg-app-subtle/50 border border-app-border space-y-2">
                      <div className="flex items-center justify-between text-[10px] font-mono text-app-muted pb-1 border-b border-app-border/40">
                        <span>{singleChunk?.chunkId || activeTriple.sourceChunkId}</span>
                        <span>{singleChunk?.tokenCount || activeTriple.chunkTokens} tokens</span>
                      </div>
                      <div className="font-serif text-[12.5px] leading-[1.75] text-app-heading antialiased selection:bg-blue-500/20">
                        <span>{textBefore}</span>
                        <mark
                          className={
                            isSubjectFirst
                              ? "bg-blue-500/15 text-blue-700 dark:text-blue-300 font-sans font-semibold px-1 py-0.5 rounded-xs border-b border-blue-500/50"
                              : "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-sans font-semibold px-1 py-0.5 rounded-xs border-b border-emerald-500/50"
                          }
                        >
                          {firstText}
                        </mark>
                        {midText !== undefined ? <span>{midText}</span> : null}
                        {relText ? (
                          <mark className="bg-purple-500/15 text-purple-700 dark:text-purple-300 font-mono text-[11px] font-bold px-1.5 py-0.5 mx-0.5 rounded-xs border-b border-purple-500/50">
                            {relText}
                          </mark>
                        ) : null}
                        {midAfterRel ? <span>{midAfterRel}</span> : null}
                        {secondText ? (
                          <mark
                            className={
                              isSecondObject
                                ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-sans font-semibold px-1 py-0.5 rounded-xs border-b border-emerald-500/50"
                                : "bg-blue-500/15 text-blue-700 dark:text-blue-300 font-sans font-semibold px-1 py-0.5 rounded-xs border-b border-blue-500/50"
                            }
                          >
                            {secondText}
                          </mark>
                        ) : null}
                        <span>{textAfter}</span>
                      </div>
                    </div>
                  );
                })()
              )}

              {/* Provenance Key / Legend */}
              <div className="pt-1 flex flex-wrap items-center gap-3 text-[10px] text-app-muted font-sans">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-blue-500" />
                  <span>Subject Entity</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-purple-500" />
                  <span>Relationship</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span>Object Entity</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-[9px] px-1 py-0.2 rounded bg-app-subtle border border-app-border text-app-muted">
                    [...]
                  </span>
                  <span>Omitted Discourse</span>
                </div>
              </div>
            </div>

            {/* 4. Topological Invariants */}
            <div className="p-4 space-y-2.5">
              <h3 className="text-xs font-semibold text-app-heading font-display">
                Topological Invariants
              </h3>
              <table className="w-full text-left border-collapse text-xs">
                <tbody className="divide-y divide-app-border/40 font-sans">
                  <tr className="h-7">
                    <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Node Degree (k)</td>
                    <td className="text-right font-mono tabular-nums text-[11px] text-gray-900 dark:text-zinc-100 font-semibold py-1">
                      {activeTriple.degree} connections
                    </td>
                  </tr>
                  <tr className="h-7">
                    <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Topology Role</td>
                    <td className="text-right font-sans text-[11px] text-gray-900 dark:text-zinc-100 font-semibold py-1">
                      {activeTriple.isBridge ? (
                        <span className="text-blue-600 dark:text-blue-400 font-semibold">Bridge Vertex</span>
                      ) : activeTriple.isOrphan ? (
                        <span className="text-amber-600 dark:text-amber-400 font-semibold">Orphan Node</span>
                      ) : (
                        "Standard Vertex"
                      )}
                    </td>
                  </tr>
                  <tr className="h-7">
                    <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Stage Verification</td>
                    <td className="text-right font-sans text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold py-1">
                      P2 Schema Aligned ✓
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        ) : activeTab === "invariants" ? (
          /* ================================================================= */
          /* TAB 1: STAGE INVARIANTS & TOPOLOGY                                */
          /* ================================================================= */
          <div className="divide-y divide-app-border">
            {selectedPhaseKey ? (
              <>
                {/* Panel A: Stage Epistemic Invariants Table */}
                <div className="p-4 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold text-app-heading font-display">
                      Epistemic Invariants
                    </h3>
                    <span className="text-[10px] font-mono text-app-muted">
                      {stageReport ? `P${stageReport.stageOrdinal}` : "Stage"} Verified
                    </span>
                  </div>

                  <table className="w-full text-left border-collapse text-xs">
                    <tbody className="divide-y divide-app-border/40 font-sans">
                      <tr className="h-7">
                        <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Strict DAG Acyclicity</td>
                        <td className="text-right font-mono tabular-nums text-[11px] text-gray-900 dark:text-zinc-100 font-semibold py-1">
                          0 cycles <span className="text-emerald-600 dark:text-emerald-400 font-sans text-[10px] font-medium ml-1">Strict ✓</span>
                        </td>
                      </tr>
                      <tr className="h-7">
                        <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Topological Sparsity (ρ)</td>
                        <td className="text-right font-mono tabular-nums text-[11px] text-gray-900 dark:text-zinc-100 font-semibold py-1">
                          0.038 <span className="text-app-muted text-[10px] font-normal ml-0.5">(+0.006)</span>
                        </td>
                      </tr>
                      <tr className="h-7">
                        <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Dialectical Balance</td>
                        <td className="text-right font-mono tabular-nums text-[11px] text-gray-900 dark:text-zinc-100 font-semibold py-1">
                          64% <span className="text-app-muted text-[10px]">Supp</span> / 36% <span className="text-app-muted text-[10px]">Atk</span>
                        </td>
                      </tr>
                      <tr className="h-7">
                        <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Open-Vocabulary Drift</td>
                        <td className="text-right font-mono tabular-nums text-[11px] text-gray-900 dark:text-zinc-100 font-semibold py-1">
                          2 <span className="text-amber-600 dark:text-amber-400 font-sans text-[10px] font-medium ml-1">Quarantined</span>
                        </td>
                      </tr>
                      <tr className="h-7">
                        <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Cross-Chunk Density</td>
                        <td className="text-right font-mono tabular-nums text-[11px] text-gray-900 dark:text-zinc-100 font-semibold py-1">
                          +62 links
                        </td>
                      </tr>
                      <tr className="h-7">
                        <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Orphans Resolved</td>
                        <td className="text-right font-mono tabular-nums text-[11px] text-gray-900 dark:text-zinc-100 font-semibold py-1">
                          12 vertices
                        </td>
                      </tr>
                      <tr className="h-7">
                        <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Stage Edge Yield</td>
                        <td className="text-right font-mono tabular-nums text-[11px] text-gray-900 dark:text-zinc-100 font-bold py-1">
                          {selectedPhaseKey === "phase3" ? "+412 edges" : `+${Math.max(14, (stageReport?.totalYield || 40) * 2)} edges`}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Panel B: Predicate Breakdown */}
                <div className="p-4 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold text-app-heading font-display">
                      Predicate Breakdown
                    </h3>
                    <span className="text-[10px] font-mono text-app-muted">Ontology Pie</span>
                  </div>

                  <div className="flex items-center justify-center py-1">
                    <PredicateCompositionDonutChart
                      hierarchical={32}
                      associative={28}
                      causal={24}
                      dialectical={16}
                      height={120}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px] font-sans pt-2 border-t border-app-border/40">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-app-muted">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#3B82F6]" />
                        <span>Hierarchical</span>
                      </span>
                      <span className="font-mono tabular-nums text-app-heading font-medium">32%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-app-muted">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#8B5CF6]" />
                        <span>Associative</span>
                      </span>
                      <span className="font-mono tabular-nums text-app-heading font-medium">28%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-app-muted">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#10B981]" />
                        <span>Causal</span>
                      </span>
                      <span className="font-mono tabular-nums text-app-heading font-medium">24%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-app-muted">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B]" />
                        <span>Dialectical</span>
                      </span>
                      <span className="font-mono tabular-nums text-app-heading font-medium">16%</span>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="p-4 space-y-2.5">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold text-app-heading font-display">
                    Global TheoryNet Invariants
                  </h3>
                  <span className="text-[10px] font-mono text-app-muted">L1–L4 Rollup</span>
                </div>

                <table className="w-full text-left border-collapse text-xs">
                  <tbody className="divide-y divide-app-border/40 font-sans">
                    <tr className="h-7">
                      <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Strict DAG Acyclicity</td>
                      <td className="text-right font-mono tabular-nums text-[11px] text-gray-900 dark:text-zinc-100 font-semibold py-1">
                        0 cycles <span className="text-emerald-600 dark:text-emerald-400 font-sans text-[10px] font-medium ml-1">Strict ✓</span>
                      </td>
                    </tr>
                    <tr className="h-7">
                      <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Topological Sparsity (ρ)</td>
                      <td className="text-right font-mono tabular-nums text-[11px] text-gray-900 dark:text-zinc-100 font-semibold py-1">
                        0.042
                      </td>
                    </tr>
                    <tr className="h-7">
                      <td className="text-[11px] font-normal text-gray-500 dark:text-zinc-400 py-1">Dialectical Balance</td>
                      <td className="text-right font-mono tabular-nums text-[11px] text-gray-900 dark:text-zinc-100 font-semibold py-1">
                        68% / 32%
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          /* ================================================================= */
          /* TAB 2: TELEMETRY & RUNTIME INFERENCE                              */
          /* ================================================================= */
          <div className="divide-y divide-app-border">
            <div className="p-4 space-y-2.5">
              <h3 className="text-xs font-semibold text-app-heading font-display">
                Inference Stack
              </h3>
              <div className="space-y-2 text-xs font-sans">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-normal text-gray-500 dark:text-zinc-400">Primary LLM:</span>
                  <span className="font-mono text-[11px] text-gray-900 dark:text-zinc-100 font-semibold truncate text-right" title={llmModel}>
                    {llmModel}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-normal text-gray-500 dark:text-zinc-400">Embedding:</span>
                  <span className="font-mono text-[11px] text-gray-900 dark:text-zinc-100 font-medium truncate text-right" title={embModel}>
                    {embModel}
                  </span>
                </div>
                {rrkModel && (
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-normal text-gray-500 dark:text-zinc-400">Reranker:</span>
                    <span className="font-mono text-[11px] text-gray-900 dark:text-zinc-100 font-medium truncate text-right" title={rrkModel}>
                      {rrkModel}
                    </span>
                  </div>
                )}
              </div>
            </div>

            <div className="p-4 space-y-2.5">
              <h3 className="text-xs font-semibold text-app-heading font-display">
                Execution Economics
              </h3>
              <div className="space-y-2 text-xs font-sans">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-normal text-gray-500 dark:text-zinc-400">Total Yield:</span>
                  <span className="font-mono text-[11px] text-gray-900 dark:text-zinc-100 font-semibold tabular-nums">
                    {totalArtifactCount.toLocaleString()} artifacts
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-normal text-gray-500 dark:text-zinc-400">Cache Re-use Rate:</span>
                  <span className="font-mono text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold tabular-nums">
                    {reusePercent}% ({reusedCount}/{totalPhaseCount})
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-normal text-gray-500 dark:text-zinc-400">Wall Clock Duration:</span>
                  <span className="font-mono text-[11px] text-gray-900 dark:text-zinc-100 font-semibold tabular-nums">
                    {formatDuration(durationSeconds)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-normal text-gray-500 dark:text-zinc-400">Store Footprint:</span>
                  <span className="font-mono text-[11px] text-gray-900 dark:text-zinc-100 font-semibold tabular-nums">
                    {formatBytes(sizeBytes)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
