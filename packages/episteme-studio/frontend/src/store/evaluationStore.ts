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
  EvaluationGraphOverlay,
  EvaluationNodeOverlay,
  EvaluationEdgeOverlay,
} from "../api/types";

export interface OptimisticScalarDeltas {
  f1: number;
  precision: number;
  recall: number;
}

export type OverlaySelectedItem =
  | { type: "node"; item: EvaluationNodeOverlay }
  | { type: "edge"; item: EvaluationEdgeOverlay };

export interface CanvasAlignmentFilters {
  tp: boolean;
  fp: boolean;
  fn: boolean;
  polarity: boolean;
  borderline: boolean;
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

  // Graph Overlay & Canvas State (Phase 2)
  graphOverlay: EvaluationGraphOverlay | null;
  isLoadingOverlay: boolean;
  selectedOverlayItem: OverlaySelectedItem | null;
  alignmentFilters: CanvasAlignmentFilters;
  ghostOpacity: number;
  bourbakiHullEnabled: boolean;
  selectedBourbakiClasses: Set<string>;
  isAmbiguousDrawerOpen: boolean;
  cycleHighlightNodeIds: string[] | null;
  selectedGroundingComponentId: string | null;

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
  fetchGraphOverlay: (evaluationId: string) => Promise<EvaluationGraphOverlay | null>;

  // Canvas & Overlay Actions
  setSelectedOverlayItem: (item: OverlaySelectedItem | null) => void;
  toggleAlignmentFilter: (key: keyof CanvasAlignmentFilters) => void;
  setAlignmentFilters: (filters: CanvasAlignmentFilters) => void;
  setGhostOpacity: (opacity: number) => void;
  setBourbakiHullEnabled: (enabled: boolean) => void;
  toggleBourbakiClass: (cls: string) => void;
  setIsAmbiguousDrawerOpen: (open: boolean) => void;
  setCycleHighlightNodeIds: (nodeIds: string[] | null) => void;
  setSelectedGroundingComponentId: (id: string | null) => void;

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

const DEFAULT_ALIGNMENT_FILTERS: CanvasAlignmentFilters = {
  tp: true,
  fp: true,
  fn: true,
  polarity: true,
  borderline: true,
};

const DEFAULT_BOURBAKI_CLASSES = new Set<string>(["Mp", "M", "Mpp", "C", "I"]);

export const useEvaluationStore = create<EvaluationState>((set, get) => ({
  activeMode: "inspector",
  activeSubTab: "canvas",

  reports: [],
  activeReportId: null,
  activeReport: null,

  benchmarks: [],
  selectedBenchmarkId: null,

  // Graph Overlay & Canvas State (Phase 2)
  graphOverlay: null,
  isLoadingOverlay: false,
  selectedOverlayItem: null,
  alignmentFilters: DEFAULT_ALIGNMENT_FILTERS,
  ghostOpacity: 0.4,
  bourbakiHullEnabled: false,
  selectedBourbakiClasses: new Set(DEFAULT_BOURBAKI_CLASSES),
  isAmbiguousDrawerOpen: false,
  cycleHighlightNodeIds: null,
  selectedGroundingComponentId: null,

  stagedAdjudications: new Map<string, EdgeAdjudicationItem>(),
  optimisticScalarDeltas: INITIAL_OPTIMISTIC_DELTAS,
  isCommittingBatch: false,

  isLoading: false,
  error: null,

  setActiveMode: (mode) => set({ activeMode: mode }),

  setActiveSubTab: (tab) => set({ activeSubTab: tab }),

  setActiveReportId: (id) => {
    set({
      activeReportId: id,
      selectedOverlayItem: null,
      cycleHighlightNodeIds: null,
    });
    if (id) {
      get().fetchReportDetail(id);
      get().fetchGraphOverlay(id);
    } else {
      set({ activeReport: null, graphOverlay: null });
    }
  },

  setActiveReport: (report) => {
    set({
      activeReport: report,
      activeReportId: report ? report.evaluation_id : null,
      selectedOverlayItem: null,
      cycleHighlightNodeIds: null,
    });
    if (report) {
      get().fetchGraphOverlay(report.evaluation_id);
    } else {
      set({ graphOverlay: null });
    }
  },

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

  fetchGraphOverlay: async (evaluationId: string) => {
    if (typeof window === "undefined") {
      set({ isLoadingOverlay: false });
      return null;
    }
    set({ isLoadingOverlay: true });
    try {
      const overlay = await api.getEvaluationGraphOverlay(evaluationId, {
        includeGhosts: true,
      });
      set({ graphOverlay: overlay, isLoadingOverlay: false });
      return overlay;
    } catch (err: any) {
      console.warn("Failed to fetch graph overlay:", err);
      set({ isLoadingOverlay: false });
      return null;
    }
  },

  setSelectedOverlayItem: (item) => set({ selectedOverlayItem: item }),

  toggleAlignmentFilter: (key) => {
    const current = get().alignmentFilters;
    set({
      alignmentFilters: {
        ...current,
        [key]: !current[key],
      },
    });
  },

  setAlignmentFilters: (filters) => set({ alignmentFilters: filters }),

  setGhostOpacity: (opacity) =>
    set({ ghostOpacity: Math.max(0.1, Math.min(1.0, opacity)) }),

  setBourbakiHullEnabled: (enabled) => set({ bourbakiHullEnabled: enabled }),

  toggleBourbakiClass: (cls) => {
    const current = new Set(get().selectedBourbakiClasses);
    if (current.has(cls)) {
      current.delete(cls);
    } else {
      current.add(cls);
    }
    set({ selectedBourbakiClasses: current });
  },

  setIsAmbiguousDrawerOpen: (open) => set({ isAmbiguousDrawerOpen: open }),

  setCycleHighlightNodeIds: (nodeIds) => set({ cycleHighlightNodeIds: nodeIds }),

  setSelectedGroundingComponentId: (id) => set({ selectedGroundingComponentId: id }),

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
      graphOverlay: null,
      selectedOverlayItem: null,
      isAmbiguousDrawerOpen: false,
      cycleHighlightNodeIds: null,
      selectedGroundingComponentId: null,
      stagedAdjudications: new Map(),
      optimisticScalarDeltas: INITIAL_OPTIMISTIC_DELTAS,
      isCommittingBatch: false,
      error: null,
    });
  },
}));
