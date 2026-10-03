import React, { useState } from "react";
import { BorderlineDecisionItem } from "../../../api/types";
import {
  CheckCircle2,
  AlertTriangle,
  Zap,
  Cpu,
  ShieldCheck,
  Send,
  Check,
  X,
  FileText,
  HelpCircle,
  Sparkles,
} from "lucide-react";

export interface AdjudicationCardProps {
  item: BorderlineDecisionItem;
  runId: string;
  onAdjudicate: (decisionId: string, value: string | number, notes?: string) => Promise<void>;
}

export const AdjudicationCard: React.FC<AdjudicationCardProps> = ({
  item,
  runId,
  onAdjudicate,
}) => {
  const [selectedOption, setSelectedOption] = useState<string>(
    item.adjudicated_value ? String(item.adjudicated_value) : String(item.prediction)
  );
  const [notes, setNotes] = useState<string>(item.adjudication_notes || "");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [status, setStatus] = useState<string | null>(item.adjudicated_value ? "adjudicated" : null);

  const options = item.context.candidate_labels && item.context.candidate_labels.length > 0
    ? item.context.candidate_labels
    : [String(item.prediction), "ALTERNATIVE", "OUT_OF_ONTOLOGY"];

  const handleAcceptS1 = async () => {
    setIsSubmitting(true);
    try {
      await onAdjudicate(item.decision_id, item.prediction, notes || "Accepted System 1 fast-exit");
      setStatus("accepted");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOverride = async () => {
    setIsSubmitting(true);
    try {
      await onAdjudicate(item.decision_id, selectedOption, notes || "Human expert override");
      setStatus("corrected");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMarkO3 = async () => {
    setIsSubmitting(true);
    try {
      await onAdjudicate(item.decision_id, "OUT_OF_ONTOLOGY", notes || "Marked out-of-ontology");
      setStatus("out_of_ontology");
    } finally {
      setIsSubmitting(false);
    }
  };

  const isDiscrepant = item.tier === "stochastic_audit" || item.conformal_set.length > 1;

  return (
    <div
      className={`p-4 rounded-lg border transition-all ${
        status
          ? "border-emerald-500/30 bg-emerald-950/5 opacity-80"
          : isDiscrepant
          ? "border-amber-500/40 bg-app-surface/90 shadow-sm"
          : "border-app-border bg-app-surface"
      }`}
    >
      {/* Card Header */}
      <div className="flex items-center justify-between pb-2 border-b border-app-border text-xs">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-app-muted">{item.decision_id}</span>
          <span className="px-1.5 py-0.5 rounded bg-app-bg border border-app-border text-[10px] font-sans font-medium">
            {item.phase}
          </span>
          <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 text-[10px] uppercase font-semibold font-mono">
            {item.primitive}
          </span>
          {isDiscrepant && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[10px] font-medium bg-amber-500/10 text-amber-500 border border-amber-500/20">
              <AlertTriangle className="w-2.5 h-2.5" /> High Uncertainty
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 text-[10px] font-mono">
          <span className="text-app-muted">Acc:</span>
          <span className="text-emerald-500 font-semibold">{(item.empirical_accuracy * 100).toFixed(1)}%</span>
          <span className="text-app-muted">•</span>
          <span className="text-app-muted">Conf:</span>
          <span className="text-blue-400">{(item.confidence * 100).toFixed(1)}%</span>
        </div>
      </div>

      {/* Input / Snippet Context */}
      <div className="my-3 space-y-1.5">
        <div className="flex items-center gap-1.5 text-xs text-app-muted">
          <FileText className="w-3.5 h-3.5" />
          <span className="font-sans font-medium">Evaluation Context:</span>
        </div>
        <div className="p-2.5 rounded bg-app-bg border border-app-border text-xs font-mono text-app-text leading-relaxed whitespace-pre-wrap">
          {item.context.input_text || item.context.hypothesis || "No input snippet available"}
        </div>
      </div>

      {/* Comparison: System 1 Choice vs Conformal Set */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 my-3 text-xs">
        <div className="p-2.5 rounded bg-app-bg border border-app-border space-y-1">
          <span className="text-[10px] uppercase font-semibold text-app-muted flex items-center gap-1">
            <Zap className="w-3 h-3 text-emerald-500" />
            System 1 Choice
          </span>
          <div className="font-mono text-sm font-bold text-emerald-500">
            {String(item.prediction)}
          </div>
          <div className="text-[10px] font-mono text-app-muted">
            Margin: Δ = {(item.margin || 0.42).toFixed(3)}
          </div>
        </div>

        <div className="p-2.5 rounded bg-app-bg border border-app-border space-y-1">
          <span className="text-[10px] uppercase font-semibold text-app-muted flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-blue-400" />
            Conformal Set (1-α = 0.95)
          </span>
          <div className="flex items-center gap-1.5 flex-wrap">
            {item.conformal_set.map((val) => (
              <span
                key={val}
                className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-blue-500/15 text-blue-400 border border-blue-500/25"
              >
                {val}
              </span>
            ))}
          </div>
          <div className="text-[10px] font-mono text-app-muted">
            |C(x)| = {item.conformal_set.length} {item.conformal_set.length > 1 ? "(Ambiguous)" : "(Calibrated)"}
          </div>
        </div>
      </div>

      {/* Interactive Option Picker */}
      <div className="my-3 space-y-1.5">
        <span className="text-xs font-medium text-app-heading font-sans">
          Select Ground Truth or Override:
        </span>
        <div className="flex items-center gap-2 flex-wrap">
          {options.map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={() => setSelectedOption(opt)}
              className={`px-3 py-1.5 rounded-md text-xs font-mono font-medium border transition-colors cursor-pointer ${
                selectedOption === opt
                  ? "bg-blue-600 text-white border-blue-500 shadow-xs"
                  : "bg-app-bg text-app-text border-app-border hover:bg-app-subtle"
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>

      {/* Curator Notes */}
      <div className="my-3">
        <input
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Curator justification notes (optional)..."
          className="w-full px-3 py-1.5 rounded bg-app-bg border border-app-border text-xs text-app-text placeholder:text-app-muted focus:outline-hidden"
        />
      </div>

      {/* Action Buttons */}
      <div className="pt-2 border-t border-app-border flex items-center justify-between gap-2 flex-wrap text-xs">
        <div className="flex items-center gap-2">
          {status && (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-500 font-sans">
              <CheckCircle2 className="w-3.5 h-3.5" /> Adjudicated ({status})
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={isSubmitting}
            onClick={handleMarkO3}
            className="px-2.5 py-1.5 rounded bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-heading border border-app-border text-[11px] font-medium transition-colors cursor-pointer disabled:opacity-50"
            title="Mark assertion as out of ontology schema"
          >
            Mark Out-of-Ontology
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={handleAcceptS1}
            className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-medium transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1"
          >
            <Check className="w-3 h-3" />
            <span>Accept S1 ({String(item.prediction)})</span>
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={handleOverride}
            className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-medium transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1"
          >
            <Send className="w-3 h-3" />
            <span>Override Choice</span>
          </button>
        </div>
      </div>
    </div>
  );
};
