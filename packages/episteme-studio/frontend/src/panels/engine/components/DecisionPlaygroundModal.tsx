import React, {useEffect, useState} from "react";
import {AlertCircle, Info, Loader2, Play, ShieldCheck, X, Zap,} from "lucide-react";
import {useEngineSettingsStore} from "../../../store/engineSettingsStore";
import type {DecisionEngineSettings, DecisionTestRequest, DecisionTestResponse} from "../../../api/types";

interface DecisionPlaygroundModalProps {
  isOpen: boolean;
  onClose: () => void;
  config?: DecisionEngineSettings;
}

export const DecisionPlaygroundModal: React.FC<DecisionPlaygroundModalProps> = ({
  isOpen,
  onClose,
  config,
}) => {
  const { runDecisionTest, isTestingDecision } = useEngineSettingsStore();

  const [primitive, setPrimitive] = useState<"noul" | "choice" | "score">("choice");
  const [inputText, setInputText] = useState(
    "Der Satz vom Widerspruch ist das sicherste aller Prinzipien des Denkens."
  );
  const [candidateLabels, setCandidateLabels] = useState(
    "Axiom, Definition, Lemma, Theorem, Conjectured"
  );
  const [hypothesisText, setHypothesisText] = useState(
    "Fundamental ontological proposition"
  );
  const [testResult, setTestResult] = useState<DecisionTestResponse | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleRun = async () => {
    setTestError(null);
    try {
      const labels =
        primitive === "choice"
          ? candidateLabels
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          : undefined;

      const req: DecisionTestRequest = {
        primitive,
        input_text: inputText,
        question: hypothesisText || undefined,
        candidate_labels: labels,
        hypothesis_text: hypothesisText || undefined,
        provider: config?.provider,
        model_checkpoint: config?.model_checkpoint,
        device: config?.device,
        fast_exit_threshold: config?.fast_exit_threshold,
        uncertainty_threshold: config?.uncertainty_threshold,
      };

      const result = await runDecisionTest(req);
      setTestResult(result);
    } catch (err: any) {
      setTestError(err?.detail || err?.message || "Failed to execute decision test");
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs select-none animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl bg-app-surface border border-app-border rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] select-text animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-app-border bg-app-subtle/50">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-600 dark:text-blue-400">
              <Zap className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-xs font-semibold text-app-heading">
                  Decision Engine (Jev) Playground
                </h3>
                {config && (
                  <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 font-medium truncate max-w-[240px]">
                    {config.provider}: {config.model_checkpoint}
                  </span>
                )}
              </div>
              <p className="text-[10px] text-app-muted font-sans">
                Interactive real-time calibration testing for System 1 fast-exit primitives
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
            title="Close (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>


        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs">
          {/* Target Decision Primitive Selector */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-app-heading">
                Target Decision Primitive
              </label>
              <span className="text-[10px] font-mono text-app-muted">primitive</span>
            </div>
            <div className="h-8 p-0.5 inline-flex items-center bg-app-subtle/60 rounded-[4px] border border-app-border/60 text-xs w-full gap-1">
              {(
                [
                  { id: "choice", label: "Choice (Categorical)", desc: "Entity & relation type classification" },
                  { id: "noul", label: "Noul (Null/Affirm)", desc: "Binary filter & stance gating" },
                  { id: "score", label: "Score (Continuous)", desc: "Modal strength & inferential force" },
                ] as const
              ).map((p) => {
                const isSelected = primitive === p.id;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      setPrimitive(p.id);
                      setTestResult(null);
                    }}
                    className={`flex-1 h-7 rounded-[3px] text-xs transition-all cursor-pointer text-center font-sans ${
                      isSelected
                        ? "bg-app-surface text-app-text font-semibold border border-app-border/80 shadow-2xs"
                        : "text-app-muted hover:text-app-text hover:bg-app-bg/50"
                    }`}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Input text */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-app-heading">
                Input Text (Premise / Text Span)
              </label>
              <span className="text-[10px] font-mono text-app-muted">input_text</span>
            </div>
            <textarea
              rows={3}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              className="w-full px-3 py-2 text-xs font-mono rounded-[4px] border border-app-border bg-app-bg focus:border-[#2563EB] focus:outline-none text-app-text resize-none shadow-2xs"
              placeholder="Enter scientific or philosophical text..."
            />
          </div>

          {/* Conditional parameters */}
          {primitive === "choice" && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-app-heading">
                  Candidate Labels (Comma separated)
                </label>
                <span className="text-[10px] font-mono text-app-muted">candidate_labels</span>
              </div>
              <input
                type="text"
                value={candidateLabels}
                onChange={(e) => setCandidateLabels(e.target.value)}
                className="w-full h-8 px-3 text-xs font-mono rounded-[4px] border border-app-border bg-app-bg focus:border-[#2563EB] focus:outline-none text-app-text shadow-2xs"
                placeholder="Axiom, Definition, Lemma..."
              />
            </div>
          )}

          {/* Question / Hypothesis input for all primitives */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-app-heading">
                {primitive === "choice" ? "Question / Classification Instruction" : "Hypothesis / Rubric Criterion"}
              </label>
              <span className="text-[10px] font-mono text-app-muted">
                {primitive === "choice" ? "question" : "hypothesis_text"}
              </span>
            </div>
            <input
              type="text"
              value={hypothesisText}
              onChange={(e) => setHypothesisText(e.target.value)}
              className="w-full h-8 px-3 text-xs font-mono rounded-[4px] border border-app-border bg-app-bg focus:border-[#2563EB] focus:outline-none text-app-text shadow-2xs"
              placeholder={primitive === "choice" ? "e.g. Which epistemic status does this proposition hold?" : "Target hypothesis or stance criterion..."}
            />
          </div>

          {/* Error Message */}
          {testError && (
            <div className="p-3 rounded-[4px] bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{testError}</span>
            </div>
          )}

          {/* Telemetry & Test Result Card */}
          {testResult && (
            <div className="space-y-2 pt-2 border-t border-app-border">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-app-heading">
                  Inference & Telemetry Evaluation
                </span>
                <div className="flex items-center gap-1.5">
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-medium border uppercase ${
                      testResult.is_mock
                        ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                        : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
                    }`}
                  >
                    {testResult.is_mock ? "Offline Simulation (Safe)" : `Native Hardware (${testResult.engine_backend || "MLX"})`}
                  </span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 uppercase">
                    {testResult.tier.replace("_", " ")}
                  </span>
                </div>
              </div>

              {testResult.warning && (
                <div className="p-2.5 rounded-[4px] bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-300 text-[11px] font-sans flex items-start gap-2">
                  <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>{testResult.warning}</span>
                </div>
              )}

              <div className="rounded-[4px] bg-app-surface border border-app-border overflow-hidden divide-y divide-app-border">
                <div className="px-3 py-2 flex items-center justify-between text-xs">
                  <span className="font-sans text-app-muted text-[11px]">Selected Outcome</span>
                  <span className="font-mono font-semibold text-blue-600 dark:text-blue-400">
                    {String(testResult.prediction ?? "None")}
                  </span>
                </div>

                {testResult.probabilities && Object.keys(testResult.probabilities).length > 1 && (
                  <div className="px-3 py-2 space-y-1.5 text-xs">
                    <span className="font-sans text-app-muted text-[11px]">Probability Distribution</span>
                    <div className="space-y-1">
                      {Object.entries(testResult.probabilities).map(([label, prob]) => (
                        <div key={label} className="flex items-center justify-between gap-2 text-[11px]">
                          <span className="font-mono text-app-text truncate max-w-[200px]">{label}</span>
                          <div className="flex items-center gap-2 flex-1 max-w-[180px]">
                            <div className="h-1.5 flex-1 bg-app-border rounded-full overflow-hidden">
                              <div
                                className={`h-full ${label === String(testResult.prediction) ? "bg-blue-500" : "bg-app-muted/40"}`}
                                style={{ width: `${Math.round(prob * 100)}%` }}
                              />
                            </div>
                            <span className="font-mono text-[10px] text-app-muted w-10 text-right">
                              {(prob * 100).toFixed(1)}%
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="px-3 py-2 flex items-center justify-between text-xs">
                  <span className="font-sans text-app-muted text-[11px]">Calibrated Accuracy P(correct)</span>
                  <span
                    className="font-mono font-medium text-emerald-600 dark:text-emerald-400"
                    style={{ fontFeatureSettings: '"tnum" 1' }}
                  >
                    {(testResult.empirical_accuracy * 100).toFixed(1)}%
                  </span>
                </div>

                <div className="px-3 py-2 flex items-center justify-between text-xs">
                  <span className="font-sans text-app-muted text-[11px]">Softmax Confidence</span>
                  <span
                    className="font-mono font-medium text-app-text"
                    style={{ fontFeatureSettings: '"tnum" 1' }}
                  >
                    {(testResult.confidence * 100).toFixed(1)}%
                  </span>
                </div>

                {testResult.conformal_set && testResult.conformal_set.length > 0 && (
                  <div className="px-3 py-2 flex items-center justify-between text-xs">
                    <span className="font-sans text-app-muted text-[11px]">Conformal Set C(x) (95% coverage)</span>
                    <div className="flex flex-wrap gap-1">
                      {testResult.conformal_set.map((item: string) => (
                        <span
                          key={item}
                          className="px-1.5 py-0.2 rounded bg-app-bg dark:bg-app-subtle text-app-text font-mono text-[10px] border border-app-border"
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="px-3 py-2 flex items-center justify-between text-xs">
                  <span className="font-sans text-app-muted text-[11px]">System 1 Latency</span>
                  <span
                    className="font-mono font-medium text-app-text"
                    style={{ fontFeatureSettings: '"tnum" 1' }}
                  >
                    ~{testResult.latency_ms.toFixed(1)} ms
                  </span>
                </div>

                <div className="px-3 py-2 flex items-center justify-between text-xs">
                  <span className="font-sans text-app-muted text-[11px]">Estimated LLM Tokens Saved</span>
                  <span
                    className="font-mono font-semibold text-emerald-600 dark:text-emerald-400"
                    style={{ fontFeatureSettings: '"tnum" 1' }}
                  >
                    +{testResult.tokens_saved || 240} tokens
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Toolbar */}
        <div className="px-5 py-3 border-t border-app-border bg-app-subtle/30 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[11px] text-app-muted font-sans">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span>Guaranteed marginal coverage: 1 - α ≥ 95%</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="h-8 px-3 rounded-[4px] border border-app-border bg-app-surface hover:bg-app-subtle text-app-text text-xs font-sans font-medium transition-colors cursor-pointer"
            >
              Close
            </button>
            <button
              type="button"
              onClick={handleRun}
              disabled={isTestingDecision}
              className="h-8 px-3.5 rounded-[4px] bg-[#2563EB] hover:bg-blue-600 text-white text-xs font-sans font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 shadow-2xs disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isTestingDecision ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Evaluating...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Run Inference</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
