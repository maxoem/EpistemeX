import { create } from "zustand";
import { api } from "../api/client";
import {
  Capabilities,
  GlobalStructuralAnchor,
  RunDetail,
  RunSummary,
  StartRunPayload,
  StudioEvent,
  StudioNode,
} from "../api/types";
import { useCredentialStore } from "./credentialStore";
import { useProjectSettingsStore } from "./projectSettingsStore";
import { resolvePhaseKey } from "../panels/phaseConfig/phaseConfigResolver";
import { calculateProgressionSnapshots } from "../panels/progressionUtils";

export interface ProgressionSnapshot {
  step: number;
  count: number;
  scores: number[];
  mean: number;
  timestamp: string;
}

export interface SubtaskProgress {
  id: string;
  taskName: string;
  description: string;
  phaseName?: string | null;
  phaseOrdinal?: number | null;
  completed: number;
  total: number | null;
  percentage: number | null;
  status: "running" | "completed" | "failed";
  startedAt: string;
  completedAt?: string | null;
  updatedAt: string;
  elapsedSeconds: number;
  remainingSeconds: number | null;
  rate: number | null;
}

export interface LiveProgress {
  phaseName?: string | null;
  phaseOrdinal?: number | null;
  taskName?: string | null;
  description?: string | null;
  step?: number | null;
  totalSteps?: number | null;
  percentage?: number | null;
  lastUpdated?: string | null;
  elapsedSeconds?: number;
  remainingSeconds?: number | null;
  rate?: number | null;
  activeSubtasks?: SubtaskProgress[];
  allSubtasks?: SubtaskProgress[];
}

interface RunsState {
  runs: RunSummary[];
  selectedRunId: string | null;
  selectedRunDetail: RunDetail | null;
  events: StudioEvent[];
  lastSeq: number;
  liveProgress: LiveProgress | null;
  subtasks: Record<string, SubtaskProgress>;
  showSubtasksInTerminal: boolean;
  setShowSubtasksInTerminal: (show: boolean) => void;
  phaseScores: Record<string, number[]>;
  phaseProgression: Record<string, ProgressionSnapshot[]>;
  getOrGenerateProgressionSnapshots: (phaseKey: string, interval?: number) => ProgressionSnapshot[];
  capabilities: Capabilities | null;
  isLoadingRuns: boolean;
  isLoadingDetail: boolean;
  isStreaming: boolean;
  logFilterLevel: string;
  logFilterPhase: string;
  logSearch: string;
  autoScroll: boolean;
  searchableNodes: StudioNode[];
  setSearchableNodes: (nodes: StudioNode[]) => void;
  focusedNodeId: string | null;
  setFocusedNodeId: (nodeId: string | null) => void;
  recentDecisions: StudioEvent[];
  liveDecisionCounters: {
    fastExit: number;
    escalated: number;
    audit: number;
    total: number;
    tokensSaved: number;
    costSavedUsd: number;
  };

  fetchCapabilities: () => Promise<void>;
  fetchRuns: () => Promise<void>;
  selectRun: (runId: string) => Promise<void>;
  refreshActiveRun: () => Promise<void>;
  addEvent: (event: StudioEvent) => void;
  addEvents: (events: StudioEvent[]) => void;
  clearEvents: () => void;
  setLogFilterLevel: (level: string) => void;
  setLogFilterPhase: (phase: string) => void;
  setLogSearch: (query: string) => void;
  setAutoScroll: (enabled: boolean) => void;
  setIsStreaming: (streaming: boolean) => void;
  defaultDriver: "artifacts" | "neo4j";
  setDefaultDriver: (driver: "artifacts" | "neo4j") => void;
  activeDataSource: "artifacts" | "neo4j";
  setActiveDataSource: (source: "artifacts" | "neo4j") => void;
  forkedRunDetail: RunDetail | null;
  setForkedRunDetail: (run: RunDetail | null) => void;
  forkRun: (run: RunDetail) => void;
  startNewRun: (
    options?:
      | boolean
      | {
          demoMode?: boolean;
          patch?: Record<string, any>;
          profileId?: string;
          sourcePaths?: string[];
          bibPaths?: string[];
          metadata?: Record<string, string>;
          structuralAnchor?: GlobalStructuralAnchor | null;
          parentRunId?: string | null;
        }
  ) => Promise<RunSummary>;
  selectedPhaseKey: string | null;
  setSelectedPhaseKey: (phaseKey: string | null) => void;
  cancelCurrentRun: () => Promise<void>;
  isCancellingRun: boolean;
  cancelError: string | null;
}

