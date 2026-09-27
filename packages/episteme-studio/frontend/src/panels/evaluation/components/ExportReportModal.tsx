import React, { useState, useEffect } from "react";
import { Check, Copy, Download, FileCode, FileJson, FileSpreadsheet, Loader2, X } from "lucide-react";
import { api } from "../../../api/client";
import type { EvaluationReportDetail } from "../../../api/types";

export type ExportReportFormat = "latex" | "jsonld" | "csv";

export interface ExportReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  report: EvaluationReportDetail | null;
}

export const ExportReportModal: React.FC<ExportReportModalProps> = ({
  isOpen,
  onClose,
  report,
}) => {
  const [activeFormat, setActiveFormat] = useState<ExportReportFormat>("latex");
  const [copied, setCopied] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportCache, setExportCache] = useState<Partial<Record<ExportReportFormat, string>>>({});

  // Reset cache when report changes
  useEffect(() => {
    setExportCache({});
    setError(null);
  }, [report?.evaluation_id]);

  // Fallback content generators if backend export route is offline or fails
  const generateFallbackLatex = (rep: EvaluationReportDetail) => {
    const f1 = (rep.key_metrics?.f1 ?? rep.key_metrics?.macro_f1 ?? 0).toFixed(3);
    const tenability = (
      rep.key_metrics?.delta_star ??
      rep.key_metrics?.tenability ??
      0
    ).toFixed(3);
    const ece = (rep.key_metrics?.ece ?? 0).toFixed(3);
    const mrr = (rep.key_metrics?.mrr ?? 0).toFixed(3);

    return `% Episteme Studio: Academic Evaluation Report
% Target: Invariant Monograph & SOTA Comparison
\\begin{table}[htbp]
\\centering
\\caption{Empirical and Structuralist Evaluation Results for \\texttt{${rep.evaluation_id}}}
\\label{tab:eval_${rep.evaluation_id.replace(/[^a-zA-Z0-9]/g, "_")}}
\\begin{tabular}{lcccc}
\\toprule
\\textbf{Evaluation ID} & \\textbf{Macro $F_1$} & \\textbf{Tenability $\\delta^*$} & \\textbf{ECE} & \\textbf{MRR} \\\\
\\midrule
\\texttt{${rep.evaluation_id}} & ${f1} & ${tenability} & ${ece} & ${mrr} \\\\
\\bottomrule
\\end{tabular}
\\vspace{1ex}
\\par\\small\\textit{Dataset: ${rep.dataset_ref || "Default Gold"}, Outcome: ${rep.outcome.toUpperCase()}}
\\end{table}`;
  };

  const generateFallbackJsonLd = (rep: EvaluationReportDetail) => {
    const f1 = rep.key_metrics?.f1 ?? rep.key_metrics?.macro_f1 ?? 0;
    const tenability = rep.key_metrics?.delta_star ?? rep.key_metrics?.tenability ?? 0;
    const ece = rep.key_metrics?.ece ?? 0;
    const mrr = rep.key_metrics?.mrr ?? 0;

    const payload = {
      "@context": {
        "@vocab": "https://episteme.org/schema/eval#",
        id: "@id",
        type: "@type",
      },
      "@id": `urn:episteme:evaluation:${rep.evaluation_id}`,
      "@type": "EvaluationReport",
      evaluation_id: rep.evaluation_id,
      run_ids: rep.run_ids,
      dataset_ref: rep.dataset_ref,
      outcome: rep.outcome,
      key_metrics: {
        macro_f1: f1,
        tenability_delta_star: tenability,
        expected_calibration_error: ece,
        mean_reciprocal_rank: mrr,
      },
      omitted_components_count: rep.omitted_components?.length ?? 0,
      violations_count: rep.violations?.length ?? 0,
      created_at: rep.created_at,
    };
    return JSON.stringify(payload, null, 2);
  };

  const generateFallbackCsv = (rep: EvaluationReportDetail) => {
    const f1 = (rep.key_metrics?.f1 ?? rep.key_metrics?.macro_f1 ?? 0).toFixed(4);
    const tenability = (
      rep.key_metrics?.delta_star ??
      rep.key_metrics?.tenability ??
      0
    ).toFixed(4);
    const ece = (rep.key_metrics?.ece ?? 0).toFixed(4);
    const mrr = (rep.key_metrics?.mrr ?? 0).toFixed(4);

    return `metric,value
evaluation_id,${rep.evaluation_id}
outcome,${rep.outcome}
dataset_ref,${rep.dataset_ref || "default"}
macro_f1,${f1}
tenability_delta_star,${tenability}
expected_calibration_error,${ece}
mean_reciprocal_rank,${mrr}
omitted_components,${rep.omitted_components?.length ?? 0}
invariant_violations,${rep.violations?.length ?? 0}
created_at,${rep.created_at}`;
  };

  // Fetch report export from backend
  useEffect(() => {
    if (!isOpen || !report) return;

    if (exportCache[activeFormat]) {
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    api
      .exportEvaluationReport(report.evaluation_id, activeFormat)
      .then((content) => {
        if (isMounted) {
          setExportCache((prev) => ({ ...prev, [activeFormat]: content }));
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.warn("Backend export request failed, using client-side fallback:", err);
          let fallback = "";
          if (activeFormat === "latex") fallback = generateFallbackLatex(report);
          else if (activeFormat === "jsonld") fallback = generateFallbackJsonLd(report);
          else fallback = generateFallbackCsv(report);

          setExportCache((prev) => ({ ...prev, [activeFormat]: fallback }));
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, report, activeFormat]);

  if (!isOpen || !report) return null;

  const currentContent = exportCache[activeFormat] || "";

  const handleCopy = () => {
    if (!currentContent) return;
    navigator.clipboard.writeText(currentContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!currentContent) return;
    const extensions: Record<ExportReportFormat, string> = {
      latex: "tex",
      jsonld: "jsonld",
      csv: "csv",
    };
    const mimeTypes: Record<ExportReportFormat, string> = {
      latex: "text/x-tex;charset=utf-8",
      jsonld: "application/ld+json;charset=utf-8",
      csv: "text/csv;charset=utf-8",
    };

    const blob = new Blob([currentContent], { type: mimeTypes[activeFormat] });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${report.evaluation_id}_export.${extensions[activeFormat]}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const lines = currentContent ? currentContent.split("\n") : [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="w-full max-w-3xl bg-app-surface border border-app-border rounded-lg shadow-2xl flex flex-col max-h-[85vh] overflow-hidden">
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-app-border flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <Download className="w-4 h-4 text-blue-500" />
            <h2 className="text-sm font-semibold text-app-heading">
              Academic & Publication Export
            </h2>
            <span className="text-[11px] font-mono text-app-muted px-1.5 py-0.5 rounded bg-app-bg border border-app-border">
              {report.evaluation_id}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Format Selector Tabs */}
        <div className="px-5 pt-3 pb-2 flex items-center justify-between border-b border-app-border bg-app-bg/50 shrink-0">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveFormat("latex")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors cursor-pointer ${
                activeFormat === "latex"
                  ? "bg-blue-600 text-white shadow-xs"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
            >
              <FileCode className="w-3.5 h-3.5" />
              <span>LaTeX Booktabs</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveFormat("jsonld")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors cursor-pointer ${
                activeFormat === "jsonld"
                  ? "bg-blue-600 text-white shadow-xs"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
            >
              <FileJson className="w-3.5 h-3.5" />
              <span>JSON-LD Semantic</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveFormat("csv")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors cursor-pointer ${
                activeFormat === "csv"
                  ? "bg-blue-600 text-white shadow-xs"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              <span>CSV Summary</span>
            </button>
          </div>

          <span className="text-[11px] text-app-muted font-mono hidden sm:inline">
            GET /api/evaluation/reports/{report.evaluation_id}/export?format={activeFormat}
          </span>
        </div>

        {/* Content Viewer with Line Numbers */}
        <div className="flex-1 overflow-auto bg-app-bg relative select-text">
          {isLoading ? (
            <div className="h-64 flex flex-col items-center justify-center gap-2 text-app-muted">
              <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
              <span className="text-xs">Generating {activeFormat.toUpperCase()} artifact...</span>
            </div>
          ) : (
            <div className="flex font-mono text-[11px] leading-relaxed p-4 min-w-full">
              {/* Line numbers gutter */}
              <div className="pr-4 border-r border-app-border/40 text-app-muted/50 select-none text-right shrink-0">
                {lines.map((_, i) => (
                  <div key={i}>{i + 1}</div>
                ))}
              </div>
              {/* Code content */}
              <pre className="pl-4 text-app-text whitespace-pre overflow-x-auto select-text font-mono flex-1">
                {currentContent}
              </pre>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-5 py-3 border-t border-app-border bg-app-surface flex items-center justify-between shrink-0">
          <span className="text-[11px] text-app-muted">
            Format: {activeFormat.toUpperCase()} · Publication Ready
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCopy}
              disabled={isLoading || !currentContent}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-app-surface hover:bg-app-subtle text-app-text border border-app-border transition-colors shadow-xs disabled:opacity-50 cursor-pointer"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                  <span className="text-emerald-500">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-app-muted" />
                  <span>Copy to Clipboard</span>
                </>
              )}
            </button>
            <button
              type="button"
              onClick={handleDownload}
              disabled={isLoading || !currentContent}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors shadow-xs disabled:opacity-50 cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download File</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
