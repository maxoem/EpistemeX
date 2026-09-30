/**
 * @file RetrievalStressView.tsx
 * @description Sub-View 3.6: Downstream Competency Retrieval & Robustness Stress Testing.
 *
 * Integrates per-query multi-hop ranking diagnostics (CompetencyRankingTable) and
 * adversarial noise degradation curves (NoiseRobustnessPlot) in a cohesive container.
 *
 * Reference: ISSUE-031, ISSUE-032
 */

import React, { useState } from "react";
import { Filter, Activity, Columns, Maximize2 } from "lucide-react";
import { CompetencyRankingTable } from "./CompetencyRankingTable";
import { NoiseRobustnessPlot } from "./NoiseRobustnessPlot";

export interface RetrievalStressViewProps {
  onOpenCanvas?: () => void;
}

export const RetrievalStressView: React.FC<RetrievalStressViewProps> = ({ onOpenCanvas }) => {
  const [layoutMode, setLayoutMode] = useState<"split" | "competency" | "robustness">("split");

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-app-bg select-none relative">
      {/* Context Mode Toggle Bar (32px Fixed) */}
      <div className="h-8 px-4 border-b border-app-border/60 bg-app-surface flex items-center justify-between shrink-0 text-xs">
        <div className="flex items-center gap-2 text-app-muted text-[11px]">
          <span>Sub-View 3.6 Layout:</span>
          <span className="font-semibold text-app-text capitalize">
            {layoutMode === "split"
              ? "Dual Split View (Competency + Robustness)"
              : layoutMode === "competency"
              ? "Competency Retrieval Matrix Focus"
              : "Adversarial Noise Robustness Focus"}
          </span>
        </div>

        {/* Segmented Layout Mode Pills */}
        <div className="flex items-center gap-1 bg-app-bg dark:bg-[#111827] p-0.5 rounded border border-app-border/60 text-[10px]">
          <button
            onClick={() => setLayoutMode("split")}
            className={`px-2 py-0.5 rounded font-medium transition-colors cursor-pointer ${
              layoutMode === "split"
                ? "bg-app-surface text-app-heading font-semibold border border-app-border/80"
                : "text-app-muted hover:text-app-text"
            }`}
          >
            Split (50 / 50)
          </button>
          <button
            onClick={() => setLayoutMode("competency")}
            className={`px-2 py-0.5 rounded font-medium transition-colors cursor-pointer ${
              layoutMode === "competency"
                ? "bg-app-surface text-app-heading font-semibold border border-app-border/80"
                : "text-app-muted hover:text-app-text"
            }`}
          >
            Competency Only
          </button>
          <button
            onClick={() => setLayoutMode("robustness")}
            className={`px-2 py-0.5 rounded font-medium transition-colors cursor-pointer ${
              layoutMode === "robustness"
                ? "bg-app-surface text-app-heading font-semibold border border-app-border/80"
                : "text-app-muted hover:text-app-text"
            }`}
          >
            Robustness Only
          </button>
        </div>
      </div>

      {/* Main Split Panels */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top / Primary Section: Competency Ranking Table */}
        {(layoutMode === "split" || layoutMode === "competency") && (
          <div
            className={`overflow-hidden flex flex-col ${
              layoutMode === "split" ? "h-1/2 min-h-[280px]" : "h-full"
            }`}
          >
            <CompetencyRankingTable onOpenCanvas={onOpenCanvas} />
          </div>
        )}

        {/* Bottom / Secondary Section: Adversarial Noise Robustness Plot */}
        {(layoutMode === "split" || layoutMode === "robustness") && (
          <div
            className={`overflow-hidden flex flex-col ${
              layoutMode === "split" ? "h-1/2 min-h-[280px]" : "h-full"
            }`}
          >
            <NoiseRobustnessPlot />
          </div>
        )}
      </div>
    </div>
  );
};
