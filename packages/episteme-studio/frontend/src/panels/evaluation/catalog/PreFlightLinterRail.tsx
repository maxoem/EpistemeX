import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Copy,
  Download,
  FileCode,
  RefreshCw,
  Sparkles,
  Wand2,
} from "lucide-react";
import { api } from "../../../api/client";
import type { BenchmarkValidationResult, BenchmarkValidationIssue } from "../../../api/types";

interface PreFlightLinterRailProps {
  initialContent?: string;
  benchmarkName?: string;
  onContentChange?: (content: string) => void;
  className?: string;
}

const DEFAULT_SAMPLE_JSONLD = JSON.stringify(
  {
    "@context": {
      "episteme": "https://episteme.org/ontology#",
      "tn": "https://episteme.org/theorynet#",
      "id": "@id",
      "type": "@type",
    },
    "@graph": [
      {
        "id": "tn:T0_aufbau_core",
        "type": "episteme:TheoryAtom",
        "class_name": "Mp",
        "label": "Aufbau Elementary Sensations Axiom",
        "provenance": {
          "doc_id": "doc_carnap_aufbau_de_1928.pdf",
          "page": 4,
          "bbox": [0.12, 0.45, 0.88, 0.62],
        },
      },
      {
        "id": "tn:T1_phenomenal_qualia",
        "type": "episteme:TheoryAtom",
        "class_name": "M",
        "label": "Phenomenal Qualia Configuration",
        "provenance": {
          "doc_id": "doc_carnap_aufbau_de_1928.pdf",
          "page": 12,
          "bbox": [0.1, 0.2, 0.85, 0.35],
        },
      },
      {
        "id": "rel_01",
        "type": "episteme:Specialization",
        "source": "tn:T0_aufbau_core",
        "target": "tn:T1_phenomenal_qualia",
        "predicate": "episteme:specializes",
      },
    ],
  },
  null,
  2
);

