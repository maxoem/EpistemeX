import React, { useMemo } from "react";
import { Award, ChevronRight, Play } from "lucide-react";
import { useEvaluationStore } from "../../../store/evaluationStore";
import type { BenchmarkDescriptor } from "../../../api/types";

interface BenchmarkRunsTabProps {
  benchmark: BenchmarkDescriptor;
  onSelectReport?: (reportId: string) => void;
  onEvaluateBenchmark?: (benchmark: BenchmarkDescriptor) => void;
}

export const BenchmarkRunsTab: React.FC<BenchmarkRunsTabProps> = ({
  benchmark,
  onSelectReport,
  onEvaluateBenchmark,
}) => {
  const { reports, setActiveMode, setActiveReportId } = useEvaluationStore();

  const matchingReports = useMemo(() => {
    return reports.filter(
      (r) =>
        (r.dataset_ref && r.dataset_ref.toLowerCase().includes(benchmark.id.toLowerCase())) ||
        r.evaluation_id.toLowerCase().includes(benchmark.id.toLowerCase())
    );
  }, [reports, benchmark.id]);

  const handleInspectReport = (reportId: string) => {
    setActiveReportId(reportId);
    setActiveMode("inspector");
    onSelectReport?.(reportId);
  };

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Centered Monograph Container */}
      <div className="max-w-4xl mx-auto w-full py-6 px-4 space-y-7 font-sans">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-display font-medium text-sm text-app-heading tracking-tight">
              Evaluation Execution History
            </h2>
            <p className="text-xs text-app-text/90 mt-0.5 font-sans">
              Recorded pipeline runs evaluated against {benchmark.name}.
            </p>
          </div>

          <button
            onClick={() => onEvaluateBenchmark?.(benchmark)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-sans font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer"
          >
            <Play className="w-3.5 h-3.5" />
            <span>Execute New Evaluation</span>
          </button>
        </div>

        <div className="border border-app-border rounded-md overflow-hidden bg-app-surface/30 divide-y divide-app-border text-xs font-sans">
          {matchingReports.length > 0 ? (
            matchingReports.map((rep) => (
              <div
                key={rep.evaluation_id}
                onClick={() => handleInspectReport(rep.evaluation_id)}
                className="p-3.5 flex items-center justify-between hover:bg-app-subtle/50 transition-colors cursor-pointer group"
              >
                <div className="flex items-center gap-3">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-app-heading group-hover:text-blue-500 transition-colors">
                        {rep.evaluation_id}
                      </span>
                      <span
                        className={`px-1.5 py-0.2 rounded text-[10px] font-sans uppercase font-medium ${
                          rep.outcome === "pass"
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                            : "bg-app-subtle text-app-muted border border-app-border"
                        }`}
                      >
                        {rep.outcome}
                      </span>
                    </div>
                    <span className="font-mono text-[11px] text-app-muted mt-0.5">
                      Target Run: {rep.run_ids.join(", ")}
                    </span>
                  </div>
                </div>

                {/* Key Metrics: font-sans tabular-nums */}
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-3 font-sans text-xs tabular-nums text-app-muted">
                    {Object.entries(rep.key_metrics || {})
                      .slice(0, 3)
                      .map(([k, v]) => (
                        <span key={k}>
                          <span className="uppercase text-[10px] text-app-muted/70">{k}:</span>{" "}
                          <span className="text-app-heading font-medium">
                            {typeof v === "number" ? v.toFixed(3) : v}
                          </span>
                        </span>
                      ))}
                  </div>

                  <ChevronRight className="w-4 h-4 text-app-muted group-hover:text-app-text transition-colors" />
                </div>
              </div>
            ))
          ) : (
            <div className="p-8 text-center text-app-muted space-y-2">
              <Award className="w-8 h-8 mx-auto text-app-muted/40" />
              <p className="font-display font-medium text-xs text-app-heading">
                No recorded evaluations for this benchmark yet
              </p>
              <p className="text-[11px] max-w-sm mx-auto text-app-muted font-sans">
                Run an evaluation from a completed pipeline run to record metrics and benchmark performance.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
