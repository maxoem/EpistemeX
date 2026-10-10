import React from "react";
import {Brain, Check, ChevronDown, ChevronRight, Database, ExternalLink, RefreshCw} from "lucide-react";
import {ConfigView} from "../../../../api/types";
import {ParameterFieldMeta, PhaseMetadata} from "../../../phaseConfig/phaseRegistry";
import {THINKING_LEVEL_PRESETS} from "../../constants";
import {ParameterRow} from "../ParameterRow";

interface PipelineDefaultsViewProps {
  patch: Record<string, any>;
  configView: ConfigView | null;
  activePhaseMeta?: PhaseMetadata;
  updateField: (fieldPath: string, value: any) => void;
  clearField: (fieldPath: string) => void;

  defaultLlm: string;
  defaultEmbed: string;
  defaultReranker: string;
  defaultTemp: number;
  defaultSeed: number;
  defaultThinkingLevel: string;

  isCustomThinkingActive: boolean;
  setIsCustomThinkingActive: (val: boolean) => void;
  customThinkingInput: string;
  setCustomThinkingInput: (val: string) => void;

  openProjectSettings: () => void;
  promptProvider: "default" | "langfuse";
  setPromptProvider: (val: "default" | "langfuse") => void;
  promptLabel: string;
  setPromptLabel: (val: string) => void;
  handleResolvePrompts: (provider: "default" | "langfuse", label: string) => void;
  isFetchingPrompts: boolean;
  promptFetchSuccess: boolean;
  setPromptFetchSuccess: (val: boolean) => void;

  isAdvancedDrawerOpen: boolean;
  setIsAdvancedDrawerOpen: (val: boolean) => void;
}

