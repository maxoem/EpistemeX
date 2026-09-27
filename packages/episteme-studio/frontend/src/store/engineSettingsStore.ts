import { create } from "zustand";
import { api } from "../api/client.ts";
import type {
  EngineSettings,
  EngineSettingsPatch,
  PredicateMapping,
  SchemaConfig,
  UnmappedPredicateInfo,
} from "../api/types.ts";
import {
  DEFAULT_L2_NODE_DEFINITIONS,
  DEFAULT_L2_RELATION_DEFINITIONS,
  DEFAULT_L3_COMPONENT_DEFINITIONS,
  DEFAULT_L3_ARGUMENT_RELATION_DEFINITIONS,
  DEFAULT_COMPONENT_PARTITIONS,
  DEFAULT_RELATION_POLARITIES,
} from "../panels/configEditor/constants.ts";
import type { SelectedItem } from "../panels/engine/types.ts";

export interface EngineSettingsState {
  settings: EngineSettings | null;
  schema: SchemaConfig;
  unmappedPredicates: UnmappedPredicateInfo[];
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;

  // Rail 1: Category selection
  activeCategory: "ontology" | "unmapped" | "models";
  setActiveCategory: (cat: "ontology" | "unmapped" | "models") => void;

  // Rail 2: Sub-tab scoping
  ontologySubTab: "nodes" | "relations" | "components" | "arg_relations";
  setOntologySubTab: (tab: "nodes" | "relations" | "components" | "arg_relations") => void;
  unmappedSubTab: "discovered" | "aliases";
  setUnmappedSubTab: (tab: "discovered" | "aliases") => void;

  // Rail 3: Contextual selection
  selectedItem: SelectedItem | null;
  setSelectedItem: (item: SelectedItem | null) => void;
  selectedUnmapped: Set<string>;
  setSelectedUnmapped: (
    val: Set<string> | ((prev: Set<string>) => Set<string>)
  ) => void;

  // Actions
  fetchEngineSettings: () => Promise<void>;
  fetchUnmappedPredicates: () => Promise<void>;
  updateEngineSettings: (patch: EngineSettingsPatch) => Promise<void>;
  resetEngineSettings: () => Promise<void>;
  mapPredicate: (mapping: PredicateMapping) => Promise<void>;

  // Zero-overhead O(1) domain lookup helpers
  getPolarity: (relationType: string) => number | null;
  getPartition: (componentType: string) => "B" | "A" | null;
  isKnownRelation: (relationType: string) => boolean;
  isKnownNode: (nodeType: string) => boolean;
  getNodeDefinition: (nodeType: string) => string | null;
  getRelationDefinition: (relationType: string) => string | null;
}

const DEFAULT_FALLBACK_SCHEMA: SchemaConfig = {
  version: "v1",
  node_types: Object.keys(DEFAULT_L2_NODE_DEFINITIONS),
  relation_types: Object.keys(DEFAULT_L2_RELATION_DEFINITIONS),
  node_definitions: DEFAULT_L2_NODE_DEFINITIONS,
  relation_definitions: DEFAULT_L2_RELATION_DEFINITIONS,
  component_types: Object.keys(DEFAULT_L3_COMPONENT_DEFINITIONS),
  argument_relation_types: Object.keys(DEFAULT_L3_ARGUMENT_RELATION_DEFINITIONS),
  component_definitions: DEFAULT_L3_COMPONENT_DEFINITIONS,
  argument_relation_definitions: DEFAULT_L3_ARGUMENT_RELATION_DEFINITIONS,
  relation_polarities: DEFAULT_RELATION_POLARITIES,
  component_partitions: DEFAULT_COMPONENT_PARTITIONS,
  predicate_aliases: {},
};

