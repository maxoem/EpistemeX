import React from "react";
import { CascadingBourbakiGrid } from "./CascadingBourbakiGrid";
import { PosetDagViewer } from "./PosetDagViewer";
import { PolarityConflictMatrix } from "./PolarityConflictMatrix";

export const EpistemicTheoryNetView: React.FC = () => {
  return (
    <div className="flex-1 flex h-full w-full overflow-hidden bg-app-bg text-app-text select-none font-sans">
      {/* Left Pane (60% Width): Cascading Bourbaki Model Tree Grid */}
      <div className="w-[60%] border-r border-app-border flex flex-col h-full overflow-hidden">
        <CascadingBourbakiGrid />
      </div>

      {/* Right Pane (40% Width): Poset DAG Hierarchy & Polarity Conflict Matrix */}
      <div className="w-[40%] flex flex-col h-full overflow-hidden divide-y divide-app-border">
        {/* Upper Half: Poset DAG Hierarchy & Cyclical Path Isolation */}
        <div className="h-[52%] flex flex-col overflow-hidden">
          <PosetDagViewer />
        </div>

        {/* Lower Half: Polarity Conflict Concordance & Critical Inversions */}
        <div className="h-[48%] flex flex-col overflow-hidden">
          <PolarityConflictMatrix />
        </div>
      </div>
    </div>
  );
};
