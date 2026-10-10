import React from "react";
import {Activity, CheckCircle2, Loader2, RotateCcw, Save, X,} from "lucide-react";
import {SelectedItem} from "../types";
import {SchemaConfig, UnmappedPredicateInfo} from "../../../api/types";
import {DemoEditHistory, DemoValidationRules} from "./DemoMetadataInspector";

interface ContextualInspectorRailProps {
  selectedItem: SelectedItem | null;
  onDeselect: () => void;
  draftSchema: SchemaConfig;
  onUpdateSchema: (nextSchema: SchemaConfig) => void;
  draftAliases: Record<string, any>;
  onUpdateAliases: (nextAliases: Record<string, any>) => void;
  unmappedPredicates: UnmappedPredicateInfo[];
  onQuickMap: (predicate: string, polarity: -1 | 0 | 1, canonical?: string) => Promise<void>;
  allCanonicalRelations: string[];
  hasUnsavedChanges: boolean;
  isSaving: boolean;
  saveSuccess: boolean;
  onSave: () => Promise<void>;
  onReset: () => Promise<void>;
  totalEntityCount: number;
  totalRelationCount: number;
  totalAliasesCount: number;
  draftModels: any;
  draftDecisionEngine?: any;
  activeCategory?: string;
}

export const ContextualInspectorRail: React.FC<ContextualInspectorRailProps> = ({
  selectedItem,
  onDeselect,
  draftSchema,
  onUpdateSchema,
  draftAliases,
  onUpdateAliases,
  unmappedPredicates,
  onQuickMap,
  allCanonicalRelations,
  hasUnsavedChanges,
  isSaving,
  saveSuccess,
  onSave,
  onReset,
  totalEntityCount,
  totalRelationCount,
  totalAliasesCount,
  draftModels,
  draftDecisionEngine,
  activeCategory,
}) => {
  // Helper to extract item definition based on type
  const getItemDefinition = (): string => {
    if (!selectedItem) return "";
    switch (selectedItem.type) {
      case "node":
        return draftSchema.node_definitions?.[selectedItem.id] || "";
      case "relation":
        return draftSchema.relation_definitions?.[selectedItem.id] || "";
      case "component":
        return draftSchema.component_definitions?.[selectedItem.id] || "";
      case "arg_relation":
        return draftSchema.argument_relation_definitions?.[selectedItem.id] || "";
      case "alias": {
        const entry = draftAliases[selectedItem.id];
        return typeof entry === "object" ? entry?.definition || "" : "";
      }
      case "unmapped_predicate":
        return "";
      default:
        return "";
    }
  };

  // Helper to update definition in draft schema
  const handleDefinitionChange = (newDef: string) => {
    if (!selectedItem) return;
    if (selectedItem.type === "node") {
      onUpdateSchema({
        ...draftSchema,
        node_definitions: {
          ...draftSchema.node_definitions,
          [selectedItem.id]: newDef,
        },
      });
    } else if (selectedItem.type === "relation") {
      onUpdateSchema({
        ...draftSchema,
        relation_definitions: {
          ...draftSchema.relation_definitions,
          [selectedItem.id]: newDef,
        },
      });
    } else if (selectedItem.type === "component") {
      onUpdateSchema({
        ...draftSchema,
        component_definitions: {
          ...draftSchema.component_definitions,
          [selectedItem.id]: newDef,
        },
      });
    } else if (selectedItem.type === "arg_relation") {
      onUpdateSchema({
        ...draftSchema,
        argument_relation_definitions: {
          ...draftSchema.argument_relation_definitions,
          [selectedItem.id]: newDef,
        },
      });
    } else if (selectedItem.type === "alias") {
      const prev = draftAliases[selectedItem.id];
      const nextEntry =
        typeof prev === "object"
          ? { ...prev, definition: newDef }
          : { polarity: prev ?? 0, definition: newDef };
      onUpdateAliases({
        ...draftAliases,
        [selectedItem.id]: nextEntry,
      });
    }
  };

  // Find linked aliases pointing to this item if it's a relation
  const linkedAliases = React.useMemo(() => {
    if (!selectedItem || (selectedItem.type !== "relation" && selectedItem.type !== "arg_relation")) {
      return [];
    }
    return Object.entries(draftAliases)
      .filter(([_, details]) => typeof details === "object" && details?.canonical === selectedItem.id)
      .map(([alias]) => alias);
  }, [selectedItem, draftAliases]);

  // Selected unmapped item lookup
  const selectedUnmappedInfo = React.useMemo(() => {
    if (!selectedItem || selectedItem.type !== "unmapped_predicate") return null;
    return unmappedPredicates.find((p) => p.predicate === selectedItem.id) || null;
  }, [selectedItem, unmappedPredicates]);

  const definitionText = getItemDefinition();

  return (
    <div className="w-full h-full flex flex-col bg-app-surface border-l border-app-border overflow-hidden select-none">
      {/* ───────────────────────────────────────────────────────────────── */}
      {/* 1. ANCHORED RAIL HEADER & ACTIONS (Unified, Compact CTA)          */}
      {/* ───────────────────────────────────────────────────────────────── */}
      <div className="h-12 px-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Activity className="w-4 h-4 text-app-text shrink-0" />
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <h2 className="font-sans font-semibold text-[13px] text-app-text tracking-tight truncate">
                Contextual Inspector
              </h2>
              {hasUnsavedChanges ? (
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse shrink-0" title="Unsaved changes" />
              ) : (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" title="Synced to disk" />
              )}
            </div>
            <span className="font-sans text-[11px] text-app-muted block truncate">
              {selectedItem ? `Inspecting ${selectedItem.id}` : "Domain Overview"}
            </span>
          </div>
        </div>

        {/* Compact Right Actions: Reset + Primary Action Save */}
        <div className="flex items-center gap-1.5 shrink-0">
          {hasUnsavedChanges && (
            <button
              type="button"
              onClick={onReset}
              disabled={isSaving}
              className="h-[28px] px-2.5 rounded-[4px] border border-app-border bg-app-bg hover:bg-app-subtle text-app-muted text-[11px] font-sans font-medium transition-colors cursor-pointer disabled:opacity-40 flex items-center gap-1"
              title="Reset engine settings to defaults"
            >
              <RotateCcw className="w-3 h-3" />
              <span className="hidden sm:inline">Reset</span>
            </button>
          )}

          <button
            type="button"
            onClick={onSave}
            disabled={isSaving || !hasUnsavedChanges}
            className={`h-[28px] px-3 rounded-[4px] font-sans font-medium text-[11px] transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
              hasUnsavedChanges
                ? "bg-[#2563EB] hover:bg-blue-600 active:bg-blue-700 text-[#FFFFFF]"
                : "bg-[#2563EB] text-[#FFFFFF]"
            }`}
            title={hasUnsavedChanges ? "Save changes to disk" : "All changes committed to disk"}
          >
            {isSaving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Saving...</span>
              </>
            ) : (
              <>
                <Save className="w-3.5 h-3.5" />
                <span>Save</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* ───────────────────────────────────────────────────────────────── */}
      {/* 2. SCROLLABLE INSPECTOR BODY (Master-Detail Pattern)               */}
      {/* ───────────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 select-text">
        {saveSuccess && (
          <div className="p-2.5 rounded-[4px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs flex items-center gap-1.5 shrink-0 animate-in fade-in">
            <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
            <span>Settings successfully committed to disk</span>
          </div>
        )}

        {selectedItem ? (
          <div className="space-y-4">
            {/* Node Metadata Identity Block */}
            <div className="bg-app-surface border border-app-border rounded-[4px] p-3 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <h3
                  className="font-display text-[16px] font-semibold text-app-text leading-snug truncate"
                  title={selectedItem.id}
                >
                  {selectedItem.id}
                </h3>
                <button
                  type="button"
                  onClick={onDeselect}
                  className="p-1 rounded hover:bg-app-subtle dark:hover:bg-white/10 text-app-muted hover:text-app-text transition-colors cursor-pointer shrink-0"
                  title="Close Inspector"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Attributes Grid (2-column key-value rows) */}
              <div className="space-y-1.5">
                <div className="grid grid-cols-[80px_1fr] items-center gap-2">
                  <span className="font-sans text-[11px] font-medium text-app-muted">
                    Scope
                  </span>
                  <span className="font-mono text-[11px] font-normal text-app-text text-right truncate">
                    schema.{selectedItem.type === "node" ? "node_types" : selectedItem.type === "relation" ? "relation_types" : selectedItem.type === "component" ? "component_types" : selectedItem.type === "arg_relation" ? "argument_relation_types" : selectedItem.type === "alias" ? "predicate_aliases" : "unmapped_predicates"}
                  </span>
                </div>
                <div className="grid grid-cols-[80px_1fr] items-center gap-2">
                  <span className="font-sans text-[11px] font-medium text-app-muted">
                    Identifier
                  </span>
                  <span className="font-mono text-[11px] font-normal text-app-text text-right truncate">
                    {selectedItem.id}
                  </span>
                </div>
              </div>
            </div>

            {/* A. Semantic Prompt Guidance Section */}
            {selectedItem.type !== "unmapped_predicate" && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-sans text-[12px] font-semibold text-app-text">
                    Semantic Prompt Guidance
                  </span>
                  <span className="font-mono text-[10px] font-normal text-app-muted uppercase">
                    {definitionText.length} CHARS
                  </span>
                </div>

                <textarea
                  value={definitionText}
                  onChange={(e) => handleDefinitionChange(e.target.value)}
                  rows={5}
                  placeholder="Enter full multi-paragraph extraction criteria and prompt guidance for this schema element..."
                  className="w-full p-[10px] rounded-[4px] bg-app-subtle text-app-text font-sans text-[13px] leading-[18px] border border-app-border focus:bg-app-bg focus:border-[#2563EB] focus:outline-none placeholder:text-app-muted/50 resize-y transition-colors"
                />
                <span className="font-sans text-[11px] text-app-muted block leading-normal">
                  Injected into extraction prompts to define taxonomy boundaries and contextual grounding.
                </span>
              </div>
            )}

            {/* B. Specific Type Modifiers */}
            {/* Component Partition Toggle */}
            {selectedItem.type === "component" && (
              <div className="space-y-2 pt-1">
                <span className="font-sans text-[12px] font-semibold text-app-text block">
                  Theory Partition Assignment
                </span>
                <div className="p-0.5 inline-flex items-center bg-app-subtle/60 rounded-[4px] border border-app-border/60 gap-0.5 text-xs font-mono w-full">
                  <button
                    type="button"
                    onClick={() => {
                      onUpdateSchema({
                        ...draftSchema,
                        component_partitions: {
                          ...draftSchema.component_partitions,
                          [selectedItem.id]: "A",
                        },
                      });
                    }}
                    className={`flex-1 py-1 px-2 rounded-[3px] transition-all cursor-pointer text-center ${
                      draftSchema.component_partitions?.[selectedItem.id] === "A"
                        ? "bg-app-bg text-purple-700 dark:text-purple-400 font-semibold border border-app-border dark:border-purple-500/30 shadow-2xs"
                        : "text-app-muted hover:text-app-text"
                    }`}
                  >
                    Part. A (Theoretical Core)
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onUpdateSchema({
                        ...draftSchema,
                        component_partitions: {
                          ...draftSchema.component_partitions,
                          [selectedItem.id]: "B",
                        },
                      });
                    }}
                    className={`flex-1 py-1 px-2 rounded-[3px] transition-all cursor-pointer text-center ${
                      draftSchema.component_partitions?.[selectedItem.id] !== "A"
                        ? "bg-app-bg text-blue-700 dark:text-blue-400 font-semibold border border-app-border dark:border-blue-500/30 shadow-2xs"
                        : "text-app-muted hover:text-app-text"
                    }`}
                  >
                    Part. B (Empirical Data)
                  </button>
                </div>
              </div>
            )}

            {/* Argument Relation Polarity Toggle */}
            {selectedItem.type === "arg_relation" && (
              <div className="space-y-2 pt-1">
                <span className="font-sans text-[12px] font-semibold text-app-text block">
                  Dialectical Polarity Weight
                </span>
                <div className="p-0.5 inline-flex items-center bg-app-subtle/60 rounded-[4px] border border-app-border/60 gap-0.5 text-xs font-mono w-full">
                  <button
                    type="button"
                    onClick={() => {
                      onUpdateSchema({
                        ...draftSchema,
                        relation_polarities: {
                          ...draftSchema.relation_polarities,
                          [selectedItem.id]: 1,
                        },
                      });
                    }}
                    className={`flex-1 py-1 rounded-[3px] transition-all cursor-pointer text-center ${
                      (draftSchema.relation_polarities?.[selectedItem.id] ?? 0) === 1
                        ? "bg-app-bg text-emerald-700 dark:text-emerald-400 font-semibold border border-app-border dark:border-emerald-500/30 shadow-2xs"
                        : "text-app-muted hover:text-app-text"
                    }`}
                  >
                    +1 Support
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onUpdateSchema({
                        ...draftSchema,
                        relation_polarities: {
                          ...draftSchema.relation_polarities,
                          [selectedItem.id]: 0,
                        },
                      });
                    }}
                    className={`flex-1 py-1 rounded-[3px] transition-all cursor-pointer text-center ${
                      (draftSchema.relation_polarities?.[selectedItem.id] ?? 0) === 0
                        ? "bg-app-bg text-app-text font-semibold border border-app-border shadow-2xs"
                        : "text-app-muted hover:text-app-text"
                    }`}
                  >
                    0 Neutral
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onUpdateSchema({
                        ...draftSchema,
                        relation_polarities: {
                          ...draftSchema.relation_polarities,
                          [selectedItem.id]: -1,
                        },
                      });
                    }}
                    className={`flex-1 py-1 rounded-[3px] transition-all cursor-pointer text-center ${
                      (draftSchema.relation_polarities?.[selectedItem.id] ?? 0) === -1
                        ? "bg-app-bg text-rose-700 dark:text-rose-400 font-semibold border border-app-border dark:border-rose-500/30 shadow-2xs"
                        : "text-app-muted hover:text-app-text"
                    }`}
                  >
                    -1 Attack
                  </button>
                </div>
              </div>
            )}

            {/* Unmapped Predicate Deep Actions */}
            {selectedItem.type === "unmapped_predicate" && selectedUnmappedInfo && (
              <div className="space-y-2.5 pt-1 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-sans text-[12px] font-semibold text-app-text">
                    Runtime Occurrences
                  </span>
                  <span className="font-mono font-bold text-amber-600 dark:text-amber-400">
                    {selectedUnmappedInfo.occurrences} hits
                  </span>
                </div>

                <div className="space-y-1">
                  <span className="font-sans text-[12px] font-semibold text-app-text">
                    Sample Run Inferences:
                  </span>
                  <div className="p-2 rounded-[4px] bg-app-bg dark:bg-app-subtle font-mono text-[11px] text-app-muted max-h-24 overflow-y-auto space-y-0.5 border border-app-border/60">
                    {selectedUnmappedInfo.sample_runs.map((r, i) => (
                      <div key={i} className="truncate">• {r}</div>
                    ))}
                  </div>
                </div>

                <div className="space-y-1.5 pt-2 border-t border-app-border">
                  <span className="font-sans text-[12px] font-semibold text-app-text block">
                    Map to Canonical Target:
                  </span>
                  <select
                    defaultValue=""
                    onChange={(e) => {
                      const canonical = e.target.value;
                      if (!canonical) return;
                      const pol = draftSchema.relation_polarities?.[canonical] ?? 0;
                      onQuickMap(selectedItem.id, pol as -1 | 0 | 1, canonical);
                      e.target.value = "";
                    }}
                    className="w-full h-7 px-2 rounded-[4px] bg-app-bg dark:bg-app-subtle text-app-text border border-app-border text-xs font-mono focus:outline-none focus:border-[#2563EB]"
                  >
                    <option value="">Select Target Relation...</option>
                    {allCanonicalRelations.map((r) => (
                      <option key={r} value={r}>
                        → {r}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-3 gap-1 pt-1 font-mono text-[11px]">
                  <button
                    type="button"
                    onClick={() => onQuickMap(selectedItem.id, 1, "SUPPORTS")}
                    className="h-6 rounded-[4px] bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/25 border border-emerald-500/25 cursor-pointer font-medium"
                  >
                    +1 Supp.
                  </button>
                  <button
                    type="button"
                    onClick={() => onQuickMap(selectedItem.id, 0, "RELATED_TO")}
                    className="h-6 rounded-[4px] bg-app-bg dark:bg-app-subtle text-app-muted hover:text-app-text border border-app-border cursor-pointer font-medium"
                  >
                    0 Neut.
                  </button>
                  <button
                    type="button"
                    onClick={() => onQuickMap(selectedItem.id, -1, "ATTACKS")}
                    className="h-6 rounded-[4px] bg-rose-500/15 text-rose-600 dark:text-rose-400 hover:bg-rose-500/25 border border-rose-500/25 cursor-pointer font-medium"
                  >
                    -1 Attack
                  </button>
                </div>
              </div>
            )}

            {/* Mapped Aliases List (if relation) */}
            {linkedAliases.length > 0 && (
              <div className="space-y-1.5 pt-2 border-t border-app-border">
                <div className="flex items-center justify-between">
                  <span className="font-sans text-[12px] font-semibold text-app-text">
                    Mapped Aliases
                  </span>
                  <span className="font-mono text-[10px] font-normal text-app-muted">
                    {linkedAliases.length} aliases
                  </span>
                </div>
                <div className="flex flex-wrap gap-1 pt-0.5">
                  {linkedAliases.map((alias) => (
                    <span
                      key={alias}
                      className="px-1.5 py-0.5 rounded-[4px] bg-app-bg dark:bg-app-subtle text-app-text font-mono text-[11px] border border-app-border/70"
                    >
                      {alias}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* C. SOLID Demo Subcomponents: Validation Rules & Audit History */}
            <DemoValidationRules itemId={selectedItem.id} itemType={selectedItem.type} />
            <DemoEditHistory itemId={selectedItem.id} itemType={selectedItem.type} />
          </div>
        ) : (
          /* Fallback: Domain Overview and Telemetry */
          <div className="space-y-4">
            <div className="space-y-1 pb-3 border-b border-app-border/70">
              <div className="font-sans text-[12px] font-semibold text-app-text">
                Domain Overview
              </div>
              <p className="font-sans text-[12px] text-app-muted leading-relaxed">
                Click any row in the center workspace table to inspect and edit its prompt criteria, validation heuristics, and runtime aliases.
              </p>
            </div>

            {/* High-Density Structural Epistemic Telemetry */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="font-sans text-[12px] font-semibold text-app-text">
                  Structural Telemetry
                </span>
                <span className="text-[10px] font-mono text-app-muted">
                  Epistemic Graph
                </span>
              </div>

              {/* High-density Key-Value Telemetry Table */}
              <div className="rounded-[4px] bg-app-surface border border-app-border overflow-hidden divide-y divide-app-border">
                <div className="px-3 py-2 flex items-center justify-between text-xs">
                  <span className="font-sans text-app-muted text-[11px]">
                    Topological Sparsity
                  </span>
                  <span
                    className="font-mono font-medium text-app-text"
                    style={{ fontFeatureSettings: '"tnum" 1' }}
                  >
                    0.042
                  </span>
                </div>

                <div className="px-3 py-2 flex items-center justify-between text-xs">
                  <span className="font-sans text-app-muted text-[11px]">
                    DAG Acyclicity (Cycles)
                  </span>
                  <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                    0.00 (Strict DAG)
                  </span>
                </div>

                <div className="px-3 py-2 flex items-center justify-between text-xs">
                  <span className="font-sans text-app-muted text-[11px]">
                    Dialectical Balance
                  </span>
                  <div className="flex items-center gap-1.5 font-mono text-[11px]">
                    <span className="text-emerald-600 dark:text-emerald-400 font-medium">64% Supp</span>
                    <span className="text-app-muted">/</span>
                    <span className="text-rose-600 dark:text-rose-400 font-medium">36% Atk</span>
                  </div>
                </div>

                <div className="px-3 py-2 flex items-center justify-between text-xs">
                  <span className="font-sans text-app-muted text-[11px]">
                    Contradiction Rate
                  </span>
                  <span
                    className="font-mono font-medium text-amber-600 dark:text-amber-400"
                    style={{ fontFeatureSettings: '"tnum" 1' }}
                  >
                    1.4%
                  </span>
                </div>

                <div className="px-3 py-2 flex items-center justify-between text-xs">
                  <span className="font-sans text-app-muted text-[11px]">
                    Open-Vocabulary Drift
                  </span>
                  <span
                    className={`font-mono font-semibold ${
                      unmappedPredicates.length > 0 ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400"
                    }`}
                    style={{ fontFeatureSettings: '"tnum" 1' }}
                  >
                    {unmappedPredicates.length} pending
                  </span>
                </div>
              </div>

              {/* Ontological Distribution Summary Bar */}
              <div className="p-3 rounded-[4px] bg-app-surface border border-app-border space-y-2">
                <div className="flex items-center justify-between text-[11px] font-sans">
                  <span className="text-app-muted">Ontological Schema Classes</span>
                  <span className="font-mono font-medium text-app-text">
                    {totalEntityCount + totalRelationCount} total
                  </span>
                </div>

                <div className="h-1.5 w-full bg-app-border rounded-full overflow-hidden flex">
                  <div
                    className="h-full bg-blue-500"
                    style={{
                      width: `${(totalEntityCount / (totalEntityCount + totalRelationCount || 1)) * 100}%`,
                    }}
                    title={`Entities: ${totalEntityCount}`}
                  />
                  <div
                    className="h-full bg-purple-500"
                    style={{
                      width: `${(totalRelationCount / (totalEntityCount + totalRelationCount || 1)) * 100}%`,
                    }}
                    title={`Relations: ${totalRelationCount}`}
                  />
                </div>

                <div className="flex items-center justify-between text-[10px] font-mono text-app-muted">
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                    {totalEntityCount} Entities ({draftSchema.node_types?.length || 0} nodes, {draftSchema.component_types?.length || 0} comps)
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                    {totalRelationCount} Relations ({draftSchema.relation_types?.length || 0} dom, {draftSchema.argument_relation_types?.length || 0} arg)
                  </span>
                </div>
              </div>
            </div>

            {/* Model / Decision Engine Telemetry */}
            {activeCategory === "decision" ? (
              <div className="space-y-2 pt-2 border-t border-app-border/70">
                <div className="flex items-center justify-between">
                  <div className="font-sans text-[12px] font-semibold text-app-text">
                    Decision Engine Telemetry
                  </div>
                  <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20 font-medium">
                    Dual-Process
                  </span>
                </div>
                <div className="space-y-1.5 text-xs">
                  <div className="font-mono text-xs text-app-text truncate font-medium" title={draftDecisionEngine?.model_checkpoint}>
                    {draftDecisionEngine?.model_checkpoint || "aac6fef/laya-mlx"}
                  </div>
                  <div className="text-[10px] font-mono text-app-muted flex items-center justify-between">
                    <span>Provider: {(draftDecisionEngine?.provider || "laya").toUpperCase()}</span>
                    <span>Device: {draftDecisionEngine?.device || "auto"}</span>
                  </div>
                  <div className="text-[10px] font-mono text-app-muted flex items-center justify-between">
                    <span>Fast-Exit: {((draftDecisionEngine?.fast_exit_threshold ?? 0.92) * 100).toFixed(0)}%</span>
                    <span>Uncertainty: {((draftDecisionEngine?.uncertainty_threshold ?? 0.55) * 100).toFixed(0)}%</span>
                  </div>
                  <div className="text-[10px] font-mono text-app-muted flex items-center justify-between">
                    <span>Audit Rate: {((draftDecisionEngine?.stochastic_audit_rate ?? 0.05) * 100).toFixed(1)}%</span>
                    <span>Active Gates: {["phase2_entity_discovery", "phase3_global_relations", "phase4_argument_mining", "phase4_entity_maturation", "phase5_fusion", "phase6_theorynet"].filter(k => (draftDecisionEngine?.phase_gates as any)?.[k] !== false).length}/6</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-1.5 pt-2 border-t border-app-border/70">
                <div className="font-sans text-[12px] font-semibold text-app-text">
                  Active Engine LLM
                </div>
                <div className="space-y-1 text-xs">
                  <div className="font-mono text-xs text-app-text truncate font-medium" title={draftModels?.llm_model}>
                    {draftModels?.llm_model || "openai/gpt-4o-mini"}
                  </div>
                  <div className="text-[10px] font-mono text-app-muted flex items-center justify-between">
                    <span>Temperature: {draftModels?.temperature ?? 0}</span>
                    <span className="uppercase">Thinking: {draftModels?.thinking_level || "off"}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