export const PreFlightLinterRail: React.FC<PreFlightLinterRailProps> = ({
  initialContent = DEFAULT_SAMPLE_JSONLD,
  benchmarkName = "Benchmark Spec",
  onContentChange,
  className = "",
}) => {
  const [content, setContent] = useState<string>(initialContent);
  const [validationResult, setValidationResult] = useState<BenchmarkValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<boolean>(false);
  const [jsonSyntaxError, setJsonSyntaxError] = useState<string | null>(null);

  // Sync when initialContent changes externally
  useEffect(() => {
    if (initialContent) {
      setContent(initialContent);
    }
  }, [initialContent]);

  // Validation execution
  const runValidation = useCallback(
    async (textToValidate: string) => {
      setIsValidating(true);
      setValidationError(null);

      // Client-side quick JSON syntax check
      try {
        JSON.parse(textToValidate);
        setJsonSyntaxError(null);
      } catch (err: any) {
        setJsonSyntaxError(err?.message || "Invalid JSON syntax");
      }

      try {
        const result = await api.validateBenchmark(textToValidate);
        setValidationResult(result);
      } catch (err: any) {
        setValidationError(err?.message || "Validation endpoint error");
      } finally {
        setIsValidating(false);
      }
    },
    []
  );

  // Validate on mount or content initialization
  useEffect(() => {
    runValidation(content);
  }, [runValidation]);

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setContent(val);
    onContentChange?.(val);
  };

  const handleFormatJson = () => {
    try {
      const parsed = JSON.parse(content);
      const formatted = JSON.stringify(parsed, null, 2);
      setContent(formatted);
      setJsonSyntaxError(null);
      onContentChange?.(formatted);
      runValidation(formatted);
    } catch (err: any) {
      setJsonSyntaxError(err?.message || "Cannot format invalid JSON");
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopyFeedback(true);
    setTimeout(() => setCopyFeedback(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: "application/ld+json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${benchmarkName.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "benchmark"}.jsonld`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Derive counts
  const errorCount = useMemo(() => {
    if (!validationResult) return 0;
    return validationResult.issues.filter((i) => i.severity === "error").length;
  }, [validationResult]);

  const warningCount = useMemo(() => {
    if (!validationResult) return 0;
    return validationResult.issues.filter((i) => i.severity === "warning").length;
  }, [validationResult]);

  const lines = useMemo(() => content.split("\n"), [content]);

  return (
    <div
      className={`w-[380px] shrink-0 border-l border-app-border bg-[#F8FAFC] dark:bg-app-rail flex flex-col h-full overflow-hidden select-none font-sans ${className}`}
    >
      {/* 44px Fixed Rail Header */}
      <div className="h-11 px-3.5 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileCode className="w-4 h-4 text-blue-500" />
          <span className="text-xs font-semibold text-app-heading tracking-tight">
            Pre-Flight Linter Rail
          </span>
        </div>

        {/* Status Pill */}
        {validationResult ? (
          validationResult.is_valid && errorCount === 0 ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium font-mono tabular-nums bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400 border border-emerald-500/30">
              <CheckCircle2 className="w-3 h-3" />
              VALID ({warningCount}W)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium font-mono tabular-nums bg-rose-500/10 text-rose-600 dark:bg-rose-500/20 dark:text-rose-400 border border-rose-500/30">
              <AlertCircle className="w-3 h-3" />
              {errorCount} ERRORS
            </span>
          )
        ) : isValidating ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono text-app-muted bg-app-subtle border border-app-border">
            <RefreshCw className="w-3 h-3 animate-spin" />
            LINTING...
          </span>
        ) : null}
      </div>

      {/* Scrollable Upper Section: Invariant Checklist & Issues */}
      <div className="p-3 border-b border-app-border space-y-3 shrink-0 max-h-[340px] overflow-y-auto">
        {/* Invariant Matrix Readout */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[11px] text-app-muted font-medium px-0.5">
            <span>FORMAL INVARIANT AUDIT</span>
            {validationResult && (
              <span className="font-mono text-[10px] tabular-nums">
                {validationResult.total_entities} Ent · {validationResult.total_triples} Rel
              </span>
            )}
          </div>

          <div className="border border-app-border rounded-md overflow-hidden bg-app-surface/50 divide-y divide-app-border text-xs">
            <div className="grid grid-cols-2 divide-x divide-app-border">
              {/* Strict DAG Acyclicity */}
              <div className="p-2 flex items-center justify-between">
                <div className="flex flex-col">
                  <span className="text-[11px] font-medium text-app-heading">DAG Acyclicity</span>
                  <span className="text-[10px] text-app-muted">Strict No-Cycle</span>
                </div>
                {validationResult?.is_dag ? (
                  <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 font-mono">
                    <CheckCircle2 className="w-3 h-3" /> PASS
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-rose-500 font-mono">
                    <AlertCircle className="w-3 h-3" /> FAIL
                  </span>
                )}
              </div>

              {/* Root Element Conformity B(TN) = {T0} */}
              <div className="p-2 flex items-center justify-between">
                <div className="flex flex-col">
                  <span className="text-[11px] font-medium text-app-heading">Root Conformity</span>
                  <span className="text-[10px] font-mono text-app-muted truncate max-w-[80px]">
                    {validationResult?.root_element || "B(TN)={T₀}"}
                  </span>
                </div>
                {validationResult?.root_element ? (
                  <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 font-mono">
                    <CheckCircle2 className="w-3 h-3" /> PASS
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-amber-500 font-mono">
                    <AlertTriangle className="w-3 h-3" /> WARN
                  </span>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 divide-x divide-app-border">
              {/* Dangling Edges Check */}
              <div className="p-2 flex items-center justify-between">
                <div className="flex flex-col">
                  <span className="text-[11px] font-medium text-app-heading">Dangling Edges</span>
                  <span className="text-[10px] text-app-muted">No Orphan Preds</span>
                </div>
                {validationResult &&
                !validationResult.issues.some((i) => i.rule_id === "DANGLING_EDGE") ? (
                  <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 font-mono">
                    <CheckCircle2 className="w-3 h-3" /> PASS
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-rose-500 font-mono">
                    <AlertCircle className="w-3 h-3" /> FAIL
                  </span>
                )}
              </div>

              {/* Grounding Integrity */}
              <div className="p-2 flex items-center justify-between">
                <div className="flex flex-col">
                  <span className="text-[11px] font-medium text-app-heading">ADU Grounding</span>
                  <span className="text-[10px] text-app-muted">PDF BBox Ratio</span>
                </div>
                {validationResult &&
                !validationResult.issues.some((i) => i.rule_id === "WEAK_GROUNDING") ? (
                  <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 font-mono">
                    <CheckCircle2 className="w-3 h-3" /> PASS
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-amber-500 font-mono">
                    <AlertTriangle className="w-3 h-3" /> WARN
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* JSON Syntax Alert if present */}
        {jsonSyntaxError && (
          <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <span className="font-semibold block">JSON Syntax Error</span>
              <p className="font-mono text-[11px] break-all leading-tight mt-0.5">
                {jsonSyntaxError}
              </p>
            </div>
          </div>
        )}

        {/* Validation Issues Feed */}
        {validationResult && validationResult.issues.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[11px] text-app-muted font-medium px-0.5">
              ANOMALIES & DIAGNOSTICS ({validationResult.issues.length})
            </div>
            <div className="space-y-1 max-h-[160px] overflow-y-auto pr-0.5">
              {validationResult.issues.map((issue, idx) => {
                const isError = issue.severity === "error";
                return (
                  <div
                    key={`${issue.rule_id}-${idx}`}
                    className={`p-2 rounded text-xs border ${
                      isError
                        ? "bg-rose-500/5 border-rose-500/30 text-rose-700 dark:text-rose-300"
                        : "bg-amber-500/5 border-amber-500/30 text-amber-700 dark:text-amber-300"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1 mb-0.5">
                      <span className="font-mono text-[10px] font-semibold tracking-wide uppercase px-1 py-0.2 rounded bg-app-surface/60">
                        {issue.rule_id}
                      </span>
                      {issue.location && (
                        <span className="font-mono text-[10px] text-app-muted truncate max-w-[140px]">
                          {issue.location}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] leading-relaxed text-app-text/90">{issue.message}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {validationError && (
          <div className="p-2 rounded bg-rose-500/10 text-rose-500 text-xs font-mono">
            {validationError}
          </div>
        )}
      </div>

      {/* Editor Section: Toolbar + Monospace CodeMirror-style View */}
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden bg-app-bg">
        {/* Editor Toolbar */}
        <div className="h-9 px-3 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs">
          <div className="flex items-center gap-1.5 text-app-muted text-[11px]">
            <span className="font-mono">{lines.length} lines</span>
            <span>·</span>
            <span className="font-mono">{content.length} chars</span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={handleFormatJson}
              className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
              title="Format JSON"
            >
              <Wand2 className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleCopy}
              className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors relative"
              title="Copy JSON-LD"
            >
              <Copy className="w-3.5 h-3.5" />
              {copyFeedback && (
                <span className="absolute -top-7 right-0 bg-blue-600 text-white text-[10px] px-1.5 py-0.5 rounded border border-blue-400/30 animate-in fade-in">
                  Copied!
                </span>
              )}
            </button>
            <button
              onClick={handleDownload}
              className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
              title="Download .jsonld"
            >
              <Download className="w-3.5 h-3.5" />
            </button>
            <div className="h-3.5 w-px bg-app-border mx-0.5" />
            <button
              onClick={() => runValidation(content)}
              disabled={isValidating}
              className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <RefreshCw className={`w-3 h-3 ${isValidating ? "animate-spin" : ""}`} />
              <span>Re-Validate</span>
            </button>
          </div>
        </div>

        {/* Monospace Code Editor Area */}
        <div className="flex-1 relative flex overflow-hidden">
          {/* Gutter / Line Numbers */}
          <div className="w-10 bg-app-surface/60 border-r border-app-border py-2 text-right pr-2 text-[10px] font-mono text-app-muted/60 select-none overflow-hidden shrink-0">
            {lines.slice(0, 500).map((_, i) => (
              <div key={i} className="leading-[18px]">
                {i + 1}
              </div>
            ))}
          </div>

          {/* Text Area */}
          <textarea
            value={content}
            onChange={handleTextChange}
            spellCheck={false}
            className="flex-1 h-full p-2 bg-transparent text-app-text font-mono text-[11px] leading-[18px] resize-none outline-hidden overflow-auto whitespace-pre tab-[2] selection:bg-blue-500/20"
            placeholder="Paste or edit benchmark JSON-LD schema specification here..."
          />
        </div>
      </div>
    </div>
  );
};