export const PipelineDefaultsView: React.FC<PipelineDefaultsViewProps> = ({
  patch,
  configView,
  activePhaseMeta,
  updateField,
  clearField,
  defaultLlm,
  defaultEmbed,
  defaultReranker,
  defaultTemp,
  defaultSeed,
  defaultThinkingLevel,
  isCustomThinkingActive,
  setIsCustomThinkingActive,
  customThinkingInput,
  setCustomThinkingInput,
  openProjectSettings,
  promptProvider,
  setPromptProvider,
  promptLabel,
  setPromptLabel,
  handleResolvePrompts,
  isFetchingPrompts,
  promptFetchSuccess,
  setPromptFetchSuccess,
  isAdvancedDrawerOpen,
  setIsAdvancedDrawerOpen,
}) => {
  return (
    <div className="space-y-6">
      {/* Title & Description */}
      <div className="pb-5 border-b border-app-border/80">
        <div className="flex items-center justify-between gap-2">
          <h3 className="type-h1 text-app-heading">
            Pipeline Defaults
          </h3>
          <span className="type-caption text-app-muted">
            Inherited across all stages
          </span>
        </div>
        <p className="type-body text-app-muted mt-1.5 max-w-2xl">
          Establishes baseline foundation models and inference parameters inherited across all pipeline stages.
          Individual stages can inherit these defaults or specify targeted custom overrides.
        </p>
      </div>

      {/* 1. Global Foundational Inference Stack */}
      <div className="space-y-4">
        <h4 className="type-h2 text-app-heading">
          Foundational Inference Stack
        </h4>

        {/* Generative Model Input */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-app-heading">
              Default Generative Model (LLM)
            </label>
            <span className="font-mono text-[10px] text-app-muted/80">models.llm_model</span>
          </div>
          <input
            type="text"
            value={defaultLlm}
            onChange={(e) => updateField("models.llm_model", e.target.value)}
            placeholder="e.g. openai/gpt-4o-mini"
            className="w-full h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80"
          />
          <span className="text-[11px] text-app-muted block">
            Inherited by extraction, entity classification, and argument relation mining stages.
          </span>
        </div>

        {/* Model Thinking Level Selector (Unboxed Peer Row) */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Brain className="w-3.5 h-3.5 text-blue-500" />
              <label className="text-xs font-medium text-app-heading">
                Model Thinking Level
              </label>
            </div>
            <span className="font-mono text-[10px] text-app-muted/80">models.thinking_level</span>
          </div>

          {/* Inset Pill Track */}
          <div className="p-0.5 inline-flex flex-wrap items-center bg-app-subtle rounded-md border border-app-border/60 gap-0.5">
            {THINKING_LEVEL_PRESETS.map((preset) => {
              const isPresetMatch = ["off", "low", "medium", "high"].includes(defaultThinkingLevel.toLowerCase());
              const isSelected =
                preset.id === "custom"
                  ? isCustomThinkingActive || !isPresetMatch
                  : !isCustomThinkingActive && defaultThinkingLevel.toLowerCase() === preset.id;

              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => {
                    if (preset.id === "custom") {
                      setIsCustomThinkingActive(true);
                      const initialVal = isPresetMatch ? "2048" : defaultThinkingLevel;
                      setCustomThinkingInput(initialVal);
                      updateField("models.thinking_level", initialVal);
                    } else {
                      setIsCustomThinkingActive(false);
                      updateField("models.thinking_level", preset.id);
                    }
                  }}
                  title={preset.description}
                  className={`h-6 px-3 rounded text-[11px] font-medium transition-all cursor-pointer inline-flex items-center gap-1.5 ${
                    isSelected
                      ? "bg-app-surface text-app-heading shadow-xs font-semibold border border-app-border/80"
                      : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
                  }`}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>

          {/* Custom Option Field */}
          {(isCustomThinkingActive || !["off", "low", "medium", "high"].includes(defaultThinkingLevel.toLowerCase())) && (
            <div className="pt-1 space-y-1.5 animate-in fade-in duration-150">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={isCustomThinkingActive ? customThinkingInput : defaultThinkingLevel}
                  onChange={(e) => {
                    const val = e.target.value;
                    setIsCustomThinkingActive(true);
                    setCustomThinkingInput(val);
                    updateField("models.thinking_level", val);
                  }}
                  placeholder="e.g. 2048, 8192, minimal, high-effort..."
                  className="flex-1 h-7 px-2.5 rounded bg-app-bg text-app-heading border border-blue-500/70 text-xs font-mono focus:outline-none"
                />
                <div className="flex items-center gap-1 shrink-0">
                  {["1024", "2048", "4096", "8192"].map((tokenPreset) => (
                    <button
                      key={tokenPreset}
                      type="button"
                      onClick={() => {
                        setIsCustomThinkingActive(true);
                        setCustomThinkingInput(tokenPreset);
                        updateField("models.thinking_level", tokenPreset);
                      }}
                      className="h-6 px-1.5 rounded text-[10px] font-mono border border-app-border bg-app-surface hover:bg-app-subtle text-app-muted hover:text-app-heading cursor-pointer transition-colors"
                    >
                      {tokenPreset}
                    </button>
                  ))}
                </div>
              </div>
              <span className="text-[10px] text-app-muted block">
                Specify token budget or model-specific reasoning tier (e.g. Claude 3.7 thinking tokens, Gemini 2.5/3 Flash budget, OpenAI reasoning effort).
              </span>
            </div>
          )}

          <span className="text-[11px] text-app-muted block">
            Controls test-time compute and chain-of-thought depth across entity discovery and argumentation phases.
          </span>
        </div>

        {/* Dense Embedding Model Input */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-app-heading">
              Dense Embedding Model
            </label>
            <span className="font-mono text-[10px] text-app-muted/80">models.embedding_model</span>
          </div>
          <input
            type="text"
            value={defaultEmbed}
            onChange={(e) => updateField("models.embedding_model", e.target.value)}
            placeholder="e.g. sentence-transformers/all-MiniLM-L6-v2"
            className="w-full h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80"
          />
          <span className="text-[11px] text-app-muted block">
            Uniform vector latent space used across chunking, candidate retrieval, and consolidation.
          </span>
        </div>

        {/* Cross-Encoder Reranker Model */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-app-heading">
              Cross-Encoder Reranker Model
            </label>
            <span className="font-mono text-[10px] text-app-muted/80">models.reranker_model</span>
          </div>
          <input
            type="text"
            value={defaultReranker}
            onChange={(e) => updateField("models.reranker_model", e.target.value)}
            placeholder="e.g. Alibaba-NLP/gte-reranker-modernbert-base"
            className="w-full h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80"
          />
        </div>

        {/* Paired Micro-Inputs: Sampling Temperature & Seed */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-app-heading">
              Sampling Temperature
            </label>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={Number(defaultTemp)}
                onChange={(e) => updateField("models.temperature", parseFloat(e.target.value))}
                className="flex-1 precision-slider accent-blue-600 cursor-pointer"
              />
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={Number(defaultTemp).toFixed(2)}
                onChange={(e) => updateField("models.temperature", parseFloat(e.target.value) || 0)}
                className="w-16 h-7 px-2 text-right font-mono text-xs rounded-md bg-app-subtle/50 text-app-heading border border-app-border focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-app-heading">
              Global Determinism Seed
            </label>
            <input
              type="number"
              value={defaultSeed}
              onChange={(e) => updateField("models.seed", parseInt(e.target.value, 10) || 0)}
              className="w-full h-7 px-2.5 font-mono text-xs rounded-md bg-app-subtle/50 text-app-heading border border-app-border focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {/* 2. Infrastructure & Telemetry Notice Card */}
      <div className="p-3.5 rounded-lg border border-app-border/80 bg-app-subtle/30 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Database className="w-4 h-4 text-blue-500 shrink-0" />
          <div>
            <h5 className="font-semibold text-xs text-app-heading">
              Langfuse Observability & Host Credentials
            </h5>
            <p className="text-[11px] text-app-muted mt-0.5">
              Infrastructure credentials, port numbers, and authentication keys are managed in Project Settings.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={openProjectSettings}
          className="px-3 py-1.5 rounded-md border border-app-border bg-app-surface hover:bg-app-subtle text-xs font-medium text-app-heading transition-colors cursor-pointer inline-flex items-center gap-1.5 shrink-0"
        >
          <span>Project Settings</span>
          <ExternalLink className="w-3 h-3 text-app-muted" />
        </button>
      </div>

      {/* 3. Prompt Governance Mode */}
      <div className="space-y-2 pt-4 border-t border-app-border/80">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="type-h2 text-app-heading">
              Prompt Governance Source
            </h4>
            <p className="type-caption text-app-muted mt-0.5">
              Choose whether stages resolve local code templates or remote versioned prompts.
            </p>
          </div>

          <div className="p-0.5 inline-flex items-center bg-app-subtle rounded-md border border-app-border/60 gap-0.5 text-xs font-medium">
            <button
              type="button"
              onClick={() => {
                setPromptProvider("default");
                handleResolvePrompts("default", "production");
              }}
              className={`h-6 px-3 rounded text-[11px] transition-all cursor-pointer ${
                promptProvider === "default"
                  ? "bg-app-surface font-semibold text-app-heading shadow-xs border border-app-border/80"
                  : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
              }`}
            >
              Built-in Default
            </button>
            <button
              type="button"
              onClick={() => {
                setPromptProvider("langfuse");
                handleResolvePrompts("langfuse", promptLabel);
              }}
              className={`h-6 px-3 rounded text-[11px] transition-all cursor-pointer ${
                promptProvider === "langfuse"
                  ? "bg-app-surface font-semibold text-app-heading shadow-xs border border-app-border/80"
                  : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
              }`}
            >
              Langfuse Managed
            </button>
          </div>
        </div>

        {promptProvider === "langfuse" && (
          <div className="flex items-center gap-2 pt-1 text-xs">
            <span className="text-app-muted font-mono text-[11px]">Tag:</span>
            <input
              type="text"
              value={promptLabel}
              onChange={(e) => {
                setPromptLabel(e.target.value);
                setPromptFetchSuccess(false);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !isFetchingPrompts) {
                  handleResolvePrompts("langfuse", promptLabel);
                }
              }}
              placeholder="production"
              className="h-7 px-2 rounded bg-app-bg text-app-heading border border-app-border text-xs font-mono w-32 focus:outline-none focus:border-blue-500"
            />
            <button
              type="button"
              onClick={() => handleResolvePrompts("langfuse", promptLabel)}
              disabled={isFetchingPrompts}
              className="h-7 px-2.5 rounded border border-app-border bg-app-bg hover:bg-app-subtle text-app-heading text-xs inline-flex items-center gap-1 cursor-pointer transition-colors"
            >
              {isFetchingPrompts ? (
                <RefreshCw className="w-3 h-3 animate-spin" />
              ) : promptFetchSuccess ? (
                <Check className="w-3 h-3 text-emerald-500" />
              ) : (
                <RefreshCw className="w-3 h-3" />
              )}
              <span>{isFetchingPrompts ? "Fetching..." : promptFetchSuccess ? "Fetched" : "Fetch"}</span>
            </button>
          </div>
        )}
      </div>

      {/* 4. Collapsible Advanced Parameters Drawer */}
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
            <span>Advanced Execution & Persistence Directives</span>
          </div>
          <span className="text-[10px] font-mono text-app-muted uppercase">
            {isAdvancedDrawerOpen ? "Hide" : "Show"}
          </span>
        </button>

        {isAdvancedDrawerOpen && (
          <div className="divide-y divide-app-border-subtle pt-1">
            {Object.entries(activePhaseMeta?.parameterMeta || {})
              .filter(([k]) => k.startsWith("execution.") || k.includes("api_base"))
              .map(([k, meta]) => (
                <ParameterRow
                  key={k}
                  paramKey={k}
                  meta={meta as ParameterFieldMeta}
                  prefix="execution"
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
    </div>
  );
};
