import React, { useEffect, useState } from "react";
import {
  Play,
  RotateCcw,
  Info,
  ShieldCheck,
} from "lucide-react";
import { useEngineSettingsStore } from "../../../store/engineSettingsStore";
import { DecisionPlaygroundModal } from "./DecisionPlaygroundModal";
import type { DecisionEngineSettings, ModalResolverSettings } from "../../../api/types";

interface DecisionEngineConfigPanelProps {
  draftSettings?: DecisionEngineSettings;
  onChange?: (patch: Partial<DecisionEngineSettings>) => void;
  // Execution page staging & override support
  isExecutionMode?: boolean;
  baselineSettings?: DecisionEngineSettings;
  onResetOverrides?: () => void;
  hasOverrides?: boolean;
}

export const DecisionEngineConfigPanel: React.FC<DecisionEngineConfigPanelProps> = ({
  draftSettings: externalDraft,
  onChange: externalOnChange,
  isExecutionMode = false,
  baselineSettings,
  onResetOverrides,
  hasOverrides = false,
}) => {
  const {
    settings,
    decisionStatus,
    fetchDecisionStatus,
    updateDecisionEngineSettings,
    updateEngineSettings,
  } = useEngineSettingsStore();

  const [isPlaygroundOpen, setIsPlaygroundOpen] = useState(false);

  useEffect(() => {
    fetchDecisionStatus();
  }, [fetchDecisionStatus]);

  const isDemoOrReadOnly = Boolean(
    decisionStatus?.model_metadata?.demo_mode ||
    decisionStatus?.model_metadata?.read_only
  );

  const currentConfig: DecisionEngineSettings =
    externalDraft ||
    settings?.decision_engine || {
      provider: "laya",
      model_checkpoint: "aac6fef/laya-mlx",
      device: "auto",
      fast_exit_threshold: 0.92,
      uncertainty_threshold: 0.55,
      stochastic_audit_rate: 0.05,
      phase_gates: {
        phase2_entity_discovery: true,
        phase3_global_relations: true,
        phase4_argument_mining: true,
        phase4_entity_maturation: true,
        phase5_fusion: true,
        phase6_theorynet: true,
      },
    };

  const updateField = <K extends keyof DecisionEngineSettings>(
    key: K,
    val: DecisionEngineSettings[K]
  ) => {
    if (externalOnChange) {
      externalOnChange({ [key]: val });
    } else {
      updateDecisionEngineSettings({ [key]: val });
    }
  };

  const updateGate = (phaseKey: keyof DecisionEngineSettings["phase_gates"], val: boolean) => {
    const updatedGates = {
      ...currentConfig.phase_gates,
      [phaseKey]: val,
    };
    updateField("phase_gates", updatedGates);
  };

  const isFieldOverridden = (key: keyof DecisionEngineSettings) => {
    if (!isExecutionMode || !baselineSettings) return false;
    if (key === "phase_gates") {
      return (
        JSON.stringify(currentConfig.phase_gates) !==
        JSON.stringify(baselineSettings.phase_gates)
      );
    }
    return currentConfig[key] !== baselineSettings[key];
  };

  const allGatesActive = Object.values(currentConfig.phase_gates || {}).every(Boolean);

  return (
    <div className="space-y-6">
      {/* ── Title & Description ── */}
      <div className="pb-5 border-b border-app-border/80">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <h3 className="type-h1 text-app-heading">
              Decision Engine (Jev)
            </h3>
            <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20 font-semibold">
              {isExecutionMode ? "Execution Overrides" : "System 1/2 Dual Process"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="type-caption text-app-muted font-mono text-[11px]">
              decision_engine
            </span>
            <button
              type="button"
              onClick={() => setIsPlaygroundOpen(true)}
              className="h-7 px-2.5 rounded-md border border-app-border bg-app-surface hover:bg-app-subtle text-app-heading text-xs font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 shadow-xs"
            >
              <Play className="w-3 h-3 text-blue-600 dark:text-blue-400 fill-current" />
              <span>Launch Playground</span>
            </button>
          </div>
        </div>
        <p className="type-body text-app-muted mt-1.5 max-w-2xl">
          Dual-process System 1/2 calibration, local accelerated inference, and confidence-gated fast-exits.
          High-confidence decisions fast-exit immediately without invoking generative LLM reasoning.
        </p>
      </div>

      {/* ── Demo Sandbox Notification Banner ── */}
      {isDemoOrReadOnly && (
        <div className="p-3.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <div className="space-y-0.5">
              <span className="text-app-heading font-medium">
                Demo Sandbox Active
              </span>
              <p className="text-[11px] text-app-muted">
                Engine hyperparameter persistence is locked in read-only mode. The Decision Playground executes safely via the high-speed deterministic simulation engine.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsPlaygroundOpen(true)}
            className="h-7 px-2.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-xs font-semibold hover:bg-emerald-500/20 transition-colors shrink-0 inline-flex items-center gap-1.5 cursor-pointer shadow-xs"
          >
            <Play className="w-3 h-3 fill-current" />
            <span>Try Playground</span>
          </button>
        </div>
      )}

      {/* ── Optional Execution Mode Overrides Header ── */}
      {isExecutionMode && (
        <div className="p-3.5 rounded-lg border border-blue-500/20 bg-blue-500/5 flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
            <span className="text-app-heading font-medium">
              Pipeline Run Overrides: Hyperparameters configured here will override engine defaults for this execution.
            </span>
          </div>
          {hasOverrides && onResetOverrides && (
            <button
              type="button"
              onClick={onResetOverrides}
              className="h-7 px-2.5 rounded-md border border-app-border bg-app-surface hover:bg-app-subtle text-app-heading text-xs font-medium transition-colors cursor-pointer inline-flex items-center gap-1 shadow-xs shrink-0"
            >
              <RotateCcw className="w-3 h-3 text-app-muted" />
              <span>Reset to Engine Defaults</span>
            </button>
          )}
        </div>
      )}

      {/* ── Hardware & Runtime Metadata ── */}
      <div className="overflow-x-auto text-xs">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-app-border/80 text-[10px] font-mono uppercase text-app-muted tracking-wider">
              <th className="py-2 pr-4 font-medium">Subsystem</th>
              <th className="py-2 pl-4 font-medium">Target / Checkpoint</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-app-border/40 text-[11px]">
            {/* 1. Compute Accelerator */}
            <tr className="hover:bg-app-subtle/20 transition-colors">
              <td className="py-2 pr-4 font-sans font-medium text-app-heading">
                Compute Accelerator
              </td>
              <td className="py-2 pl-4 font-mono text-app-heading">
                {decisionStatus?.device || currentConfig.device}
              </td>
            </tr>

            {/* 2. Weight Checkpoint */}
            <tr className="hover:bg-app-subtle/20 transition-colors">
              <td className="py-2 pr-4 font-sans font-medium text-app-heading">
                Weight Checkpoint
              </td>
              <td className="py-2 pl-4 font-mono text-app-heading truncate" title={currentConfig.model_checkpoint}>
                {currentConfig.model_checkpoint}
              </td>
            </tr>

            {/* 3. System 1 Performance */}
            <tr className="hover:bg-app-subtle/20 transition-colors">
              <td className="py-2 pr-4 font-sans font-medium text-app-heading">
                System 1 Performance
              </td>
              <td className="py-2 pl-4 font-mono text-app-heading" style={{ fontFeatureSettings: '"tnum" 1' }}>
                {(decisionStatus?.latency_benchmark_ms ?? decisionStatus?.benchmark_latency_p50_ms) !== null &&
                (decisionStatus?.latency_benchmark_ms ?? decisionStatus?.benchmark_latency_p50_ms) !== undefined
                  ? `~${(decisionStatus?.latency_benchmark_ms ?? decisionStatus?.benchmark_latency_p50_ms)!.toFixed(1)} ms (P50)`
                  : "< 25.0 ms (P50)"}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* ── 1. Inference Architecture & Checkpoint ── */}
      <div className="space-y-4">
        <h4 className="type-h2 text-app-heading">
          Inference Architecture & Checkpoint
        </h4>

        {/* Provider Architecture */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-app-heading">
                Inference Provider Architecture
              </label>
              {isFieldOverridden("provider") && (
                <span className="font-mono text-[9px] text-amber-600 dark:text-amber-400 bg-amber-500/10 px-1 py-0.2 rounded border border-amber-500/20">
                  Overridden
                </span>
              )}
            </div>
            <span className="font-mono text-[10px] text-app-muted/80">decision_engine.provider</span>
          </div>
          <select
            value={currentConfig.provider}
            onChange={(e) => updateField("provider", e.target.value as any)}
            className="w-full h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs transition-all focus:outline-none focus:border-blue-500/80 cursor-pointer"
          >
            <option value="laya">TypeSafe Jev / Laya (Domain-Calibrated Adapter)</option>
            <option value="auto">Auto-Detect (Apple Silicon MLX or Transformers Fallback)</option>
            <option value="mlx">Apple MLX Native (Apple Silicon Unified Memory)</option>
            <option value="transformers">PyTorch / HuggingFace Transformers (CUDA / CPU)</option>
            <option value="onnx">ONNX Runtime (Cross-platform optimized)</option>
            <option value="stub">Simulation Stub (Deterministic Offline Testing)</option>
            <option value="none">Disabled / Bypass to LLM Only</option>
          </select>
          <span className="text-[11px] text-app-muted block">
            Select local accelerated inference engine or simulation backend for System 1 fast-exits.
          </span>
        </div>

        {/* Model Weight Checkpoint */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-app-heading">
                Model Weight Checkpoint
              </label>
              {isFieldOverridden("model_checkpoint") && (
                <span className="font-mono text-[9px] text-amber-600 dark:text-amber-400 bg-amber-500/10 px-1 py-0.2 rounded border border-amber-500/20">
                  Overridden
                </span>
              )}
            </div>
            <span className="font-mono text-[10px] text-app-muted/80">decision_engine.model_checkpoint</span>
          </div>
          <input
            type="text"
            value={currentConfig.model_checkpoint}
            onChange={(e) => updateField("model_checkpoint", e.target.value)}
            placeholder="e.g. aac6fef/laya-mlx or convaiinnovations/laya"
            className="w-full h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80"
          />
          <span className="text-[11px] text-app-muted block">
            Hugging Face model repository ID or local weight snapshot directory.
          </span>
        </div>

        {/* Compute Accelerator Device */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-app-heading">
                Compute Accelerator Device
              </label>
              {isFieldOverridden("device") && (
                <span className="font-mono text-[9px] text-amber-600 dark:text-amber-400 bg-amber-500/10 px-1 py-0.2 rounded border border-amber-500/20">
                  Overridden
                </span>
              )}
            </div>
            <span className="font-mono text-[10px] text-app-muted/80">decision_engine.device</span>
          </div>
          <select
            value={currentConfig.device}
            onChange={(e) => updateField("device", e.target.value as any)}
            className="w-full h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs transition-all focus:outline-none focus:border-blue-500/80 cursor-pointer"
          >
            <option value="auto">Auto-detect optimal accelerator</option>
            <option value="mps">Apple Metal (MPS / MLX)</option>
            <option value="cuda">NVIDIA CUDA GPU</option>
            <option value="cpu">Host CPU Fallback</option>
          </select>
          <span className="text-[11px] text-app-muted block">
            Target hardware compute device (Metal GPU on macOS, CUDA on Linux, or CPU).
          </span>
        </div>
      </div>

      {/* ── 2. Dual-Process Confidence & Calibration ── */}
      <div className="space-y-4">
        <h4 className="type-h2 text-app-heading">
          Dual-Process Confidence & Calibration
        </h4>

        {/* Fast-Exit Threshold */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-app-heading">
                Fast-Exit Confidence Threshold (τ_exit)
              </label>
              {isFieldOverridden("fast_exit_threshold") && (
                <span className="font-mono text-[9px] text-amber-600 dark:text-amber-400 bg-amber-500/10 px-1 py-0.2 rounded border border-amber-500/20">
                  Overridden
                </span>
              )}
            </div>
            <span className="font-mono text-[10px] text-app-muted/80">decision_engine.fast_exit_threshold</span>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min="0.70"
              max="0.99"
              step="0.01"
              value={Number(currentConfig.fast_exit_threshold ?? 0.92)}
              onChange={(e) =>
                updateField("fast_exit_threshold", parseFloat(e.target.value))
              }
              className="flex-1 precision-slider accent-blue-600 cursor-pointer"
            />
            <input
              type="number"
              step="0.01"
              min="0.70"
              max="0.99"
              value={Number(currentConfig.fast_exit_threshold ?? 0.92).toFixed(2)}
              onChange={(e) =>
                updateField("fast_exit_threshold", parseFloat(e.target.value) || 0.92)
              }
              className="w-16 h-7 px-2 text-right font-mono text-xs rounded-md bg-app-subtle/50 text-app-heading border border-app-border focus:outline-none focus:border-blue-500"
              style={{ fontFeatureSettings: '"tnum" 1' }}
            />
            <span className="font-mono text-xs text-app-muted w-10">
              {((currentConfig.fast_exit_threshold ?? 0.92) * 100).toFixed(0)}%
            </span>
          </div>
          <span className="text-[11px] text-app-muted block">
            Decisions exceeding this calibrated score bypass the generative LLM immediately (System 1).
          </span>
        </div>

        {/* Uncertainty Threshold */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-app-heading">
                Uncertainty Escalation Threshold (τ_uncertainty)
              </label>
              {isFieldOverridden("uncertainty_threshold") && (
                <span className="font-mono text-[9px] text-amber-600 dark:text-amber-400 bg-amber-500/10 px-1 py-0.2 rounded border border-amber-500/20">
                  Overridden
                </span>
              )}
            </div>
            <span className="font-mono text-[10px] text-app-muted/80">decision_engine.uncertainty_threshold</span>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min="0.30"
              max="0.80"
              step="0.01"
              value={Number(currentConfig.uncertainty_threshold ?? 0.55)}
              onChange={(e) =>
                updateField("uncertainty_threshold", parseFloat(e.target.value))
              }
              className="flex-1 precision-slider accent-amber-600 cursor-pointer"
            />
            <input
              type="number"
              step="0.01"
              min="0.30"
              max="0.80"
              value={Number(currentConfig.uncertainty_threshold ?? 0.55).toFixed(2)}
              onChange={(e) =>
                updateField("uncertainty_threshold", parseFloat(e.target.value) || 0.55)
              }
              className="w-16 h-7 px-2 text-right font-mono text-xs rounded-md bg-app-subtle/50 text-app-heading border border-app-border focus:outline-none focus:border-blue-500"
              style={{ fontFeatureSettings: '"tnum" 1' }}
            />
            <span className="font-mono text-xs text-app-muted w-10">
              {((currentConfig.uncertainty_threshold ?? 0.55) * 100).toFixed(0)}%
            </span>
          </div>
          <span className="text-[11px] text-app-muted block">
            Decisions falling below this score are automatically escalated to LLM reasoning (System 2).
          </span>
        </div>

        {/* Stochastic Audit Rate */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-app-heading">
                Stochastic Audit Rate (p_audit)
              </label>
              {isFieldOverridden("stochastic_audit_rate") && (
                <span className="font-mono text-[9px] text-amber-600 dark:text-amber-400 bg-amber-500/10 px-1 py-0.2 rounded border border-amber-500/20">
                  Overridden
                </span>
              )}
            </div>
            <span className="font-mono text-[10px] text-app-muted/80">decision_engine.stochastic_audit_rate</span>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min="0.00"
              max="0.20"
              step="0.005"
              value={Number(currentConfig.stochastic_audit_rate ?? 0.05)}
              onChange={(e) =>
                updateField("stochastic_audit_rate", parseFloat(e.target.value))
              }
              className="flex-1 precision-slider accent-indigo-600 cursor-pointer"
            />
            <input
              type="number"
              step="0.005"
              min="0.00"
              max="0.20"
              value={Number(currentConfig.stochastic_audit_rate ?? 0.05).toFixed(3)}
              onChange={(e) =>
                updateField("stochastic_audit_rate", parseFloat(e.target.value) || 0.05)
              }
              className="w-16 h-7 px-2 text-right font-mono text-xs rounded-md bg-app-subtle/50 text-app-heading border border-app-border focus:outline-none focus:border-blue-500"
              style={{ fontFeatureSettings: '"tnum" 1' }}
            />
            <span className="font-mono text-xs text-app-muted w-10">
              {((currentConfig.stochastic_audit_rate ?? 0.05) * 100).toFixed(1)}%
            </span>
          </div>
          <span className="text-[11px] text-app-muted block">
            Random sample of fast-exit decisions simultaneously verified by LLM for online drift tracking.
          </span>
        </div>
      </div>

      {/* ── 3. Pipeline Phase Deployment Gating ── */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="type-h2 text-app-heading">
              Pipeline Phase Deployment Gating
            </h4>
            <p className="type-caption text-app-muted mt-0.5">
              Control which pipeline phases deploy System 1 fast-exit gating.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isFieldOverridden("phase_gates") && (
              <span className="font-mono text-[9px] text-amber-600 dark:text-amber-400 bg-amber-500/10 px-1 py-0.2 rounded border border-amber-500/20 uppercase">
                Overridden
              </span>
            )}
            <button
              type="button"
              onClick={() => {
                const toggled = !allGatesActive;
                updateField("phase_gates", {
                  phase2_entity_discovery: toggled,
                  phase3_global_relations: toggled,
                  phase4_argument_mining: toggled,
                  phase4_entity_maturation: toggled,
                  phase5_fusion: toggled,
                  phase6_theorynet: toggled,
                });
              }}
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-mono cursor-pointer"
            >
              {allGatesActive ? "Disable All" : "Enable All"}
            </button>
          </div>
        </div>

        {/* Gating Card List */}
        <div className="space-y-2">
          {(
            [
              {
                key: "phase2_entity_discovery" as const,
                ordinal: "02",
                label: "Phase 2: Entity Discovery",
                role: "Mention filtering & entity class validation",
                capability: "Categorical Choice",
              },
              {
                key: "phase3_global_relations" as const,
                ordinal: "03",
                label: "Phase 3: Global Relations",
                role: "Cross-document relation candidate gating & pruning",
                capability: "Binary Noul",
              },
              {
                key: "phase4_argument_mining" as const,
                ordinal: "04b",
                label: "Phase 4: Argument Mining",
                role: "ADU segmentation & argument stance classification",
                capability: "Categorical Choice",
              },
              {
                key: "phase4_entity_maturation" as const,
                ordinal: "04a",
                label: "Phase 4b: Entity Maturation",
                role: "Epistemic synthesis & confidence voting verification",
                capability: "Continuous Score",
              },
              {
                key: "phase5_fusion" as const,
                ordinal: "05",
                label: "Phase 5: Inter-Document Web",
                role: "Entity resolution & argument cluster equivalence",
                capability: "Binary Noul",
              },
              {
                key: "phase6_theorynet" as const,
                ordinal: "06",
                label: "Phase 6: Epistemic TheoryNet",
                role: "QBAF node base scores & inferential warrants",
                capability: "Continuous Score",
              },
            ] as const
          ).map((gate) => {
            const isEnabled = Boolean(currentConfig.phase_gates?.[gate.key]);
            return (
              <div
                key={gate.key}
                className="p-3 rounded-lg border border-app-border/80 bg-app-subtle/30 hover:bg-app-subtle/50 flex items-center justify-between gap-3 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="w-7 h-5 rounded-[4px] bg-app-surface text-app-muted border border-app-border text-[10px] font-mono font-medium flex items-center justify-center shrink-0">
                    {gate.ordinal}
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-app-heading">
                        {gate.label}
                      </span>
                      <span className="font-mono text-[10px] text-app-muted bg-app-surface px-1.5 py-0.2 rounded border border-app-border">
                        {gate.capability}
                      </span>
                    </div>
                    <p className="text-[11px] text-app-muted mt-0.5 truncate">
                      {gate.role}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0 ml-4">
                  <span
                    className={`font-mono text-[11px] font-medium ${
                      isEnabled
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-app-muted"
                    }`}
                  >
                    {isEnabled ? "Active" : "Bypassed"}
                  </span>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isEnabled}
                      onChange={(e) => updateGate(gate.key, e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-8 h-4 bg-app-border peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-[#2563EB]" />
                  </label>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 5. Propositional Modality & Structuralist Syntax (ADR 0020) */}
      <div className="space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-app-border">
          <div>
            <h3 className="text-sm font-semibold text-app-heading flex items-center gap-2">
              <span>Propositional Modality & Structural Syntax (ADR 0020)</span>
              <span className="font-mono text-[10px] text-blue-500 bg-blue-500/10 px-1.5 py-0.2 rounded border border-blue-500/20 font-semibold">
                M(φ) ≡ τ₀(a)
              </span>
            </h3>
            <p className="text-xs text-app-muted mt-0.5">
              Decoupled QBAF base score resolver combining Schurz (2014) structuralist sentence taxonomy with System 1 calibrated linguistic scoring.
            </p>
          </div>
        </div>

        {(() => {
          const modalConfig: ModalResolverSettings = settings?.modal_resolver || {
            mode: "guardrail",
            fusion_alpha: 0.5,
            default_base_score: 0.6,
          };

          return (
            <div className="p-4 rounded-lg border border-app-border bg-app-subtle/20 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-semibold text-app-heading block mb-1">
                    Resolution Mode
                  </label>
                  <select
                    value={modalConfig.mode}
                    onChange={(e) =>
                      updateEngineSettings({
                        modal_resolver: {
                          ...modalConfig,
                          mode: e.target.value as any,
                        },
                      })
                    }
                    className="w-full text-xs bg-app-surface text-app-heading px-3 py-2 rounded-md border border-app-border focus:outline-hidden font-mono"
                  >
                    <option value="guardrail">guardrail — syntax bounds [M_min, M_max] clamp calibrated score</option>
                    <option value="convex">convex — α · syntax + (1 - α) · engine</option>
                    <option value="structural_only">structural_only — pure Schurz (2014) syntax priors</option>
                    <option value="engine_only">engine_only — pure System 1 DecisionEngine</option>
                  </select>
                  <p className="text-[11px] text-app-muted mt-1 leading-relaxed">
                    Guardrail mode guarantees formal consistency with structuralist philosophy of science while allowing linguistic hedging to tune certitude.
                  </p>
                </div>

                <div>
                  <label className="text-xs font-semibold text-app-heading block mb-1">
                    Fallback Baseline Base Score (τ₀)
                  </label>
                  <input
                    type="number"
                    step="0.05"
                    min="0.0"
                    max="1.0"
                    value={modalConfig.default_base_score}
                    onChange={(e) =>
                      updateEngineSettings({
                        modal_resolver: {
                          ...modalConfig,
                          default_base_score: parseFloat(e.target.value) || 0.6,
                        },
                      })
                    }
                    className="w-full text-xs bg-app-surface text-app-heading px-3 py-2 rounded-md border border-app-border focus:outline-hidden font-mono"
                  />
                  <p className="text-[11px] text-app-muted mt-1 leading-relaxed">
                    Prior base score assigned if neither syntax classification nor linguistic evidence provides determinate bounds.
                  </p>
                </div>
              </div>

              {modalConfig.mode === "convex" && (
                <div className="pt-2 border-t border-app-border/40">
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="font-medium text-app-heading">
                      Convex Interpolation Weight α: {(modalConfig.fusion_alpha * 100).toFixed(0)}% Syntax / {((1 - modalConfig.fusion_alpha) * 100).toFixed(0)}% Engine
                    </span>
                    <span className="font-mono text-app-muted text-[11px]">
                      α = {modalConfig.fusion_alpha.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0.0"
                    max="1.0"
                    step="0.05"
                    value={modalConfig.fusion_alpha}
                    onChange={(e) =>
                      updateEngineSettings({
                        modal_resolver: {
                          ...modalConfig,
                          fusion_alpha: parseFloat(e.target.value),
                        },
                      })
                    }
                    className="w-full accent-blue-600"
                  />
                </div>
              )}
            </div>
          );
        })()}
      </div>

      {/* Decision Playground Modal */}
      <DecisionPlaygroundModal
        isOpen={isPlaygroundOpen}
        onClose={() => setIsPlaygroundOpen(false)}
        config={currentConfig}
      />
    </div>
  );
};
