import React, { useState, useEffect, useMemo } from "react";
import {
  Plus,
  Trash2,
  AlertCircle,
  Link2,
  Cpu,
  Layers,
  Search,
  Database,
  RefreshCw,
  X,
  ChevronDown,
  Network,
  Compass,
  Sliders,
  Save,
  RotateCcw,
} from "lucide-react";
import { useEngineSettingsStore } from "../../store/engineSettingsStore";
import { SchemaConfig } from "../../api/types";
import { SelectedItem } from "./types";
import { ContextualInspectorRail } from "./components/ContextualInspectorRail";
import { ResizablePanel } from "../ResizablePanel";
import {
  OntologyNodesTable,
  OntologyRelationsTable,
  OntologyComponentsTable,
  OntologyArgRelationsTable,
  UnmappedDiscoveredTable,
  UnmappedAliasesTable,
} from "./components/EngineTanStackTables";

export const EngineSettingsPage: React.FC = () => {
  const {
    settings,
    schema,
    unmappedPredicates,
    isLoading,
    isSaving,
    error,
    activeCategory,
    setActiveCategory,
    ontologySubTab,
    setOntologySubTab,
    unmappedSubTab,
    setUnmappedSubTab,
    selectedItem,
    setSelectedItem,
    selectedUnmapped,
    setSelectedUnmapped,
    fetchEngineSettings,
    fetchUnmappedPredicates,
    updateEngineSettings,
    resetEngineSettings,
    mapPredicate,
  } = useEngineSettingsStore();

  // Search filters
  const [searchFilter, setSearchFilter] = useState("");
  const [unmappedSearch, setUnmappedSearch] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Multi-select state for unmapped predicates batch canonical
  const [batchCanonical, setBatchCanonical] = useState<string>("");
  const [isBatchMapping, setIsBatchMapping] = useState(false);

  // Local draft state for schema modifications
  const [draftSchema, setDraftSchema] = useState<SchemaConfig>(schema);
  const [draftAliases, setDraftAliases] = useState<Record<string, any>>({});
  const [draftModels, setDraftModels] = useState<any>({
    llm_model: "openai/gpt-4o-mini",
    embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
    reranker_model: "Alibaba-NLP/gte-reranker-modernbert-base",
    temperature: 0.0,
    thinking_level: "off",
  });

  // Sync draft from loaded settings
  useEffect(() => {
    fetchEngineSettings();
    fetchUnmappedPredicates();
  }, [fetchEngineSettings, fetchUnmappedPredicates]);

  useEffect(() => {
    if (schema) {
      setDraftSchema(schema);
    }
    if (settings) {
      setDraftAliases(settings.predicate_aliases || {});
      if (settings.models) {
        setDraftModels(settings.models);
      }
    }
  }, [schema, settings]);

  // If sub-tab changes, auto-select first item if current selection doesn't match
  useEffect(() => {
    if (activeCategory === "ontology") {
      if (ontologySubTab === "nodes" && draftSchema.node_types?.length > 0) {
        if (selectedItem?.type !== "node" || !draftSchema.node_types.includes(selectedItem.id)) {
          setSelectedItem({ type: "node", id: draftSchema.node_types[0] });
        }
      } else if (ontologySubTab === "relations" && draftSchema.relation_types?.length > 0) {
        if (selectedItem?.type !== "relation" || !draftSchema.relation_types.includes(selectedItem.id)) {
          setSelectedItem({ type: "relation", id: draftSchema.relation_types[0] });
        }
      } else if (ontologySubTab === "components" && draftSchema.component_types?.length > 0) {
        if (selectedItem?.type !== "component" || !draftSchema.component_types.includes(selectedItem.id)) {
          setSelectedItem({ type: "component", id: draftSchema.component_types[0] });
        }
      } else if (ontologySubTab === "arg_relations" && draftSchema.argument_relation_types?.length > 0) {
        if (selectedItem?.type !== "arg_relation" || !draftSchema.argument_relation_types.includes(selectedItem.id)) {
          setSelectedItem({ type: "arg_relation", id: draftSchema.argument_relation_types[0] });
        }
      }
    } else if (activeCategory === "unmapped") {
      if (unmappedSubTab === "discovered" && unmappedPredicates.length > 0) {
        if (selectedItem?.type !== "unmapped_predicate" || !unmappedPredicates.some((p) => p.predicate === selectedItem.id)) {
          setSelectedItem({ type: "unmapped_predicate", id: unmappedPredicates[0].predicate });
        }
      } else if (unmappedSubTab === "aliases" && Object.keys(draftAliases).length > 0) {
        const firstAlias = Object.keys(draftAliases)[0];
        if (selectedItem?.type !== "alias" || !(selectedItem.id in draftAliases)) {
          setSelectedItem({ type: "alias", id: firstAlias });
        }
      }
    } else if (activeCategory === "models") {
      setSelectedItem(null);
    }
  }, [activeCategory, ontologySubTab, unmappedSubTab]);

  // Add Item Modal state (Linear / Retool style)
  const [addModalType, setAddModalType] = useState<
    "node" | "relation" | "component" | "arg_relation" | "alias" | null
  >(null);
  const [modalName, setModalName] = useState("");
  const [modalDef, setModalDef] = useState("");
  const [modalPartition, setModalPartition] = useState<"A" | "B">("B");
  const [modalPolarity, setModalPolarity] = useState<number>(1);
  const [modalCanonical, setModalCanonical] = useState<string>("");
  const [modalError, setModalError] = useState<string | null>(null);

  const hasUnsavedChanges = useMemo(() => {
    if (!settings) return false;
    const schemaChanged = JSON.stringify(draftSchema) !== JSON.stringify(settings.schema_config);
    const aliasesChanged =
      JSON.stringify(draftAliases) !== JSON.stringify(settings.predicate_aliases || {});
    const modelsChanged = JSON.stringify(draftModels) !== JSON.stringify(settings.models || {});
    return schemaChanged || aliasesChanged || modelsChanged;
  }, [draftSchema, draftAliases, draftModels, settings]);

  const handleSave = async () => {
    try {
      await updateEngineSettings({
        schema_config: draftSchema,
        predicate_aliases: draftAliases,
        models: draftModels,
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch {
      // Handled by store
    }
  };

  const handleReset = async () => {
    if (
      window.confirm(
        "Are you sure you want to reset all engine settings, ontology definitions, and predicate aliases to factory defaults?"
      )
    ) {
      await resetEngineSettings();
    }
  };

  const handleQuickMap = async (predicate: string, polarity: -1 | 0 | 1, canonical?: string) => {
    await mapPredicate({
      predicate,
      polarity,
      canonical: canonical || null,
      definition: `Quick-mapped via Engine Studio (${polarity > 0 ? "Support" : polarity < 0 ? "Attack" : "Neutral"})`,
    });
  };

  // Available canonical relations for linking
  const allCanonicalRelations = useMemo(() => {
    const set = new Set<string>();
    (draftSchema.relation_types || []).forEach((r) => set.add(r));
    (draftSchema.argument_relation_types || []).forEach((r) => set.add(r));
    return Array.from(set).sort();
  }, [draftSchema.relation_types, draftSchema.argument_relation_types]);

  // Batch map helper
  const handleBatchMap = async (polarity: -1 | 0 | 1, canonical?: string) => {
    if (selectedUnmapped.size === 0) return;
    setIsBatchMapping(true);
    try {
      for (const pred of Array.from(selectedUnmapped)) {
        await mapPredicate({
          predicate: pred,
          polarity,
          canonical: canonical || null,
          definition: `Batch-mapped via Engine Studio (${polarity > 0 ? "Support" : polarity < 0 ? "Attack" : "Neutral"})`,
        });
      }
      setSelectedUnmapped(new Set());
    } finally {
      setIsBatchMapping(false);
    }
  };

  const normalizedFilter = searchFilter.trim().toLowerCase();

  // Filtered lists
  const filteredNodes = useMemo(() => {
    return (draftSchema.node_types || []).filter((type) => {
      const def = draftSchema.node_definitions?.[type] || "";
      return (
        !normalizedFilter ||
        type.toLowerCase().includes(normalizedFilter) ||
        def.toLowerCase().includes(normalizedFilter)
      );
    });
  }, [draftSchema.node_types, draftSchema.node_definitions, normalizedFilter]);

  const filteredRelations = useMemo(() => {
    return (draftSchema.relation_types || []).filter((type) => {
      const def = draftSchema.relation_definitions?.[type] || "";
      return (
        !normalizedFilter ||
        type.toLowerCase().includes(normalizedFilter) ||
        def.toLowerCase().includes(normalizedFilter)
      );
    });
  }, [draftSchema.relation_types, draftSchema.relation_definitions, normalizedFilter]);

  const filteredComponents = useMemo(() => {
    return (draftSchema.component_types || []).filter((type) => {
      const def = draftSchema.component_definitions?.[type] || "";
      return (
        !normalizedFilter ||
        type.toLowerCase().includes(normalizedFilter) ||
        def.toLowerCase().includes(normalizedFilter)
      );
    });
  }, [draftSchema.component_types, draftSchema.component_definitions, normalizedFilter]);

  const filteredArgRelations = useMemo(() => {
    return (draftSchema.argument_relation_types || []).filter((type) => {
      const def = draftSchema.argument_relation_definitions?.[type] || "";
      return (
        !normalizedFilter ||
        type.toLowerCase().includes(normalizedFilter) ||
        def.toLowerCase().includes(normalizedFilter)
      );
    });
  }, [draftSchema.argument_relation_types, draftSchema.argument_relation_definitions, normalizedFilter]);

  // Filtered unmapped predicates
  const filteredUnmapped = useMemo(() => {
    const q = unmappedSearch.trim().toLowerCase();
    return unmappedPredicates.filter(
      (item) => !q || item.predicate.toLowerCase().includes(q) || item.sample_runs.some((r) => r.toLowerCase().includes(q))
    );
  }, [unmappedPredicates, unmappedSearch]);

  // Filtered aliases
  const filteredAliases = useMemo(() => {
    const q = unmappedSearch.trim().toLowerCase();
    return Object.entries(draftAliases).filter(([pred, details]: [string, any]) => {
      if (!q) return true;
      const def = typeof details === "object" ? details?.definition || "" : "";
      const can = typeof details === "object" ? details?.canonical || "" : "";
      return pred.toLowerCase().includes(q) || def.toLowerCase().includes(q) || can.toLowerCase().includes(q);
    });
  }, [draftAliases, unmappedSearch]);

  const totalEntityCount = (draftSchema.node_types?.length || 0) + (draftSchema.component_types?.length || 0);
  const totalRelationCount = (draftSchema.relation_types?.length || 0) + (draftSchema.argument_relation_types?.length || 0);
  const totalAliasesCount = Object.keys(draftAliases).length;

  // Active items list for j/k keyboard navigation
  const activeItems = useMemo<{ type: SelectedItem["type"]; id: string }[]>(() => {
    if (activeCategory === "ontology") {
      if (ontologySubTab === "nodes") return filteredNodes.map((id) => ({ type: "node", id }));
      if (ontologySubTab === "relations") return filteredRelations.map((id) => ({ type: "relation", id }));
      if (ontologySubTab === "components") return filteredComponents.map((id) => ({ type: "component", id }));
      if (ontologySubTab === "arg_relations") return filteredArgRelations.map((id) => ({ type: "arg_relation", id }));
    } else if (activeCategory === "unmapped") {
      if (unmappedSubTab === "discovered") return filteredUnmapped.map((u) => ({ type: "unmapped_predicate", id: u.predicate }));
      if (unmappedSubTab === "aliases") return filteredAliases.map(([pred]) => ({ type: "alias", id: pred }));
    }
    return [];
  }, [
    activeCategory,
    ontologySubTab,
    unmappedSubTab,
    filteredNodes,
    filteredRelations,
    filteredComponents,
    filteredArgRelations,
    filteredUnmapped,
    filteredAliases,
  ]);

  // Keyboard navigation (j/k, ArrowDown/ArrowUp)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Do not trigger if typing in an input, textarea, or select
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select" || (e.target as HTMLElement)?.isContentEditable) {
        return;
      }

      if (e.key === "j" || e.key === "ArrowDown") {
        if (activeItems.length === 0) return;
        e.preventDefault();
        const currentIndex = activeItems.findIndex((it) => it.id === selectedItem?.id && it.type === selectedItem?.type);
        const nextIndex = currentIndex < 0 ? 0 : Math.min(currentIndex + 1, activeItems.length - 1);
        setSelectedItem(activeItems[nextIndex]);
      } else if (e.key === "k" || e.key === "ArrowUp") {
        if (activeItems.length === 0) return;
        e.preventDefault();
        const currentIndex = activeItems.findIndex((it) => it.id === selectedItem?.id && it.type === selectedItem?.type);
        const prevIndex = currentIndex < 0 ? 0 : Math.max(currentIndex - 1, 0);
        setSelectedItem(activeItems[prevIndex]);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeItems, selectedItem]);

  return (
    <div className="flex h-full w-full bg-app-surface dark:bg-app-bg text-app-text overflow-hidden select-none">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* RAIL 1: Left Rail (Resizable — Pipeline Composer style)              */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <ResizablePanel
        side="left"
        storageKey="glp-studio-engine-left-width"
        defaultWidth={280}
        minWidth={220}
        maxWidth={480}
        collapsible={false}
        showFooter={false}
        className="!bg-app-surface dark:!bg-app-rail !border-r !border-app-border dark:!border-app-border"
      >
        <div className="w-full h-full flex flex-col bg-app-surface overflow-hidden select-none">
          {/* Rail Header */}
          <div className="h-12 px-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-2 shrink-0">
            <div className="flex items-center gap-2 min-w-0">
              <Layers className="w-4 h-4 text-app-text shrink-0" />
              <div className="min-w-0">
                <h2 className="text-xs font-semibold text-app-text tracking-tight truncate font-display">
                  Engine Configuration
                </h2>
                <span className="text-[11px] text-app-muted block truncate font-sans">
                  Ontology & Runtime Systems
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleReset}
              className="h-6 px-2 rounded-[4px] border border-app-border bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-text dark:hover:text-app-heading text-[11px] font-medium transition-colors cursor-pointer inline-flex items-center gap-1 shrink-0"
              title="Reset engine settings to factory defaults"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Defaults</span>
            </button>
          </div>

        {/* Configuration Tree Navigation */}
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          {/* 1. BASELINE ONTOLOGY */}
          <div className="space-y-1">
            <h3 className="px-2 py-1 text-xs font-semibold text-app-heading tracking-tight font-display">
              Baseline Ontology
            </h3>

            <div className="space-y-0.5">
              {/* Entity Types */}
              <button
                type="button"
                onClick={() => {
                  setActiveCategory("ontology");
                  setOntologySubTab("nodes");
                }}
                className={`w-full px-2.5 py-2 rounded-md text-left transition-colors cursor-pointer relative group flex items-center justify-between gap-2 ${
                  activeCategory === "ontology" && ontologySubTab === "nodes"
                    ? "bg-app-subtle text-app-heading font-medium"
                    : "hover:bg-app-subtle/50 text-app-muted hover:text-app-heading"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-5 flex justify-center shrink-0">
                    <Database className="w-3.5 h-3.5 text-app-muted" />
                  </div>
                  <div className="min-w-0">
                    <div
                      className={`text-xs truncate ${
                        activeCategory === "ontology" && ontologySubTab === "nodes"
                          ? "font-semibold text-app-heading"
                          : "text-app-text font-normal"
                      }`}
                    >
                      Entity Types
                    </div>
                    <div className="text-[11px] text-app-muted font-sans truncate">
                      {draftSchema.node_types?.length || 0} classes · node_types
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {activeCategory === "ontology" && ontologySubTab === "nodes" && (
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block shrink-0" />
                  )}
                </div>
              </button>

              {/* Domain Relations */}
              <button
                type="button"
                onClick={() => {
                  setActiveCategory("ontology");
                  setOntologySubTab("relations");
                }}
                className={`w-full px-2.5 py-2 rounded-md text-left transition-colors cursor-pointer relative group flex items-center justify-between gap-2 ${
                  activeCategory === "ontology" && ontologySubTab === "relations"
                    ? "bg-app-subtle text-app-heading font-medium"
                    : "hover:bg-app-subtle/50 text-app-muted hover:text-app-heading"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-5 flex justify-center shrink-0">
                    <Link2 className="w-3.5 h-3.5 text-app-muted" />
                  </div>
                  <div className="min-w-0">
                    <div
                      className={`text-xs truncate ${
                        activeCategory === "ontology" && ontologySubTab === "relations"
                          ? "font-semibold text-app-heading"
                          : "text-app-text font-normal"
                      }`}
                    >
                      Domain Relations
                    </div>
                    <div className="text-[11px] text-app-muted font-sans truncate">
                      {draftSchema.relation_types?.length || 0} predicates · relation_types
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {activeCategory === "ontology" && ontologySubTab === "relations" && (
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block shrink-0" />
                  )}
                </div>
              </button>

              {/* Theory Components */}
              <button
                type="button"
                onClick={() => {
                  setActiveCategory("ontology");
                  setOntologySubTab("components");
                }}
                className={`w-full px-2.5 py-2 rounded-md text-left transition-colors cursor-pointer relative group flex items-center justify-between gap-2 ${
                  activeCategory === "ontology" && ontologySubTab === "components"
                    ? "bg-app-subtle text-app-heading font-medium"
                    : "hover:bg-app-subtle/50 text-app-muted hover:text-app-heading"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-5 flex justify-center shrink-0">
                    <Layers className="w-3.5 h-3.5 text-app-muted" />
                  </div>
                  <div className="min-w-0">
                    <div
                      className={`text-xs truncate ${
                        activeCategory === "ontology" && ontologySubTab === "components"
                          ? "font-semibold text-app-heading"
                          : "text-app-text font-normal"
                      }`}
                    >
                      Theory Components
                    </div>
                    <div className="text-[11px] text-app-muted font-sans truncate">
                      {draftSchema.component_types?.length || 0} partitions · component_types
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {activeCategory === "ontology" && ontologySubTab === "components" && (
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block shrink-0" />
                  )}
                </div>
              </button>

              {/* Argument Relations */}
              <button
                type="button"
                onClick={() => {
                  setActiveCategory("ontology");
                  setOntologySubTab("arg_relations");
                }}
                className={`w-full px-2.5 py-2 rounded-md text-left transition-colors cursor-pointer relative group flex items-center justify-between gap-2 ${
                  activeCategory === "ontology" && ontologySubTab === "arg_relations"
                    ? "bg-app-subtle text-app-heading font-medium"
                    : "hover:bg-app-subtle/50 text-app-muted hover:text-app-heading"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-5 flex justify-center shrink-0">
                    <Network className="w-3.5 h-3.5 text-app-muted" />
                  </div>
                  <div className="min-w-0">
                    <div
                      className={`text-xs truncate ${
                        activeCategory === "ontology" && ontologySubTab === "arg_relations"
                          ? "font-semibold text-app-heading"
                          : "text-app-text font-normal"
                      }`}
                    >
                      Argument Relations
                    </div>
                    <div className="text-[11px] text-app-muted font-sans truncate">
                      {draftSchema.argument_relation_types?.length || 0} dialectical weights
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {activeCategory === "ontology" && ontologySubTab === "arg_relations" && (
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block shrink-0" />
                  )}
                </div>
              </button>
            </div>
          </div>

          {/* 2. DYNAMIC VOCABULARY */}
          <div className="space-y-1">
            <div className="px-2 py-1 flex items-center justify-between">
              <h3 className="text-xs font-semibold text-app-heading tracking-tight font-display">
                Dynamic Vocabulary
              </h3>
              {unmappedPredicates.length > 0 ? (
                <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold border border-amber-500/20">
                  {unmappedPredicates.length} pending
                </span>
              ) : (
                <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
                  Aligned
                </span>
              )}
            </div>

            <div className="space-y-0.5">
              {/* Discovered In Runs */}
              <button
                type="button"
                onClick={() => {
                  setActiveCategory("unmapped");
                  setUnmappedSubTab("discovered");
                }}
                className={`w-full px-2.5 py-2 rounded-md text-left transition-colors cursor-pointer relative group flex items-center justify-between gap-2 ${
                  activeCategory === "unmapped" && unmappedSubTab === "discovered"
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
                        activeCategory === "unmapped" && unmappedSubTab === "discovered"
                          ? "font-semibold text-app-heading"
                          : "text-app-text font-normal"
                      }`}
                    >
                      Discovered Predicates
                    </div>
                    <div className="text-[11px] text-app-muted font-sans truncate">
                      {unmappedPredicates.length} discovered in runs
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {activeCategory === "unmapped" && unmappedSubTab === "discovered" && (
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block shrink-0" />
                  )}
                </div>
              </button>

              {/* Configured Aliases */}
              <button
                type="button"
                onClick={() => {
                  setActiveCategory("unmapped");
                  setUnmappedSubTab("aliases");
                }}
                className={`w-full px-2.5 py-2 rounded-md text-left transition-colors cursor-pointer relative group flex items-center justify-between gap-2 ${
                  activeCategory === "unmapped" && unmappedSubTab === "aliases"
                    ? "bg-app-subtle text-app-heading font-medium"
                    : "hover:bg-app-subtle/50 text-app-muted hover:text-app-heading"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-5 flex justify-center shrink-0">
                    <Sliders className="w-3.5 h-3.5 text-app-muted" />
                  </div>
                  <div className="min-w-0">
                    <div
                      className={`text-xs truncate ${
                        activeCategory === "unmapped" && unmappedSubTab === "aliases"
                          ? "font-semibold text-app-heading"
                          : "text-app-text font-normal"
                      }`}
                    >
                      Predicate Aliases
                    </div>
                    <div className="text-[11px] text-app-muted font-sans truncate">
                      {totalAliasesCount} active mappings
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {activeCategory === "unmapped" && unmappedSubTab === "aliases" && (
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block shrink-0" />
                  )}
                </div>
              </button>
            </div>
          </div>

          {/* 3. RUNTIME INFERENCE */}
          <div className="space-y-1">
            <h3 className="px-2 py-1 text-xs font-semibold text-app-heading tracking-tight font-display">
              Runtime Inference
            </h3>

            <div className="space-y-0.5">
              <button
                type="button"
                onClick={() => setActiveCategory("models")}
                className={`w-full px-2.5 py-2 rounded-md text-left transition-colors cursor-pointer relative group flex items-center justify-between gap-2 ${
                  activeCategory === "models"
                    ? "bg-app-subtle text-app-heading font-medium"
                    : "hover:bg-app-subtle/50 text-app-muted hover:text-app-heading"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-5 flex justify-center shrink-0">
                    <Cpu className="w-3.5 h-3.5 text-app-muted" />
                  </div>
                  <div className="min-w-0">
                    <div
                      className={`text-xs truncate ${
                        activeCategory === "models"
                          ? "font-semibold text-app-heading"
                          : "text-app-text font-normal"
                      }`}
                    >
                      Model & Reasoning
                    </div>
                    <div className="text-[11px] text-app-muted font-mono truncate">
                      LLM: {draftModels.llm_model ? draftModels.llm_model.split("/").pop() : "gpt-4o-mini"}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {activeCategory === "models" && (
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block shrink-0" />
                  )}
                </div>
              </button>
            </div>
          </div>
        </div>

        {/* Quiet System Spec Footer */}
        <div className="p-3 border-t border-app-border text-[11px] font-mono text-app-muted flex items-center justify-between bg-app-surface shrink-0">
          <span>Schema Specification</span>
          <span className="text-app-text font-medium">Dual-Graph Core</span>
        </div>
      </div>
    </ResizablePanel>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* RAIL 2: Center Rail (Fluid — StageScopeHeader & Canvas)              */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 bg-app-surface dark:bg-app-bg overflow-hidden">
        {/* Error Notification Banner */}
        {error && (
          <div className="m-4 p-3 rounded bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Top Target Scope Bar / Sub-Header Toolbar (Fixed 44px Docked) */}
        <div className="h-[44px] px-4 border-b border-app-border bg-app-surface dark:bg-app-bg flex items-center justify-between gap-4 shrink-0 select-none z-10">
          <div className="flex items-center gap-3 min-w-0">
            {/* Breadcrumb Path */}
            <div className="flex items-center gap-1.5 text-xs font-sans min-w-0">
              <span className="text-app-muted font-medium">
                {activeCategory === "ontology"
                  ? "Epistemic Ontology"
                  : activeCategory === "unmapped"
                  ? "Open-Vocabulary"
                  : "Runtime Inference"}
              </span>
              <span className="text-app-muted">/</span>
              <span className="font-semibold text-app-text truncate">
                {activeCategory === "ontology" && ontologySubTab === "nodes" && "Entity Types"}
                {activeCategory === "ontology" && ontologySubTab === "relations" && "Domain Relations"}
                {activeCategory === "ontology" && ontologySubTab === "components" && "Theory Components"}
                {activeCategory === "ontology" && ontologySubTab === "arg_relations" && "Argument Relations"}
                {activeCategory === "unmapped" && unmappedSubTab === "discovered" && "Discovered In Runs"}
                {activeCategory === "unmapped" && unmappedSubTab === "aliases" && "Configured Aliases"}
                {activeCategory === "models" && "Model & Reasoning Defaults"}
              </span>
            </div>

            {/* Scope Count Pill */}
            {activeCategory === "ontology" && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-app-border text-app-muted">
                {ontologySubTab === "nodes" && `${draftSchema.node_types?.length || 0} types`}
                {ontologySubTab === "relations" && `${draftSchema.relation_types?.length || 0} relations`}
                {ontologySubTab === "components" && `${draftSchema.component_types?.length || 0} components`}
                {ontologySubTab === "arg_relations" && `${draftSchema.argument_relation_types?.length || 0} types`}
              </span>
            )}
            {activeCategory === "unmapped" && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-app-border text-app-muted">
                {unmappedSubTab === "discovered" && `${unmappedPredicates.length} pending`}
                {unmappedSubTab === "aliases" && `${totalAliasesCount} active`}
              </span>
            )}

            {/* Keyboard shortcut hint */}
            {activeCategory !== "models" && (
              <div className="hidden lg:flex items-center gap-1 text-[11px] text-app-muted font-mono ml-2 pl-3 border-l border-app-border">
                <kbd className="px-1.5 py-0.5 rounded bg-app-subtle border border-app-border text-[10px] text-app-muted">j</kbd>
                <kbd className="px-1.5 py-0.5 rounded bg-app-subtle border border-app-border text-[10px] text-app-muted">k</kbd>
                <span className="text-[10px]">to navigate</span>
              </div>
            )}
          </div>

          {/* Right Header Actions */}
          <div className="flex items-center gap-2 shrink-0">
            {activeCategory !== "models" && (
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-app-muted/60 dark:text-app-muted pointer-events-none" />
                <input
                  type="text"
                  value={activeCategory === "ontology" ? searchFilter : unmappedSearch}
                  onChange={(e) => {
                    if (activeCategory === "ontology") setSearchFilter(e.target.value);
                    else setUnmappedSearch(e.target.value);
                  }}
                  placeholder="Filter rows..."
                  className="h-7 pl-6.5 pr-6 rounded-[4px] bg-app-bg dark:bg-app-subtle/50 hover:bg-app-subtle text-app-text border border-app-border text-xs font-mono focus:outline-none focus:border-[#2563EB] transition-colors w-36 sm:w-48"
                />
                {(activeCategory === "ontology" ? searchFilter : unmappedSearch) && (
                  <button
                    type="button"
                    onClick={() => {
                      if (activeCategory === "ontology") setSearchFilter("");
                      else setUnmappedSearch("");
                    }}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 text-app-muted hover:text-app-text dark:hover:text-app-heading cursor-pointer"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
            )}

            {/* Contextual + Add Action Button */}
            {activeCategory === "ontology" && (
              <button
                type="button"
                onClick={() => {
                  if (ontologySubTab === "nodes") {
                    setAddModalType("node");
                    setModalName("");
                    setModalDef("");
                    setModalError(null);
                  } else if (ontologySubTab === "relations") {
                    setAddModalType("relation");
                    setModalName("");
                    setModalDef("");
                    setModalError(null);
                  } else if (ontologySubTab === "components") {
                    setAddModalType("component");
                    setModalName("");
                    setModalDef("");
                    setModalPartition("B");
                    setModalError(null);
                  } else if (ontologySubTab === "arg_relations") {
                    setAddModalType("arg_relation");
                    setModalName("");
                    setModalDef("");
                    setModalPolarity(1);
                    setModalError(null);
                  }
                }}
                className="h-7 px-2.5 rounded-[4px] border border-app-border bg-app-surface hover:bg-app-subtle text-app-text text-xs font-sans font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 shadow-2xs"
              >
                <Plus className="w-3.5 h-3.5 text-[#2563EB]" />
                <span>
                  {ontologySubTab === "nodes" && "Add Entity"}
                  {ontologySubTab === "relations" && "Add Relation"}
                  {ontologySubTab === "components" && "Add Component"}
                  {ontologySubTab === "arg_relations" && "Add Argument Relation"}
                </span>
              </button>
            )}

            {activeCategory === "unmapped" && unmappedSubTab === "aliases" && (
              <button
                type="button"
                onClick={() => {
                  setAddModalType("alias");
                  setModalName("");
                  setModalDef("");
                  setModalPolarity(1);
                  setModalCanonical("");
                  setModalError(null);
                }}
                className="h-7 px-2.5 rounded-[4px] border border-app-border bg-app-surface hover:bg-app-subtle text-app-text text-xs font-sans font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 shadow-2xs"
              >
                <Plus className="w-3.5 h-3.5 text-[#2563EB]" />
                <span>Add Alias</span>
              </button>
            )}

            {activeCategory === "unmapped" && (
              <button
                type="button"
                onClick={() => fetchUnmappedPredicates()}
                className="h-7 px-2.5 rounded-[4px] border border-app-border bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-text dark:hover:text-app-heading text-xs font-mono transition-colors cursor-pointer inline-flex items-center gap-1"
                title="Rescan database runs"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Rescan</span>
              </button>
            )}

            {hasUnsavedChanges && (
              <button
                type="button"
                onClick={handleSave}
                disabled={isSaving}
                className="h-7 px-2.5 rounded-[4px] bg-[#2563EB] hover:bg-blue-600 text-white text-xs font-sans font-medium transition-colors cursor-pointer inline-flex items-center gap-1 shadow-2xs"
              >
                <Save className="w-3 h-3" />
                <span>{isSaving ? "Saving..." : "Save"}</span>
              </button>
            )}
          </div>
        </div>

        {/* Scrollable Center Canvas (Edge-to-Edge Docked) */}
        <div className="flex-1 overflow-y-auto select-text bg-app-bg">
          <div className="w-full flex flex-col">
            {/* ── WORKSPACE A: Epistemic Ontology & Schema ── */}
            {activeCategory === "ontology" && (
              <div className="space-y-4">
                {/* SUB-TAB 1: L2 Entity Types */}
                {ontologySubTab === "nodes" && (
                  <div className="w-full flex flex-col">
                    {/* Flush Section Header Banner */}
                    <div className="px-6 py-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="type-h1 text-app-text font-display text-base font-semibold">
                            L2 Entity Types
                          </h3>
                          <span className="type-caption text-app-muted font-mono text-[11px]">
                            schema.node_types
                          </span>
                        </div>
                        <p className="type-body text-app-muted mt-0.5 text-xs font-sans">
                          Ontological classifications for entity mention resolution. Injected into prompts as <code className="font-mono text-xs text-[#2563EB] dark:text-blue-400 bg-blue-500/10 px-1 py-0.5 rounded border border-blue-500/20">&#123;entity_types&#125;</code>.
                        </p>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => {
                            setAddModalType("node");
                            setModalName("");
                            setModalDef("");
                            setModalError(null);
                          }}
                          className="h-7 px-2.5 rounded-[4px] border border-app-border bg-app-surface hover:bg-app-subtle text-app-text text-xs font-sans font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 shadow-2xs"
                        >
                          <Plus className="w-3.5 h-3.5 text-[#2563EB]" />
                          <span>Add Entity</span>
                        </button>
                      </div>
                    </div>

                    {/* TanStack Table Data Grid */}
                    <OntologyNodesTable
                      nodes={filteredNodes}
                      definitions={draftSchema.node_definitions || {}}
                      selectedId={selectedItem?.type === "node" ? selectedItem.id : null}
                      onSelect={(type) => setSelectedItem({ type: "node", id: type })}
                      onDelete={(type) => {
                        const nextTypes = draftSchema.node_types.filter((t) => t !== type);
                        const nextDefs = { ...draftSchema.node_definitions };
                        delete nextDefs[type];
                        setDraftSchema({
                          ...draftSchema,
                          node_types: nextTypes,
                          node_definitions: nextDefs,
                        });
                        if (selectedItem?.id === type) {
                          setSelectedItem(null);
                        }
                      }}
                    />
                  </div>
                )}

                {/* SUB-TAB 2: L2 Domain Relations */}
                {ontologySubTab === "relations" && (
                  <div className="w-full flex flex-col">
                    {/* Flush Section Header Banner */}
                    <div className="px-6 py-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="type-h1 text-app-text font-display text-base font-semibold">
                            L2 Domain Relations
                          </h3>
                          <span className="type-caption text-app-muted font-mono text-[11px]">
                            schema.relation_types
                          </span>
                        </div>
                        <p className="type-body text-app-muted mt-0.5 text-xs font-sans">
                          Domain-specific relational predicates for knowledge graph triplets. Injected into prompts as <code className="font-mono text-xs text-[#2563EB] dark:text-blue-400 bg-blue-500/10 px-1 py-0.5 rounded border border-blue-500/20">&#123;relation_types&#125;</code>.
                        </p>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => {
                            setAddModalType("relation");
                            setModalName("");
                            setModalDef("");
                            setModalError(null);
                          }}
                          className="h-7 px-2.5 rounded-[4px] border border-app-border bg-app-surface hover:bg-app-subtle text-app-text text-xs font-sans font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 shadow-2xs"
                        >
                          <Plus className="w-3.5 h-3.5 text-[#2563EB]" />
                          <span>Add Relation</span>
                        </button>
                      </div>
                    </div>

                    {/* TanStack Table Data Grid */}
                    <OntologyRelationsTable
                      relations={filteredRelations}
                      definitions={draftSchema.relation_definitions || {}}
                      selectedId={selectedItem?.type === "relation" ? selectedItem.id : null}
                      onSelect={(rel) => setSelectedItem({ type: "relation", id: rel })}
                      onDelete={(rel) => {
                        const nextTypes = draftSchema.relation_types.filter((r) => r !== rel);
                        const nextDefs = { ...draftSchema.relation_definitions };
                        delete nextDefs[rel];
                        setDraftSchema({
                          ...draftSchema,
                          relation_types: nextTypes,
                          relation_definitions: nextDefs,
                        });
                        if (selectedItem?.id === rel) {
                          setSelectedItem(null);
                        }
                      }}
                    />
                  </div>
                )}

                {/* SUB-TAB 3: L3 Argument Components & Partitions */}
                {ontologySubTab === "components" && (
                  <div className="w-full flex flex-col">
                    {/* Flush Section Header Banner */}
                    <div className="px-6 py-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="type-h1 text-app-text font-display text-base font-semibold">
                            L3 Theory Components & Partitions
                          </h3>
                          <span className="type-caption text-app-muted font-mono text-[11px]">
                            schema.component_types
                          </span>
                        </div>
                        <p className="type-body text-app-muted mt-0.5 text-xs font-sans">
                          Epistemic structural partitions categorizing theoretical core versus empirical observation statements. Injected into prompts as <code className="font-mono text-xs text-[#2563EB] dark:text-blue-400 bg-blue-500/10 px-1 py-0.5 rounded border border-blue-500/20">&#123;component_types&#125;</code>.
                        </p>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => {
                            setAddModalType("component");
                            setModalName("");
                            setModalDef("");
                            setModalPartition("B");
                            setModalError(null);
                          }}
                          className="h-7 px-2.5 rounded-[4px] border border-app-border bg-app-surface hover:bg-app-subtle text-app-text text-xs font-sans font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 shadow-2xs"
                        >
                          <Plus className="w-3.5 h-3.5 text-[#2563EB]" />
                          <span>Add Component</span>
                        </button>
                      </div>
                    </div>

                    {/* TanStack Table Data Grid */}
                    <OntologyComponentsTable
                      components={filteredComponents}
                      partitions={draftSchema.component_partitions || {}}
                      definitions={draftSchema.component_definitions || {}}
                      selectedId={selectedItem?.type === "component" ? selectedItem.id : null}
                      onSelect={(comp) => setSelectedItem({ type: "component", id: comp })}
                      onDelete={(comp) => {
                        const nextTypes = draftSchema.component_types.filter((c) => c !== comp);
                        const nextDefs = { ...draftSchema.component_definitions };
                        delete nextDefs[comp];
                        const nextParts = { ...draftSchema.component_partitions };
                        delete nextParts[comp];
                        setDraftSchema({
                          ...draftSchema,
                          component_types: nextTypes,
                          component_definitions: nextDefs,
                          component_partitions: nextParts,
                        });
                        if (selectedItem?.id === comp) {
                          setSelectedItem(null);
                        }
                      }}
                    />
                  </div>
                )}

                {/* SUB-TAB 4: L3 Argument Relations & Polarities */}
                {ontologySubTab === "arg_relations" && (
                  <div className="w-full flex flex-col">
                    {/* Flush Section Header Banner */}
                    <div className="px-6 py-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="type-h1 text-app-text font-display text-base font-semibold">
                            L3 Argument Relations & Polarities
                          </h3>
                          <span className="type-caption text-app-muted font-mono text-[11px]">
                            schema.argument_relation_types
                          </span>
                        </div>
                        <p className="type-body text-app-muted mt-0.5 text-xs font-sans">
                          Dialectical and deductive edge inference with epistemic polarity weights (+1 Support, 0 Neutral, -1 Attack).
                        </p>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => {
                            setAddModalType("arg_relation");
                            setModalName("");
                            setModalDef("");
                            setModalPolarity(1);
                            setModalError(null);
                          }}
                          className="h-7 px-2.5 rounded-[4px] border border-app-border bg-app-surface hover:bg-app-subtle text-app-text text-xs font-sans font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 shadow-2xs"
                        >
                          <Plus className="w-3.5 h-3.5 text-[#2563EB]" />
                          <span>Add Relation</span>
                        </button>
                      </div>
                    </div>

                    {/* TanStack Table Data Grid */}
                    <OntologyArgRelationsTable
                      argRelations={filteredArgRelations}
                      polarities={draftSchema.relation_polarities || {}}
                      definitions={draftSchema.argument_relation_definitions || {}}
                      selectedId={selectedItem?.type === "arg_relation" ? selectedItem.id : null}
                      onSelect={(rel) => setSelectedItem({ type: "arg_relation", id: rel })}
                      onDelete={(rel) => {
                        const nextTypes = draftSchema.argument_relation_types.filter((r) => r !== rel);
                        const nextDefs = { ...draftSchema.argument_relation_definitions };
                        delete nextDefs[rel];
                        const nextPols = { ...draftSchema.relation_polarities };
                        delete nextPols[rel];
                        setDraftSchema({
                          ...draftSchema,
                          argument_relation_types: nextTypes,
                          argument_relation_definitions: nextDefs,
                          relation_polarities: nextPols,
                        });
                        if (selectedItem?.id === rel) {
                          setSelectedItem(null);
                        }
                      }}
                    />
                  </div>
                )}
              </div>
            )}

            {/* ── WORKSPACE B: Open-Vocabulary Predicates ── */}
            {activeCategory === "unmapped" && (
              <div className="space-y-4">
                {unmappedSubTab === "discovered" && (
                  <div className="w-full flex flex-col">
                    {/* Flush Section Header Banner */}
                    <div className="px-6 py-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="type-h1 text-app-text font-display text-base font-semibold">
                            Discovered In Historical Runs
                          </h3>
                          <span className="type-caption text-app-muted font-mono text-[11px]">
                            runs.unmapped_predicates
                          </span>
                        </div>
                        <p className="type-body text-app-muted mt-0.5 text-xs font-sans">
                          Language models extracted these open-vocabulary predicates during ingestion. Click any row to inspect runtime occurrences or map to canonical schema.
                        </p>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => fetchUnmappedPredicates()}
                          className="h-7 px-2.5 rounded-[4px] border border-app-border bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-text dark:hover:text-app-heading text-xs font-mono transition-colors cursor-pointer inline-flex items-center gap-1 shadow-2xs"
                          title="Rescan database runs"
                        >
                          <RefreshCw className="w-3 h-3" />
                          <span>Rescan</span>
                        </button>
                      </div>
                    </div>

                    {/* Batch Actions Bar */}
                    {selectedUnmapped.size > 0 && (
                      <div className="px-6 py-2 bg-app-subtle dark:bg-blue-500/10 border-b border-app-border dark:border-blue-500/20 flex flex-wrap items-center justify-between gap-3 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-semibold text-[#2563EB] dark:text-blue-400">
                            {selectedUnmapped.size} selected
                          </span>
                          <button
                            type="button"
                            onClick={() => setSelectedUnmapped(new Set())}
                            className="text-[11px] text-app-muted hover:text-app-text dark:text-app-muted dark:hover:text-app-heading underline cursor-pointer"
                          >
                            Clear
                          </button>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-[11px] text-app-muted font-medium">Batch map:</span>
                          <button
                            type="button"
                            disabled={isBatchMapping}
                            onClick={() => handleBatchMap(1, "SUPPORTS")}
                            className="h-6 px-2 rounded-[4px] bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-[11px] font-medium cursor-pointer disabled:opacity-50"
                          >
                            +1 Supp
                          </button>
                          <button
                            type="button"
                            disabled={isBatchMapping}
                            onClick={() => handleBatchMap(0, "RELATED_TO")}
                            className="h-6 px-2 rounded-[4px] bg-slate-700 hover:bg-slate-600 text-white font-mono text-[11px] font-medium cursor-pointer disabled:opacity-50"
                          >
                            0 Neut
                          </button>
                          <button
                            type="button"
                            disabled={isBatchMapping}
                            onClick={() => handleBatchMap(-1, "ATTACKS")}
                            className="h-6 px-2 rounded-[4px] bg-rose-600 hover:bg-rose-500 text-white font-mono text-[11px] font-medium cursor-pointer disabled:opacity-50"
                          >
                            -1 Attack
                          </button>

                          <div className="flex items-center gap-1.5 pl-2 border-l border-app-border dark:border-blue-500/30">
                            <select
                              value={batchCanonical}
                              onChange={(e) => setBatchCanonical(e.target.value)}
                              className="h-6 px-1.5 rounded-[4px] bg-app-surface text-app-text border border-app-border text-[11px] font-mono focus:outline-none"
                            >
                              <option value="">Canonical Target...</option>
                              {allCanonicalRelations.map((r) => (
                                <option key={r} value={r}>
                                  → {r}
                                </option>
                              ))}
                            </select>
                            <button
                              type="button"
                              disabled={isBatchMapping || !batchCanonical}
                              onClick={() => {
                                const pol = draftSchema.relation_polarities?.[batchCanonical] ?? 0;
                                handleBatchMap(pol as -1 | 0 | 1, batchCanonical);
                                setBatchCanonical("");
                              }}
                              className="h-6 px-2 rounded-[4px] bg-[#2563EB] hover:bg-blue-600 text-white text-[11px] font-sans font-medium cursor-pointer disabled:opacity-50"
                            >
                              Apply
                            </button>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* TanStack Table Data Rows */}
                    {unmappedPredicates.length === 0 ? (
                      <div className="p-12 text-center text-xs text-app-muted font-mono">
                        No unmapped predicates detected in historical runs. All relation edges conform to the schema.
                      </div>
                    ) : (
                      <UnmappedDiscoveredTable
                        unmapped={filteredUnmapped}
                        selectedItem={selectedItem}
                        selectedPredicates={selectedUnmapped}
                        onToggleSelect={(pred, checked) => {
                          const next = new Set(selectedUnmapped);
                          if (checked) next.add(pred);
                          else next.delete(pred);
                          setSelectedUnmapped(next);
                        }}
                        onToggleSelectAll={(checked) => {
                          if (checked) {
                            const next = new Set(selectedUnmapped);
                            filteredUnmapped.forEach((item) => next.add(item.predicate));
                            setSelectedUnmapped(next);
                          } else {
                            const next = new Set(selectedUnmapped);
                            filteredUnmapped.forEach((item) => next.delete(item.predicate));
                            setSelectedUnmapped(next);
                          }
                        }}
                        onSelect={(pred) => setSelectedItem({ type: "unmapped_predicate", id: pred })}
                        onQuickMap={handleQuickMap}
                      />
                    )}
                  </div>
                )}

                {unmappedSubTab === "aliases" && (
                  <div className="w-full flex flex-col">
                    {/* Flush Section Header Banner */}
                    <div className="px-6 py-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="type-h1 text-app-text font-display text-base font-semibold">
                            Configured Predicate Aliases
                          </h3>
                          <span className="type-caption text-app-muted font-mono text-[11px]">
                            settings.predicate_aliases
                          </span>
                        </div>
                        <p className="type-body text-app-muted mt-0.5 text-xs font-sans">
                          Explicit predicate mappings and dialectical polarity overrides stored in engine configuration.
                        </p>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => {
                            setAddModalType("alias");
                            setModalName("");
                            setModalDef("");
                            setModalPolarity(1);
                            setModalCanonical("");
                            setModalError(null);
                          }}
                          className="h-7 px-2.5 rounded-[4px] border border-app-border bg-app-surface hover:bg-app-subtle text-app-text text-xs font-sans font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 shadow-2xs"
                        >
                          <Plus className="w-3.5 h-3.5 text-[#2563EB]" />
                          <span>Add Alias</span>
                        </button>
                      </div>
                    </div>

                    {Object.keys(draftAliases).length === 0 ? (
                      <div className="p-12 text-center text-xs text-app-muted font-mono">
                        No custom predicate aliases configured.
                      </div>
                    ) : (
                      <UnmappedAliasesTable
                        aliases={filteredAliases}
                        selectedPredicateId={selectedItem?.type === "alias" ? selectedItem.id : null}
                        onSelect={(pred) => setSelectedItem({ type: "alias", id: pred })}
                        onDelete={(pred) => {
                          const next = { ...draftAliases };
                          delete next[pred];
                          setDraftAliases(next);
                          if (selectedItem?.id === pred) {
                            setSelectedItem(null);
                          }
                        }}
                      />
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── WORKSPACE C: Model & Inference Defaults ── */}
            {activeCategory === "models" && (
              <div className="w-full flex flex-col">
                {/* Flush Section Header Banner */}
                <div className="px-6 py-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="type-h1 text-app-text font-display text-base font-semibold">
                        Pipeline Model & Reasoning Defaults
                      </h3>
                      <span className="type-caption text-app-muted font-mono text-[11px]">
                        pipeline.models
                      </span>
                    </div>
                    <p className="type-body text-app-muted mt-0.5 text-xs font-sans">
                      Baseline foundation models and inference parameters inherited across all pipeline stages.
                    </p>
                  </div>
                </div>

                {/* Edge-to-Edge Docked Parameter Grid */}
                <div className="w-full divide-y divide-app-border">
                  {/* Section Header: Foundation Models */}
                  <div className="px-6 py-2.5 bg-app-surface border-b border-app-border font-sans text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
                    Foundation Models & Latent Embeddings
                  </div>

                  {/* Row 1: Generative LLM Model */}
                  <div className="px-6 py-3.5 grid grid-cols-1 lg:grid-cols-[280px_1fr] items-center gap-4 hover:bg-app-surface dark:hover:bg-app-subtle/40 transition-colors">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-sans text-xs font-medium text-app-text">
                          Generative LLM Model
                        </span>
                        <span className="font-mono text-[10px] text-[#2563EB] dark:text-blue-400 bg-blue-500/10 px-1 py-0.2 rounded border border-blue-500/20">
                          LLM
                        </span>
                      </div>
                      <span className="font-mono text-[11px] text-app-muted block mt-0.5">
                        models.llm_model
                      </span>
                      <p className="text-[11px] font-sans text-app-muted mt-1">
                        Primary generative model for extraction, synthesis, and argument mining.
                      </p>
                    </div>
                    <div className="max-w-xl">
                      <input
                        type="text"
                        value={draftModels.llm_model || ""}
                        onChange={(e) => setDraftModels({ ...draftModels, llm_model: e.target.value })}
                        placeholder="e.g. openai/gpt-4o-mini"
                        className="w-full h-8 px-3 rounded-[4px] bg-app-surface text-app-text text-xs font-mono border border-app-border focus:border-[#2563EB] focus:outline-none shadow-2xs"
                      />
                    </div>
                  </div>

                  {/* Row 2: Dense Vector Embedding Model */}
                  <div className="px-6 py-3.5 grid grid-cols-1 lg:grid-cols-[280px_1fr] items-center gap-4 hover:bg-app-surface dark:hover:bg-app-subtle/40 transition-colors">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-sans text-xs font-medium text-app-text">
                          Dense Vector Embedding Model
                        </span>
                        <span className="font-mono text-[10px] text-purple-600 dark:text-purple-400 bg-purple-500/10 px-1 py-0.2 rounded border border-purple-500/20">
                          Vectors
                        </span>
                      </div>
                      <span className="font-mono text-[11px] text-app-muted block mt-0.5">
                        models.embedding_model
                      </span>
                      <p className="text-[11px] font-sans text-app-muted mt-1">
                        Uniform vector latent space for chunking and candidate retrieval.
                      </p>
                    </div>
                    <div className="max-w-xl">
                      <input
                        type="text"
                        value={draftModels.embedding_model || ""}
                        onChange={(e) => setDraftModels({ ...draftModels, embedding_model: e.target.value })}
                        placeholder="e.g. sentence-transformers/all-MiniLM-L6-v2"
                        className="w-full h-8 px-3 rounded-[4px] bg-app-surface text-app-text text-xs font-mono border border-app-border focus:border-[#2563EB] focus:outline-none shadow-2xs"
                      />
                    </div>
                  </div>

                  {/* Row 3: Cross-Encoder Reranker Model */}
                  <div className="px-6 py-3.5 grid grid-cols-1 lg:grid-cols-[280px_1fr] items-center gap-4 hover:bg-app-surface dark:hover:bg-app-subtle/40 transition-colors">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-sans text-xs font-medium text-app-text">
                          Cross-Encoder Reranker Model
                        </span>
                        <span className="font-mono text-[10px] text-amber-600 dark:text-amber-400 bg-amber-500/10 px-1 py-0.2 rounded border border-amber-500/20">
                          Reranker
                        </span>
                      </div>
                      <span className="font-mono text-[11px] text-app-muted block mt-0.5">
                        models.reranker_model
                      </span>
                      <p className="text-[11px] font-sans text-app-muted mt-1">
                        Cross-encoder scoring and relevance thresholding across candidate spans.
                      </p>
                    </div>
                    <div className="max-w-xl">
                      <input
                        type="text"
                        value={draftModels.reranker_model || ""}
                        onChange={(e) => setDraftModels({ ...draftModels, reranker_model: e.target.value })}
                        placeholder="e.g. Alibaba-NLP/gte-reranker-modernbert-base"
                        className="w-full h-8 px-3 rounded-[4px] bg-app-surface text-app-text text-xs font-mono border border-app-border focus:border-[#2563EB] focus:outline-none shadow-2xs"
                      />
                    </div>
                  </div>

                  {/* Section Header: Inference & Budget */}
                  <div className="px-6 py-2.5 bg-app-surface border-y border-app-border font-sans text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
                    Inference Telemetry & Reasoning Budget
                  </div>

                  {/* Row 4: Generation Temperature */}
                  <div className="px-6 py-3.5 grid grid-cols-1 lg:grid-cols-[280px_1fr] items-center gap-4 hover:bg-app-surface dark:hover:bg-app-subtle/40 transition-colors">
                    <div>
                      <span className="font-sans text-xs font-medium text-app-text">
                        Generation Temperature
                      </span>
                      <span className="font-mono text-[11px] text-app-muted block mt-0.5">
                        models.temperature
                      </span>
                      <p className="text-[11px] font-sans text-app-muted mt-1">
                        Stochastic sampling variance (0.00 for deterministic epistemic extraction).
                      </p>
                    </div>
                    <div className="max-w-md flex items-center gap-3">
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={Number(draftModels.temperature ?? 0)}
                        onChange={(e) =>
                          setDraftModels({
                            ...draftModels,
                            temperature: parseFloat(e.target.value),
                          })
                        }
                        className="flex-1 accent-blue-600 cursor-pointer h-1.5 bg-app-border dark:bg-app-subtle rounded-lg"
                      />
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        max="1"
                        value={Number(draftModels.temperature ?? 0).toFixed(2)}
                        onChange={(e) =>
                          setDraftModels({
                            ...draftModels,
                            temperature: parseFloat(e.target.value) || 0,
                          })
                        }
                        className="w-16 h-7 px-1.5 text-right font-mono text-xs rounded-[4px] bg-app-surface text-app-text border border-app-border focus:border-[#2563EB] focus:outline-none"
                        style={{ fontFeatureSettings: '"tnum" 1' }}
                      />
                    </div>
                  </div>

                  {/* Row 5: Reasoning Thinking Budget */}
                  <div className="px-6 py-3.5 grid grid-cols-1 lg:grid-cols-[280px_1fr] items-center gap-4 hover:bg-app-surface dark:hover:bg-app-subtle/40 transition-colors">
                    <div>
                      <span className="font-sans text-xs font-medium text-app-text">
                        Reasoning Thinking Budget
                      </span>
                      <span className="font-mono text-[11px] text-app-muted block mt-0.5">
                        models.thinking_level
                      </span>
                      <p className="text-[11px] font-sans text-app-muted mt-1">
                        Deliberate token budget allocation for extended dialectical reasoning.
                      </p>
                    </div>
                    <div className="max-w-md">
                      <div className="h-7 p-0.5 inline-flex items-center bg-app-subtle/60 rounded-[4px] border border-app-border/60 text-xs w-full gap-0.5">
                        {[
                          { id: "off", label: "Off" },
                          { id: "low", label: "Low" },
                          { id: "medium", label: "Med" },
                          { id: "high", label: "High" },
                        ].map((tier) => {
                          const isSelected = (draftModels.thinking_level || "off").toLowerCase() === tier.id;
                          return (
                            <button
                              key={tier.id}
                              type="button"
                              onClick={() => setDraftModels({ ...draftModels, thinking_level: tier.id })}
                              className={`flex-1 h-6 rounded-[3px] text-xs transition-all cursor-pointer text-center font-mono ${
                                isSelected
                                  ? "bg-app-surface text-app-text font-semibold border border-app-border/80 shadow-2xs"
                                  : "text-app-muted hover:text-app-text dark:hover:text-app-heading hover:bg-app-bg/50"
                              }`}
                            >
                              {tier.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* RAIL 3: Right Rail (Resizable — Contextual Inspector & Guardrail)    */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <ResizablePanel
        side="right"
        storageKey="glp-studio-engine-right-width"
        defaultWidth={340}
        minWidth={280}
        maxWidth={650}
        collapsible={false}
        showFooter={false}
        className="!bg-app-surface dark:!bg-app-rail !border-l !border-app-border dark:!border-app-border"
      >
        <ContextualInspectorRail
          selectedItem={selectedItem}
          onDeselect={() => setSelectedItem(null)}
          draftSchema={draftSchema}
          onUpdateSchema={setDraftSchema}
          draftAliases={draftAliases}
          onUpdateAliases={setDraftAliases}
          unmappedPredicates={unmappedPredicates}
          onQuickMap={handleQuickMap}
          allCanonicalRelations={allCanonicalRelations}
          hasUnsavedChanges={hasUnsavedChanges}
          isSaving={isSaving}
          saveSuccess={saveSuccess}
          onSave={handleSave}
          onReset={handleReset}
          totalEntityCount={totalEntityCount}
          totalRelationCount={totalRelationCount}
          totalAliasesCount={totalAliasesCount}
          draftModels={draftModels}
        />
      </ResizablePanel>
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* ADD ITEM MODAL (Linear / Retool Style Dialog)                       */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {addModalType && (
        <div
          className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4 select-text"
          onClick={() => setAddModalType(null)}
        >
          <div
            className="w-full max-w-md bg-app-surface border border-app-border rounded-[8px] shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="h-12 px-5 border-b border-app-border flex items-center justify-between bg-app-surface">
              <h3 className="font-display text-sm font-semibold text-app-text">
                {addModalType === "node" && "Add Entity Type"}
                {addModalType === "relation" && "Add Domain Relation"}
                {addModalType === "component" && "Add Theory Component"}
                {addModalType === "arg_relation" && "Add Argument Relation"}
                {addModalType === "alias" && "Add Predicate Alias"}
              </h3>
              <button
                type="button"
                onClick={() => setAddModalType(null)}
                className="p-1 rounded text-app-muted hover:text-app-text dark:hover:text-app-heading cursor-pointer transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                const trimmed = modalName.trim();
                if (!trimmed) {
                  setModalError("Identifier is required");
                  return;
                }

                if (addModalType === "node") {
                  if (draftSchema.node_types?.includes(trimmed)) {
                    setModalError(`Entity "${trimmed}" already exists.`);
                    return;
                  }
                  setDraftSchema({
                    ...draftSchema,
                    node_types: [...(draftSchema.node_types || []), trimmed],
                    node_definitions: {
                      ...(draftSchema.node_definitions || {}),
                      [trimmed]: modalDef.trim(),
                    },
                  });
                  setSelectedItem({ type: "node", id: trimmed });
                } else if (addModalType === "relation") {
                  if (draftSchema.relation_types?.includes(trimmed)) {
                    setModalError(`Relation "${trimmed}" already exists.`);
                    return;
                  }
                  setDraftSchema({
                    ...draftSchema,
                    relation_types: [...(draftSchema.relation_types || []), trimmed],
                    relation_definitions: {
                      ...(draftSchema.relation_definitions || {}),
                      [trimmed]: modalDef.trim(),
                    },
                  });
                  setSelectedItem({ type: "relation", id: trimmed });
                } else if (addModalType === "component") {
                  if (draftSchema.component_types?.includes(trimmed)) {
                    setModalError(`Component "${trimmed}" already exists.`);
                    return;
                  }
                  setDraftSchema({
                    ...draftSchema,
                    component_types: [...(draftSchema.component_types || []), trimmed],
                    component_definitions: {
                      ...(draftSchema.component_definitions || {}),
                      [trimmed]: modalDef.trim(),
                    },
                    component_partitions: {
                      ...(draftSchema.component_partitions || {}),
                      [trimmed]: modalPartition,
                    },
                  });
                  setSelectedItem({ type: "component", id: trimmed });
                } else if (addModalType === "arg_relation") {
                  if (draftSchema.argument_relation_types?.includes(trimmed)) {
                    setModalError(`Argument relation "${trimmed}" already exists.`);
                    return;
                  }
                  setDraftSchema({
                    ...draftSchema,
                    argument_relation_types: [...(draftSchema.argument_relation_types || []), trimmed],
                    argument_relation_definitions: {
                      ...(draftSchema.argument_relation_definitions || {}),
                      [trimmed]: modalDef.trim(),
                    },
                    relation_polarities: {
                      ...(draftSchema.relation_polarities || {}),
                      [trimmed]: modalPolarity,
                    },
                  });
                  setSelectedItem({ type: "arg_relation", id: trimmed });
                } else if (addModalType === "alias") {
                  if (trimmed in draftAliases) {
                    setModalError(`Alias "${trimmed}" already exists.`);
                    return;
                  }
                  setDraftAliases({
                    ...draftAliases,
                    [trimmed]: {
                      polarity: modalPolarity,
                      canonical: modalCanonical || null,
                      definition: modalDef.trim(),
                    },
                  });
                  setSelectedItem({ type: "alias", id: trimmed });
                }

                setAddModalType(null);
              }}
              className="p-5 space-y-4"
            >
              {modalError && (
                <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs font-medium">
                  {modalError}
                </div>
              )}

              <div className="space-y-1.5">
                <label className="block text-[11px] font-sans font-semibold uppercase tracking-[0.05em] text-app-muted">
                  {addModalType === "node" && "Entity Type Identifier"}
                  {addModalType === "relation" && "Relation Predicate Identifier"}
                  {addModalType === "component" && "Component Identifier"}
                  {addModalType === "arg_relation" && "Argument Relation Identifier"}
                  {addModalType === "alias" && "Custom Predicate Identifier"}
                </label>
                <input
                  type="text"
                  autoFocus
                  value={modalName}
                  onChange={(e) => {
                    setModalName(e.target.value);
                    if (modalError) setModalError(null);
                  }}
                  placeholder={
                    addModalType === "node"
                      ? "e.g. TheoreticalTerm"
                      : addModalType === "relation"
                      ? "e.g. EXPLAINS"
                      : addModalType === "component"
                      ? "e.g. TheoreticalCore"
                      : addModalType === "arg_relation"
                      ? "e.g. SUPPORTS"
                      : "e.g. corroborates"
                  }
                  className="w-full h-8 px-3 rounded-[4px] bg-app-subtle text-app-text text-xs font-mono border border-app-border focus:border-[#2563EB] focus:outline-none"
                />
              </div>

              {addModalType === "component" && (
                <div className="space-y-1.5">
                  <label className="block text-[11px] font-sans font-semibold uppercase tracking-[0.05em] text-app-muted">
                    Theory Partition
                  </label>
                  <select
                    value={modalPartition}
                    onChange={(e) => setModalPartition(e.target.value as "A" | "B")}
                    className="w-full h-8 px-2.5 rounded-[4px] bg-app-subtle text-app-text text-xs font-sans border border-app-border focus:border-[#2563EB] focus:outline-none"
                  >
                    <option value="A">Partition A (Theoretical Core)</option>
                    <option value="B">Partition B (Empirical Observation / Data)</option>
                  </select>
                </div>
              )}

              {(addModalType === "arg_relation" || addModalType === "alias") && (
                <div className="space-y-1.5">
                  <label className="block text-[11px] font-sans font-semibold uppercase tracking-[0.05em] text-app-muted">
                    Dialectical Polarity
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { value: 1, label: "+1 Support", color: "text-emerald-600 bg-emerald-500/10 border-emerald-500/30" },
                      { value: 0, label: "0 Neutral", color: "text-slate-600 bg-slate-500/10 border-slate-500/30" },
                      { value: -1, label: "-1 Attack", color: "text-rose-600 bg-rose-500/10 border-rose-500/30" },
                    ].map((pol) => {
                      const isSelected = modalPolarity === pol.value;
                      return (
                        <button
                          key={pol.value}
                          type="button"
                          onClick={() => setModalPolarity(pol.value)}
                          className={`h-7 rounded-[4px] text-xs font-mono font-medium border transition-colors cursor-pointer ${
                            isSelected
                              ? `${pol.color} font-bold ring-1 ring-[#2563EB]`
                              : "bg-app-subtle text-app-muted border-app-border hover:text-app-text"
                          }`}
                        >
                          {pol.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {addModalType === "alias" && (
                <div className="space-y-1.5">
                  <label className="block text-[11px] font-sans font-semibold uppercase tracking-[0.05em] text-app-muted">
                    Canonical Target
                  </label>
                  <select
                    value={modalCanonical}
                    onChange={(e) => setModalCanonical(e.target.value)}
                    className="w-full h-8 px-2.5 rounded-[4px] bg-app-subtle text-app-text text-xs font-mono border border-app-border focus:border-[#2563EB] focus:outline-none"
                  >
                    <option value="">No Canonical Target</option>
                    {allCanonicalRelations.map((r) => (
                      <option key={r} value={r}>
                        → {r}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="space-y-1.5">
                <label className="block text-[11px] font-sans font-semibold uppercase tracking-[0.05em] text-app-muted">
                  Semantic Definition / Guidance
                </label>
                <textarea
                  rows={3}
                  value={modalDef}
                  onChange={(e) => setModalDef(e.target.value)}
                  placeholder="Classification criteria and extraction guidance..."
                  className="w-full p-2.5 rounded-[4px] bg-app-subtle text-app-text text-[13px] font-sans border border-app-border focus:border-[#2563EB] focus:outline-none resize-none"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setAddModalType(null)}
                  className="h-8 px-3 rounded-[4px] border border-app-border bg-app-surface hover:bg-app-subtle text-app-muted hover:text-app-text text-xs font-sans font-medium transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="h-8 px-3.5 rounded-[4px] bg-[#2563EB] hover:bg-blue-600 text-white text-xs font-sans font-medium cursor-pointer transition-colors shadow-2xs inline-flex items-center gap-1.5"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Create</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
