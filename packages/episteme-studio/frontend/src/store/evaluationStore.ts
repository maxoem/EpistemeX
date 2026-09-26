import { create } from "zustand";
import { api } from "../api/client.ts";
import type {
  AdjudicateAndRecalculateResponse,
  BenchmarkDescriptor,
  EdgeAdjudicationItem,
  EvaluationMode,
  EvaluationReportDetail,
  EvaluationReportSummary,
  EvaluationSubTab,
} from "../api/types";

export interface OptimisticScalarDeltas {
  f1: number;
  precision: number;
  recall: number;
}

export interface EvaluationState {
  // Navigation & View Mode
  activeMode: EvaluationMode;
  activeSubTab: EvaluationSubTab;

  // Active Report & Listing
  reports: EvaluationReportSummary[];
  activeReportId: string | null;
  activeReport: EvaluationReportDetail | null;

  // Benchmarks
  benchmarks: BenchmarkDescriptor[];
  selectedBenchmarkId: string | null;

  // HITL Staging Buffer (Deterministic, no auto-debounce race conditions)
  stagedAdjudications: Map<string, EdgeAdjudicationItem>;
  optimisticScalarDeltas: OptimisticScalarDeltas;
  isCommittingBatch: boolean;

  // Status & Telemetry
  isLoading: boolean;
  error: string | null;

  // Navigation Setters
  setActiveMode: (mode: EvaluationMode) => void;
  setActiveSubTab: (tab: EvaluationSubTab) => void;
  setActiveReportId: (id: string | null) => void;
  setActiveReport: (report: EvaluationReportDetail | null) => void;
  setSelectedBenchmarkId: (id: string | null) => void;

  // Data Fetching
  fetchReports: (params?: { run_id?: string; outcome?: string }) => Promise<void>;
  fetchReportDetail: (evaluationId: string) => Promise<EvaluationReportDetail | null>;
  fetchBenchmarks: () => Promise<void>;

  // Staging Buffer Actions
  stageAdjudication: (candidateId: string, item: EdgeAdjudicationItem) => void;
  unstageAdjudication: (candidateId: string) => void;
  clearStagedAdjudications: () => void;
  setOptimisticDeltas: (deltas: OptimisticScalarDeltas) => void;
  commitStagedAdjudications: (
    evaluationId: string,
    exportDatasetPath?: string | null
  ) => Promise<AdjudicateAndRecalculateResponse | null>;

  // Cleanup
  resetStore: () => void;
}

const INITIAL_OPTIMISTIC_DELTAS: OptimisticScalarDeltas = {
  f1: 0.0,
  precision: 0.0,
  recall: 0.0,
};

