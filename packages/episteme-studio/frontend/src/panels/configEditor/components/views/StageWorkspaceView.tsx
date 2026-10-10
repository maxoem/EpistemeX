import React from "react";
import {ChevronDown, ChevronRight, Code2} from "lucide-react";
import {ConfigView, ResolvedPromptItem} from "../../../../api/types";
import {ParameterFieldMeta, PhaseMetadata} from "../../../phaseConfig/phaseRegistry";
import {PromptCodeEditor} from "../../../phaseConfig/PromptCodeEditor";
import {ParameterRow} from "../ParameterRow";

interface StageWorkspaceViewProps {
  selectedPhaseKey: string;
  activePhaseMeta: PhaseMetadata;
  patch: Record<string, any>;
  configView: ConfigView | null;
  updateField: (fieldPath: string, value: any) => void;
  clearField: (fieldPath: string) => void;

  // Prompt templates state & callbacks
  promptProvider: "default" | "langfuse";
  promptLabel: string;
  resolvedPrompts: Record<string, ResolvedPromptItem>;
  stagedPrompts: Record<string, string>;
  setStagedPrompts: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  activePromptSubTab: string;
  setActivePromptSubTab: (key: string) => void;

  // Baseline inheritance values (D-14)
  defaultLlm: string;
  defaultTemp: number;
  defaultThinkingLevel: string;
  onSelectPhase: (phaseKey: string) => void;

  // Advanced drawer state
  isAdvancedDrawerOpen: boolean;
  setIsAdvancedDrawerOpen: (val: boolean) => void;
}

