import type {GraphDiffView, MetricResult, MetricRunInstance, Overlay} from "../../api/types.ts";
import type {GraphSettings} from "../../store/graphSettingsStore.ts";

export interface NodeStyleContext {
  isDark: boolean;
  activeOverlay: Overlay | null;
  activeMetricResult: MetricResult | null;
  metricInstances?: MetricRunInstance[];
  scaleMode?: "stack" | "overwrite";
  isDiffActive: boolean;
  diffData: GraphDiffView | null;
  graphSettings: GraphSettings;
  getPartition: (componentType: string) => "B" | "A" | null;
  getNodeDefinition?: (nodeType: string) => string | null;
}

export interface EdgeStyleContext {
  isDark: boolean;
  activeOverlay: Overlay | null;
  activeMetricResult: MetricResult | null;
  metricInstances?: MetricRunInstance[];
  isDiffActive: boolean;
  diffData: GraphDiffView | null;
  graphSettings: GraphSettings;
  getPolarity: (relationType: string) => number | null;
  getRelationDefinition?: (relationType: string) => string | null;
}

