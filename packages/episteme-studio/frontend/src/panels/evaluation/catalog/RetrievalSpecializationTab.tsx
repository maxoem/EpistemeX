import React from "react";
import type { BenchmarkDescriptor } from "../../../api/types";

interface RetrievalSpecializationTabProps {
  benchmark: BenchmarkDescriptor;
}

export const RetrievalSpecializationTab: React.FC<RetrievalSpecializationTabProps> = ({
  benchmark,
}) => {
  const details = benchmark.retrieval_details;

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Centered Monograph Container */}
      <div className="max-w-4xl mx-auto w-full py-6 px-4 space-y-7 font-sans">
        <div className="space-y-2">
          <h2 className="font-display font-medium text-sm text-app-heading tracking-tight">
            Competency Retrieval Query Testbed
          </h2>
          <p className="text-xs text-app-text/90 leading-relaxed font-sans">
            Competency queries assess whether the extracted theory graph functions as an effective structured retrieval index for answering domain-specific, counterfactual, and axiomatic queries.
          </p>
        </div>

        {/* Metadata Table replacing boxes */}
        <div className="space-y-2">
          <h2 className="font-display font-medium text-sm text-app-heading tracking-tight">
            Query Suite Specifications
          </h2>
          <div className="border border-app-border rounded-md overflow-hidden bg-app-surface/30 divide-y divide-app-border text-xs font-sans">
            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Total Query Volume</span>
              <span className="text-app-heading font-medium tabular-nums">
                {details?.query_count || 85} queries
              </span>
            </div>

            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Extracted Query Categories</span>
              <span className="text-app-text">
                {details?.query_categories?.join(", ") || "Axiomatic, Empirical, General"}
              </span>
            </div>

            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Target Evaluator Metrics</span>
              <span className="text-app-text">
                MRR (Mean Reciprocal Rank), Hits@1, Hits@10, nDCG
              </span>
            </div>

            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Queries Configuration File</span>
              <span className="font-mono text-[11px] text-app-muted truncate" title={benchmark.queries_path || ""}>
                {benchmark.queries_path || "datasets/queries.yaml"}
              </span>
            </div>
          </div>
        </div>

        {/* Sample Queries Table */}
        <div className="space-y-2">
          <h2 className="font-display font-medium text-sm text-app-heading tracking-tight">
            Sample Competency Questions & Target Grounding
          </h2>
          <div className="border border-app-border rounded-md overflow-hidden bg-app-surface/30 divide-y divide-app-border text-xs">
            {details?.sample_queries && details.sample_queries.length > 0 ? (
              details.sample_queries.map((q) => (
                <div key={q.id} className="p-3.5 space-y-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[11px] text-app-heading font-semibold">{q.id}</span>
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-sans bg-app-subtle border border-app-border text-app-muted">
                        {q.category || "General"}
                      </span>
                    </div>
                    {q.target_nodes && (
                      <span className="text-[11px] font-mono text-app-muted">
                        Target nodes: {q.target_nodes.join(", ")}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-app-text font-medium">{q.text}</p>
                </div>
              ))
            ) : (
              <div className="p-4 text-app-muted text-xs">
                Queries configured in YAML: <span className="font-mono text-app-text">{benchmark.queries_path}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