export const StageWorkspaceView: React.FC<StageWorkspaceViewProps> = ({
  selectedPhaseKey,
  activePhaseMeta,
  patch,
  configView,
  updateField,
  clearField,
  promptProvider,
  promptLabel,
  resolvedPrompts,
  stagedPrompts,
  setStagedPrompts,
  activePromptSubTab,
  setActivePromptSubTab,
  defaultLlm,
  defaultTemp,
  defaultThinkingLevel,
  onSelectPhase,
  isAdvancedDrawerOpen,
  setIsAdvancedDrawerOpen,
}) => {
  const prefix = activePhaseMeta.configPrefix || selectedPhaseKey;

  return (
    <div className="space-y-6">
      {/* Stage Header */}
      <div className="pb-5 border-b border-app-border/80">
        <div className="flex items-center gap-2.5">
          <span className="type-caption uppercase tracking-wider text-app-muted bg-app-subtle border border-app-border px-2 py-0.5 rounded">
            {activePhaseMeta.category}
          </span>
          <h3 className="type-h1 text-app-heading">
            {activePhaseMeta.displayName}
          </h3>
        </div>
        <p className="type-body text-app-muted mt-1.5 max-w-2xl">
          {activePhaseMeta.description}
        </p>
      </div>

      {/* 1. Full-Width Prompt Template Editor (if stage has prompts) */}
      {activePhaseMeta.promptKeys && activePhaseMeta.promptKeys.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between pb-1.5 border-b border-app-border">
            <div className="flex items-center gap-2">
              <Code2 className="w-4 h-4 text-app-muted" />
              <h4 className="text-xs font-semibold text-app-heading">
                Prompt Template Editor
              </h4>
            </div>

            <div className="flex items-center gap-2 text-[11px]">
              {promptProvider === "langfuse" ? (
                <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20 font-mono text-[10px]">
                  Langfuse Managed ({promptLabel}) · Read-only
                </span>
              ) : (
                <span className="text-app-muted font-mono text-[10px]">
                  Built-in Default · Staged Editable
                </span>
              )}
            </div>
          </div>

          {/* Multiple Prompt Tabs if stage has >1 prompt */}
          {activePhaseMeta.promptKeys.length > 1 && (
            <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-none">
              {activePhaseMeta.promptKeys.map((pKey: string) => {
                const activeKey = activePromptSubTab || activePhaseMeta.promptKeys[0];
                const isTabActive = activeKey === pKey;
                return (
                  <button
                    key={pKey}
                    type="button"
                    onClick={() => setActivePromptSubTab(pKey)}
                    className={`px-2.5 py-1 rounded text-xs font-mono transition-colors cursor-pointer shrink-0 ${
                      isTabActive
                        ? "bg-app-subtle text-app-heading font-semibold border border-app-border"
                        : "text-app-muted hover:text-app-heading"
                    }`}
                  >
                    {pKey.replace("_prompts", "").replace("_prompt_template", "")}
                  </button>
                );
              })}
            </div>
          )}

          {(() => {
            const promptKey =
              activePromptSubTab && activePhaseMeta.promptKeys.includes(activePromptSubTab)
                ? activePromptSubTab
                : activePhaseMeta.promptKeys[0];

            const canonicalName = promptKey
              .replace("_prompts", "")
              .replace("_prompt_template", "");

            const resolved =
              resolvedPrompts[canonicalName] ||
              resolvedPrompts[promptKey] ||
              Object.values(resolvedPrompts).find((p) => p.name.includes(canonicalName));

            const targetPromptPath = promptKey.endsWith("_template")
              ? `${selectedPhaseKey}.${promptKey}`
              : `${selectedPhaseKey}.${promptKey}.direct_template`;

            const currentText =
              stagedPrompts[promptKey] ??
              patch[targetPromptPath] ??
              patch[`${selectedPhaseKey}.${promptKey}`] ??
              resolved?.direct_template ??
              `// Default prompt template for ${promptKey}\nExtract information adhering strictly to provided schema variables {{schema}}.\nText: {context}`;

            const isReadOnly = promptProvider === "langfuse";

            return (
              <div className="space-y-1.5">
                <div className="rounded-lg border border-app-border overflow-hidden bg-app-bg shadow-2xs">
                  <PromptCodeEditor
                    value={currentText}
                    onChange={(val: string) => {
                      if (!isReadOnly) {
                        setStagedPrompts((prev) => ({ ...prev, [promptKey]: val }));
                        updateField(targetPromptPath, val);
                      }
                    }}
                    readOnly={isReadOnly}
                    minHeight="120px"
                    maxHeight="320px"
                  />
                </div>
                <div className="flex items-center justify-between text-[10px] font-mono text-app-muted px-1">
                  <span>Variables: &#123;&#123;schema&#125;&#125;, &#123;context&#125;</span>
                  <span>{currentText.length} characters</span>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* 2. Inference Stack & Baseline Inheritance (D-14) */}
      <div className="space-y-3 pt-2 border-t border-app-border">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-xs font-semibold text-app-heading">
              Inference Stack & Baseline Inheritance
            </h4>
            <p className="text-[11px] text-app-muted mt-0.5">
              Inherited from global pipeline defaults unless stage-specific parameters override them.
            </p>
          </div>
          <button
            type="button"
            onClick={() => onSelectPhase("phase0")}
            className="text-[11px] font-mono text-blue-600 dark:text-blue-400 hover:underline cursor-pointer inline-flex items-center gap-1 shrink-0"
          >
            <span>Configure Baseline</span>
            <ChevronRight className="w-3 h-3" />
          </button>
        </div>

        <div className="divide-y divide-app-border-subtle">
          <div className="py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium text-xs text-app-heading">Generative Model (LLM)</span>
                <span className="font-mono text-[10px] text-app-muted">models.llm_model</span>
              </div>
              <span className="text-[11px] text-app-muted font-mono block mt-0.5">
                {defaultLlm}
              </span>
            </div>
            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-app-subtle text-app-muted border border-app-border uppercase tracking-wider self-start sm:self-auto">
              Inherited Baseline
            </span>
          </div>

          <div className="py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium text-xs text-app-heading">Sampling Temperature</span>
                <span className="font-mono text-[10px] text-app-muted">models.temperature</span>
              </div>
              <span className="text-[11px] text-app-muted font-mono block mt-0.5">
                {Number(defaultTemp).toFixed(2)}
              </span>
            </div>
            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-app-subtle text-app-muted border border-app-border uppercase tracking-wider self-start sm:self-auto">
              Inherited Baseline
            </span>
          </div>

          <div className="py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium text-xs text-app-heading">Thinking / Reasoning Level</span>
                <span className="font-mono text-[10px] text-app-muted">models.thinking_level</span>
              </div>
              <span className="text-[11px] text-app-muted font-mono block mt-0.5">
                {String(defaultThinkingLevel).toUpperCase()}
              </span>
            </div>
            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-app-subtle text-app-muted border border-app-border uppercase tracking-wider self-start sm:self-auto">
              Inherited Baseline
            </span>
          </div>

          {/* Decision Engine Fast-Exit Gating for this stage */}
          {(() => {
            const gateMap: Record<string, { gateKey: string; label: string; capability: string }> = {
              phase2: { gateKey: "phase2_entity_discovery", label: "Phase 2: Entity Discovery", capability: "Categorical Choice Mention Filter" },
              phase3: { gateKey: "phase3_global_relations", label: "Phase 3: Global Relations", capability: "Binary Noul Candidate Pruning" },
              phase4: { gateKey: "phase4_argument_mining", label: "Phase 4: Argument Mining", capability: "Categorical Choice ADU & Stance" },
              phase4_maturation: { gateKey: "phase4_entity_maturation", label: "Phase 4b: Entity Maturation", capability: "Continuous Score Verification" },
              phase5: { gateKey: "phase5_fusion", label: "Phase 5: Inter-Document Web", capability: "Binary Noul Cluster Equivalence" },
              phase6: { gateKey: "phase6_theorynet", label: "Phase 6: Epistemic TheoryNet", capability: "Continuous Score QBAF Warrants" },
            };
            const gate = gateMap[selectedPhaseKey];
            if (!gate) return null;

            const patchKey = `decision_engine.phase_gates.${gate.gateKey}`;
            const isGated =
              patch[patchKey] !== undefined
                ? Boolean(patch[patchKey])
                : patch["decision_engine.phase_gates"]?.[gate.gateKey] !== undefined
                ? Boolean(patch["decision_engine.phase_gates"][gate.gateKey])
                : true;
            const isOverridden =
              patch[patchKey] !== undefined ||
              patch["decision_engine.phase_gates"]?.[gate.gateKey] !== undefined;

            return (
              <div className="py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-t border-app-border/40">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-xs text-app-heading">
                      Decision Engine (Jev) Fast-Exit Gating
                    </span>
                    <span className="font-mono text-[10px] text-app-muted bg-app-subtle px-1.5 py-0.2 rounded border border-app-border">
                      {gate.capability}
                    </span>
                  </div>
                  <span className="text-[11px] text-app-muted font-sans block mt-0.5">
                    {isGated
                      ? "System 1 local accelerated fast-exit active for this stage."
                      : "Gating bypassed. All decisions escalated directly to generative LLM."}
                  </span>
                </div>
                <div className="flex items-center gap-2 self-start sm:self-auto">
                  {isOverridden && (
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold border border-blue-500/20">
                      Overridden
                    </span>
                  )}
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isGated}
                      onChange={(e) => updateField(patchKey, e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-8 h-4 bg-app-border peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-[#2563EB]" />
                  </label>
                </div>
              </div>
            );
          })()}

          {/* Modal Strength Resolution Strategy (ADR 0020) for Phase 4 & Phase 6 */}
          {(selectedPhaseKey === "phase4" || selectedPhaseKey === "phase6") && (() => {
            const modeKey = `${selectedPhaseKey}.modal_resolver.mode`;
            const alphaKey = `${selectedPhaseKey}.modal_resolver.fusion_alpha`;
            const baseKey = `${selectedPhaseKey}.modal_resolver.default_base_score`;

            const currentMode = patch[modeKey] || "guardrail";
            const currentAlpha = patch[alphaKey] !== undefined ? Number(patch[alphaKey]) : 0.5;
            const isOverridden = patch[modeKey] !== undefined || patch[alphaKey] !== undefined || patch[baseKey] !== undefined;

            return (
              <div className="py-3 border-t border-app-border/40 space-y-2.5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-xs text-app-heading">
                        Modal Strength Resolver (ADR 0020)
                      </span>
                      <span className="font-mono text-[10px] text-blue-500 bg-blue-500/10 px-1.5 py-0.2 rounded border border-blue-500/20 font-semibold">
                        M(φ) ≡ τ₀(a)
                      </span>
                    </div>
                    <span className="text-[11px] text-app-muted font-sans block mt-0.5">
                      Synthesizes structuralist sentence syntax (Schurz 2014) with System 1 calibrated certainty.
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {isOverridden && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold border border-blue-500/20">
                        Overridden
                      </span>
                    )}
                    <select
                      value={currentMode}
                      onChange={(e) => updateField(modeKey, e.target.value)}
                      className="text-xs bg-app-surface text-app-heading px-2.5 py-1 rounded border border-app-border focus:outline-hidden font-mono"
                    >
                      <option value="guardrail">guardrail (syntax bounded)</option>
                      <option value="convex">convex (α · syntax + (1-α) · engine)</option>
                      <option value="structural_only">structural_only (syntax only)</option>
                      <option value="engine_only">engine_only (System 1 Jev only)</option>
                    </select>
                  </div>
                </div>

                {currentMode === "convex" && (
                  <div className="flex items-center justify-between gap-4 pt-1 px-1 bg-app-subtle/30 p-2 rounded border border-app-border/50">
                    <span className="text-[11px] font-sans text-app-muted">
                      Fusion Weight α ({Math.round(currentAlpha * 100)}% Syntax / {Math.round((1 - currentAlpha) * 100)}% Engine)
                    </span>
                    <input
                      type="range"
                      min="0.0"
                      max="1.0"
                      step="0.05"
                      value={currentAlpha}
                      onChange={(e) => updateField(alphaKey, parseFloat(e.target.value))}
                      className="w-32 accent-blue-600"
                    />
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      </div>

      {/* 3. Stage Primary Hyperparameters */}
      <div className="space-y-3 pt-2 border-t border-app-border">
        <h4 className="text-xs font-semibold text-app-heading">
          Stage Hyperparameters
        </h4>

        <div className="divide-y divide-app-border-subtle">
          {Object.entries(activePhaseMeta.parameterMeta)
            .filter(([_, meta]) => !meta.isAdvanced)
            .map(([paramKey, meta]) => (
              <ParameterRow
                key={paramKey}
                paramKey={paramKey}
                meta={meta as ParameterFieldMeta}
                prefix={prefix}
                patch={patch}
                configValues={configView?.values}
                provenanceMap={configView?.provenance}
                onUpdateField={updateField}
                onClearField={clearField}
              />
            ))}
        </div>
      </div>

      {/* 4. Collapsible Advanced Parameters Drawer */}
      {Object.entries(activePhaseMeta.parameterMeta).some(([_, m]) => m.isAdvanced) && (
        <div className="pt-2 border-t border-app-border">
          <button
            type="button"
            onClick={() => setIsAdvancedDrawerOpen(!isAdvancedDrawerOpen)}
            className="flex items-center justify-between w-full py-2 text-xs font-semibold text-app-heading hover:text-blue-500 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              {isAdvancedDrawerOpen ? (
                <ChevronDown className="w-4 h-4 text-app-muted" />
              ) : (
                <ChevronRight className="w-4 h-4 text-app-muted" />
              )}
              <span>Advanced Parameters & Directives</span>
            </div>
            <span className="text-[10px] font-mono text-app-muted uppercase">
              {isAdvancedDrawerOpen ? "Hide" : "Show"}
            </span>
          </button>

          {isAdvancedDrawerOpen && (
            <div className="divide-y divide-app-border-subtle pt-1">
              {Object.entries(activePhaseMeta.parameterMeta)
                .filter(([_, meta]) => meta.isAdvanced)
                .map(([paramKey, meta]) => (
                  <ParameterRow
                    key={paramKey}
                    paramKey={paramKey}
                    meta={meta as ParameterFieldMeta}
                    prefix={prefix}
                    patch={patch}
                    configValues={configView?.values}
                    provenanceMap={configView?.provenance}
                    onUpdateField={updateField}
                    onClearField={clearField}
                  />
                ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
