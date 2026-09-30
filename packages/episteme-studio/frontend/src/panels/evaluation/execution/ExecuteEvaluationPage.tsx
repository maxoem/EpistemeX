import React, { useState, useEffect } from "react";
import {
  Activity,
  AlertCircle,
  Brain,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Cpu,
  Database,
  ExternalLink,
  Layers,
  Network,
  Play,
  RefreshCw,
  RotateCcw,
  Sliders,
  Sparkles,
  Zap,
} from "lucide-react";
import { useEvaluationStore } from "../../../store/evaluationStore";
import { useRunsStore } from "../../../store/runsStore";
import { useNavigationStore } from "../../../store/navigationStore";
import { apiClient } from "../../../api/client";
import { useEvaluationJob } from "../hooks/useEvaluationJob";
import { JobProgressStepper } from "../components/JobProgressStepper";
import type { EvaluateRunRequest } from "../../../api/types";

export type EvalMode =
  | "benchmark_alignment"
  | "structuralist"
  | "competency_retrieval"
  | "stress_test";

export interface ExecuteEvaluationPageProps {
  initialRunId?: string;
  onNavigateToInspector?: (reportId: string) => void;
}

export const ExecuteEvaluationPage: React.FC<ExecuteEvaluationPageProps> = ({
  initialRunId,
  onNavigateToInspector,
}) => {
  const {
    benchmarks,
    targetRunId,
    setTargetRunId,
    setActiveReportId,
    setActiveMode,
    setActiveSubTab,
    fetchReports,
    fetchBenchmarks,
  } = useEvaluationStore();

  const { runs, fetchRuns } = useRunsStore();
  const { setActiveTab } = useNavigationStore();

  // Mode and Targets
  const [mode, setMode] = useState<EvalMode>("benchmark_alignment");
  const [runId, setRunId] = useState<string>(
    initialRunId || targetRunId || (runs.length > 0 ? runs[0].run_id : "")
  );
  const [benchmarkId, setBenchmarkId] = useState<string>(
    benchmarks[0]?.id || "stnb_cpm_pilot"
  );

  // Evaluator Inference Stack Models
  const [modelSource, setModelSource] = useState<"inherit" | "custom">("inherit");
  const [evalLlmModel, setEvalLlmModel] = useState("openai/gpt-4o-mini");
  const [evalEmbeddingModel, setEvalEmbeddingModel] = useState(
    "sentence-transformers/all-MiniLM-L6-v2"
  );

  const selectedRun = runs.find((r) => r.run_id === runId);

  // Sync default models when selectedRun changes
  useEffect(() => {
    if (selectedRun?.models?.llm_model) {
      setEvalLlmModel(selectedRun.models.llm_model);
    }
    if (selectedRun?.models?.embedding_model) {
      setEvalEmbeddingModel(selectedRun.models.embedding_model);
    }
  }, [selectedRun]);

  // Hyperparameters
  const [strategy, setStrategy] = useState("structuralist");
  const [simThreshold, setSimThreshold] = useState(0.85);
  const [deltaStar, setDeltaStar] = useState(0.1);
  const [minMcc, setMinMcc] = useState(1.0);
  const [minPfs, setMinPfs] = useState(0.8);
  const [evaluateRetrieval, setEvaluateRetrieval] = useState(false);

  // Advanced Drawer & Overrides
  const [isAdvancedDrawerOpen, setIsAdvancedDrawerOpen] = useState(false);
  const [customGoldPath, setCustomGoldPath] = useState("");
  const [customQueriesPath, setCustomQueriesPath] = useState("");
  const [baselineRunId, setBaselineRunId] = useState("");
  const [persistReport, setPersistReport] = useState(true);

  // Active Job State
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Sync initialRunId / targetRunId when available
  useEffect(() => {
    if (initialRunId) {
      setRunId(initialRunId);
    } else if (targetRunId) {
      setRunId(targetRunId);
    } else if (!runId && runs.length > 0) {
      setRunId(runs[0].run_id);
    }
  }, [initialRunId, targetRunId, runs]);

  // Sync benchmarks default
  useEffect(() => {
    if (benchmarks.length > 0 && !benchmarks.some((b) => b.id === benchmarkId)) {
      setBenchmarkId(benchmarks[0].id);
    }
  }, [benchmarks, benchmarkId]);

  // Refresh benchmarks and runs on mount
  useEffect(() => {
    fetchBenchmarks();
    if (runs.length === 0) {
      fetchRuns();
    }
  }, [fetchBenchmarks, fetchRuns, runs.length]);

  const jobHook = useEvaluationJob({
    jobId: activeJobId,
    onCompleted: (_reportId) => {
      fetchReports();
    },
  });

  const handleExecute = async () => {
    if (!runId.trim()) {
      setSubmitError("Please enter or select a valid target Pipeline Run ID.");
      return;
    }

    setSubmitError(null);
    setIsSubmitting(true);

    try {
      const payload: EvaluateRunRequest = {
        run_id: runId.trim(),
        benchmark_id: mode === "benchmark_alignment" ? benchmarkId : undefined,
        gold_standard_path: customGoldPath.trim() ? customGoldPath.trim() : undefined,
        queries_path: customQueriesPath.trim() ? customQueriesPath.trim() : undefined,
        strategy: strategy.trim() || "structuralist",
        baseline: baselineRunId.trim() ? baselineRunId.trim() : undefined,
        sim_threshold: simThreshold,
        delta_star: deltaStar,
        min_mcc: minMcc,
        min_pfs: minPfs,
        mode: mode,
        evaluate_retrieval: evaluateRetrieval,
        persist: persistReport,
        llm_model:
          modelSource === "custom"
            ? evalLlmModel.trim() || undefined
            : selectedRun?.models?.llm_model || undefined,
        embedding_model:
          modelSource === "custom"
            ? evalEmbeddingModel.trim() || undefined
            : selectedRun?.models?.embedding_model || undefined,
      };

      const descriptor = await apiClient.startRunEvaluationJob(payload);
      setActiveJobId(descriptor.job_id);
    } catch (e: any) {
      setSubmitError(e.message || "Failed to dispatch evaluation job.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetToDefaults = () => {
    setMode("benchmark_alignment");
    setStrategy("structuralist");
    setModelSource("inherit");
    setEvalLlmModel(selectedRun?.models?.llm_model || "openai/gpt-4o-mini");
    setEvalEmbeddingModel(
      selectedRun?.models?.embedding_model || "sentence-transformers/all-MiniLM-L6-v2"
    );
    setSimThreshold(0.85);
    setDeltaStar(0.1);
    setMinMcc(1.0);
    setMinPfs(0.8);
    setEvaluateRetrieval(false);
    setCustomGoldPath("");
    setCustomQueriesPath("");
    setBaselineRunId("");
    setPersistReport(true);
    setSubmitError(null);
  };

  const handleResetToNewJob = () => {
    setActiveJobId(null);
    setSubmitError(null);
  };

  const handleOpenReport = (reportId: string) => {
    setActiveReportId(reportId);
    setActiveMode("inspector");
    if (onNavigateToInspector) {
      onNavigateToInspector(reportId);
    }
  };

  const handleOpenCanvas = (reportId: string) => {
    setActiveReportId(reportId);
    setActiveMode("inspector");
    setActiveSubTab("canvas");
    if (onNavigateToInspector) {
      onNavigateToInspector(reportId);
    }
  };

  const handleOpenAdjudication = (reportId: string) => {
    setActiveReportId(reportId);
    setActiveMode("inspector");
    setActiveSubTab("adjudication");
    if (onNavigateToInspector) {
      onNavigateToInspector(reportId);
    }
  };

  const completedRuns = runs.filter((r) => r.status === "completed");

  return (
    <div className="flex-1 overflow-y-auto select-text bg-app-bg text-app-text">
      <div className="divide-y divide-app-border">
        {/* Title & Description Strip */}
        <div className="px-6 sm:px-8 py-5 bg-app-surface border-b border-app-border/60">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h3 className="type-h1 text-app-heading">
                Execute Evaluation
              </h3>
              <span className="type-caption text-app-muted block mt-0.5">
                On-demand benchmark alignment, intrinsic tenability, and competency suites
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleResetToDefaults}
                disabled={Boolean(activeJobId)}
                className="px-2.5 py-1 rounded text-xs text-app-muted hover:text-app-text hover:bg-app-subtle border border-transparent hover:border-app-border transition-colors inline-flex items-center gap-1.5 cursor-pointer disabled:opacity-40"
                title="Reset hyperparameters to defaults"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset Defaults</span>
              </button>
            </div>
          </div>
          <p className="type-body text-app-muted mt-2 max-w-2xl leading-relaxed">
            Dispatch Hungarian bipartite graph matching against gold-standard benchmarks (GM-GBS),
            evaluate Bourbaki quintuple decomposition completeness, or execute adversarial stress suites across
            pipeline runs.
          </p>
        </div>

        {/* Active Job Progress View */}
        {activeJobId ? (
          <div className="px-6 sm:px-8 py-6 space-y-5 animate-in fade-in duration-200">
            <div className="p-4 rounded-lg bg-blue-500/5 border border-blue-500/20">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-blue-500 animate-pulse" />
                  <span className="text-xs font-semibold text-app-heading">
                    Active Evaluation Execution
                  </span>
                </div>
                <span className="font-mono text-[11px] text-app-muted">
                  Target Run: <span className="text-app-heading font-medium">{runId}</span>
                </span>
              </div>
              <p className="text-[11px] text-app-muted">
                Running real-time evaluation pipeline with Sneedian tenability blur \(\delta^* = {deltaStar.toFixed(2)}\) and soft matching threshold \(\tau = {simThreshold.toFixed(2)}\).
              </p>
            </div>

            <div>
              <JobProgressStepper
                jobId={activeJobId}
                status={jobHook.status}
                progress={jobHook.progress}
                currentStage={jobHook.currentStage}
                events={jobHook.events}
                error={jobHook.error}
                reportId={jobHook.reportId}
                isCancelling={jobHook.isCancelling}
                onCancel={jobHook.cancelJob}
                onOpenReport={handleOpenReport}
                onOpenCanvas={handleOpenCanvas}
                onOpenAdjudication={handleOpenAdjudication}
                onClose={handleResetToNewJob}
              />
            </div>

            {(jobHook.status === "failed" ||
              jobHook.status === "aborted" ||
              jobHook.status === "completed") && (
              <div className="pt-2 flex items-center justify-between">
                <button
                  type="button"
                  onClick={handleResetToNewJob}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-blue-500 hover:text-blue-600 hover:bg-blue-500/10 border border-blue-500/30 transition-colors cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Configure & Start Another Evaluation</span>
                </button>

                {jobHook.reportId && (
                  <button
                    type="button"
                    onClick={() => handleOpenReport(jobHook.reportId!)}
                    className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors cursor-pointer"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Navigate to Report Inspector</span>
                  </button>
                )}
              </div>
            )}
          </div>
        ) : (
          /* Configuration Wizard Form */
          <div className="px-6 sm:px-8 py-6 space-y-6">
            {submitError && (
              <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-500 text-xs flex items-center gap-2.5">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span className="font-medium">{submitError}</span>
              </div>
            )}

            {/* 1. Evaluation Archetype & Mode */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="type-h2 text-app-heading">
                  1. Evaluation Archetype & Strategy
                </h4>
                <span className="font-mono text-[10px] text-app-muted/80">evaluation.mode</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Benchmark Alignment */}
                <button
                  type="button"
                  onClick={() => setMode("benchmark_alignment")}
                  className={`p-3.5 rounded-lg border text-left transition-all cursor-pointer ${
                    mode === "benchmark_alignment"
                      ? "bg-blue-500/10 border-blue-500/70 ring-1 ring-blue-500/20"
                      : "bg-app-subtle/50 hover:bg-app-subtle border-app-border"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 font-medium text-xs text-app-heading">
                      <Network className="w-4 h-4 text-blue-500" />
                      <span>Benchmark Alignment</span>
                    </div>
                    {mode === "benchmark_alignment" && (
                      <Check className="w-3.5 h-3.5 text-blue-500" />
                    )}
                  </div>
                  <p className="text-[11px] text-app-muted mt-1.5 leading-relaxed">
                    Compare reconstructed TheoryNet against curated gold-standard axioms using Hungarian bipartite GM-GBS matching.
                  </p>
                </button>

                {/* Intrinsic Structuralist */}
                <button
                  type="button"
                  onClick={() => setMode("structuralist")}
                  className={`p-3.5 rounded-lg border text-left transition-all cursor-pointer ${
                    mode === "structuralist"
                      ? "bg-emerald-500/10 border-emerald-500/70 ring-1 ring-emerald-500/20"
                      : "bg-app-subtle/50 hover:bg-app-subtle border-app-border"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 font-medium text-xs text-app-heading">
                      <Layers className="w-4 h-4 text-emerald-500" />
                      <span>Intrinsic Structuralist</span>
                    </div>
                    {mode === "structuralist" && (
                      <Check className="w-3.5 h-3.5 text-emerald-500" />
                    )}
                  </div>
                  <p className="text-[11px] text-app-muted mt-1.5 leading-relaxed">
                    Verify Bourbaki quintuple decomposition, core empirical claims, and Sneedian tenability blur \(\delta^*\).
                  </p>
                </button>

                {/* Competency Retrieval */}
                <button
                  type="button"
                  onClick={() => setMode("competency_retrieval")}
                  className={`p-3.5 rounded-lg border text-left transition-all cursor-pointer ${
                    mode === "competency_retrieval"
                      ? "bg-purple-500/10 border-purple-500/70 ring-1 ring-purple-500/20"
                      : "bg-app-subtle/50 hover:bg-app-subtle border-app-border"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 font-medium text-xs text-app-heading">
                      <Activity className="w-4 h-4 text-purple-500" />
                      <span>Competency Retrieval</span>
                    </div>
                    {mode === "competency_retrieval" && (
                      <Check className="w-3.5 h-3.5 text-purple-500" />
                    )}
                  </div>
                  <p className="text-[11px] text-app-muted mt-1.5 leading-relaxed">
                    Execute philosophical competency queries to quantify Mean Reciprocal Rank (MRR), Hits@k, and nDCG.
                  </p>
                </button>

                {/* Adversarial Stress Test */}
                <button
                  type="button"
                  onClick={() => setMode("stress_test")}
                  className={`p-3.5 rounded-lg border text-left transition-all cursor-pointer ${
                    mode === "stress_test"
                      ? "bg-amber-500/10 border-amber-500/70 ring-1 ring-amber-500/20"
                      : "bg-app-subtle/50 hover:bg-app-subtle border-app-border"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 font-medium text-xs text-app-heading">
                      <Zap className="w-4 h-4 text-amber-500" />
                      <span>Adversarial Stress Test</span>
                    </div>
                    {mode === "stress_test" && (
                      <Check className="w-3.5 h-3.5 text-amber-500" />
                    )}
                  </div>
                  <p className="text-[11px] text-app-muted mt-1.5 leading-relaxed">
                    Simulate OCR typos, sentence permutations, and measure semantic drift and degradation factor.
                  </p>
                </button>
              </div>
            </div>

            {/* 2. Target Pipeline Run & Benchmark Association */}
            <div className="space-y-4 pt-4 border-t border-app-border/80">
              <h4 className="type-h2 text-app-heading">
                2. Target Pipeline Run & Benchmark Binding
              </h4>

              {/* Target Pipeline Run */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-app-heading">
                    Target Pipeline Run
                  </label>
                  <span className="font-mono text-[10px] text-app-muted/80">request.run_id</span>
                </div>

                <div className="flex flex-col sm:flex-row gap-2">
                  <input
                    type="text"
                    value={runId}
                    onChange={(e) => {
                      setRunId(e.target.value);
                      setTargetRunId(e.target.value);
                    }}
                    placeholder="e.g. run-kant-cpr-v1 or uuid..."
                    className="flex-1 h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80"
                  />

                  {completedRuns.length > 0 && (
                    <select
                      value={completedRuns.some((r) => r.run_id === runId) ? runId : ""}
                      onChange={(e) => {
                        if (e.target.value) {
                          setRunId(e.target.value);
                          setTargetRunId(e.target.value);
                        }
                      }}
                      className="h-8 px-2.5 rounded-md bg-app-subtle border border-app-border text-xs text-app-text font-mono focus:outline-none focus:border-blue-500/80 sm:w-64 shrink-0"
                    >
                      <option value="">Select from recent runs...</option>
                      {completedRuns.map((r) => (
                        <option key={r.run_id} value={r.run_id}>
                          {r.run_id} ({r.models?.llm_model || r.primary_input || "run"})
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <span className="text-[11px] text-app-muted block">
                  Completed pipeline run whose materialization artifacts and TheoryNet graph will be evaluated.
                </span>
              </div>

              {/* Gold Standard Benchmark Selection (when benchmark_alignment) */}
              {mode === "benchmark_alignment" && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-app-heading">
                      Gold Standard Benchmark
                    </label>
                    <span className="font-mono text-[10px] text-app-muted/80">
                      request.benchmark_id
                    </span>
                  </div>

                  <select
                    value={benchmarkId}
                    onChange={(e) => setBenchmarkId(e.target.value)}
                    className="w-full h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs transition-all focus:outline-none focus:border-blue-500/80"
                  >
                    {benchmarks.length === 0 ? (
                      <option value="stnb_cpm_pilot">
                        STNB CPM Pilot Benchmark (stnb_cpm_pilot.jsonld)
                      </option>
                    ) : (
                      benchmarks.map((bm) => (
                        <option key={bm.id} value={bm.id}>
                          {bm.name} ({bm.id}) — {bm.task_type}
                        </option>
                      ))
                    )}
                  </select>
                  <span className="text-[11px] text-app-muted block">
                    Curated epistemological reference graph registered in Benchmark Catalog.
                  </span>
                </div>
              )}
            </div>

            {/* 3. Evaluator Inference Stack */}
            <div className="space-y-4 pt-4 border-t border-app-border/80">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="type-h2 text-app-heading">
                    3. Evaluator Inference Stack
                  </h4>
                  <p className="type-caption text-app-muted mt-0.5">
                    Foundational vector embeddings and LLM judge models for alignment scoring, drift estimation, and baselines
                  </p>
                </div>

                <div className="p-0.5 inline-flex items-center bg-app-subtle rounded-md border border-app-border/60 gap-0.5 text-xs font-medium">
                  <button
                    type="button"
                    onClick={() => setModelSource("inherit")}
                    className={`h-6 px-3 rounded text-[11px] transition-all cursor-pointer ${
                      modelSource === "inherit"
                        ? "bg-app-surface font-semibold text-app-heading border border-app-border/80"
                        : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
                    }`}
                  >
                    Inherit from Run
                  </button>
                  <button
                    type="button"
                    onClick={() => setModelSource("custom")}
                    className={`h-6 px-3 rounded text-[11px] transition-all cursor-pointer ${
                      modelSource === "custom"
                        ? "bg-app-surface font-semibold text-app-heading border border-app-border/80"
                        : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
                    }`}
                  >
                    Custom Evaluator Stack
                  </button>
                </div>
              </div>

              {modelSource === "inherit" ? (
                <div className="p-3.5 rounded bg-app-subtle/30 border-l-2 border-blue-500 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <Brain className="w-4 h-4 text-blue-500 shrink-0" />
                    <div>
                      <h5 className="font-semibold text-xs text-app-heading font-sans">
                        Inherited from Target Run {selectedRun ? `(${selectedRun.run_id})` : ""}
                      </h5>
                      <div className="flex items-center gap-3 mt-1 text-[11px] font-mono text-app-muted flex-wrap">
                        <span>
                          Embedding:{" "}
                          <span className="text-app-heading font-medium">
                            {selectedRun?.models?.embedding_model || "sentence-transformers/all-MiniLM-L6-v2"}
                          </span>
                        </span>
                        <span>•</span>
                        <span>
                          LLM / Judge:{" "}
                          <span className="text-app-heading font-medium">
                            {selectedRun?.models?.llm_model || "openai/gpt-4o-mini"}
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-blue-500/10 text-blue-500 border border-blue-500/20 shrink-0">
                    Auto-Configured
                  </span>
                </div>
              ) : (
                <div className="space-y-4 animate-in fade-in duration-150">
                  {/* Dense Embedding Model */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-app-heading">
                        Evaluator Dense Embedding Model
                      </label>
                      <span className="font-mono text-[10px] text-app-muted/80">models.embedding_model</span>
                    </div>
                    <input
                      type="text"
                      value={evalEmbeddingModel}
                      onChange={(e) => setEvalEmbeddingModel(e.target.value)}
                      placeholder="e.g. sentence-transformers/all-MiniLM-L6-v2"
                      className="w-full h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80"
                    />
                    <span className="text-[11px] text-app-muted block">
                      Uniform vector latent space used for Hungarian GM-GBS alignment (soft similarity cutoff \(\tau\)), adversarial semantic drift, and competency retrieval.
                    </span>
                  </div>

                  {/* Evaluator Generative Model (LLM) */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-app-heading">
                        Evaluator & Baseline Generative Model (LLM)
                      </label>
                      <span className="font-mono text-[10px] text-app-muted/80">models.llm_model</span>
                    </div>
                    <input
                      type="text"
                      value={evalLlmModel}
                      onChange={(e) => setEvalLlmModel(e.target.value)}
                      placeholder="e.g. openai/gpt-4o-mini"
                      className="w-full h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80"
                    />
                    <span className="text-[11px] text-app-muted block">
                      Employed for comparative single-pass baselines (zero-shot, text-RAG, naive-KG) and LLM-as-a-judge rubric verification.
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* 4. Evaluation Hyperparameters & Numerical Precision */}
            <div className="space-y-4 pt-4 border-t border-app-border/80">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="type-h2 text-app-heading">
                    4. Evaluation Hyperparameters & Thresholds
                  </h4>
                  <p className="type-caption text-app-muted mt-0.5">
                    Structuralist relaxation boundaries and Hungarian assignment matching cutoffs
                  </p>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-app-muted">
                  <Sliders className="w-3.5 h-3.5 text-blue-500" />
                  <span className="font-mono text-[11px]">Precision: 0.01</span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                {/* Alignment Threshold tau */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-app-heading">
                      Alignment Threshold \(\tau\)
                    </label>
                    <span className="font-mono text-[10px] text-app-muted/80">sim_threshold</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min="0.5"
                      max="1.0"
                      step="0.01"
                      value={simThreshold}
                      onChange={(e) => setSimThreshold(parseFloat(e.target.value))}
                      className="flex-1 precision-slider accent-blue-600 cursor-pointer"
                    />
                    <input
                      type="number"
                      min="0.5"
                      max="1.0"
                      step="0.01"
                      value={simThreshold.toFixed(2)}
                      onChange={(e) =>
                        setSimThreshold(
                          Math.max(0.5, Math.min(1.0, parseFloat(e.target.value) || 0.5))
                        )
                      }
                      className="w-16 h-7 px-2 text-right font-mono text-xs rounded-md bg-app-subtle/50 text-app-heading border border-app-border focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <span className="text-[11px] text-app-muted block">
                    Soft similarity cutoff threshold for Hungarian bipartite assignment (GM-GBS).
                  </span>
                </div>

                {/* Tenability Blur delta* */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-app-heading">
                      Tenability Blur \(\delta^*\)
                    </label>
                    <span className="font-mono text-[10px] text-app-muted/80">delta_star</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min="0.0"
                      max="0.5"
                      step="0.01"
                      value={deltaStar}
                      onChange={(e) => setDeltaStar(parseFloat(e.target.value))}
                      className="flex-1 precision-slider accent-emerald-600 cursor-pointer"
                    />
                    <input
                      type="number"
                      min="0.0"
                      max="0.5"
                      step="0.01"
                      value={deltaStar.toFixed(2)}
                      onChange={(e) =>
                        setDeltaStar(
                          Math.max(0.0, Math.min(0.5, parseFloat(e.target.value) || 0.0))
                        )
                      }
                      className="w-16 h-7 px-2 text-right font-mono text-xs rounded-md bg-app-subtle/50 text-app-heading border border-app-border focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <span className="text-[11px] text-app-muted block">
                    Maximum structuralist semantic drift permissible for core theoretical posits.
                  </span>
                </div>

                {/* Min Model Component Completeness (MCC) */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-app-heading">
                      Min Completeness (MCC)
                    </label>
                    <span className="font-mono text-[10px] text-app-muted/80">min_mcc</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min="0.5"
                      max="1.0"
                      step="0.01"
                      value={minMcc}
                      onChange={(e) => setMinMcc(parseFloat(e.target.value))}
                      className="flex-1 precision-slider accent-purple-600 cursor-pointer"
                    />
                    <input
                      type="number"
                      min="0.5"
                      max="1.0"
                      step="0.01"
                      value={minMcc.toFixed(2)}
                      onChange={(e) =>
                        setMinMcc(
                          Math.max(0.5, Math.min(1.0, parseFloat(e.target.value) || 0.5))
                        )
                      }
                      className="w-16 h-7 px-2 text-right font-mono text-xs rounded-md bg-app-subtle/50 text-app-heading border border-app-border focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <span className="text-[11px] text-app-muted block">
                    Bourbaki quintuple completeness constraint for reconstructed theoretical components.
                  </span>
                </div>

                {/* Property Fidelity Score (PFS) */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-app-heading">
                      Min Property Fidelity (PFS)
                    </label>
                    <span className="font-mono text-[10px] text-app-muted/80">min_pfs</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min="0.5"
                      max="1.0"
                      step="0.01"
                      value={minPfs}
                      onChange={(e) => setMinPfs(parseFloat(e.target.value))}
                      className="flex-1 precision-slider accent-amber-600 cursor-pointer"
                    />
                    <input
                      type="number"
                      min="0.5"
                      max="1.0"
                      step="0.01"
                      value={minPfs.toFixed(2)}
                      onChange={(e) =>
                        setMinPfs(
                          Math.max(0.5, Math.min(1.0, parseFloat(e.target.value) || 0.5))
                        )
                      }
                      className="w-16 h-7 px-2 text-right font-mono text-xs rounded-md bg-app-subtle/50 text-app-heading border border-app-border focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <span className="text-[11px] text-app-muted block">
                    Fidelity bound for reconstructed axiomatic property assertions and polarity coherence.
                  </span>
                </div>
              </div>
            </div>

            {/* 5. Downstream Competency Retrieval Notice Card */}
            <div className="p-3.5 rounded bg-app-subtle/30 border-l-2 border-blue-500 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Activity className="w-4 h-4 text-blue-500 shrink-0" />
                <div>
                  <h5 className="font-semibold text-xs text-app-heading font-sans">
                    Downstream Competency Query Retrieval Scoring
                  </h5>
                  <p className="text-[11px] text-app-muted mt-0.5">
                    Execute downstream question answering, MRR, Hits@k, and nDCG ranking benchmarks against the target TheoryNet.
                  </p>
                </div>
              </div>

              <label className="flex items-center gap-2 cursor-pointer select-none shrink-0">
                <input
                  type="checkbox"
                  checked={evaluateRetrieval}
                  onChange={(e) => setEvaluateRetrieval(e.target.checked)}
                  className="w-4 h-4 rounded border-app-border accent-blue-600 cursor-pointer"
                />
                <span className="text-xs font-medium text-app-heading font-sans">Enable</span>
              </label>
            </div>

            {/* 6. Collapsible Advanced Directives Drawer */}
            <div className="pt-2 border-t border-app-border">
              <button
                type="button"
                onClick={() => setIsAdvancedDrawerOpen(!isAdvancedDrawerOpen)}
                className="flex items-center justify-between w-full py-2 text-xs font-semibold text-app-heading hover:text-blue-500 transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  {isAdvancedDrawerOpen ? (
                    <ChevronDown className="w-4 h-4 text-app-muted" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-app-muted" />
                  )}
                  <span>Advanced Execution & Persistence Directives</span>
                </div>
                <span className="text-[10px] font-mono text-app-muted uppercase">
                  {isAdvancedDrawerOpen ? "Hide" : "Show"}
                </span>
              </button>

              {isAdvancedDrawerOpen && (
                <div className="pt-3 space-y-4 animate-in fade-in duration-150">
                  {/* Strategy Override */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-app-heading">
                        Evaluation Strategy Engine
                      </label>
                      <span className="font-mono text-[10px] text-app-muted/80">
                        request.strategy
                      </span>
                    </div>
                    <div className="p-0.5 inline-flex items-center bg-app-subtle rounded-md border border-app-border/60 gap-0.5 text-xs font-medium">
                      {["structuralist", "bourbaki_strict", "lax_semantic"].map((strat) => (
                        <button
                          key={strat}
                          type="button"
                          onClick={() => setStrategy(strat)}
                          className={`h-6 px-3 rounded text-[11px] transition-all cursor-pointer ${
                            strategy === strat
                              ? "bg-app-surface font-semibold text-app-heading border border-app-border/80"
                              : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
                          }`}
                        >
                          {strat}
                        </button>
                      ))}
                    </div>
                    <span className="text-[11px] text-app-muted block">
                      Determines formal graph matching algorithm and Bourbaki poset constraints.
                    </span>
                  </div>

                  {/* Baseline Run ID for Comparative Deltas */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-app-heading">
                        Comparative Baseline Run ID (Optional)
                      </label>
                      <span className="font-mono text-[10px] text-app-muted/80">
                        request.baseline
                      </span>
                    </div>
                    <input
                      type="text"
                      value={baselineRunId}
                      onChange={(e) => setBaselineRunId(e.target.value)}
                      placeholder="e.g. run-baseline-v0 or prior run id..."
                      className="w-full h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80"
                    />
                    <span className="text-[11px] text-app-muted block">
                      When provided, generates comparative delta vectors (\(\Delta F_1\), \(\Delta\delta^*\)) against this baseline.
                    </span>
                  </div>

                  {/* Custom Gold Standard JSON-LD Path */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-app-heading">
                        Custom Gold Standard Graph Path (Optional)
                      </label>
                      <span className="font-mono text-[10px] text-app-muted/80">
                        request.gold_standard_path
                      </span>
                    </div>
                    <input
                      type="text"
                      value={customGoldPath}
                      onChange={(e) => setCustomGoldPath(e.target.value)}
                      placeholder="e.g. /path/to/custom_gold_standard.jsonld"
                      className="w-full h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80"
                    />
                  </div>

                  {/* Custom Queries JSON Path */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-app-heading">
                        Custom Competency Queries Path (Optional)
                      </label>
                      <span className="font-mono text-[10px] text-app-muted/80">
                        request.queries_path
                      </span>
                    </div>
                    <input
                      type="text"
                      value={customQueriesPath}
                      onChange={(e) => setCustomQueriesPath(e.target.value)}
                      placeholder="e.g. /path/to/competency_queries.json"
                      className="w-full h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80"
                    />
                  </div>

                  {/* Materialization & Persistence Checkbox */}
                  <div className="pt-2 border-t border-app-border/60">
                    <label className="flex items-center gap-2 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={persistReport}
                        onChange={(e) => setPersistReport(e.target.checked)}
                        className="rounded border-app-border accent-blue-600"
                      />
                      <span className="text-xs font-medium text-app-heading">
                        Persist evaluation report and materialized JSON-LD artifact to disk
                      </span>
                    </label>
                  </div>
                </div>
              )}
            </div>

            {/* 7. Execution Dispatch Action Bar */}
            <div className="pt-4 border-t border-app-border/80 flex items-center justify-between gap-4">
              <div className="flex items-center gap-2 text-xs text-app-muted">
                <Clock className="w-3.5 h-3.5" />
                <span>Synchronous background job with SSE progress streaming</span>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleExecute}
                  disabled={isSubmitting || !runId.trim()}
                  className="flex items-center gap-2 px-5 py-2 rounded-md text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4 fill-current" />
                  )}
                  <span>{isSubmitting ? "Dispatching Job..." : "Execute Evaluation"}</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
