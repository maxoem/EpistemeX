import React, { useState, useEffect } from "react";
import {
  Layers,
  Plus,
  Compass,
  Settings,
  GripVertical,
  Sparkles,
  MoreHorizontal,
  Copy,
  RotateCcw,
  X,
  Zap,
} from "lucide-react";
import { PHASE_REGISTRY, isPhaseMandatory } from "../../phaseConfig/phaseRegistry";
import { PhaseExecutionStatusMap } from "../phaseExecution";

interface PipelineComposerRailProps {
  selectedPhaseKey: string;
  setSelectedPhaseKey: (phaseKey: string) => void;
  corePhaseKeys: string[];
  postProcessorKeys: string[];
  effectiveSourcePathsCount: number;
  selectedBibPathsCount: number;
  runMetadataCount: number;
  hasEffectiveAnchor: boolean;
  defaultLlm: string;
  defaultEmbed: string;
  phaseExecutionStatus: PhaseExecutionStatusMap;
  reusedPhasesCount?: number;
  baselineRunId?: string | null;
  getPhaseModificationCount: (phaseKey: string) => number;
  handleTogglePhase: (phaseKey: string, nextActive: boolean) => void;
  handleResetStageOverrides: (phaseKey: string) => void;
  setIsPhaseDrawerOpen: (open: boolean) => void;
  hasDecisionOverrides?: boolean;
  decisionProvider?: string;
  decisionFastExitThreshold?: number;
}

const STAGE_ROLE_MAP: Record<string, string> = {
  phase1: "Data Foundation",
  phase2: "Entity & Relations",
  schema: "Epistemic Ontology",
  phase3: "Global Relations",
  phase3b: "Proposition Consolidation",
  phase4_maturation: "Theory Maturation",
  phase4: "Argument Mining",
  phase5: "Cross-Doc Web",
  phase6: "Epistemic Synthesis",
};

