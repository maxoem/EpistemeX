import React, { useState } from "react";
import { Award, CheckCircle2, FileText, Layers, ShieldCheck, X } from "lucide-react";
import { api } from "../../../api/client";
import { useEvaluationStore } from "../../../store/evaluationStore";
import { useRunsStore } from "../../../store/runsStore";
import type { RegisterBenchmarkRequest } from "../../../api/types";

interface PromoteToGoldModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultRunId?: string;
  onSuccess?: (benchmarkId: string) => void;
}

export const PromoteToGoldModal: React.FC<PromoteToGoldModalProps> = ({
  isOpen,
  onClose,
  defaultRunId,
  onSuccess,
}) => {
  const { reports, fetchBenchmarks, setSelectedBenchmarkId } = useEvaluationStore();
  const { runs } = useRunsStore();

  const [selectedRunId, setSelectedRunId] = useState<string>(
    defaultRunId || reports[0]?.evaluation_id || runs[0]?.run_id || ""
  );
  const [benchmarkId, setBenchmarkId] = useState<string>("");
  const [benchmarkName, setBenchmarkName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [versionTag, setVersionTag] = useState<string>("v1.0-gold");
  const [taskType, setTaskType] = useState<string>("structuralist");
  const [primarySourceAnchor, setPrimarySourceAnchor] = useState<string>("");

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Auto-populate slug and name when run is picked
  const handleRunChange = (runId: string) => {
    setSelectedRunId(runId);
    if (!benchmarkId) {
      const slug = `gold-${runId.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
      setBenchmarkId(slug);
      setBenchmarkName(`Gold Benchmark (${runId})`);
    }
  };

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!benchmarkId.trim() || !benchmarkName.trim() || !selectedRunId) {
      setError("Please fill in all mandatory fields.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      // Find matching report or synthesize JSON-LD from run
      const matchedReport = reports.find((r) => r.evaluation_id === selectedRunId);

      // Synthesize gold standard JSON-LD bundle
      const goldStandardPayload = {
        "@context": {
          "episteme": "https://episteme.org/ontology#",
          "tn": "https://episteme.org/theorynet#",
          "id": "@id",
          "type": "@type",
        },
        "@id": `benchmark:${benchmarkId}`,
        "version": versionTag,
        "promoted_from_run": selectedRunId,
        "task_type": taskType,
        "created_at": new Date().toISOString(),
        "primary_source_anchor": primarySourceAnchor || undefined,
        "metrics_baseline": matchedReport?.key_metrics || {},
        "@graph": [
          {
            "id": `tn:${benchmarkId}_root_t0`,
            "type": "episteme:TheoryAtom",
            "class_name": "Mp",
            "label": `${benchmarkName} Fundamental Core Axiom (T₀)`,
            "is_immutable_gold": true,
            "provenance": {
              "source_run": selectedRunId,
              "source_doc": primarySourceAnchor || "unspecified.pdf",
            },
          },
        ],
      };

      const payload: RegisterBenchmarkRequest = {
        id: benchmarkId.trim(),
        name: benchmarkName.trim(),
        description: description.trim() || `Promoted from verified pipeline run ${selectedRunId} (${versionTag})`,
        task_type: taskType,
        gold_standard_jsonld: JSON.stringify(goldStandardPayload, null, 2),
      };

      const registered = await api.registerBenchmark(payload);

      await fetchBenchmarks();
      setSelectedBenchmarkId(registered.id);
      onSuccess?.(registered.id);
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to promote run to gold benchmark");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs select-none p-4">
      <div className="w-full max-w-lg bg-app-surface border border-app-border rounded-lg flex flex-col overflow-hidden text-app-text animate-in zoom-in-95 duration-150 font-sans">
        {/* Header */}
        <div className="h-12 px-4 border-b border-app-border flex items-center justify-between shrink-0 bg-app-bg/50">
          <div className="flex items-center gap-2">
            <div className="p-1 rounded bg-amber-500/10 text-amber-500 border border-amber-500/30">
              <Award className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-xs font-semibold text-app-heading">
                Promote Run to Gold Standard
              </h2>
              <p className="text-[10px] text-app-muted">
                The Golden Pathway: Freeze verified pipeline outputs as immutable benchmark
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-4 space-y-3 text-xs overflow-y-auto max-h-[75vh]">
          {error && (
            <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs">
              {error}
            </div>
          )}

          {/* Select Source Run */}
          <div>
            <label className="block text-[11px] font-medium text-app-muted mb-1">
              Source Pipeline Run / Evaluation Report *
            </label>
            <select
              value={selectedRunId}
              onChange={(e) => handleRunChange(e.target.value)}
              className="w-full bg-app-bg text-app-text px-2.5 py-1.5 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden font-mono"
            >
              <option value="" disabled>
                Select executed run...
              </option>
              {reports.map((r) => (
                <option key={r.evaluation_id} value={r.evaluation_id}>
                  {r.evaluation_id} — {r.outcome.toUpperCase()} (F₁:{" "}
                  {(r.key_metrics?.f1 ?? 0).toFixed(3)})
                </option>
              ))}
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({Object.values(r.models || {})[0] || "Custom"})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            {/* Benchmark ID */}
            <div>
              <label className="block text-[11px] font-medium text-app-muted mb-1">
                Benchmark ID (slug) *
              </label>
              <input
                type="text"
                value={benchmarkId}
                onChange={(e) => setBenchmarkId(e.target.value)}
                placeholder="e.g. carnap-1928-aufbau"
                className="w-full bg-app-bg text-app-text px-2.5 py-1.5 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden font-mono"
                required
              />
            </div>

            {/* Version Tag */}
            <div>
              <label className="block text-[11px] font-medium text-app-muted mb-1">
                Version Tag
              </label>
              <input
                type="text"
                value={versionTag}
                onChange={(e) => setVersionTag(e.target.value)}
                placeholder="v1.0-gold"
                className="w-full bg-app-bg text-app-text px-2.5 py-1.5 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden font-mono"
              />
            </div>
          </div>

          {/* Benchmark Title */}
          <div>
            <label className="block text-[11px] font-medium text-app-muted mb-1">
              Benchmark Title *
            </label>
            <input
              type="text"
              value={benchmarkName}
              onChange={(e) => setBenchmarkName(e.target.value)}
              placeholder="e.g. Carnap 1928 Aufbau Core Hierarchy"
              className="w-full bg-app-bg text-app-text px-2.5 py-1.5 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            {/* Task Type */}
            <div>
              <label className="block text-[11px] font-medium text-app-muted mb-1">
                Task Paradigm
              </label>
              <select
                value={taskType}
                onChange={(e) => setTaskType(e.target.value)}
                className="w-full bg-app-bg text-app-text px-2.5 py-1.5 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden"
              >
                <option value="structuralist">Bourbaki Structuralist (TheoryNet)</option>
                <option value="extraction">Entity & Relation Extraction</option>
                <option value="argumentation">Dialectical Argument Mining</option>
                <option value="retrieval">Multi-Hop Competency Retrieval</option>
              </select>
            </div>

            {/* Source Anchor Document */}
            <div>
              <label className="block text-[11px] font-medium text-app-muted mb-1">
                Primary Source Anchor
              </label>
              <input
                type="text"
                value={primarySourceAnchor}
                onChange={(e) => setPrimarySourceAnchor(e.target.value)}
                placeholder="doc_carnap_aufbau_1928.pdf"
                className="w-full bg-app-bg text-app-text px-2.5 py-1.5 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden font-mono"
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-[11px] font-medium text-app-muted mb-1">
              Methodological Description
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Detail epistemic scope, verified Bourbaki classes (Mp, M, Mpp, C, I), and source text grounding..."
              className="w-full bg-app-bg text-app-text p-2 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden resize-none"
            />
          </div>

          {/* Golden Pathway Notice */}
          <div className="p-2.5 rounded bg-blue-500/10 border border-blue-500/30 flex items-start gap-2 text-blue-600 dark:text-blue-400 text-[11px]">
            <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5" />
            <p className="leading-tight">
              Promoting creates an immutable gold standard snapshot. Subsequent pipeline runs can be evaluated against this reference dataset on the Leaderboard.
            </p>
          </div>

          {/* Footer Actions */}
          <div className="pt-2 border-t border-app-border flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded text-xs font-medium text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !benchmarkId || !benchmarkName}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-amber-600 hover:bg-amber-700 text-white disabled:opacity-50 transition-colors cursor-pointer"
            >
              <Award className="w-3.5 h-3.5" />
              <span>{isSubmitting ? "Promoting..." : "Freeze & Register Gold"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