export const useEngineSettingsStore = create<EngineSettingsState>((set, get) => ({
  settings: null,
  schema: DEFAULT_FALLBACK_SCHEMA,
  unmappedPredicates: [],
  isLoading: false,
  isSaving: false,
  error: null,

  activeCategory: "ontology",
  setActiveCategory: (cat) => set({ activeCategory: cat }),

  ontologySubTab: "nodes",
  setOntologySubTab: (tab) => set({ ontologySubTab: tab }),

  unmappedSubTab: "discovered",
  setUnmappedSubTab: (tab) => set({ unmappedSubTab: tab }),

  selectedItem: { type: "node", id: "Concept" },
  setSelectedItem: (item) => set({ selectedItem: item }),

  selectedUnmapped: new Set<string>(),
  setSelectedUnmapped: (val) =>
    set((state) => ({
      selectedUnmapped: typeof val === "function" ? val(state.selectedUnmapped) : val,
    })),

  fetchEngineSettings: async () => {
    set({ isLoading: true, error: null });
    try {
      const settings = await api.getEngineSettings();
      set({
        settings,
        schema: settings.schema_config,
        isLoading: false,
      });
    } catch (err: any) {
      console.warn("Failed to load engine settings from backend, falling back to defaults:", err);
      set({ isLoading: false, error: err?.detail || err?.message || "Failed to load settings" });
    }
  },

  fetchUnmappedPredicates: async () => {
    try {
      const unmapped = await api.getUnmappedPredicates();
      set({ unmappedPredicates: unmapped });
    } catch (err) {
      console.warn("Failed to fetch unmapped predicates:", err);
    }
  },

  updateEngineSettings: async (patch: EngineSettingsPatch) => {
    set({ isSaving: true, error: null });
    try {
      const updated = await api.updateEngineSettings(patch);
      set({
        settings: updated,
        schema: updated.schema_config,
        isSaving: false,
      });
      // Re-fetch unmapped predicates to reflect newly resolved mappings
      get().fetchUnmappedPredicates();
    } catch (err: any) {
      set({
        isSaving: false,
        error: err?.detail || err?.message || "Failed to save engine settings",
      });
      throw err;
    }
  },

  resetEngineSettings: async () => {
    set({ isSaving: true, error: null });
    try {
      const clean = await api.resetEngineSettings();
      set({
        settings: clean,
        schema: clean.schema_config,
        isSaving: false,
      });
      get().fetchUnmappedPredicates();
    } catch (err: any) {
      set({
        isSaving: false,
        error: err?.detail || err?.message || "Failed to reset engine settings",
      });
      throw err;
    }
  },

  mapPredicate: async (mapping: PredicateMapping) => {
    set({ isSaving: true, error: null });
    try {
      const updated = await api.mapUnmappedPredicate(mapping);
      set({
        settings: updated,
        schema: updated.schema_config,
        isSaving: false,
      });
      get().fetchUnmappedPredicates();
    } catch (err: any) {
      set({
        isSaving: false,
        error: err?.detail || err?.message || "Failed to map predicate",
      });
      throw err;
    }
  },

  getPolarity: (relationType: string): number | null => {
    const { schema, settings } = get();
    if (!relationType) return null;

    // 1. Direct schema polarities
    if (schema.relation_polarities && relationType in schema.relation_polarities) {
      return schema.relation_polarities[relationType];
    }

    // 2. Predicate aliases configured in engine settings
    const aliases = settings?.predicate_aliases || schema.predicate_aliases;
    if (aliases && relationType in aliases) {
      const entry = aliases[relationType];
      if (typeof entry === "number") return entry;
      if (typeof entry === "object" && entry?.polarity !== undefined) return entry.polarity;
      if (typeof entry === "string" && schema.relation_polarities?.[entry] !== undefined) {
        return schema.relation_polarities[entry];
      }
    }

    return null;
  },

  getPartition: (componentType: string): "B" | "A" | null => {
    const { schema } = get();
    const p = schema.component_partitions?.[componentType];
    return p === "B" || p === "A" ? p : null;
  },

  isKnownRelation: (relationType: string): boolean => {
    const { schema, settings } = get();
    if (!relationType) return false;
    const inTypes =
      schema.relation_types.includes(relationType) ||
      schema.argument_relation_types.includes(relationType);
    if (inTypes) return true;

    const aliases = settings?.predicate_aliases || schema.predicate_aliases;
    return Boolean(aliases && relationType in aliases);
  },

  isKnownNode: (nodeType: string): boolean => {
    const { schema } = get();
    if (!nodeType) return false;
    return schema.node_types.includes(nodeType) || schema.component_types.includes(nodeType);
  },

  getNodeDefinition: (nodeType: string): string | null => {
    const { schema } = get();
    return (
      schema.node_definitions?.[nodeType] ||
      schema.component_definitions?.[nodeType] ||
      null
    );
  },

  getRelationDefinition: (relationType: string): string | null => {
    const { schema, settings } = get();
    const directDef =
      schema.relation_definitions?.[relationType] ||
      schema.argument_relation_definitions?.[relationType];
    if (directDef) return directDef;

    const aliases = settings?.predicate_aliases || schema.predicate_aliases;
    if (aliases && relationType in aliases) {
      const entry = aliases[relationType];
      if (typeof entry === "object" && entry?.definition) return entry.definition;
    }
    return null;
  },
}));

/**
 * Ergonomic, zero-overhead hook for consuming schema properties anywhere in the React tree.
 *
 * Examples
 * --------
 * const { schema, getPolarity, getPartition } = useEngineSchema();
 * const polarity = getPolarity(edge.type);
 */
export function useEngineSchema() {
  const schema = useEngineSettingsStore((s) => s.schema);
  const getPolarity = useEngineSettingsStore((s) => s.getPolarity);
  const getPartition = useEngineSettingsStore((s) => s.getPartition);
  const isKnownRelation = useEngineSettingsStore((s) => s.isKnownRelation);
  const isKnownNode = useEngineSettingsStore((s) => s.isKnownNode);
  const getNodeDefinition = useEngineSettingsStore((s) => s.getNodeDefinition);
  const getRelationDefinition = useEngineSettingsStore((s) => s.getRelationDefinition);

  return {
    schema,
    getPolarity,
    getPartition,
    isKnownRelation,
    isKnownNode,
    getNodeDefinition,
    getRelationDefinition,
  };
}
