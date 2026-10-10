import {create} from "zustand";
import {api} from "../api/client.ts";
import type {
    ExecuteMetricRequest,
    ExecutionStatusResponse,
    MetricDescriptor,
    MetricExecutionQueuedResponse,
    MetricResult,
    MetricRunInstance,
    MetricScope,
    StyleConflictInfo,
} from "../api/types.ts";

export function computeStyleConflicts(instances: MetricRunInstance[]): StyleConflictInfo {
  const activeCompleted = instances.filter(
    (i) => i.status === "completed" && i.result && i.styling?.enabled !== false
  );
  const sizeInstances = activeCompleted
    .filter((i) => i.styling?.sizeScaling)
    .map((i) => i.instanceId);
  const colorInstances = activeCompleted
    .filter((i) => i.styling?.colorGradient)
    .map((i) => i.instanceId);

  return {
    hasSizeConflict: sizeInstances.length > 1,
    conflictingSizeInstances: sizeInstances,
    hasColorConflict: colorInstances.length > 1,
    conflictingColorInstances: colorInstances,
    activeSizeCount: sizeInstances.length,
    activeColorCount: colorInstances.length,
  };
}

export function extractDescriptorDefaults(descriptor?: MetricDescriptor): Record<string, any> {
  if (!descriptor?.param_schema?.properties) return {};
  const defaults: Record<string, any> = {};
  for (const [key, spec] of Object.entries<any>(descriptor.param_schema.properties)) {
    if (spec.default !== undefined) {
      defaults[key] = spec.default;
    } else if (spec.type === "boolean") {
      defaults[key] = false;
    } else if (spec.type === "integer" || spec.type === "number") {
      defaults[key] = 0;
    } else if (spec.type === "string") {
      defaults[key] = "";
    }
  }
  return defaults;
}

interface InstanceTask {
  abortController: AbortController;
  timerInterval: any;
}

const instanceTasks = new Map<string, InstanceTask>();

interface MetricsState {
  descriptors: MetricDescriptor[];
  isLoadingDescriptors: boolean;
  instances: MetricRunInstance[];
  activeInstanceId: string | null;
  currentView: "stack" | "detail" | "catalog";
  scaleMode: "stack" | "overwrite";
  isDrawerOpen: boolean;

  // Single-metric backward compatibility properties
  activeMetricResult: MetricResult | null;
  selectedMetricId: string | null;
  selectedScope: MetricScope;
  isCalculating: boolean;
  calculationElapsedSeconds: number;
  calculationError: string | null;
  stylingVersion: number;
  executionElapsed: Record<string, number>;
  activeFocusNodeId: string | null;
  requestSequence: number;

  fetchDescriptors: () => Promise<void>;
  addInstance: (metricId?: string, focusNodeId?: string) => string;
  removeInstance: (instanceId: string) => void;
  updateInstance: (instanceId: string, updates: Partial<MetricRunInstance>) => void;
  updateInstanceStyling: (
    instanceId: string,
    updates: Partial<MetricRunInstance["styling"]>
  ) => void;
  toggleInstanceConfig: (instanceId: string) => void;
  toggleInstanceCollapsed: (instanceId: string) => void;
  setScaleMode: (mode: "stack" | "overwrite") => void;
  setCurrentView: (view: "stack" | "detail" | "catalog") => void;
  openDetailView: (instanceId: string) => void;
  clearAllInstances: () => void;
  openDrawer: (scope?: MetricScope, metricId?: string, focusNodeId?: string) => void;
  closeDrawer: () => void;

  runInstance: (
    instanceId: string,
    options?: {
      source?: "artifacts" | "neo4j" | null;
      runId?: string | null;
      graphVersion?: string | null;
    }
  ) => Promise<void>;
  cancelInstance: (instanceId: string) => Promise<void>;

