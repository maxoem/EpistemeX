import {create} from "zustand";

export interface GraphSettings {
  // Layout & Physics
  linkDistance: number; // default: 90 (range: 40 - 300)
  nodeRepulsion: number; // default: -120 (range: -500 - -30)
  hierarchicalRankSep: number; // default: 80 (range: 30 - 250)
  forceLayoutAnimated: boolean; // default: false (instant offscreen settle vs animated physics)
  forceIterations: number; // default: 80 (range: 30 - 200)
  autoAdaptLabels: boolean; // default: true (dynamically cull overlapping labels)

  // Node Appearance
  nodeSizeMultiplier: number; // default: 1.0 (range: 0.6 - 2.0)
  labelMaxLength: number; // default: 22 (range: 10 - 60)
  labelFontSize: number; // default: 10 (range: 8 - 16)

  // Edge Appearance
  edgeThicknessMultiplier: number; // default: 1.0 (range: 0.5 - 3.0)
  showEdgeLabels: boolean; // default: true
}

export const DEFAULT_GRAPH_SETTINGS: GraphSettings = {
  linkDistance: 90,
  nodeRepulsion: -120,
  hierarchicalRankSep: 80,
  forceLayoutAnimated: false,
  forceIterations: 80,
  autoAdaptLabels: true,
  nodeSizeMultiplier: 1.0,
  labelMaxLength: 22,
  labelFontSize: 10,
  edgeThicknessMultiplier: 1.0,
  showEdgeLabels: true,
};

const STORAGE_KEY = "glp-studio-graph-settings";

const loadStoredSettings = (): GraphSettings => {
  if (typeof window === "undefined") return DEFAULT_GRAPH_SETTINGS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_GRAPH_SETTINGS;
    const parsed = JSON.parse(raw);
    return {
      ...DEFAULT_GRAPH_SETTINGS,
      ...parsed,
    };
  } catch {
    return DEFAULT_GRAPH_SETTINGS;
  }
};

interface GraphSettingsState {
  settings: GraphSettings;
  updateSettings: (partial: Partial<GraphSettings>) => void;
  resetSettings: () => void;
}

export const useGraphSettingsStore = create<GraphSettingsState>((set, get) => ({
  settings: loadStoredSettings(),

  updateSettings: (partial: Partial<GraphSettings>) => {
    const next = { ...get().settings, ...partial };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // ignore storage write errors
    }
    set({ settings: next });
  },

  resetSettings: () => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
    set({ settings: { ...DEFAULT_GRAPH_SETTINGS } });
  },
}));
