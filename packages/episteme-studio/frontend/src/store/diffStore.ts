import {create} from "zustand";
import {api} from "../api/client";
import {GraphDiffView} from "../api/types";

export type DiffScrubMode = "run_a" | "diff" | "run_b";
export type DiffFilter = "all" | "polarity_inversions" | "gained" | "lost" | "arg_drift";

interface DiffState {
  isDiffActive: boolean;
  baseRunId: string | null;
  targetRunId: string | null;
  diffData: GraphDiffView | null;
  isLoadingDiff: boolean;
  diffError: string | null;

  scrubMode: DiffScrubMode;
  activeFilter: DiffFilter;
  isBlinking: boolean;

  isConfigDrawerOpen: boolean;
  isPolarityModalOpen: boolean;
  isCompareModalOpen: boolean;

  startDiff: (baseRunId: string, targetRunId: string) => Promise<void>;
  closeDiff: () => void;
  setScrubMode: (mode: DiffScrubMode) => void;
  setActiveFilter: (filter: DiffFilter) => void;
  toggleBlink: () => void;
  setIsBlinking: (blinking: boolean) => void;
  setIsConfigDrawerOpen: (open: boolean) => void;
  setIsPolarityModalOpen: (open: boolean) => void;
  setIsCompareModalOpen: (open: boolean) => void;
}

export const useDiffStore = create<DiffState>((set, get) => ({
  isDiffActive: false,
  baseRunId: null,
  targetRunId: null,
  diffData: null,
  isLoadingDiff: false,
  diffError: null,

  scrubMode: "diff",
  activeFilter: "all",
  isBlinking: false,

  isConfigDrawerOpen: false,
  isPolarityModalOpen: false,
  isCompareModalOpen: false,

  startDiff: async (baseRunId: string, targetRunId: string) => {
    set({
      isLoadingDiff: true,
      diffError: null,
      baseRunId,
      targetRunId,
      isDiffActive: true,
      scrubMode: "diff",
      activeFilter: "all",
      isBlinking: false,
    });

    try {
      const diffData = await api.getRunDiff(baseRunId, targetRunId);
      set({
        diffData,
        isLoadingDiff: false,
      });
    } catch (err: any) {
      console.error("Failed to load run difference:", err);
      set({
        diffError: err?.detail || err?.title || "Failed to compute difference between runs.",
        isLoadingDiff: false,
      });
    }
  },

  closeDiff: () => {
    set({
      isDiffActive: false,
      baseRunId: null,
      targetRunId: null,
      diffData: null,
      isLoadingDiff: false,
      diffError: null,
      isBlinking: false,
      isConfigDrawerOpen: false,
      isPolarityModalOpen: false,
    });
  },

  setScrubMode: (mode: DiffScrubMode) => {
    set({ scrubMode: mode, isBlinking: false });
  },

  setActiveFilter: (filter: DiffFilter) => {
    set({ activeFilter: filter });
  },

  toggleBlink: () => {
    set((state) => ({ isBlinking: !state.isBlinking }));
  },

  setIsBlinking: (blinking: boolean) => {
    set({ isBlinking: blinking });
  },

  setIsConfigDrawerOpen: (open: boolean) => {
    set({ isConfigDrawerOpen: open });
  },

  setIsPolarityModalOpen: (open: boolean) => {
    set({ isPolarityModalOpen: open });
  },

  setIsCompareModalOpen: (open: boolean) => {
    set({ isCompareModalOpen: open });
  },
}));
