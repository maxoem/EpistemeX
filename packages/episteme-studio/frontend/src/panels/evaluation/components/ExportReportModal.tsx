import React, { useState } from "react";
import { Check, Copy, Download, FileCode, FileJson, FileText, X } from "lucide-react";
import type { EvaluationReportDetail } from "../../../api/types";

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
  const [activeFormat, setActiveFormat] = useState<"latex" | "jsonld" | "markdown">("latex");
  const [copied, setCopied] = useState(false);

  if (!isOpen || !report) return null;

  const f1 = (report.key_metrics?.f1 ?? report.key_metrics?.macro_f1 ?? 0).toFixed(3);
  const tenability = (
    report.key_metrics?.delta_star ??
    report.key_metrics?.tenability ??
    0
  ).toFixed(3);
  const ece = (report.key_metrics?.ece ?? 0).toFixed(3);
  const mrr = (report.key_metrics?.mrr ?? 0).toFixed(3);

  const generateLatex = () => {
    return `% Episteme Studio: Academic Evaluation Report
% Target: Invariant Monograph & SOTA Comparison
\\begin{table}[htbp]
\\centering
\\caption{Empirical and Structuralist Evaluation Results for \\texttt{${report.evaluation_id}}}
\\label{tab:eval_${report.evaluation_id.replace(/[^a-zA-Z0-9]/g, "_")}}
\\begin{tabular}{lcccc}
\\toprule
\\textbf{Evaluation ID} & \\textbf{Macro $F_1$} & \\textbf{Tenability $\\delta^*$} & \\textbf{ECE} & \\textbf{MRR} \\\\
\\midrule
\\texttt{${report.evaluation_id}} & ${f1} & ${tenability} & ${ece} & ${mrr} \\\\
\\bottomrule
\\end{tabular}
\\vspace{1ex}
\\par\\small\\textit{Dataset: ${report.dataset_ref || "Default Gold"}, Outcome: ${report.outcome.toUpperCase()}}
\\end{table}`;
  };

  const generateJsonLd = () => {
    const payload = {
      "@context": {
        "@vocab": "https://episteme.org/schema/eval#",
        id: "@id",
        type: "@type",
      },
      "@id": `urn:episteme:evaluation:${report.evaluation_id}`,
      "@type": "EvaluationReport",
      evaluationId: report.evaluation_id,
      runIds: report.run_ids,
      datasetRef: report.dataset_ref,
      outcome: report.outcome,
      metrics: {
        macroF1: parseFloat(f1),
        tenabilityDeltaStar: parseFloat(tenability),
        expectedCalibrationError: parseFloat(ece),
        meanReciprocalRank: parseFloat(mrr),
      },
      omittedCount: report.omitted_components?.length ?? 0,
      violationCount: report.violations?.length ?? 0,
      createdAt: report.created_at,
    };
    return JSON.stringify(payload, null, 2);
  };

  const generateMarkdown = () => {
    return `## Episteme Studio Evaluation Report
- **Evaluation ID:** \`${report.evaluation_id}\`
- **Benchmark / Dataset:** ${report.dataset_ref || "Default Gold"}
- **Outcome:** \`${report.outcome.toUpperCase()}\`
- **Timestamp:** ${report.created_at}

### Key Metrics
| Macro $F_1$ | Bourbaki Tenability $\\delta^*$ | Expected Calibration Error (ECE) | Retrieval MRR |
|:---:|:---:|:---:|:---:|
| ${f1} | ${tenability} | ${ece} | ${mrr} |

### Decomposition Summary
- Omitted Components: ${report.omitted_components?.length ?? 0}
- Invariant Violations: ${report.violations?.length ?? 0}
`;
  };

  const getContent = () => {
    switch (activeFormat) {
      case "latex":
        return generateLatex();
      case "jsonld":
        return generateJsonLd();
      case "markdown":
        return generateMarkdown();
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(getContent());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const content = getContent();
    const extensions = { latex: "tex", jsonld: "jsonld", markdown: "md" };
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${report.evaluation_id}_report.${extensions[activeFormat]}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="w-full max-w-2xl bg-app-surface border border-app-border rounded-lg shadow-2xl flex flex-col max-h-[85vh] overflow-hidden">
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-app-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Download className="w-4 h-4 text-blue-500" />
            <h2 className="text-sm font-semibold text-app-heading">
              Export Evaluation Report
            </h2>
            <span className="text-[11px] font-mono text-app-muted px-1.5 py-0.5 rounded bg-app-bg border border-app-border">
              {report.evaluation_id}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Format Selector Tabs */}
        <div className="px-5 pt-3 pb-2 flex items-center gap-2 border-b border-app-border bg-app-bg/50">
          <button
            onClick={() => setActiveFormat("latex")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              activeFormat === "latex"
                ? "bg-blue-600 text-white shadow-xs"
                : "text-app-muted hover:text-app-text hover:bg-app-subtle"
            }`}
          >
            <FileCode className="w-3.5 h-3.5" />
            <span>LaTeX Booktabs</span>
          </button>
          <button
            onClick={() => setActiveFormat("jsonld")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              activeFormat === "jsonld"
                ? "bg-blue-600 text-white shadow-xs"
                : "text-app-muted hover:text-app-text hover:bg-app-subtle"
            }`}
          >
            <FileJson className="w-3.5 h-3.5" />
            <span>JSON-LD Metadata</span>
          </button>
          <button
            onClick={() => setActiveFormat("markdown")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              activeFormat === "markdown"
                ? "bg-blue-600 text-white shadow-xs"
                : "text-app-muted hover:text-app-text hover:bg-app-subtle"
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Markdown Summary</span>
          </button>
        </div>

        {/* Content Viewer */}
        <div className="p-5 flex-1 overflow-auto bg-app-bg font-mono text-[11px] leading-relaxed text-app-text selection:bg-blue-500/30">
          <pre className="whitespace-pre-wrap select-text">{getContent()}</pre>
        </div>

        {/* Footer Actions */}
        <div className="px-5 py-3 border-t border-app-border bg-app-surface flex items-center justify-between">
          <span className="text-[11px] text-app-muted">
            Format: {activeFormat.toUpperCase()} · Publication Ready
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-app-surface hover:bg-app-subtle text-app-text border border-app-border transition-colors shadow-xs"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                  <span className="text-emerald-500">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-app-muted" />
                  <span>Copy Content</span>
                </>
              )}
            </button>
            <button
              onClick={handleDownload}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors shadow-xs"
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