const getInitialDriver = (): "artifacts" | "neo4j" => {
  if (typeof window === "undefined") return "artifacts";
  try {
    const stored = localStorage.getItem("glp-studio-default-driver");
    if (stored === "artifacts" || stored === "neo4j") return stored;
    return "artifacts";
  } catch {
    return "artifacts";
  }
};

const getInitialDataSource = (): "artifacts" | "neo4j" => {
  if (typeof window === "undefined") return "artifacts";
  try {
    const stored = localStorage.getItem("glp-studio-active-data-source");
    if (stored === "artifacts" || stored === "neo4j") return stored;
    return "artifacts";
  } catch {
    return "artifacts";
  }
};

export const useRunsStore = create<RunsState>((set, get) => ({
  runs: [],
  selectedRunId: null,
  selectedRunDetail: null,
  events: [],
  lastSeq: 0,
  liveProgress: null,
  subtasks: {},
  showSubtasksInTerminal: true,
  setShowSubtasksInTerminal: (show: boolean) => set({ showSubtasksInTerminal: show }),
  phaseScores: {},
  phaseProgression: {},
  capabilities: null,
  isLoadingRuns: false,
  isLoadingDetail: false,
  isStreaming: false,
  isCancellingRun: false,
  cancelError: null,
  logFilterLevel: "all",
  logFilterPhase: "all",
  logSearch: "",
  autoScroll: true,
  searchableNodes: [],
  setSearchableNodes: (nodes: StudioNode[]) => set({ searchableNodes: nodes }),
  focusedNodeId: null,
  setFocusedNodeId: (nodeId: string | null) => set({ focusedNodeId: nodeId }),
  recentDecisions: [],
  liveDecisionCounters: {
    fastExit: 0,
    escalated: 0,
    audit: 0,
    total: 0,
    tokensSaved: 0,
    costSavedUsd: 0,
  },
  defaultDriver: getInitialDriver(),
  activeDataSource: getInitialDataSource(),
  forkedRunDetail: null,
  setForkedRunDetail: (run: RunDetail | null) => set({ forkedRunDetail: run }),
  forkRun: (run: RunDetail) => set({ forkedRunDetail: run }),
  selectedPhaseKey: "phase2",
  setSelectedPhaseKey: (phaseKey: string | null) => set({ selectedPhaseKey: phaseKey }),

  setDefaultDriver: (driver: "artifacts" | "neo4j") => {
    try {
      localStorage.setItem("glp-studio-default-driver", driver);
    } catch {}
    set({ defaultDriver: driver });
  },

  setActiveDataSource: (source: "artifacts" | "neo4j") => {
    const isRunning = get().selectedRunDetail?.status === "running";
    const hasNeo4j = Boolean(get().capabilities?.neo4j);
    const runUsesNeo4j = hasNeo4j && (get().selectedRunDetail?.config_snapshot?.execution?.project_artifacts_to_graph ?? false);
    const targetSource = isRunning && runUsesNeo4j ? "neo4j" : source;
    try {
      localStorage.setItem("glp-studio-active-data-source", targetSource);
    } catch {}
    set({ activeDataSource: targetSource });
  },

  getOrGenerateProgressionSnapshots: (phaseKey: string, customInterval?: number): ProgressionSnapshot[] => {
    const { phaseProgression, phaseScores } = get();
    const existing = phaseProgression[phaseKey];
    if (existing && existing.length > 0) {
      return existing;
    }
    const rawScores = phaseScores[phaseKey] || [];
    const interval = customInterval || useProjectSettingsStore.getState().confidenceProgressionInterval || 20;
    return calculateProgressionSnapshots(rawScores, interval);
  },

  fetchCapabilities: async () => {
    try {
      const caps = await api.getCapabilities();
      set({ capabilities: caps });
    } catch (err) {
      console.error("Failed to load capabilities:", err);
    }
  },

  fetchRuns: async () => {
    set({ isLoadingRuns: true });
    try {
      const runs = await api.listRuns();
      set({ runs, isLoadingRuns: false });
      // If no run selected and runs exist, auto-select first run
      if (!get().selectedRunId && runs.length > 0) {
        get().selectRun(runs[0].run_id);
      }
    } catch (err) {
      console.error("Failed to load runs:", err);
      set({ isLoadingRuns: false });
    }
  },

  selectRun: async (runId: string) => {
    const currentSource = get().activeDataSource || getInitialDataSource();
    set({
      selectedRunId: runId,
      isLoadingDetail: true,
      events: [],
      lastSeq: 0,
      liveProgress: null,
      subtasks: {},
      phaseScores: {},
      phaseProgression: {},
      activeDataSource: currentSource,
    });
    try {
      const detail = await api.getRun(runId);
      const isRunning = detail.status === "running";
      const hasNeo4j = Boolean(get().capabilities?.neo4j);
      const runUsesNeo4j = hasNeo4j && (detail.config_snapshot?.execution?.project_artifacts_to_graph ?? false);
      const resolvedSource = isRunning
        ? (runUsesNeo4j ? "neo4j" : "artifacts")
        : (currentSource === "neo4j" && !hasNeo4j ? "artifacts" : currentSource);
      try {
        localStorage.setItem("glp-studio-active-data-source", resolvedSource);
      } catch {}
      set({ selectedRunDetail: detail, isLoadingDetail: false, activeDataSource: resolvedSource });
    } catch (err) {
      console.error(`Failed to load detail for run ${runId}:`, err);
      set({ isLoadingDetail: false });
    }
  },

  refreshActiveRun: async () => {
    const { selectedRunId } = get();
    if (!selectedRunId) return;
    try {
      const [detail, runs] = await Promise.all([
        api.getRun(selectedRunId),
        api.listRuns(),
      ]);
      const isRunning = detail.status === "running";
      const hasNeo4j = Boolean(get().capabilities?.neo4j);
      const runUsesNeo4j = hasNeo4j && (detail.config_snapshot?.execution?.project_artifacts_to_graph ?? false);
      set((state) => ({
        selectedRunDetail: detail,
        runs,
        activeDataSource: isRunning && runUsesNeo4j ? "neo4j" : state.activeDataSource,
      }));
    } catch (err) {
      // transient fetch failure during active run poll
    }
  },

  addEvent: (event: StudioEvent) => {
    get().addEvents([event]);
  },

  addEvents: (incomingEvents: StudioEvent[]) => {
    if (!incomingEvents || incomingEvents.length === 0) return;
    set((state) => {
      let lastSeq = state.lastSeq || 0;
      const validEvents: StudioEvent[] = [];

      for (const event of incomingEvents) {
        if (typeof event.seq === "number") {
          if (event.seq <= lastSeq) {
            continue;
          }
          lastSeq = event.seq;
        } else if (state.events.some((e) => e.seq === event.seq)) {
          continue;
        }
        validEvents.push(event);
      }

      if (validEvents.length === 0) {
        return state;
      }

      let newEvents = [...state.events, ...validEvents];
      const MAX_STORE_EVENTS = 5000;
      if (newEvents.length > MAX_STORE_EVENTS) {
        newEvents = newEvents.slice(newEvents.length - MAX_STORE_EVENTS);
      }

      let newDetail = state.selectedRunDetail;
      let newLiveProgress = state.liveProgress;
      let newRuns = state.runs;
      const newSubtasks: Record<string, SubtaskProgress> = { ...state.subtasks };
      const newPhaseScores: Record<string, number[]> = { ...state.phaseScores };
      const newPhaseProgression: Record<string, ProgressionSnapshot[]> = { ...state.phaseProgression };
      let newRecentDecisions = [...(state.recentDecisions || [])];
      const newDecisionCounters = {
        ...(state.liveDecisionCounters || {
          fastExit: 0,
          escalated: 0,
          audit: 0,
          total: 0,
          tokensSaved: 0,
          costSavedUsd: 0,
        }),
      };

      for (const event of validEvents) {
        const kind = event.kind || "";
        const rawType = (event.payload?._raw_type as string) || "";

        if (kind.startsWith("decision.")) {
          newRecentDecisions.push(event);
          if (newRecentDecisions.length > 500) {
            newRecentDecisions = newRecentDecisions.slice(newRecentDecisions.length - 500);
          }
          const tier = (event.payload?.tier as string) || "";
          if (tier === "fast_exit") newDecisionCounters.fastExit++;
          else if (tier === "system2") newDecisionCounters.escalated++;
          else if (tier === "stochastic_audit") newDecisionCounters.audit++;
          newDecisionCounters.total++;

          if (typeof event.payload?.tokens_saved === "number") {
            newDecisionCounters.tokensSaved += event.payload.tokens_saved;
          }
          if (typeof event.payload?.cost_saved_usd === "number") {
            newDecisionCounters.costSavedUsd += event.payload.cost_saved_usd;
          }
        }
        let phaseName =
          event.phase ||
          (event.payload?.component_name as string) ||
          (event.payload?.phase_name as string) ||
          (event.payload?.phase as string);

        if (!phaseName) {
          const taskStr = (event.payload?.task_name as string) || (event.payload?.description as string) || "";
          if (taskStr.toLowerCase().includes("maturation")) {
            phaseName = "Phase 4: Entity Maturation (Batch Epistemic Synthesis)";
          } else if (taskStr.toLowerCase().includes("argument")) {
            phaseName = "Phase 4: Argument Mining";
          }
        }

        const phaseOrdinal = typeof event.payload?.phase_ordinal === "number" ? event.payload.phase_ordinal : undefined;
        const isCurrentRun = !event.run_id || event.run_id === state.selectedRunId;

        const matchesPhase = (pName: string, pOrd: number) => {
          if (phaseOrdinal !== undefined && pOrd === phaseOrdinal) return true;
          if (!phaseName) return false;
          const targetStr = phaseName.trim().toLowerCase();
          const recLower = pName.trim().toLowerCase();
          if (recLower === targetStr) return true;
          // Guard against cross-matching distinct phases that share prefix numbers
          if (
            (targetStr.includes("maturation") && recLower.includes("argument")) ||
            (targetStr.includes("argument") && recLower.includes("maturation"))
          ) {
            return false;
          }
          if (
            (targetStr.includes("3b") && !recLower.includes("3b")) ||
            (recLower.includes("3b") && !targetStr.includes("3b"))
          ) {
            return false;
          }
          if (/^phase\s*\d+$/i.test(targetStr)) {
            return false;
          }
          if (recLower.includes(targetStr) || targetStr.includes(recLower)) return true;
          return false;
        };

        // Extract confidence score or evaluation metric from event payload
        let scoreVal: number | null = null;
        if (typeof event.payload?.confidence === "number") {
          scoreVal = event.payload.confidence;
        } else if (typeof event.payload?.score === "number") {
          scoreVal = event.payload.score;
        } else if (typeof event.payload?.plausibility === "number") {
          scoreVal = event.payload.plausibility;
        }

        // Determine canonical target phase key
        let targetScorePhaseKey: string | null = null;
        if (phaseName || phaseOrdinal !== undefined) {
          targetScorePhaseKey = resolvePhaseKey({ phase_name: phaseName, phase_ordinal: phaseOrdinal });
        } else {
          const runningRec = (newDetail?.phase_records || []).find((p) => p.status === "running");
          if (runningRec) {
            targetScorePhaseKey = resolvePhaseKey(runningRec);
          }
        }

        if (targetScorePhaseKey && scoreVal !== null && Number.isFinite(scoreVal)) {
          const clamped = Math.max(0, Math.min(1, scoreVal));
          const prevScores = newPhaseScores[targetScorePhaseKey] || [];
          const updatedScores = [...prevScores, clamped];
          newPhaseScores[targetScorePhaseKey] = updatedScores;

          const interval = useProjectSettingsStore.getState().confidenceProgressionInterval || 20;
          if (updatedScores.length % interval === 0) {
            const prevProg = newPhaseProgression[targetScorePhaseKey] || [];
            const mean = updatedScores.reduce((a, b) => a + b, 0) / updatedScores.length;
            newPhaseProgression[targetScorePhaseKey] = [
              ...prevProg,
              {
                step: Math.floor(updatedScores.length / interval),
                count: updatedScores.length,
                scores: [...updatedScores],
                mean: Math.round(mean * 1000) / 1000,
                timestamp: event.ts || new Date().toISOString(),
              },
            ];
          }
        }

        if (isCurrentRun && newDetail) {
          const taskName = (event.payload?.task_name as string) || (event.payload?.description as string) || phaseName || "";
          const taskKey = taskName || "active-task";

          // Handle phase/component started
          const isPhaseStart =
            kind === "phase.component_started" ||
            rawType === "ComponentStarted" ||
            rawType === "PhaseStarted" ||
            (kind === "progress.started" && !!phaseName) ||
            (kind.includes("started") && !!phaseName);

          if (isPhaseStart) {
            const phases = (newDetail.phase_records || []).map((p) => {
              const matches = matchesPhase(p.phase_name, p.phase_ordinal);
              if (matches) {
                return { ...p, status: "running" as const, started_at: p.started_at || event.ts };
              }
              // Auto-complete preceding running phases when a new phase starts
              if (p.status === "running") {
                return { ...p, status: "completed" as const, completed_at: p.completed_at || event.ts };
              }
              return p;
            });
            newDetail = { ...newDetail, status: "running", phase_records: phases };
          }

          // Subtask / Progress tracking: ProgressStarted
          if (kind === "progress.started" || rawType === "ProgressStarted") {
            const totalItems = (event.payload?.total_items as number) ?? (event.payload?.total as number) ?? null;
            const desc = (event.payload?.description as string) || taskName || `Starting ${phaseName || "task"}...`;
            newSubtasks[taskKey] = {
              id: taskKey,
              taskName,
              description: desc,
              phaseName: phaseName || null,
              phaseOrdinal: phaseOrdinal ?? null,
              completed: 0,
              total: totalItems,
              percentage: totalItems && totalItems > 0 ? 0 : null,
              status: "running",
              startedAt: event.ts || new Date().toISOString(),
              updatedAt: event.ts || new Date().toISOString(),
              elapsedSeconds: 0,
              remainingSeconds: null,
              rate: null,
            };
          }
          // Subtask / Progress tracking: ProgressAdvanced
          else if (kind === "progress.step" || rawType === "ProgressAdvanced") {
            const advance = (event.payload?.advance as number) || 1;
            const existing = newSubtasks[taskKey];
            const current = (event.payload?.current as number) ?? ((existing?.completed ?? 0) + advance);
            const total = (event.payload?.total_items as number) ?? (event.payload?.total as number) ?? existing?.total ?? null;
            const startedAt = existing?.startedAt || event.ts || new Date().toISOString();
            const nowMs = event.ts ? new Date(event.ts).getTime() : Date.now();
            const startMs = new Date(startedAt).getTime();
            const elapsedSeconds = Math.max(0.1, (nowMs - startMs) / 1000);
            const rate = current > 0 ? current / elapsedSeconds : null;
            const remainingSeconds =
              rate && total && total > current
                ? Math.max(0, Math.round((total - current) / rate))
                : 0;
            const percentage = total && total > 0 ? Math.min(100, Math.round((current / total) * 100)) : null;

            newSubtasks[taskKey] = {
              ...(existing || {}),
              id: taskKey,
              taskName: (event.payload?.task_name as string) || existing?.taskName || taskKey,
              description: (event.payload?.description as string) || existing?.description || taskKey,
              phaseName: phaseName || existing?.phaseName || null,
              phaseOrdinal: phaseOrdinal ?? existing?.phaseOrdinal ?? null,
              completed: current,
              total,
              percentage,
              status: "running", // Keep honest remaining state; only ProgressCompleted transitions to completed
              startedAt,
              updatedAt: event.ts || new Date().toISOString(),
              elapsedSeconds: Math.round(elapsedSeconds),
              remainingSeconds,
              rate,
            };
          }
          // Subtask / Progress tracking: ProgressCompleted
          else if (kind === "progress.completed" || rawType === "ProgressCompleted") {
            const existing = newSubtasks[taskKey];
            const finalCompleted = existing?.total ?? existing?.completed ?? 1;
            const startedAt = existing?.startedAt || event.ts || new Date().toISOString();
            const elapsed = Math.round(
              Math.max(0.1, ((event.ts ? new Date(event.ts).getTime() : Date.now()) - new Date(startedAt).getTime()) / 1000)
            );

            newSubtasks[taskKey] = {
              ...(existing || {}),
              id: taskKey,
              taskName: (event.payload?.task_name as string) || existing?.taskName || taskKey,
              description: (event.payload?.description as string) || existing?.description || taskKey,
              phaseName: phaseName || existing?.phaseName || null,
              phaseOrdinal: phaseOrdinal ?? existing?.phaseOrdinal ?? null,
              completed: finalCompleted,
              total: finalCompleted,
              percentage: 100,
              status: "completed",
              startedAt,
              completedAt: event.ts || new Date().toISOString(),
              updatedAt: event.ts || new Date().toISOString(),
              elapsedSeconds: elapsed,
              remainingSeconds: 0,
              rate: existing?.rate ?? null,
            };
          }

          // Recompute consolidated liveProgress from active subtasks and phase
          const activeSubtaskList = Object.values(newSubtasks).filter((s) => s.status === "running");
          const allSubtaskList = Object.values(newSubtasks);
          const primaryActive = activeSubtaskList[activeSubtaskList.length - 1] || allSubtaskList[allSubtaskList.length - 1];

          if (primaryActive) {
            newLiveProgress = {
              phaseName: primaryActive.phaseName || phaseName || newLiveProgress?.phaseName,
              phaseOrdinal: primaryActive.phaseOrdinal ?? phaseOrdinal ?? newLiveProgress?.phaseOrdinal,
              taskName: primaryActive.taskName,
              description: primaryActive.description,
              step: primaryActive.completed,
              totalSteps: primaryActive.total,
              percentage: primaryActive.percentage,
              elapsedSeconds: primaryActive.elapsedSeconds,
              remainingSeconds: primaryActive.remainingSeconds,
              rate: primaryActive.rate,
              activeSubtasks: activeSubtaskList,
              allSubtasks: allSubtaskList,
              lastUpdated: event.ts,
            };
          } else if (isPhaseStart) {
            newLiveProgress = {
              ...newLiveProgress,
              phaseName: phaseName || newLiveProgress?.phaseName,
              taskName: (event.payload?.task_name as string) || phaseName || newLiveProgress?.taskName,
              description: (event.payload?.description as string) || `Executing ${phaseName || "pipeline phase"}...`,
              activeSubtasks: [],
              allSubtasks: allSubtaskList,
              lastUpdated: event.ts,
            };
          }
          // Handle phase completed
          else if (
            kind === "phase.completed" ||
            kind === "phase.component_completed" ||
            rawType === "PhaseCompleted" ||
            rawType === "ComponentCompleted"
          ) {
            const addedArtifacts = (event.payload?.artifact_count as number) || 0;
            const phases = (newDetail.phase_records || []).map((p) => {
              const matches = matchesPhase(p.phase_name, p.phase_ordinal);
              if (matches) {
                return {
                  ...p,
                  status: "completed" as const,
                  completed_at: event.ts,
                  artifact_count: p.artifact_count + addedArtifacts,
                  duration_seconds: (event.payload?.duration_seconds as number) ?? p.duration_seconds,
                };
              }
              return p;
            });
            const totalArts = phases.reduce((sum, p) => sum + (p.artifact_count || 0), 0);
            newDetail = {
              ...newDetail,
              phase_records: phases,
              artifact_count: Math.max(newDetail.artifact_count, totalArts),
            };

            // Record final progression snapshot on phase completion if not already captured
            if (targetScorePhaseKey && newPhaseScores[targetScorePhaseKey]?.length > 0) {
              const raw = newPhaseScores[targetScorePhaseKey];
              const prog = newPhaseProgression[targetScorePhaseKey] || [];
              if (prog.length === 0 || prog[prog.length - 1].count < raw.length) {
                const mean = raw.reduce((a, b) => a + b, 0) / raw.length;
                newPhaseProgression[targetScorePhaseKey] = [
                  ...prog,
                  {
                    step: prog.length + 1,
                    count: raw.length,
                    scores: [...raw],
                    mean: Math.round(mean * 1000) / 1000,
                    timestamp: event.ts || new Date().toISOString(),
                  },
                ];
              }
            }
          }
          // Real-time domain events incrementing live artifact counts
          else if (
            kind === "chunks.generated" ||
            rawType === "ChunksGenerated" ||
            kind === "entity.processed" ||
            rawType === "EntityProcessed" ||
            kind === "relation.triple_committed" ||
            rawType === "TripleCommitted" ||
            kind === "fusion.decision_made" ||
            rawType === "FusionDecisionMade"
          ) {
            const currentCounts = { ...(newDetail.artifact_counts_by_kind || {}) };
            let delta = 1;
            let kindKey = "artifact";

            if (kind === "chunks.generated" || rawType === "ChunksGenerated") {
              kindKey = "chunk";
              delta = (event.payload?.count as number) || 1;
            } else if (kind === "entity.processed" || rawType === "EntityProcessed") {
              kindKey = "entity";
            } else if (kind === "relation.triple_committed" || rawType === "TripleCommitted") {
              kindKey = "local_relation";
            } else if (kind === "fusion.decision_made" || rawType === "FusionDecisionMade") {
              kindKey = "fusion_cluster";
            }

            currentCounts[kindKey] = (currentCounts[kindKey] || 0) + delta;
            const newTotalArtifacts = Math.max(
              newDetail.artifact_count + delta,
              Object.values(currentCounts).reduce((acc, val) => acc + val, 0)
            );

            // If there's an active running phase, increment its artifact count as well
            const updatedPhases = (newDetail.phase_records || []).map((p) => {
              if (p.status === "running") {
                const pCounts = { ...(p.artifact_counts_by_kind || {}) };
                pCounts[kindKey] = (pCounts[kindKey] || 0) + delta;
                return {
                  ...p,
                  artifact_count: p.artifact_count + delta,
                  artifact_counts_by_kind: pCounts,
                };
              }
              return p;
            });

            newDetail = {
              ...newDetail,
              artifact_count: newTotalArtifacts,
              artifact_counts_by_kind: currentCounts,
              phase_records: updatedPhases,
            };
          }
          // Handle terminal states
          else if (kind === "run.completed" || event.payload?._type === "RUN_COMPLETED") {
            newDetail = { ...newDetail, status: "completed", completed_at: event.ts };
            newLiveProgress = null;
          } else if (kind === "run.failed" || event.payload?._type === "RUN_FAILED") {
            newDetail = { ...newDetail, status: "failed", completed_at: event.ts };
            newLiveProgress = null;
          } else if (kind === "run.aborted") {
            newDetail = { ...newDetail, status: "aborted", completed_at: event.ts };
            newLiveProgress = null;
          }

          // Keep matching run in runs array synchronized
          if (newDetail) {
            newRuns = newRuns.map((r) => (r.run_id === newDetail?.run_id ? { ...r, ...newDetail } : r));
          }
        }
      }

      const isRunRunning = newDetail?.status === "running";
      const hasNeo4j = Boolean(state.capabilities?.neo4j);
      const runUsesNeo4j = hasNeo4j && (newDetail?.config_snapshot?.execution?.project_artifacts_to_graph ?? false);
      const nextSource = isRunRunning && runUsesNeo4j ? "neo4j" : state.activeDataSource;

      return {
        events: newEvents,
        lastSeq,
        selectedRunDetail: newDetail,
        liveProgress: newLiveProgress,
        subtasks: newSubtasks,
        runs: newRuns,
        phaseScores: newPhaseScores,
        phaseProgression: newPhaseProgression,
        recentDecisions: newRecentDecisions,
        liveDecisionCounters: newDecisionCounters,
        activeDataSource: nextSource,
      };
    });
  },

  clearEvents: () =>
    set({
      events: [],
      lastSeq: 0,
      subtasks: {},
      liveProgress: null,
      phaseScores: {},
      phaseProgression: {},
      recentDecisions: [],
      liveDecisionCounters: {
        fastExit: 0,
        escalated: 0,
        audit: 0,
        total: 0,
        tokensSaved: 0,
        costSavedUsd: 0,
      },
    }),
  setLogFilterLevel: (level: string) => set({ logFilterLevel: level }),
  setLogFilterPhase: (phase: string) => set({ logFilterPhase: phase }),
  setLogSearch: (query: string) => set({ logSearch: query }),
  setAutoScroll: (enabled: boolean) => set({ autoScroll: enabled }),
  setIsStreaming: (streaming: boolean) => set({ isStreaming: streaming }),

  startNewRun: async (options) => {
    let payload: StartRunPayload = {};
    if (typeof options === "boolean") {
      payload = { demo_mode: options, parent_run_id: get().forkedRunDetail?.run_id || null };
    } else if (options) {
      payload = {
        demo_mode: options.demoMode ?? false,
        patch: options.patch,
        profile_id: options.profileId,
        source_paths: options.sourcePaths,
        bib_paths: options.bibPaths,
        metadata: options.metadata,
        structural_anchor: options.structuralAnchor,
        parent_run_id: options.parentRunId || get().forkedRunDetail?.run_id || null,
      };
    } else {
      payload = { demo_mode: false, parent_run_id: get().forkedRunDetail?.run_id || null };
    }
    const summary = await api.startRun(payload);
    // If last used Neo4j credentials exist, associate them with this new run in browser storage
    const lastCreds = useCredentialStore.getState().lastUsedCredentials;
    if (lastCreds) {
      useCredentialStore.getState().saveRunCredentials(summary.run_id, lastCreds);
    }
    const hasNeo4j = Boolean(get().capabilities?.neo4j);
    const projectsToNeo4j = options && typeof options === "object"
      ? options.patch?.["execution.project_artifacts_to_graph"] ?? false
      : false;
    const targetSource = (hasNeo4j && projectsToNeo4j) ? "neo4j" : "artifacts";
    set({ activeDataSource: targetSource, forkedRunDetail: null });
    try {
      localStorage.setItem("glp-studio-active-data-source", targetSource);
    } catch {}

    await get().fetchRuns();
    await get().selectRun(summary.run_id);
    return summary;
  },

  cancelCurrentRun: async () => {
    const { selectedRunId } = get();
    if (!selectedRunId) return;
    set({ isCancellingRun: true, cancelError: null });
    try {
      const summary = await api.cancelRun(selectedRunId);
      // Immediately reflect aborted status in store state
      set((state) => ({
        runs: state.runs.map((r) => (r.run_id === selectedRunId ? { ...r, status: "aborted" } : r)),
        selectedRunDetail:
          state.selectedRunDetail?.run_id === selectedRunId
            ? {
                ...state.selectedRunDetail,
                status: "aborted",
                completed_at: summary.completed_at || new Date().toISOString(),
                phase_records: state.selectedRunDetail.phase_records.map((p) =>
                  p.status === "running" ? { ...p, status: "aborted" } : p
                ),
              }
            : state.selectedRunDetail,
        liveProgress: null,
      }));
      await get().selectRun(selectedRunId);
      await get().fetchRuns();
    } catch (err: any) {
      console.error("Failed to cancel run:", err);
      set({ cancelError: err?.message || "Failed to cancel run." });
    } finally {
      set({ isCancellingRun: false });
    }
  },
}));
