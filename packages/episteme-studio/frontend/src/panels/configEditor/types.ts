import type { AvailableInputDoc, ConfigView, FieldProvenance, GlobalStructuralAnchor, InvalidationPreview, ResolvedPromptItem } from "../../api/types.ts";
import type { PhaseMetadata } from "../phaseConfig/phaseRegistry.ts";

export interface ConfigEditorProps {
  onNavigateToRuns?: () => void;
}

export interface RunMetadataItem {
  id: string;
  key: string;
  value: string;
}

export interface ThinkingLevelPreset {
  id: string;
  label: string;
  description: string;
}

export interface SchemaFilterState {
  activeTab: "all" | "l2_nodes" | "l2_relations" | "l3_components" | "l3_relations";
  filterText: string;
}