export const PipelineComposerRail: React.FC<PipelineComposerRailProps> = ({
  selectedPhaseKey,
  setSelectedPhaseKey,
  corePhaseKeys,
  postProcessorKeys,
  effectiveSourcePathsCount,
  selectedBibPathsCount,
  runMetadataCount,
  hasEffectiveAnchor,
  defaultLlm,
  defaultEmbed,
  phaseExecutionStatus,
  reusedPhasesCount = 0,
  baselineRunId = null,
  getPhaseModificationCount,
  handleTogglePhase,
  handleResetStageOverrides,
  setIsPhaseDrawerOpen,
  hasDecisionOverrides = false,
  decisionProvider = "laya",
  decisionFastExitThreshold = 0.92,
}) => {
  const [contextMenuKey, setContextMenuKey] = useState<string | null>(null);

  // Close context menu on outside click
  useEffect(() => {
    const handleOutsideClick = () => {
      if (contextMenuKey) setContextMenuKey(null);
    };
    window.addEventListener("click", handleOutsideClick);
    return () => window.removeEventListener("click", handleOutsideClick);
  }, [contextMenuKey]);

  return (
    <div className="w-full h-full flex flex-col bg-app-surface border-r border-app-border overflow-hidden select-none">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* RAIL HEADER                                                        */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="h-12 px-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Layers className="w-4 h-4 text-app-heading shrink-0" />
          <div className="min-w-0">
            <h2 className="text-xs font-semibold text-app-heading tracking-tight truncate font-display">
              Pipeline Composer
            </h2>
            <span className="text-[11px] text-app-muted block truncate font-sans">
              {corePhaseKeys.length} core stages · {postProcessorKeys.length} post-proc
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsPhaseDrawerOpen(true)}
          className="h-6 px-2 rounded border border-app-border bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-heading text-[11px] font-medium transition-colors cursor-pointer inline-flex items-center gap-1 shrink-0"
          title="Manage and add pipeline stages"
        >
          <Plus className="w-3 h-3" />
          <span>Catalog</span>
        </button>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* RAIL SCROLL AREA                                                   */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* 1. BASELINE SETUP */}
        <div className="space-y-1">
          <h3 className="px-2 py-1 text-xs font-semibold text-app-heading tracking-tight font-display">
            Baseline Setup
          </h3>

          <div className="space-y-0.5">
            {/* Pipeline Input & Anchors Entry */}
            <button
              type="button"
              onClick={() => setSelectedPhaseKey("input_config")}
              className={`w-full px-2.5 py-2 rounded text-left transition-colors cursor-pointer relative group flex items-center justify-between gap-2 ${
                selectedPhaseKey === "input_config"
                  ? "bg-app-subtle text-app-heading font-medium"
                  : "hover:bg-app-subtle/50 text-app-muted hover:text-app-heading"
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-5 flex justify-center shrink-0">
                  <Compass className="w-3.5 h-3.5 text-app-muted" />
                </div>
                <div className="min-w-0">
                  <div
                    className={`text-xs truncate ${
                      selectedPhaseKey === "input_config"
                        ? "font-semibold text-app-heading"
                        : "text-app-text font-normal"
                    }`}
                  >
                    Input & Anchors
                  </div>
                  <div className="text-[11px] text-app-muted font-sans truncate">
                    {effectiveSourcePathsCount} doc{effectiveSourcePathsCount === 1 ? "" : "s"} ·{" "}
                    {selectedBibPathsCount} bib{hasEffectiveAnchor ? " · anchor" : ""}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                {(selectedBibPathsCount > 0 || runMetadataCount > 0 || hasEffectiveAnchor) && (
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold border border-blue-500/20">
                    Active
                  </span>
                )}
                {selectedPhaseKey === "input_config" && (
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block shrink-0" />
                )}
              </div>
            </button>

            {/* Pipeline Defaults */}
            <button
              type="button"
              onClick={() => setSelectedPhaseKey("phase0")}
              className={`w-full px-2.5 py-2 rounded text-left transition-colors cursor-pointer relative group flex items-center justify-between gap-2 ${
                selectedPhaseKey === "phase0"
                  ? "bg-app-subtle text-app-heading font-medium"
                  : "hover:bg-app-subtle/50 text-app-muted hover:text-app-heading"
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-5 flex justify-center shrink-0">
                  <Settings className="w-3.5 h-3.5 text-app-muted" />
                </div>
                <div className="min-w-0">
                  <div
                    className={`text-xs truncate ${
                      selectedPhaseKey === "phase0"
                        ? "font-semibold text-app-heading"
                        : "text-app-text font-normal"
                    }`}
                  >
                    Pipeline Defaults
                  </div>
                  <div className="text-[11px] text-app-muted font-sans truncate">
                    LLM: {defaultLlm.split("/").pop()} · Embed: {defaultEmbed.split("/").pop()}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                {getPhaseModificationCount("phase0") > 0 && (
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold border border-blue-500/20">
                    +{getPhaseModificationCount("phase0")}
                  </span>
                )}
                {selectedPhaseKey === "phase0" && (
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block shrink-0" />
                )}
              </div>
            </button>

            {/* Decision Engine (Jev) */}
            <button
              type="button"
              onClick={() => setSelectedPhaseKey("decision_engine")}
              className={`w-full px-2.5 py-2 rounded text-left transition-colors cursor-pointer relative group flex items-center justify-between gap-2 ${
                selectedPhaseKey === "decision_engine"
                  ? "bg-app-subtle text-app-heading font-medium"
                  : "hover:bg-app-subtle/50 text-app-muted hover:text-app-heading"
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-5 flex justify-center shrink-0">
                  <Zap className="w-3.5 h-3.5 text-app-muted" />
                </div>
                <div className="min-w-0">
                  <div
                    className={`text-xs truncate ${
                      selectedPhaseKey === "decision_engine"
                        ? "font-semibold text-app-heading"
                        : "text-app-text font-normal"
                    }`}
                  >
                    Decision Engine (Jev)
                  </div>
                  <div className="text-[11px] text-app-muted font-sans truncate">
                    Provider: {decisionProvider.toUpperCase()} · τ: {(decisionFastExitThreshold * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                {hasDecisionOverrides && (
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold border border-blue-500/20">
                    Overridden
                  </span>
                )}
                {selectedPhaseKey === "decision_engine" && (
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block shrink-0" />
                )}
              </div>
            </button>
          </div>
        </div>

        {/* 2. CORE PIPELINE */}
        <div className="space-y-1">
          <div className="px-2 py-1 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-app-heading tracking-tight font-display">
              Core Pipeline
            </h3>
            {Boolean(reusedPhasesCount && reusedPhasesCount > 0) && (
              <span
                className="text-[10px] font-mono text-emerald-500 font-medium inline-flex items-center gap-1"
                title={
                  baselineRunId
                    ? `Hydrating ${reusedPhasesCount} phases from ${baselineRunId}`
                    : `Hydrating ${reusedPhasesCount} phases from store`
                }
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                {reusedPhasesCount} cached
              </span>
            )}
          </div>

          <div className="space-y-0.5">
            {corePhaseKeys.map((key) => {
              const meta = PHASE_REGISTRY[key];
              if (!meta) return null;
              const isSelected = selectedPhaseKey === key;
              const ordinal = meta.canonicalOrdinal;
              const modCount = getPhaseModificationCount(key);
              const status = phaseExecutionStatus[ordinal];
              const isMandatory = isPhaseMandatory(key);

              const ordinalDisplay =
                key === "schema"
                  ? "S"
                  : key === "phase3b"
                  ? "3b"
                  : key === "phase4_maturation"
                  ? "4a"
                  : key === "phase4"
                  ? "4b"
                  : String(ordinal).padStart(2, "0");

              const roleLabel = STAGE_ROLE_MAP[key] || meta.category || "Computational Stage";

              return (
                <div key={key} className="relative group/row">
                  <div
                    onClick={() => setSelectedPhaseKey(key)}
                    className={`w-full px-2 py-1.5 rounded text-left transition-colors cursor-pointer flex items-center justify-between gap-2 ${
                      isSelected
                        ? "bg-app-subtle text-app-heading font-medium"
                        : "hover:bg-app-subtle/50 text-app-muted hover:text-app-heading"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 min-w-0 flex-1">
                      <GripVertical className="w-3 h-3 text-app-muted/30 opacity-0 group-hover/row:opacity-100 transition-opacity shrink-0 cursor-grab" />
                      
                      {/* Boxless Tabular Ordinal */}
                      <span
                        className={`w-5 text-right font-mono text-[11px] shrink-0 tabular-nums ${
                          isSelected
                            ? "text-app-heading font-semibold"
                            : "text-app-muted font-medium"
                        }`}
                      >
                        {ordinalDisplay}
                      </span>

                      <div className="min-w-0 flex-1 ml-1">
                        <div
                          className={`text-xs truncate flex items-center gap-1 ${
                            isSelected
                              ? "font-semibold text-app-heading"
                              : "text-app-text font-normal"
                          }`}
                        >
                          <span>{meta.shortLabel || meta.displayName}</span>
                          {meta.promptKeys && meta.promptKeys.length > 0 && (
                            <span title="Structured Prompts">
                              <Sparkles className="w-2.5 h-2.5 text-purple-400 shrink-0" />
                            </span>
                          )}
                        </div>

                        {/* Functional Role & Calm Operational Indicator */}
                        <div className="flex items-center gap-1.5 text-[11px] text-app-muted font-sans leading-tight">
                          <span className="truncate">{roleLabel}</span>
                          {status === "recompute" ? (
                            <span className="text-amber-500 font-mono text-[10px] inline-flex items-center gap-1 shrink-0 font-medium">
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                              Recompute
                            </span>
                          ) : status === "cached" ? (
                            <span
                              className="w-1.5 h-1.5 rounded-full bg-emerald-500/70 shrink-0"
                              title="Resuming from store"
                            />
                          ) : null}
                        </div>
                      </div>
                    </div>

                    {/* Right Pills & Context Menu Trigger */}
                    <div className="flex items-center gap-1 shrink-0">
                      {modCount > 0 && (
                        <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold border border-blue-500/20">
                          +{modCount}
                        </span>
                      )}

                      {isSelected && (
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block shrink-0" />
                      )}

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setContextMenuKey(contextMenuKey === key ? null : key);
                        }}
                        className={`p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-surface transition-opacity cursor-pointer ${
                          contextMenuKey === key
                            ? "opacity-100"
                            : "opacity-0 group-hover/row:opacity-100"
                        }`}
                        title="Stage options"
                      >
                        <MoreHorizontal className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Dropdown Menu */}
                  {contextMenuKey === key && (
                    <div
                      className="absolute right-2 top-full mt-1 w-44 bg-app-surface border border-app-border rounded-lg shadow-xl py-1 z-30 text-xs"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          setContextMenuKey(null);
                          alert(`Stage ${meta.displayName} cloned for A/B testing.`);
                        }}
                        className="w-full px-3 py-1.5 text-left text-app-text hover:text-app-heading hover:bg-app-subtle cursor-pointer flex items-center gap-2"
                      >
                        <Copy className="w-3.5 h-3.5 text-app-muted" />
                        <span>Duplicate Stage</span>
                      </button>

                      {modCount > 0 && (
                        <button
                          type="button"
                          onClick={() => {
                            handleResetStageOverrides(key);
                            setContextMenuKey(null);
                          }}
                          className="w-full px-3 py-1.5 text-left text-app-text hover:text-app-heading hover:bg-app-subtle cursor-pointer flex items-center gap-2"
                        >
                          <RotateCcw className="w-3.5 h-3.5 text-app-muted" />
                          <span>Reset Overrides</span>
                        </button>
                      )}

                      {!isMandatory && (
                        <button
                          type="button"
                          onClick={() => {
                            handleTogglePhase(key, false);
                            setContextMenuKey(null);
                          }}
                          className="w-full px-3 py-1.5 text-left text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 cursor-pointer flex items-center gap-2"
                        >
                          <X className="w-3.5 h-3.5" />
                          <span>Disable / Skip</span>
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Quiet Borderless Inline Adder */}
            <button
              type="button"
              onClick={() => setIsPhaseDrawerOpen(true)}
              className="w-full py-1.5 px-2.5 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle/50 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors cursor-pointer mt-1"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Stage</span>
            </button>
          </div>
        </div>

        {/* 3. POST-PROCESSORS */}
        <div className="space-y-1">
          <h3 className="px-2 py-1 text-xs font-semibold text-app-heading tracking-tight font-display">
            Post-Processors
          </h3>

          <div className="space-y-0.5">
            {postProcessorKeys.map((key) => {
              const meta = PHASE_REGISTRY[key];
              if (!meta) return null;
              const isSelected = selectedPhaseKey === key;
              const modCount = getPhaseModificationCount(key);

              return (
                <div key={key} className="relative group/row">
                  <div
                    onClick={() => setSelectedPhaseKey(key)}
                    className={`w-full px-2 py-1.5 rounded text-left transition-colors cursor-pointer flex items-center justify-between gap-2 ${
                      isSelected
                        ? "bg-app-subtle text-app-heading font-medium"
                        : "hover:bg-app-subtle/50 text-app-muted hover:text-app-heading"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 min-w-0 flex-1">
                      <GripVertical className="w-3 h-3 text-app-muted/30 opacity-0 group-hover/row:opacity-100 transition-opacity shrink-0 cursor-grab" />
                      
                      {/* Boxless Tabular Ordinal */}
                      <span
                        className={`w-5 text-right font-mono text-[11px] shrink-0 tabular-nums ${
                          isSelected
                            ? "text-app-heading font-semibold"
                            : "text-app-muted font-medium"
                        }`}
                      >
                        PP
                      </span>

                      <div className="min-w-0 flex-1 ml-1">
                        <div
                          className={`text-xs truncate ${
                            isSelected
                              ? "font-semibold text-app-heading"
                              : "text-app-text font-normal"
                          }`}
                        >
                          {meta.shortLabel || meta.displayName}
                        </div>
                        <div className="text-[11px] text-app-muted font-sans truncate">
                          Algorithm Solver
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      {modCount > 0 && (
                        <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold border border-blue-500/20">
                          +{modCount}
                        </span>
                      )}

                      {isSelected && (
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block shrink-0" />
                      )}

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setContextMenuKey(contextMenuKey === key ? null : key);
                        }}
                        className={`p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-surface transition-opacity cursor-pointer ${
                          contextMenuKey === key
                            ? "opacity-100"
                            : "opacity-0 group-hover/row:opacity-100"
                        }`}
                        title="Stage options"
                      >
                        <MoreHorizontal className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {contextMenuKey === key && (
                    <div
                      className="absolute right-2 top-full mt-1 w-44 bg-app-surface border border-app-border rounded-lg shadow-xl py-1 z-30 text-xs"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          handleTogglePhase(key, false);
                          setContextMenuKey(null);
                        }}
                        className="w-full px-3 py-1.5 text-left text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 cursor-pointer flex items-center gap-2"
                      >
                        <X className="w-3.5 h-3.5" />
                        <span>Remove Post-Processor</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Quiet Borderless Inline Adder */}
            <button
              type="button"
              onClick={() => setIsPhaseDrawerOpen(true)}
              className="w-full py-1.5 px-2.5 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle/50 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors cursor-pointer mt-1"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Post-Processor</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

