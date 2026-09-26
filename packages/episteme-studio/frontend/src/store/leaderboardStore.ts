import { create } from "zustand";
import { api } from "../api/client.ts";
import type {
  ComparativeEvaluationResponse,
  LeaderboardEntry,
  LeaderboardResponse,
  ParetoFrontierPoint,
} from "../api/types";

export interface LeaderboardState {
  // Leaderboard data
  leaderboard: LeaderboardResponse | null;
  entries: LeaderboardEntry[];
  paretoFrontier: ParetoFrontierPoint[];
  selectedBenchmarkId: string | null;

  // Sorting & Axes
  sortBy: string;
  ascending: boolean;
  xAxis: string; // "cost", "duration", "ece"
  yAxis: string; // "f1", "delta_star", "mrr", "polarity"

  // Comparison & Diff Drawer
  selectedRunIdA: string | null;
  selectedRunIdB: string | null;
  isDiffDrawerOpen: boolean;
  diffComparison: ComparativeEvaluationResponse | null;
  isLoadingDiff: boolean;

  // Status
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchLeaderboard: (params?: {
    benchmark_id?: string | null;
    sort_by?: string;
    ascending?: boolean;
  }) => Promise<void>;
  setSelectedBenchmarkId: (id: string | null) => void;
  setSortBy: (field: string) => void;
  setAscending: (asc: boolean) => void;
  setXAxis: (axis: string) => void;
  setYAxis: (axis: string) => void;

  // Run selection for pairwise diff
  setSelectedRunIdA: (runId: string | null) => void;
  setSelectedRunIdB: (runId: string | null) => void;
  toggleRunForDiff: (runId: string) => void;
  setIsDiffDrawerOpen: (open: boolean) => void;
  fetchComparison: (runIdA: string, runIdB: string, axis?: string) => Promise<void>;
  clearComparison: () => void;
}

export const useLeaderboardStore = create<LeaderboardState>((set, get) => ({
  leaderboard: null,
  entries: [],
  paretoFrontier: [],
  selectedBenchmarkId: null,

  sortBy: "f1",
  ascending: false,
  xAxis: "cost",
  yAxis: "f1",

  selectedRunIdA: null,
  selectedRunIdB: null,
  isDiffDrawerOpen: false,
  diffComparison: null,
  isLoadingDiff: false,

  isLoading: false,
  error: null,

  fetchLeaderboard: async (params) => {
    const benchmark_id = params?.benchmark_id ?? get().selectedBenchmarkId ?? undefined;
    const sort_by = params?.sort_by ?? get().sortBy;
    const ascending = params?.ascending ?? get().ascending;

    set({ isLoading: true, error: null });
    try {
      const res = await api.getLeaderboard({
        benchmark_id: benchmark_id || undefined,
        sort_by,
        ascending,
      });

      set({
        leaderboard: res,
        entries: res.entries || [],
        paretoFrontier: res.pareto_frontier || [],
        isLoading: false,
      });
    } catch (err: any) {
      set({
        error: err?.message || "Failed to fetch benchmark leaderboard",
        isLoading: false,
      });
    }
  },

  setSelectedBenchmarkId: (id) => {
    set({ selectedBenchmarkId: id });
    get().fetchLeaderboard({ benchmark_id: id });
  },

  setSortBy: (field) => {
    const isCurrent = get().sortBy === field;
    const newAsc = isCurrent ? !get().ascending : false;
    set({ sortBy: field, ascending: newAsc });
    get().fetchLeaderboard({ sort_by: field, ascending: newAsc });
  },

  setAscending: (asc) => {
    set({ ascending: asc });
    get().fetchLeaderboard({ ascending: asc });
  },

  setXAxis: (axis) => set({ xAxis: axis }),
  setYAxis: (axis) => set({ yAxis: axis }),

  setSelectedRunIdA: (runId) => {
    set({ selectedRunIdA: runId });
    const runB = get().selectedRunIdB;
    if (runId && runB && runId !== runB) {
      get().fetchComparison(runId, runB);
    }
  },

  setSelectedRunIdB: (runId) => {
    set({ selectedRunIdB: runId });
    const runA = get().selectedRunIdA;
    if (runA && runId && runA !== runId) {
      get().fetchComparison(runA, runId);
    }
  },

  toggleRunForDiff: (runId) => {
    const { selectedRunIdA, selectedRunIdB } = get();

    if (selectedRunIdA === runId) {
      // Deselect A
      set({ selectedRunIdA: null, diffComparison: null });
    } else if (selectedRunIdB === runId) {
      // Deselect B
      set({ selectedRunIdB: null, diffComparison: null });
    } else if (!selectedRunIdA) {
      // Set as A
      set({ selectedRunIdA: runId });
      if (selectedRunIdB) {
        get().fetchComparison(runId, selectedRunIdB);
        set({ isDiffDrawerOpen: true });
      }
    } else if (!selectedRunIdB) {
      // Set as B
      set({ selectedRunIdB: runId, isDiffDrawerOpen: true });
      get().fetchComparison(selectedRunIdA, runId);
    } else {
      // Both full -> replace B with new run
      set({ selectedRunIdB: runId, isDiffDrawerOpen: true });
      get().fetchComparison(selectedRunIdA, runId);
    }
  },

  setIsDiffDrawerOpen: (open) => set({ isDiffDrawerOpen: open }),

  fetchComparison: async (runIdA, runIdB, axis = "overall") => {
    if (!runIdA || !runIdB || runIdA === runIdB) return;
    set({ isLoadingDiff: true, error: null });
    try {
      const diff = await api.compareEvaluationRuns({
        run_id_a: runIdA,
        run_id_b: runIdB,
        axis,
      });
      set({ diffComparison: diff, isLoadingDiff: false, isDiffDrawerOpen: true });
    } catch (err: any) {
      set({
        error: err?.message || `Failed to compare runs ${runIdA} and ${runIdB}`,
        isLoadingDiff: false,
      });
    }
  },

  clearComparison: () => {
    set({
      selectedRunIdA: null,
      selectedRunIdB: null,
      diffComparison: null,
      isDiffDrawerOpen: false,
    });
  },
}));
