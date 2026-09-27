import { create } from "zustand";

export type StudioTab = "runs" | "graph" | "cypher" | "config" | "engine" | "evaluation";

export interface PromptTuningTarget {
  phaseKey?: string;
  promptKey?: string;
  sourceText?: string;
  assertionId?: string;
}

export interface NavigationState {
  activeTab: StudioTab;
  promptTuningTarget: PromptTuningTarget | null;

  setActiveTab: (tab: StudioTab) => void;
  setPromptTuningTarget: (target: PromptTuningTarget | null) => void;
  resetNavigation: () => void;
}

export const useNavigationStore = create<NavigationState>((set) => ({
  activeTab: "runs",
  promptTuningTarget: null,

  setActiveTab: (tab: StudioTab) => {
    set({ activeTab: tab });
  },

  setPromptTuningTarget: (target: PromptTuningTarget | null) => {
    set({ promptTuningTarget: target });
  },

  resetNavigation: () => {
    set({ activeTab: "runs", promptTuningTarget: null });
  },
}));