  // Legacy single-metric runners
  runCalculation: (options: {
    metric_id: string;
    focus_node_id?: string | null;
    params?: Record<string, any>;
    source?: "artifacts" | "neo4j" | null;
    run_id?: string | null;
    graph_version?: string | null;
  }) => Promise<void>;
  cancelCalculation: () => Promise<void>;
  clearMetricResult: () => void;
  setSelectedMetricId: (id: string) => void;
  setSelectedScope: (scope: MetricScope) => void;
}

export const useMetricsStore = create<MetricsState>((set, get) => ({
  descriptors: [],
  isLoadingDescriptors: false,
  instances: [],
  activeInstanceId: null,
  currentView: "stack",
  scaleMode: "stack",
  isDrawerOpen: false,

  stylingVersion: 0,
  executionElapsed: {},
  activeMetricResult: null,
  selectedMetricId: "gradual_strength_local",
  selectedScope: "single_node",
  isCalculating: false,
  calculationElapsedSeconds: 0,
  calculationError: null,
  activeFocusNodeId: null,
  requestSequence: 0,

  fetchDescriptors: async () => {
    set({ isLoadingDescriptors: true });
    try {
      const descriptors = await api.getMetricDefinitions();
      set({ descriptors, isLoadingDescriptors: false });

      // If no instances yet, initialize with a default PageRank instance or first descriptor
      const { instances } = get();
      if (instances.length === 0 && descriptors.length > 0) {
        const defaultMetric =
          descriptors.find((d) => d.id === "pagerank_global") || descriptors[0];
        const defaultInstId = `metric-${Date.now()}`;
        const newInstance: MetricRunInstance = {
          instanceId: defaultInstId,
          metricId: defaultMetric.id,
          params: extractDescriptorDefaults(defaultMetric),
          nodeLabels: [],
          relationshipTypes: [],
          orientation: "natural",
          styling: {
            enabled: true,
            sizeScaling: true,
            colorGradient: false,
            sizeStrength: "normal",
          },
          status: "idle",
          isConfigOpen: false,
          isCollapsed: false,
        };
        set({
          instances: [newInstance],
          activeInstanceId: defaultInstId,
          selectedMetricId: defaultMetric.id,
          selectedScope: defaultMetric.scope,
        });
      }
    } catch (err) {
      console.error("Failed to load metric descriptors:", err);
      set({ isLoadingDescriptors: false });
    }
  },

  addInstance: (metricId?: string, focusNodeId?: string) => {
    const { descriptors, instances } = get();
    const targetMetricId =
      metricId ||
      descriptors.find((d) => !instances.some((inst) => inst.metricId === d.id))?.id ||
      descriptors[0]?.id ||
      "pagerank_global";

    const desc = descriptors.find((d) => d.id === targetMetricId);
    const newId = `metric-${Date.now()}-${Math.floor(Math.random() * 1000)}`;

    const isCentralityOrRanking =
      targetMetricId.includes("pagerank") ||
      targetMetricId.includes("degree") ||
      targetMetricId.includes("centrality");

    const newInstance: MetricRunInstance = {
      instanceId: newId,
      metricId: targetMetricId,
      focusNodeId: focusNodeId ?? null,
      params: extractDescriptorDefaults(desc),
      nodeLabels: [],
      relationshipTypes: [],
      orientation: "natural",
      styling: {
        enabled: true,
        sizeScaling: isCentralityOrRanking,
        colorGradient: !isCentralityOrRanking, // e.g. community or QBAF uses color by default
        sizeStrength: "normal",
      },
      status: "idle",
      isConfigOpen: false,
      isCollapsed: false,
    };

    set((state) => ({
      instances: [newInstance, ...state.instances],
      activeInstanceId: newId,
      currentView: "stack",
    }));

    return newId;
  },

  removeInstance: (instanceId: string) => {
    const task = instanceTasks.get(instanceId);
    if (task) {
      task.abortController.abort();
      clearInterval(task.timerInterval);
      instanceTasks.delete(instanceId);
    }

    set((state) => {
      const filtered = state.instances.filter((i) => i.instanceId !== instanceId);
      const nextActiveId =
        state.activeInstanceId === instanceId
          ? filtered[0]?.instanceId || null
          : state.activeInstanceId;
      const nextActiveResult =
        filtered.find((i) => i.instanceId === nextActiveId)?.result ||
        filtered.find((i) => i.result)?.result ||
        null;

      return {
        instances: filtered,
        activeInstanceId: nextActiveId,
        activeMetricResult: nextActiveResult,
      };
    });
  },

  updateInstance: (instanceId: string, updates: Partial<MetricRunInstance>) => {
    set((state) => {
      const next = state.instances.map((inst) => {
        if (inst.instanceId !== instanceId) return inst;
        const updated = { ...inst, ...updates };

        // If metricId changed, reset default params for new descriptor
        if (updates.metricId && updates.metricId !== inst.metricId) {
          const desc = state.descriptors.find((d) => d.id === updates.metricId);
          updated.params = extractDescriptorDefaults(desc);
          updated.status = "idle";
          updated.result = undefined;
          updated.error = undefined;
        }
        return updated;
      });

      const activeInst = next.find((i) => i.instanceId === state.activeInstanceId);
      return {
        instances: next,
        activeMetricResult: activeInst?.result || state.activeMetricResult,
      };
    });
  },

  updateInstanceStyling: (instanceId: string, updates: Partial<MetricRunInstance["styling"]>) => {
    set((state) => ({
      stylingVersion: state.stylingVersion + 1,
      instances: state.instances.map((inst) =>
        inst.instanceId === instanceId
          ? { ...inst, styling: { ...inst.styling, ...updates } }
          : inst
      ),
    }));
  },

  toggleInstanceConfig: (instanceId: string) => {
    set((state) => ({
      instances: state.instances.map((inst) =>
        inst.instanceId === instanceId
          ? { ...inst, isConfigOpen: !inst.isConfigOpen }
          : inst
      ),
    }));
  },

  toggleInstanceCollapsed: (instanceId: string) => {
    set((state) => ({
      instances: state.instances.map((inst) =>
        inst.instanceId === instanceId
          ? { ...inst, isCollapsed: !inst.isCollapsed }
          : inst
      ),
    }));
  },

  setScaleMode: (mode: "stack" | "overwrite") =>
    set((state) => ({ scaleMode: mode, stylingVersion: state.stylingVersion + 1 })),

  setCurrentView: (view: "stack" | "detail" | "catalog") => set({ currentView: view }),

  openDetailView: (instanceId: string) => {
    const inst = get().instances.find((i) => i.instanceId === instanceId);
    set({
      activeInstanceId: instanceId,
      currentView: "detail",
      activeMetricResult: inst?.result || null,
      selectedMetricId: inst?.metricId || get().selectedMetricId,
    });
  },

  clearAllInstances: () => {
    for (const [, task] of instanceTasks) {
      task.abortController.abort();
      clearInterval(task.timerInterval);
    }
    instanceTasks.clear();
    set({
      instances: [],
      activeInstanceId: null,
      activeMetricResult: null,
    });
  },

  openDrawer: (scope?: MetricScope, metricId?: string, focusNodeId?: string) => {
    set((state) => {
      const targetScope = scope || state.selectedScope;
      const targetMetric = metricId || state.selectedMetricId;

      // If a focus node was given, update active focus node or create a node-scoped instance if none exists
      let instances = state.instances;
      if (focusNodeId && !instances.some((i) => i.focusNodeId === focusNodeId)) {
        const localMetric =
          state.descriptors.find((d) => d.scope === "single_node")?.id ||
          "gradual_strength_local";
        const newId = `metric-${Date.now()}`;
        const newInst: MetricRunInstance = {
          instanceId: newId,
          metricId: localMetric,
          focusNodeId,
          params: extractDescriptorDefaults(
            state.descriptors.find((d) => d.id === localMetric)
          ),
          nodeLabels: [],
          relationshipTypes: [],
          orientation: "natural",
          styling: { enabled: true, sizeScaling: true, colorGradient: true, sizeStrength: "normal" },
          status: "idle",
          isConfigOpen: false,
          isCollapsed: false,
        };
        instances = [newInst, ...instances];
      }

      return {
        isDrawerOpen: true,
        instances,
        selectedScope: targetScope,
        selectedMetricId: targetMetric,
        activeFocusNodeId: focusNodeId !== undefined ? focusNodeId : state.activeFocusNodeId,
      };
    });
  },

  closeDrawer: () => set({ isDrawerOpen: false }),

  runInstance: async (instanceId, options) => {
    const { instances } = get();
    const inst = instances.find((i) => i.instanceId === instanceId);
    if (!inst) return;

    // Abort prior execution for this instance
    const existingTask = instanceTasks.get(instanceId);
    if (existingTask) {
      existingTask.abortController.abort();
      clearInterval(existingTask.timerInterval);
      instanceTasks.delete(instanceId);
    }

    const abortController = new AbortController();
    const startTime = Date.now();
    const timerInterval = setInterval(() => {
      set((state) => ({
        executionElapsed: {
          ...state.executionElapsed,
          [instanceId]: (Date.now() - startTime) / 1000,
        },
      }));
    }, 150);

    instanceTasks.set(instanceId, { abortController, timerInterval });

    // Mark instance running
    set((state) => ({
      instances: state.instances.map((i) =>
        i.instanceId === instanceId
          ? {
              ...i,
              status: "running",
              elapsedSeconds: 0,
              error: null,
              executionId: null,
            }
          : i
      ),
      isCalculating: true,
    }));

    const payload: ExecuteMetricRequest = {
      metric_id: inst.metricId,
      focus_node_id: inst.focusNodeId,
      params: {
        ...inst.params,
        ...(inst.nodeLabels.length > 0 ? { node_labels: inst.nodeLabels } : {}),
        ...(inst.relationshipTypes.length > 0
          ? { relationship_types: inst.relationshipTypes }
          : {}),
        ...(inst.orientation ? { orientation: inst.orientation } : {}),
        ...(inst.relationshipWeightProperty
          ? { weight_property: inst.relationshipWeightProperty }
          : {}),
      },
      source: options?.source ?? "neo4j",
      run_id: options?.runId,
      graph_version: options?.graphVersion,
    };

    try {
      const initialResponse = await api.executeMetric(payload, abortController.signal);

      // Fast-path: 200 OK MetricResult
      if ("affected_nodes" in initialResponse) {
        const result = initialResponse as MetricResult;
        clearInterval(timerInterval);
        instanceTasks.delete(instanceId);

        set((state) => {
          const next = state.instances.map((i) =>
            i.instanceId === instanceId
              ? {
                  ...i,
                  status: "completed" as const,
                  result,
                  executionId: result.execution_id,
                  elapsedSeconds: result.duration_ms / 1000,
                }
              : i
          );
          return {
            stylingVersion: state.stylingVersion + 1,
            instances: next,
            isCalculating: next.some((i) => i.status === "running"),
            activeMetricResult:
              state.activeInstanceId === instanceId ? result : state.activeMetricResult || result,
          };
        });
        return;
      }

      // 202 Accepted: poll execution status
      const queued = initialResponse as MetricExecutionQueuedResponse;
      set((state) => ({
        instances: state.instances.map((i) =>
          i.instanceId === instanceId ? { ...i, executionId: queued.execution_id } : i
        ),
      }));

      while (true) {
        if (abortController.signal.aborted) return;
        await new Promise((resolve) => setTimeout(resolve, 350));

        const statusRes: ExecutionStatusResponse = await api.getMetricExecution(
          queued.execution_id,
          abortController.signal
        );

        if (statusRes.status === "completed" && statusRes.result) {
          clearInterval(timerInterval);
          instanceTasks.delete(instanceId);

          set((state) => {
            const next = state.instances.map((i) =>
              i.instanceId === instanceId
                ? {
                    ...i,
                    status: "completed" as const,
                    result: statusRes.result!,
                    elapsedSeconds: statusRes.result!.duration_ms / 1000,
                  }
                : i
            );
            return {
              stylingVersion: state.stylingVersion + 1,
              instances: next,
              isCalculating: next.some((i) => i.status === "running"),
              activeMetricResult:
                state.activeInstanceId === instanceId
                  ? statusRes.result!
                  : state.activeMetricResult || statusRes.result!,
            };
          });
          return;
        } else if (statusRes.status === "failed") {
          clearInterval(timerInterval);
          instanceTasks.delete(instanceId);
          set((state) => {
            const errMsg = statusRes.error?.detail || "Execution failed.";
            const next = state.instances.map((i) =>
              i.instanceId === instanceId
                ? { ...i, status: "failed" as const, error: errMsg }
                : i
            );
            return {
              instances: next,
              isCalculating: next.some((i) => i.status === "running"),
            };
          });
          return;
        } else if (statusRes.status === "cancelled") {
          clearInterval(timerInterval);
          instanceTasks.delete(instanceId);
          set((state) => {
            const next = state.instances.map((i) =>
              i.instanceId === instanceId
                ? { ...i, status: "idle" as const, error: "Execution cancelled." }
                : i
            );
            return {
              instances: next,
              isCalculating: next.some((i) => i.status === "running"),
            };
          });
          return;
        }
      }
    } catch (err: any) {
      clearInterval(timerInterval);
      instanceTasks.delete(instanceId);
      if (abortController.signal.aborted) return;

      const errMsg = err?.detail || err?.title || err?.message || "Calculation failed.";
      set((state) => {
        const next = state.instances.map((i) =>
          i.instanceId === instanceId
            ? { ...i, status: "failed" as const, error: errMsg }
            : i
        );
        return {
          instances: next,
          isCalculating: next.some((i) => i.status === "running"),
        };
      });
    }
  },

  cancelInstance: async (instanceId: string) => {
    const task = instanceTasks.get(instanceId);
    if (task) {
      task.abortController.abort();
      clearInterval(task.timerInterval);
      instanceTasks.delete(instanceId);
    }

    const { instances } = get();
    const inst = instances.find((i) => i.instanceId === instanceId);

    set((state) => {
      const next = state.instances.map((i) =>
        i.instanceId === instanceId
          ? { ...i, status: "idle" as const, error: "Calculation cancelled by user." }
          : i
      );
      return {
        instances: next,
        isCalculating: next.some((i) => i.status === "running"),
      };
    });

    if (inst?.executionId) {
      try {
        await api.cancelMetricExecution(inst.executionId);
      } catch (err) {
        console.warn("Could not cancel execution on backend:", err);
      }
    }
  },

  // Legacy single-metric runners
  runCalculation: async (options) => {
    const { instances, addInstance, runInstance } = get();
    let target = instances.find((i) => i.metricId === options.metric_id);
    if (!target) {
      const newId = addInstance(options.metric_id, options.focus_node_id || undefined);
      target = get().instances.find((i) => i.instanceId === newId);
    }
    if (target) {
      if (options.params) {
        get().updateInstance(target.instanceId, { params: options.params });
      }
      await runInstance(target.instanceId, {
        source: options.source,
        runId: options.run_id,
        graphVersion: options.graph_version,
      });
    }
  },

  cancelCalculation: async () => {
    const { instances, cancelInstance } = get();
    const running = instances.find((i) => i.status === "running");
    if (running) {
      await cancelInstance(running.instanceId);
    }
  },

  clearMetricResult: () => {
    set((state) => ({
      activeMetricResult: null,
      instances: state.instances.map((i) => ({ ...i, result: undefined, status: "idle" })),
    }));
  },

  setSelectedMetricId: (id: string) => set({ selectedMetricId: id }),
  setSelectedScope: (scope: MetricScope) => set({ selectedScope: scope }),
}));
