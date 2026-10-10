import React, {useEffect, useState} from "react";
import {useProjectSettingsStore} from "../store/projectSettingsStore";
import {Activity, AlertTriangle, CheckCircle2, Database, Eye, EyeOff, RefreshCw, X,} from "lucide-react";

export const ProjectSettingsModal: React.FC = () => {
  const {
    isProjectSettingsOpen,
    closeProjectSettings,
    langfuseHost,
    setLangfuseHost,
    langfusePublicKey,
    setLangfusePublicKey,
    langfuseSecretKey,
    setLangfuseSecretKey,
    langfuseStatus,
    isTesting,
    testFeedback,
    testConnection,
    fetchLangfuseStatus,
    promptProvider,
    setPromptProvider,
    promptLabel,
    setPromptLabel,
    stageRefreshIntervalSeconds,
    setStageRefreshIntervalSeconds,
    advancedVisualizations,
    setAdvancedVisualizations,
    confidenceProgressionInterval,
    setConfidenceProgressionInterval,
  } = useProjectSettingsStore();

  const [showSecretKey, setShowSecretKey] = useState(false);

  useEffect(() => {
    if (isProjectSettingsOpen) {
      fetchLangfuseStatus();
    }
  }, [isProjectSettingsOpen, fetchLangfuseStatus]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isProjectSettingsOpen) {
        closeProjectSettings();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isProjectSettingsOpen, closeProjectSettings]);

  if (!isProjectSettingsOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs select-none animate-in fade-in duration-150"
      onClick={closeProjectSettings}
    >
      <div
        className="w-full max-w-xl bg-app-surface border border-app-border rounded-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh] text-xs text-app-text"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-app-border bg-app-surface shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-md bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-500 shrink-0">
              <Database className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-app-heading leading-tight">
                Project Settings & Infrastructure
              </h2>
              <span className="text-[11px] text-app-muted">
                Static telemetry credentials and prompt governance policies
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-app-muted px-1.5 py-0.5 rounded bg-app-subtle border border-app-border">
              ESC
            </span>
            <button
              onClick={closeProjectSettings}
              className="p-1 rounded-md text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
              title="Close (Esc)"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs select-text">
          {/* Section 1: Langfuse Connection */}
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1.5 border-b border-app-border">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    langfuseStatus?.connected
                      ? "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]"
                      : langfuseStatus?.configured
                      ? "bg-blue-500"
                      : "bg-app-muted"
                  }`}
                />
                <h3 className="text-xs font-semibold text-app-heading">
                  Langfuse Observability & Telemetry
                </h3>
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={fetchLangfuseStatus}
                  disabled={isTesting}
                  className="h-6 px-2 inline-flex items-center gap-1 rounded border border-app-border bg-app-surface hover:bg-app-subtle text-[11px] text-app-muted hover:text-app-heading transition-colors cursor-pointer"
                  title="Reload configuration from .env file"
                >
                  <RefreshCw className={`w-3 h-3 ${isTesting ? "animate-spin" : ""}`} />
                  <span>Reload .env</span>
                </button>
                <button
                  type="button"
                  onClick={testConnection}
                  disabled={isTesting}
                  className="h-6 px-2.5 inline-flex items-center gap-1 rounded bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-medium transition-colors cursor-pointer disabled:opacity-50"
                  title="Test connection against Langfuse host"
                >
                  <Activity className="w-3 h-3" />
                  <span>{isTesting ? "Testing..." : "Test Connection"}</span>
                </button>
              </div>
            </div>

            <p className="text-[11px] text-app-muted leading-relaxed">
              Langfuse captures multi-phase LLM trace spans, token counts, and cost telemetry.
              Credentials set here apply project-wide and do not invalidate cached intermediate artifacts.
            </p>

            {/* Test feedback notice */}
            {testFeedback && (
              <div
                className={`p-2.5 rounded text-[11px] flex items-center gap-2 border ${
                  testFeedback.success
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
                    : "bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400"
                }`}
              >
                {testFeedback.success ? (
                  <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                ) : (
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                )}
                <span>{testFeedback.message}</span>
              </div>
            )}

            <div className="space-y-3 pt-1">
              {/* Host URL */}
              <div className="space-y-1">
                <label className="block text-[11px] font-medium text-app-heading">
                  Langfuse Host URL
                </label>
                <input
                  type="text"
                  value={langfuseHost}
                  onChange={(e) => setLangfuseHost(e.target.value)}
                  placeholder="http://localhost:3000"
                  className="w-full h-8 px-2.5 rounded bg-app-bg text-app-heading border border-app-border text-xs font-mono focus:outline-none focus:border-blue-500"
                />
                <span className="text-[10px] text-app-muted block">
                  Self-hosted server address or cloud endpoint (e.g. https://cloud.langfuse.com)
                </span>
              </div>

              {/* Public Key */}
              <div className="space-y-1">
                <label className="block text-[11px] font-medium text-app-heading">
                  Public API Key <span className="font-mono text-[10px] text-app-muted">(LANGFUSE_PUBLIC_KEY)</span>
                </label>
                <input
                  type="text"
                  value={langfusePublicKey}
                  onChange={(e) => setLangfusePublicKey(e.target.value)}
                  placeholder={langfuseStatus?.public_key_preview || "pk-lf-..."}
                  className="w-full h-8 px-2.5 rounded bg-app-bg text-app-heading border border-app-border text-xs font-mono focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Secret Key */}
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-[11px] font-medium text-app-heading">
                    Secret API Key <span className="font-mono text-[10px] text-app-muted">(LANGFUSE_SECRET_KEY)</span>
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowSecretKey(!showSecretKey)}
                    className="flex items-center gap-1 text-[10px] text-app-muted hover:text-app-heading cursor-pointer"
                  >
                    {showSecretKey ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                    <span>{showSecretKey ? "Hide" : "Show"}</span>
                  </button>
                </div>
                <input
                  type={showSecretKey ? "text" : "password"}
                  value={langfuseSecretKey}
                  onChange={(e) => setLangfuseSecretKey(e.target.value)}
                  placeholder={
                    langfuseStatus?.has_secret_key
                      ? "•••••••••••••••• (prepopulated from .env)"
                      : "sk-lf-..."
                  }
                  className="w-full h-8 px-2.5 rounded bg-app-bg text-app-heading border border-app-border text-xs font-mono focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Section 2: Prompt Governance Source */}
          <div className="space-y-3 pt-3 border-t border-app-border">
            <div className="pb-1 border-b border-app-border">
              <h3 className="text-xs font-semibold text-app-heading">
                Prompt Governance Source of Truth
              </h3>
            </div>
            <p className="text-[11px] text-app-muted leading-relaxed">
              Define whether computational stages resolve static built-in templates from code or fetch versioned prompt releases from the remote Langfuse prompt registry.
            </p>

            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="radio"
                  name="promptProvider"
                  value="default"
                  checked={promptProvider === "default"}
                  onChange={() => setPromptProvider("default")}
                  className="text-blue-600 focus:ring-0 cursor-pointer"
                />
                <div>
                  <span className="font-medium text-app-heading text-xs block">Built-in Default</span>
                  <span className="text-[10px] text-app-muted block">Locally editable templates in repository</span>
                </div>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none ml-4">
                <input
                  type="radio"
                  name="promptProvider"
                  value="langfuse"
                  checked={promptProvider === "langfuse"}
                  onChange={() => setPromptProvider("langfuse")}
                  className="text-blue-600 focus:ring-0 cursor-pointer"
                />
                <div>
                  <span className="font-medium text-app-heading text-xs block">Langfuse Managed</span>
                  <span className="text-[10px] text-app-muted block">Versioned releases from remote registry</span>
                </div>
              </label>
            </div>

            {promptProvider === "langfuse" && (
              <div className="p-2.5 rounded bg-app-bg border border-app-border space-y-1.5 mt-2">
                <label className="block text-[11px] font-medium text-app-heading">
                  Release Label / Version Tag
                </label>
                <input
                  type="text"
                  value={promptLabel}
                  onChange={(e) => setPromptLabel(e.target.value)}
                  placeholder="production"
                  className="w-48 h-7 px-2 rounded bg-app-surface text-app-heading border border-app-border text-xs font-mono focus:outline-none focus:border-blue-500"
                />
                <span className="text-[10px] text-app-muted block">
                  Stages will dynamically bind prompts marked with this label (e.g. <code>production</code> or <code>staging</code>).
                </span>
              </div>
            )}
          </div>

          {/* Section 3: Telemetry & Live Execution Refresh */}
          <div className="space-y-3 pt-3 border-t border-app-border">
            <div className="pb-1 border-b border-app-border">
              <h3 className="text-xs font-semibold text-app-heading">
                Telemetry & Live Execution Refresh
              </h3>
            </div>
            <p className="text-[11px] text-app-muted leading-relaxed">
              Configure how frequently the stage detail view polls on-disk artifact yields and structural statistics while a pipeline execution run is active.
            </p>

            <div className="p-3 rounded bg-app-bg border border-app-border space-y-2">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <label className="text-[11px] font-medium text-app-heading block">
                    Stage Detail Refresh Interval
                  </label>
                  <span className="text-[10px] text-app-muted block">
                    Interval in seconds (default: 30s, range: 5s – 300s)
                  </span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <input
                    type="number"
                    min={5}
                    max={300}
                    value={stageRefreshIntervalSeconds}
                    onChange={(e) => setStageRefreshIntervalSeconds(Number(e.target.value))}
                    className="w-20 h-7 px-2 text-right rounded bg-app-surface text-app-heading border border-app-border text-xs font-mono focus:outline-none focus:border-blue-500"
                  />
                  <span className="text-xs text-app-muted font-mono">sec</span>
                </div>
              </div>
            </div>
          </div>

          {/* Section 4: Advanced Visualizations & Progression Replay */}
          <div className="space-y-3 pt-3 border-t border-app-border">
            <div className="pb-1 border-b border-app-border flex items-center justify-between">
              <h3 className="text-xs font-semibold text-app-heading">
                Advanced Visualizations & Progression Replay
              </h3>
              <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-500 border border-blue-500/20">
                Analytics
              </span>
            </div>
            <p className="text-[11px] text-app-muted leading-relaxed">
              Enables step-by-step replay scrubber on confidence score distributions for completed stages and captures progression snapshots at configurable intervals.
            </p>

            <div className="p-3 rounded bg-app-bg border border-app-border space-y-3">
              {/* Feature Toggle */}
              <div className="flex items-center justify-between gap-3">
                <div>
                  <label className="text-[11px] font-medium text-app-heading block">
                    Advanced Visualizations
                  </label>
                  <span className="text-[10px] text-app-muted block">
                    Show confidence progression replay controls on completed phases
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setAdvancedVisualizations(!advancedVisualizations)}
                  className={`w-9 h-5 flex items-center rounded-full p-0.5 transition-colors cursor-pointer ${
                    advancedVisualizations ? "bg-blue-600 justify-end" : "bg-app-border justify-start"
                  }`}
                  role="switch"
                  aria-checked={advancedVisualizations}
                >
                  <span className="w-4 h-4 rounded-full bg-white shadow-xs" />
                </button>
              </div>

              {/* Interval Setting */}
              <div className="pt-2.5 border-t border-app-border-subtle flex items-center justify-between gap-3">
                <div>
                  <label className="text-[11px] font-medium text-app-heading block">
                    Progression Capture Interval
                  </label>
                  <span className="text-[10px] text-app-muted block">
                    Capture snapshot every N emitted data points (default: 20, range: 5 – 200)
                  </span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <input
                    type="number"
                    min={5}
                    max={200}
                    step={5}
                    value={confidenceProgressionInterval}
                    onChange={(e) => setConfidenceProgressionInterval(Number(e.target.value))}
                    className="w-20 h-7 px-2 text-right rounded bg-app-surface text-app-heading border border-app-border text-xs font-mono focus:outline-none focus:border-blue-500"
                  />
                  <span className="text-xs text-app-muted font-mono">pts</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-app-border bg-app-surface flex items-center justify-between text-xs text-app-muted shrink-0">
          <span className="text-[11px]">Settings persist across browser sessions</span>
          <button
            onClick={closeProjectSettings}
            className="px-3.5 py-1.5 rounded-md bg-app-heading text-app-surface font-medium hover:opacity-90 transition-opacity cursor-pointer text-xs"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
