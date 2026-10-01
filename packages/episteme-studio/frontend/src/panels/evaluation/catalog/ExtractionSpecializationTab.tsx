import React from "react";
import type { BenchmarkDescriptor } from "../../../api/types";

interface ExtractionSpecializationTabProps {
  benchmark: BenchmarkDescriptor;
}

export const ExtractionSpecializationTab: React.FC<ExtractionSpecializationTabProps> = ({
  benchmark,
}) => {
  const details = benchmark.extraction_details;

  const entityTypes = details?.entity_types || [
    "Task",
    "Method",
    "Metric",
    "Material",
    "OtherScientificTerm",
  ];
  const relationTypes = details?.relation_types || [
    "USED-FOR",
    "FEATURE-OF",
    "EVALUATE-FOR",
    "COMPARE",
    "CONJUNCTION",
  ];

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Centered Monograph Container */}
      <div className="max-w-4xl mx-auto w-full py-6 px-4 space-y-7 font-sans">
        <div className="space-y-2">
          <h2 className="font-display font-medium text-sm text-app-heading tracking-tight">
            Scientific Information Extraction Taxonomy
          </h2>
          <p className="text-xs text-app-text/90 leading-relaxed font-sans">
            Scientific information extraction evaluation assessing named entity recognition (NER), relationship extraction (RE), and boundary alignment over scientific literature.
          </p>
        </div>

        {/* Metadata Table replacing boxes */}
        <div className="space-y-2">
          <h2 className="font-display font-medium text-sm text-app-heading tracking-tight">
            Dataset Annotation Specifications
          </h2>
          <div className="border border-app-border rounded-md overflow-hidden bg-app-surface/30 divide-y divide-app-border text-xs font-sans">
            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Corpus Scale</span>
              <span className="text-app-heading font-medium tabular-nums">
                {details?.document_count || 500} abstracts / documents
              </span>
            </div>

            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Span Volume</span>
              <span className="text-app-text tabular-nums">
                {details?.sentence_count || 3200} annotated sentences
              </span>
            </div>

            <div className="flex items-center px-4 py-2.5">
              <span className="w-52 text-app-muted font-medium shrink-0">Evaluation Protocols</span>
              <span className="text-app-text">
                Graph Matching BERTScore (GM-GBS), Soft F1, Optimal Edit Paths (OEP)
              </span>
            </div>
          </div>
        </div>

        {/* Taxonomy Categories */}
        <div className="grid grid-cols-2 gap-4 text-xs font-sans">
          <div className="p-4 rounded-md border border-app-border bg-app-surface/30 space-y-2.5">
            <h3 className="font-display font-medium text-xs text-app-heading">Entity Types</h3>
            <div className="flex flex-wrap gap-1.5">
              {entityTypes.map((ent) => (
                <span
                  key={ent}
                  className="px-2 py-0.5 rounded text-[11px] font-sans bg-app-subtle border border-app-border text-app-text"
                >
                  {ent}
                </span>
              ))}
            </div>
          </div>

          <div className="p-4 rounded-md border border-app-border bg-app-surface/30 space-y-2.5">
            <h3 className="font-display font-medium text-xs text-app-heading">Relational Predicates</h3>
            <div className="flex flex-wrap gap-1.5">
              {relationTypes.map((rel) => (
                <span
                  key={rel}
                  className="px-2 py-0.5 rounded text-[11px] font-sans bg-app-subtle border border-app-border text-app-text"
                >
                  {rel}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
