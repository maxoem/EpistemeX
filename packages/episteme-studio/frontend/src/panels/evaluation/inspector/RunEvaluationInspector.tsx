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
import { EvaluationHeader } from "../components/EvaluationHeader";
import { TopologicalCanvasView } from "./canvas/TopologicalCanvasView";

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
      {/* 2.1 Run Evaluation Inspector Header (Row 1: 48px Header + Row 2: 40px Zero-Box Segmented Sub-Nav) */}
      <EvaluationHeader onOpenConfigEditor={onOpenConfigEditor} />

      {/* Sub-View Content Body */}
      <div className="flex-1 overflow-hidden relative">
        {activeSubTab === "canvas" ? (
          /* Sub-View 3.1: Topological Alignment Canvas (Phase 2) */
          <TopologicalCanvasView />
        ) : (
          /* Placeholder / Preparatory views for Subsequent Phases */
          <div className="flex flex-col items-center justify-center h-full p-8 text-center text-app-muted select-none">
            <div className="p-3 rounded-full bg-blue-500/10 text-blue-500 mb-3">
              {activeSubTab === "epistemics" && <Layers className="w-6 h-6" />}
              {activeSubTab === "adjudication" && <Sliders className="w-6 h-6" />}
              {activeSubTab === "calibration" && <Sparkles className="w-6 h-6" />}
              {activeSubTab === "grounding" && <BookOpen className="w-6 h-6" />}
              {activeSubTab === "retrieval" && <Filter className="w-6 h-6" />}
            </div>

            <h3 className="text-sm font-semibold text-app-heading mb-1 capitalize">
              {activeSubTab === "epistemics" && "Sub-View 3.2: Epistemic & TheoryNet Inspector"}
              {activeSubTab === "adjudication" && "Sub-View 3.3: HITL Borderline Adjudication Desk"}
              {activeSubTab === "calibration" && "Sub-View 3.4: Confidence Calibration & Reliability Lab"}
              {activeSubTab === "grounding" && "Sub-View 3.5: Multimodal Document Grounding"}
              {activeSubTab === "retrieval" && "Sub-View 3.6: Competency Query & Noise Diagnostics"}
            </h3>

            <p className="text-xs max-w-md text-app-muted leading-relaxed mb-4">
              Active Evaluation: <span className="font-mono text-app-text">{activeReport.evaluation_id}</span>
              <br />
              {activeSubTab === "epistemics" &&
                "Bourbaki structuralist model tree and Poset cyclical back-edge isolation ready for Phase 3."}
              {activeSubTab === "adjudication" &&
                "Keyboard-first relation triage desk with staged batch commits ready for Phase 4."}
              {activeSubTab === "calibration" &&
                "10-bin Expected Calibration Error diagrams and threshold optimization ready for Phase 4."}
              {activeSubTab === "grounding" &&
                "Two-tier continuous PDF coordinate scaling and KaTeX verification ready for Phase 5."}
              {activeSubTab === "retrieval" &&
                "Competency question ranking matrix and RDF noise degradation curves ready for Phase 5."}
            </p>

            <button
              onClick={() => useEvaluationStore.getState().setActiveSubTab("canvas")}
              className="px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors shadow-2xs flex items-center gap-1.5"
            >
              <Network className="w-3.5 h-3.5" />
              <span>Switch to Topological Canvas (Sub-View 3.1)</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
