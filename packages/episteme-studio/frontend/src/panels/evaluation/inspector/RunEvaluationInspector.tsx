import React from "react";
import {
  Activity,
  BookOpen,
  Filter,
  Layers,
  Network,
  Sliders,
  Sparkles,
} from "lucide-react";
import { useEvaluationStore } from "../../../store/evaluationStore";
import { TopologicalCanvasView } from "./canvas/TopologicalCanvasView";
import { EpistemicTheoryNetView } from "./epistemics/EpistemicTheoryNetView";
import { AdjudicationDeskView } from "./adjudication/AdjudicationDeskView";
import { CalibrationLabView } from "./calibration/CalibrationLabView";
import { DocumentGroundingView } from "./grounding/DocumentGroundingView";
import { RetrievalStressView } from "./retrieval/RetrievalStressView";

export interface RunEvaluationInspectorProps {
  onOpenConfigEditor?: () => void;
}

export const RunEvaluationInspector: React.FC<RunEvaluationInspectorProps> = ({
  onOpenConfigEditor,
}) => {
  const { activeReport, activeSubTab } = useEvaluationStore();

  if (!activeReport) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center text-app-muted select-none">
        <Activity className="w-10 h-10 text-app-muted/40 mb-3" />
        <h3 className="text-sm font-semibold text-app-heading mb-1">
          No Evaluation Run Selected
        </h3>
        <p className="text-xs max-w-sm text-app-muted leading-relaxed">
          Select an evaluation report from the left panel to inspect its metrics, topological error
          canvas, and epistemic invariants.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-app-bg select-none">
      {/* Sub-View Content Body */}
      <div className="flex-1 overflow-hidden relative">
        {activeSubTab === "canvas" ? (
          /* Sub-View 3.1: Topological Alignment Canvas (Phase 2) */
          <TopologicalCanvasView />
        ) : activeSubTab === "epistemics" ? (
          /* Sub-View 3.2: Formal Epistemic Invariants & Dialectical Verification (Phase 3) */
          <EpistemicTheoryNetView />
        ) : activeSubTab === "adjudication" ? (
          /* Sub-View 3.3: HITL Borderline Adjudication Desk (Phase 4) */
          <AdjudicationDeskView />
        ) : activeSubTab === "calibration" ? (
          /* Sub-View 3.4: Confidence Calibration & Reliability Lab (Phase 4) */
          <CalibrationLabView onOpenConfigEditor={onOpenConfigEditor} />
        ) : activeSubTab === "grounding" ? (
          /* Sub-View 3.5: Multimodal Document Grounding & Reader (Phase 5) */
          <DocumentGroundingView />
        ) : activeSubTab === "retrieval" ? (
          /* Sub-View 3.6: Downstream Competency Retrieval & Noise Diagnostics (Phase 5) */
          <RetrievalStressView />
        ) : null}
      </div>
    </div>
  );
};
