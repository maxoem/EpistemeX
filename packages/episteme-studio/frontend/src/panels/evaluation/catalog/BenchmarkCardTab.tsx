import React, { useState } from "react";
import { Copy, Terminal } from "lucide-react";
import type { BenchmarkDescriptor } from "../../../api/types";

interface BenchmarkCardTabProps {
  benchmark: BenchmarkDescriptor;
}

export const BenchmarkCardTab: React.FC<BenchmarkCardTabProps> = ({
  benchmark,
}) => {
  const [copiedCitation, setCopiedCitation] = useState<boolean>(false);
  const [copiedCode, setCopiedCode] = useState<boolean>(false);

  const bibtex =
    benchmark.citation ||
    `@dataset{episteme_${benchmark.id.replace(/[^a-zA-Z0-9_]/g, "_")},
  author    = {Episteme Theory-Graph Research Group},
  title     = {${benchmark.name}},
  year      = {2026},
  publisher = {Episteme Benchmark Catalog},
  note      = {Formal gold-standard evaluation dataset for scientific literature}
}`;

  const pythonSnippet = `# Load and evaluate against this benchmark in episteme-pipeline:
from episteme_pipeline.evaluation import load_benchmark, evaluate_graph

# 1. Ingest gold standard reference
benchmark = load_benchmark("${benchmark.id}")
print(f"Loaded: {benchmark.name} ({benchmark.task_type})")

# 2. Evaluate pipeline run output
report = evaluate_graph(
    run_id="my_pipeline_run_01",
    benchmark_id="${benchmark.id}",
    target_metrics=${JSON.stringify(benchmark.target_metrics || ["MCC", "PFS", "GM-GBS"])}
)
print(report.summary_markdown)`;

  const handleCopyCitation = () => {
    navigator.clipboard.writeText(bibtex);
    setCopiedCitation(true);
    setTimeout(() => setCopiedCitation(false), 2000);
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(pythonSnippet);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const splitsList = benchmark.splits ? Object.values(benchmark.splits) : [];

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Centered Monograph Container */}
      <div className="max-w-4xl mx-auto w-full py-6 px-4 space-y-7 font-sans">
        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 1. Dataset Abstract / Scope                                       */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="space-y-2">
          <h2 className="font-display font-medium text-sm text-app-heading tracking-tight">
            Scope & Methodological Description
          </h2>
          <p className="text-xs text-app-text/90 leading-relaxed font-sans">
            {benchmark.description ||
              "Authoritative scientific reference gold-standard dataset engineered for reproducible knowledge extraction and theory-graph verification."}
          </p>
        </div>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 2. Structured Metadata Table (Replacing scattered boxes)          */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="space-y-2">
          <h2 className="font-display font-medium text-sm text-app-heading tracking-tight">
            Benchmark Metadata Specification
          </h2>
          <div className="border border-app-border rounded-md overflow-hidden bg-app-surface/30 divide-y divide-app-border text-xs">
            {/* Identifier */}
            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Benchmark Identifier</span>
              <span className="font-mono text-xs text-app-heading">{benchmark.id}</span>
            </div>

            {/* Quality Tier / Gold Status (Given its own clean row instead of inline badge) */}
            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Dataset Tier</span>
              <span className="text-app-text font-sans">
                Gold Standard Reference Dataset (Authoritative Curation)
              </span>
            </div>

            {/* Task Category */}
            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Evaluation Task</span>
              <span className="text-app-text font-sans capitalize">
                {benchmark.task_type} Task (Level {benchmark.level || 4} Evaluation)
              </span>
            </div>

            {/* Scientific Domain */}
            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Scientific Domain</span>
              <span className="text-app-text font-sans">{benchmark.domain || "General Science"}</span>
            </div>

            {/* Target Metrics */}
            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Recommended Metrics</span>
              <span className="text-app-text font-sans">
                {benchmark.target_metrics?.join(", ") || "MCC, PFS, GM-GBS"}
              </span>
            </div>

            {/* License */}
            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">License & Attribution</span>
              <span className="text-app-text font-sans">{benchmark.license || "Open Data"}</span>
            </div>

            {/* Primary Reference File */}
            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Gold Annotations Path</span>
              <span className="font-mono text-[11px] text-app-muted truncate" title={benchmark.gold_standard_path}>
                {benchmark.gold_standard_path}
              </span>
            </div>

            {/* Competency Queries File if applicable */}
            {benchmark.queries_path && (
              <div className="flex items-center px-4 py-2.5">
                <span className="w-52 text-app-muted font-medium shrink-0">Competency Queries Path</span>
                <span className="font-mono text-[11px] text-app-muted truncate" title={benchmark.queries_path}>
                  {benchmark.queries_path}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 3. Resource Splits Table                                          */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="space-y-2">
          <h2 className="font-display font-medium text-sm text-app-heading tracking-tight">
            Resource Splits & Artifacts
          </h2>
          <div className="border border-app-border rounded-md overflow-hidden bg-app-surface/30">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="bg-app-surface border-b border-app-border text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
                <tr className="h-8">
                  <th className="px-4 py-0 w-28 font-medium">Split</th>
                  <th className="px-3 py-0 w-24 font-medium">Format</th>
                  <th className="px-3 py-0 w-32 font-medium">Items</th>
                  <th className="px-3 py-0 w-28 font-medium">File Size</th>
                  <th className="px-3 py-0 font-medium">Filesystem Path</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-app-border/70 text-xs">
                {splitsList.length > 0 ? (
                  splitsList.map((split) => (
                    <tr key={split.name} className="h-9">
                      <td className="px-4 py-1 font-medium capitalize text-app-heading">
                        {split.name}
                      </td>
                      <td className="px-3 py-1 text-app-muted uppercase">
                        {split.format}
                      </td>
                      <td className="px-3 py-1 tabular-nums text-app-text">
                        {split.item_count !== null && split.item_count !== undefined
                          ? `${split.item_count} records`
                          : "—"}
                      </td>
                      <td className="px-3 py-1 tabular-nums text-app-muted">
                        {split.size_bytes ? `${(split.size_bytes / 1024).toFixed(1)} KB` : "—"}
                      </td>
                      <td className="px-3 py-1 font-mono text-[11px] text-app-muted truncate max-w-sm" title={split.path}>
                        {split.path}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr className="h-9">
                    <td className="px-4 py-1 font-medium text-app-heading">gold</td>
                    <td className="px-3 py-1 text-app-muted uppercase">jsonld</td>
                    <td className="px-3 py-1 text-app-muted">—</td>
                    <td className="px-3 py-1 text-app-muted">—</td>
                    <td className="px-3 py-1 font-mono text-[11px] text-app-muted">{benchmark.gold_standard_path}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 4. Quickstart Code Snippet                                        */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-display font-medium text-sm text-app-heading tracking-tight flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-app-muted" />
              <span>Python Evaluation Quickstart</span>
            </h2>
            <button
              onClick={handleCopyCode}
              className="flex items-center gap-1 text-[11px] text-app-muted hover:text-app-text cursor-pointer transition-colors"
            >
              <Copy className="w-3 h-3" />
              <span>{copiedCode ? "Copied!" : "Copy code"}</span>
            </button>
          </div>
          <div className="p-3.5 rounded-md bg-app-surface border border-app-border font-mono text-[11px] text-app-text overflow-x-auto">
            <pre>{pythonSnippet}</pre>
          </div>
        </div>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 5. Bibliographic Citation Block (BibTeX)                          */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-display font-medium text-sm text-app-heading tracking-tight">
              Bibliographic Reference (BibTeX)
            </h2>
            <button
              onClick={handleCopyCitation}
              className="flex items-center gap-1 text-[11px] text-app-muted hover:text-app-text cursor-pointer transition-colors"
            >
              <Copy className="w-3 h-3" />
              <span>{copiedCitation ? "Copied!" : "Copy BibTeX"}</span>
            </button>
          </div>
          <div className="p-3.5 rounded-md bg-app-surface/60 border border-app-border font-mono text-[11px] text-app-muted overflow-x-auto">
            <pre>{bibtex}</pre>
          </div>
        </div>
      </div>
    </div>
  );
};