export const useEvaluationStore = create<EvaluationState>((set, get) => ({
  activeMode: "inspector",
  activeSubTab: "canvas",

  reports: [],
  activeReportId: null,
  activeReport: null,

  benchmarks: [],
  selectedBenchmarkId: null,

  stagedAdjudications: new Map<string, EdgeAdjudicationItem>(),
  optimisticScalarDeltas: INITIAL_OPTIMISTIC_DELTAS,
  isCommittingBatch: false,

  isLoading: false,
  error: null,

  setActiveMode: (mode) => set({ activeMode: mode }),

  setActiveSubTab: (tab) => set({ activeSubTab: tab }),

  setActiveReportId: (id) => {
    set({ activeReportId: id });
    if (id) {
      get().fetchReportDetail(id);
    } else {
      set({ activeReport: null });
    }
  },

  setActiveReport: (report) =>
    set({
      activeReport: report,
      activeReportId: report ? report.evaluation_id : null,
    }),

  setSelectedBenchmarkId: (id) => set({ selectedBenchmarkId: id }),

  fetchReports: async (params) => {
    set({ isLoading: true, error: null });
    try {
      const reports = await api.listEvaluationReports(params);
      set({ reports, isLoading: false });
    } catch (err: any) {
      set({
        error: err?.message || "Failed to load evaluation reports",
        isLoading: false,
      });
    }
  },

  fetchReportDetail: async (evaluationId: string) => {
    set({ isLoading: true, error: null });
    try {
      const detail = await api.getEvaluationReport(evaluationId);
      set({ activeReport: detail, activeReportId: detail.evaluation_id, isLoading: false });
      return detail;
    } catch (err: any) {
      set({
        error: err?.message || `Failed to fetch report ${evaluationId}`,
        isLoading: false,
      });
      return null;
    }
  },

  fetchBenchmarks: async () => {
    set({ isLoading: true, error: null });
    try {
      const benchmarks = await api.listBenchmarks();
      set({ benchmarks, isLoading: false });
    } catch (err: any) {
      set({
        error: err?.message || "Failed to load benchmarks",
        isLoading: false,
      });
    }
  },

  stageAdjudication: (candidateId, item) => {
    const current = get().stagedAdjudications;
    const nextMap = new Map(current);
    nextMap.set(candidateId, item);

    // Compute basic heuristic optimistic delta based on staged decisions
    let tpDelta = 0;
    let fpDelta = 0;
    for (const staged of nextMap.values()) {
      if (staged.decision === "true_positive" || staged.decision === "schema_alias") {
        tpDelta += 1;
      } else if (staged.decision === "false_positive") {
        fpDelta += 1;
      }
    }
    const totalStaged = nextMap.size;
    const approximateDelta = totalStaged > 0 ? (tpDelta - fpDelta) * 0.005 : 0;

    set({
      stagedAdjudications: nextMap,
      optimisticScalarDeltas: {
        f1: Math.round(approximateDelta * 1000) / 1000,
        precision: Math.round((tpDelta * 0.004) * 1000) / 1000,
        recall: Math.round((tpDelta * 0.006) * 1000) / 1000,
      },
    });
  },

  unstageAdjudication: (candidateId) => {
    const current = get().stagedAdjudications;
    if (!current.has(candidateId)) return;
    const nextMap = new Map(current);
    nextMap.delete(candidateId);

    let tpDelta = 0;
    let fpDelta = 0;
    for (const staged of nextMap.values()) {
      if (staged.decision === "true_positive" || staged.decision === "schema_alias") {
        tpDelta += 1;
      } else if (staged.decision === "false_positive") {
        fpDelta += 1;
      }
    }
    const totalStaged = nextMap.size;
    const approximateDelta = totalStaged > 0 ? (tpDelta - fpDelta) * 0.005 : 0;

    set({
      stagedAdjudications: nextMap,
      optimisticScalarDeltas: {
        f1: Math.round(approximateDelta * 1000) / 1000,
        precision: Math.round((tpDelta * 0.004) * 1000) / 1000,
        recall: Math.round((tpDelta * 0.006) * 1000) / 1000,
      },
    });
  },

  clearStagedAdjudications: () => {
    set({
      stagedAdjudications: new Map(),
      optimisticScalarDeltas: INITIAL_OPTIMISTIC_DELTAS,
    });
  },

  setOptimisticDeltas: (deltas) => set({ optimisticScalarDeltas: deltas }),

  commitStagedAdjudications: async (evaluationId, exportDatasetPath) => {
    const items = Array.from(get().stagedAdjudications.values());
    if (items.length === 0) return null;

    set({ isCommittingBatch: true, error: null });
    try {
      const res = await api.adjudicateAndRecalculate(evaluationId, {
        items,
        export_dataset_path: exportDatasetPath,
      });

      // Update active report if updated_report returned
      if (res.updated_report) {
        set({
          activeReport: res.updated_report,
          stagedAdjudications: new Map(),
          optimisticScalarDeltas: INITIAL_OPTIMISTIC_DELTAS,
          isCommittingBatch: false,
        });
      } else {
        // Refetch full report detail
        await get().fetchReportDetail(evaluationId);
        set({
          stagedAdjudications: new Map(),
          optimisticScalarDeltas: INITIAL_OPTIMISTIC_DELTAS,
          isCommittingBatch: false,
        });
      }
      return res;
    } catch (err: any) {
      set({
        error: err?.message || "Failed to commit staged adjudications",
        isCommittingBatch: false,
      });
      return null;
    }
  },

  resetStore: () => {
    set({
      activeReportId: null,
      activeReport: null,
      stagedAdjudications: new Map(),
      optimisticScalarDeltas: INITIAL_OPTIMISTIC_DELTAS,
      isCommittingBatch: false,
      error: null,
    });
  },
}));
