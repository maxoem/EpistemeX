import React, { useState } from "react";
import { Plus, X, FileCode, CheckCircle2, AlertCircle } from "lucide-react";
import { api } from "../../../api/client";
import { useEvaluationStore } from "../../../store/evaluationStore";
import type { RegisterBenchmarkRequest } from "../../../api/types";

interface RegisterBenchmarkModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (benchmarkId: string) => void;
}

const STARTER_JSONLD = JSON.stringify(
  {
    "@context": {
      "episteme": "https://episteme.org/ontology#",
      "tn": "https://episteme.org/theorynet#",
      "id": "@id",
      "type": "@type",
    },
    "@graph": [
      {
        "id": "tn:T0_root",
        "type": "episteme:TheoryAtom",
        "class_name": "Mp",
        "label": "Fundamental Axiom Core",
      },
    ],
  },
  null,
  2
);

export const RegisterBenchmarkModal: React.FC<RegisterBenchmarkModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { fetchBenchmarks, setSelectedBenchmarkId } = useEvaluationStore();

  const [id, setId] = useState<string>("");
  const [name, setName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [taskType, setTaskType] = useState<string>("structuralist");
  const [jsonld, setJsonld] = useState<string>(STARTER_JSONLD);

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id.trim() || !name.trim() || !jsonld.trim()) {
      setError("ID, Name, and JSON-LD content are required.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const payload: RegisterBenchmarkRequest = {
        id: id.trim(),
        name: name.trim(),
        description: description.trim(),
        task_type: taskType,
        gold_standard_jsonld: jsonld.trim(),
      };

      const result = await api.registerBenchmark(payload);
      await fetchBenchmarks();
      setSelectedBenchmarkId(result.id);
      onSuccess?.(result.id);
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to register benchmark");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs select-none p-4">
      <div className="w-full max-w-xl bg-app-surface border border-app-border rounded-lg flex flex-col overflow-hidden text-app-text animate-in zoom-in-95 duration-150 font-sans">
        {/* Header */}
        <div className="h-12 px-4 border-b border-app-border flex items-center justify-between shrink-0 bg-app-bg/50">
          <div className="flex items-center gap-2">
            <div className="p-1 rounded bg-blue-500/10 text-blue-500 border border-blue-500/30">
              <Plus className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-xs font-semibold text-app-heading">
                Register Gold-Standard Benchmark
              </h2>
              <p className="text-[10px] text-app-muted">
                Add an authoritative scientific reference dataset to the evaluation catalog
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

          <div className="grid grid-cols-2 gap-2.5">
            <div>
              <label className="block text-[11px] font-medium text-app-muted mb-1">
                Benchmark Identifier (slug) *
              </label>
              <input
                type="text"
                value={id}
                onChange={(e) => setId(e.target.value)}
                placeholder="e.g. lakatos-proofs-1976"
                className="w-full bg-app-bg text-app-text px-2.5 py-1.5 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden font-mono"
                required
              />
            </div>

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
          </div>

          <div>
            <label className="block text-[11px] font-medium text-app-muted mb-1">
              Benchmark Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Lakatos Proofs and Refutations (1976)"
              className="w-full bg-app-bg text-app-text px-2.5 py-1.5 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-app-muted mb-1">
              Description & Scientific Grounding
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Primary treatise references, historical editions, domain taxonomy..."
              className="w-full bg-app-bg text-app-text p-2 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden resize-none"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-[11px] font-medium text-app-muted">
                Gold-Standard JSON-LD Specification *
              </label>
              <span className="text-[10px] text-app-muted font-mono">
                {jsonld.length} chars
              </span>
            </div>
            <textarea
              rows={8}
              value={jsonld}
              onChange={(e) => setJsonld(e.target.value)}
              spellCheck={false}
              className="w-full bg-app-bg text-app-text p-2 rounded border border-app-border text-[11px] font-mono leading-relaxed focus:border-blue-500 focus:outline-hidden resize-y"
              required
            />
          </div>

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
              disabled={isSubmitting || !id || !name}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors cursor-pointer"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{isSubmitting ? "Registering..." : "Register Benchmark"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
