import React, {useEffect, useMemo, useState} from "react";
import {useEvaluationStore} from "../../../store/evaluationStore";
import {useRunsStore} from "../../../store/runsStore";
import {AdjudicationCard} from "./AdjudicationCard";
import {AlertTriangle, CheckCircle2, Download, RefreshCw, Search,} from "lucide-react";

export const BorderlineAdjudicationQueue: React.FC = () => {
  const {
    borderlineQueue,
    isLoadingBorderline,
    fetchBorderlineDecisions,
    adjudicateDecisionItem,
    exportActiveLearningData,
  } = useEvaluationStore();

  const { selectedRunId, runs } = useRunsStore();
  const runId = selectedRunId || (runs[0]?.run_id ?? "run-latest");

  const [phaseFilter, setPhaseFilter] = useState<string>("all");
  const [primitiveFilter, setPrimitiveFilter] = useState<string>("all");
  const [discrepancyOnly, setDiscrepancyOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState<boolean>(false);

  useEffect(() => {
    if (runId) {
      fetchBorderlineDecisions(runId);
    }
  }, [runId, fetchBorderlineDecisions]);

  const handleExport = async () => {
    setIsExporting(true);
    setExportMessage(null);
    try {
      const res = await exportActiveLearningData(runId);
      setExportMessage(`Successfully exported ${res.exported_count} samples to ${res.target_file}`);
    } catch (err: any) {
      setExportMessage(`Export failed: ${err.message || String(err)}`);
    } finally {
      setIsExporting(false);
    }
  };

  const filteredItems = useMemo(() => {
    return borderlineQueue.filter((item) => {
      if (phaseFilter !== "all" && item.phase.toLowerCase() !== phaseFilter.toLowerCase()) {
        return false;
      }
      if (primitiveFilter !== "all" && item.primitive.toLowerCase() !== primitiveFilter.toLowerCase()) {
        return false;
      }
      if (discrepancyOnly && item.conformal_set.length <= 1 && item.empirical_accuracy >= 0.85) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const text = (item.context.input_text || "").toLowerCase();
        const pred = String(item.prediction).toLowerCase();
        if (!text.includes(q) && !pred.includes(q) && !item.decision_id.toLowerCase().includes(q)) {
          return false;
        }
      }
      return true;
    });
  }, [borderlineQueue, phaseFilter, primitiveFilter, discrepancyOnly, searchQuery]);

  const handleAdjudicate = async (decisionId: string, val: string | number, notes?: string) => {
    await adjudicateDecisionItem(runId, decisionId, val, notes);
  };

  const pendingCount = filteredItems.filter((i) => !i.adjudicated_value).length;

  return (
    <div className="flex-1 flex flex-col h-full bg-app-bg select-none overflow-hidden">
      {/* Header Toolbar */}
      <div className="p-4 border-b border-app-border bg-app-surface flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-semibold text-app-heading font-display tracking-tight">
              Borderline Decisions & Active Learning Queue
            </h2>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-amber-500/15 text-amber-500 border border-amber-500/25">
              {pendingCount} Pending Triage
            </span>
          </div>
          <p className="text-[11px] text-app-muted mt-0.5 font-sans">
            Curate ambiguous conformal sets (|C| &gt; 1) and stochastic audit discrepancies for active learning fine-tuning
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => fetchBorderlineDecisions(runId)}
            disabled={isLoadingBorderline}
            className="p-1.5 rounded bg-app-bg hover:bg-app-subtle border border-app-border text-app-muted hover:text-app-heading transition-colors cursor-pointer disabled:opacity-50"
            title="Refresh queue"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingBorderline ? "animate-spin" : ""}`} />
          </button>

          <button
            type="button"
            onClick={handleExport}
            disabled={isExporting || borderlineQueue.length === 0}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-colors cursor-pointer disabled:opacity-50 shadow-xs"
            title="Export adjudicated records to JSONL active learning dataset"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{isExporting ? "Exporting..." : "Export Active Learning (JSONL)"}</span>
          </button>
        </div>
      </div>

      {/* Export notification banner */}
      {exportMessage && (
        <div className="px-4 py-2 bg-emerald-500/10 border-b border-emerald-500/20 text-xs text-emerald-400 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{exportMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setExportMessage(null)}
            className="text-app-muted hover:text-app-heading text-xs cursor-pointer"
          >
            ×
          </button>
        </div>
      )}

      {/* Filters Toolbar */}
      <div className="px-4 py-2.5 border-b border-app-border bg-app-bg flex flex-wrap items-center justify-between gap-3 text-xs shrink-0">
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={phaseFilter}
            onChange={(e) => setPhaseFilter(e.target.value)}
            className="px-2 py-1 rounded bg-app-surface border border-app-border text-app-text text-[11px] font-sans focus:outline-hidden"
          >
            <option value="all">All Phases</option>
            <option value="phase1">Phase 1 (Ingestion)</option>
            <option value="phase2">Phase 2 (Local KG)</option>
            <option value="phase3">Phase 3 (Global Rel)</option>
            <option value="phase4">Phase 4 (Argument Mining)</option>
            <option value="phase5">Phase 5 (Theory Fusion)</option>
            <option value="phase6">Phase 6 (TheoryNet)</option>
          </select>

          <select
            value={primitiveFilter}
            onChange={(e) => setPrimitiveFilter(e.target.value)}
            className="px-2 py-1 rounded bg-app-surface border border-app-border text-app-text text-[11px] font-sans focus:outline-hidden"
          >
            <option value="all">All Primitives</option>
            <option value="noul">noul</option>
            <option value="choice">choice</option>
            <option value="score">score</option>
          </select>

          <button
            type="button"
            onClick={() => setDiscrepancyOnly(!discrepancyOnly)}
            className={`inline-flex items-center gap-1.5 px-2 py-1 rounded border text-[11px] font-medium transition-colors cursor-pointer ${
              discrepancyOnly
                ? "bg-amber-500/15 border-amber-500/30 text-amber-500"
                : "bg-app-surface border-app-border text-app-muted hover:text-app-text"
            }`}
          >
            <AlertTriangle className="w-3 h-3" />
            <span>Discrepant / Ambiguous Only</span>
          </button>
        </div>

        <div className="relative w-56">
          <Search className="w-3.5 h-3.5 text-app-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search context / prediction..."
            className="w-full pl-8 pr-3 py-1 rounded bg-app-surface border border-app-border text-app-text placeholder:text-app-muted text-xs focus:outline-hidden"
          />
        </div>
      </div>

      {/* Cards Scrollable Queue */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {isLoadingBorderline ? (
          <div className="py-12 flex flex-col items-center justify-center text-app-muted space-y-2">
            <RefreshCw className="w-5 h-5 animate-spin" />
            <span className="text-xs">Loading borderline decisions...</span>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="py-16 flex flex-col items-center justify-center text-center text-app-muted space-y-2">
            <CheckCircle2 className="w-8 h-8 text-emerald-500/50" />
            <span className="text-xs font-semibold text-app-heading">
              Queue Clear: No Borderline Decisions
            </span>
            <p className="text-[11px] max-w-sm text-app-muted">
              All decisions for this run satisfy high empirical confidence (1-α coverage) without ambiguity.
            </p>
          </div>
        ) : (
          filteredItems.map((item) => (
            <AdjudicationCard
              key={item.decision_id}
              item={item}
              runId={runId}
              onAdjudicate={handleAdjudicate}
            />
          ))
        )}
      </div>
    </div>
  );
};
