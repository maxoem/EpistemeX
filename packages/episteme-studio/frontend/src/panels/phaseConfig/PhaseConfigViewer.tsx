import React, {useMemo, useState} from "react";
import {PhaseConfigDescriptor, PhaseConfigField} from "./types";
import {PromptTemplateViewer} from "./PromptTemplateViewer";
import {
    Check,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Copy,
    Eye,
    EyeOff,
    FileCode,
    Gauge,
    HardDrive,
    Percent,
    Search,
    Sliders,
    Sparkles,
    XCircle,
} from "lucide-react";

interface PhaseConfigViewerProps {
  descriptor: PhaseConfigDescriptor;
  onUpdateField?: (key: string, value: any) => void;
  isEditable?: boolean;
}

type ViewerTab = "hyperparameters" | "prompts" | "raw";

const isZeroToOneField = (field: PhaseConfigField): boolean => {
  if (field.valueType !== "number") return false;
  const k = field.key.toLowerCase();
  const isThreshold = k.includes("threshold") || k.includes("confidence") || k.includes("ratio") || k.includes("weight") || k.includes("temperature");
  const numVal = Number(field.value);
  return isThreshold || (!isNaN(numVal) && numVal >= 0 && numVal <= 1);
};

export const PhaseConfigViewer: React.FC<PhaseConfigViewerProps> = ({
  descriptor,
  onUpdateField,
  isEditable = false,
}) => {
  const [activeTab, setActiveTab] = useState<ViewerTab>("hyperparameters");
  const [isAdvancedMode, setIsAdvancedMode] = useState<boolean>(false);
  const [isAdvancedGroupOpen, setIsAdvancedGroupOpen] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [copiedRaw, setCopiedRaw] = useState(false);

  const { parameters, prompts, executionSettings, rawConfig, description, category } = descriptor;

  // Filter parameters by query
  const queryFilteredParams = useMemo(() => {
    return parameters.filter((p) => {
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (
        p.key.toLowerCase().includes(q) ||
        p.label.toLowerCase().includes(q) ||
        (p.description && p.description.toLowerCase().includes(q)) ||
        String(p.value).toLowerCase().includes(q)
      );
    });
  }, [parameters, searchQuery]);

  // Group into Probabilistic Thresholds (0.00 - 1.00 numeric fields) and Execution Limits (batch sizes, max candidates, hops, counts)
  const { probabilisticThresholds, executionLimits, generalParameters } = useMemo(() => {
    const thresholds: PhaseConfigField[] = [];
    const limits: PhaseConfigField[] = [];
    const general: PhaseConfigField[] = [];

    queryFilteredParams.forEach((field) => {
      if (isZeroToOneField(field)) {
        thresholds.push(field);
      } else if (
        field.valueType === "number" ||
        field.unit ||
        field.key.includes("batch") ||
        field.key.includes("size") ||
        field.key.includes("max") ||
        field.key.includes("depth") ||
        field.key.includes("top_k") ||
        field.group === "limits"
      ) {
        limits.push(field);
      } else {
        general.push(field);
      }
    });

    return {
      probabilisticThresholds: thresholds,
      executionLimits: limits,
      generalParameters: general,
    };
  }, [queryFilteredParams]);

  // Separate basic vs advanced parameters
  const basicThresholds = probabilisticThresholds.filter((p) => !p.isAdvanced);
  const advancedThresholds = probabilisticThresholds.filter((p) => p.isAdvanced);

  const basicLimits = executionLimits.filter((p) => !p.isAdvanced);
  const advancedLimits = executionLimits.filter((p) => p.isAdvanced);

  const basicGeneral = generalParameters.filter((p) => !p.isAdvanced);
  const advancedGeneral = generalParameters.filter((p) => p.isAdvanced);

  const hasAdvancedItems =
    advancedThresholds.length > 0 ||
    advancedLimits.length > 0 ||
    advancedGeneral.length > 0 ||
    executionSettings.some((e) => e.isAdvanced);

  const handleCopyRaw = () => {
    navigator.clipboard.writeText(JSON.stringify(rawConfig, null, 2));
    setCopiedRaw(true);
    setTimeout(() => setCopiedRaw(false), 1800);
  };

  const renderFieldDisplayOrInput = (field: PhaseConfigField) => {
    const { value, valueType, unit, key, defaultValue } = field;
    const isZeroToOne = isZeroToOneField(field);

    if (isZeroToOne) {
      const numVal = typeof value === "number" ? value : parseFloat(value) || 0;
      return (
        <div className="flex items-center gap-2.5 w-full sm:w-64">
          {isEditable ? (
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={numVal}
              onChange={(e) => onUpdateField?.(key, parseFloat(e.target.value))}
              className="flex-1 precision-slider"
            />
          ) : (
            <div className="flex-1 h-1 bg-app-border relative overflow-hidden">
              <div
                className="h-full bg-app-heading"
                style={{ width: `${Math.min(100, Math.max(0, numVal * 100))}%` }}
              />
            </div>
          )}
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            readOnly={!isEditable}
            value={numVal.toFixed(2)}
            onChange={(e) => isEditable && onUpdateField?.(key, parseFloat(e.target.value) || 0)}
            placeholder={defaultValue !== undefined ? `Default: ${defaultValue}` : undefined}
            className="w-16 h-6 px-1.5 text-right font-mono text-xs rounded-none bg-app-bg text-app-heading border border-app-border focus:outline-none focus:border-app-muted"
          />
        </div>
      );
    }

    if (valueType === "boolean") {
      if (isEditable) {
        return (
          <label className="inline-flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={Boolean(value)}
              onChange={(e) => onUpdateField?.(key, e.target.checked)}
              className="w-3.5 h-3.5 rounded-none border border-app-border bg-app-bg text-blue-600 focus:ring-0 cursor-pointer"
            />
            <span className="text-xs font-mono text-app-heading">
              {value ? "true" : "false"}
            </span>
          </label>
        );
      }
      return value ? (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-none text-[11px] font-mono bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
          <CheckCircle2 className="w-3 h-3" /> true
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-none text-[11px] font-mono bg-app-subtle text-app-muted border border-app-border">
          <XCircle className="w-3 h-3" /> false
        </span>
      );
    }

    if (valueType === "number") {
      return (
        <div className="flex items-center gap-1.5">
          <input
            type="number"
            readOnly={!isEditable}
            value={value ?? ""}
            onChange={(e) => isEditable && onUpdateField?.(key, parseFloat(e.target.value) || 0)}
            placeholder={defaultValue !== undefined ? `Default: ${defaultValue}` : undefined}
            className="w-24 h-6 px-1.5 text-right font-mono text-xs rounded-none bg-app-bg text-app-heading border border-app-border focus:outline-none focus:border-app-muted"
          />
          {unit && <span className="text-[10px] text-app-muted font-mono shrink-0">[{unit}]</span>}
        </div>
      );
    }

    if (valueType === "string") {
      return (
        <div className="flex items-center gap-1.5 w-full sm:max-w-xs">
          <input
            type="text"
            readOnly={!isEditable}
            value={value ?? ""}
            onChange={(e) => isEditable && onUpdateField?.(key, e.target.value)}
            placeholder={defaultValue !== undefined ? `Default: ${defaultValue}` : undefined}
            className="w-full h-6 px-2 font-mono text-xs rounded-none bg-app-bg text-app-heading border border-app-border focus:outline-none focus:border-app-muted"
          />
        </div>
      );
    }

    if (valueType === "array") {
      return (
        <div className="flex flex-wrap gap-1">
          {(value as any[]).map((item, idx) => (
            <span
              key={idx}
              className="font-mono text-[10px] px-1.5 py-0.2 rounded-none bg-app-subtle text-app-heading border border-app-border"
            >
              {typeof item === "object" ? JSON.stringify(item) : String(item)}
            </span>
          ))}
        </div>
      );
    }

    if (valueType === "null") {
      return <span className="text-[11px] font-mono text-app-muted italic">null</span>;
    }

    return (
      <pre className="text-[10px] font-mono p-1 rounded-none bg-app-bg text-app-heading max-h-20 overflow-auto border border-app-border">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  };

  const renderFieldRow = (field: PhaseConfigField) => {
    return (
      <div
        key={field.key}
        className="px-3 py-2 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-app-subtle/40 transition-colors"
      >
        <div className="flex flex-col min-w-0 pr-3 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold text-app-heading">
              {field.label}
            </span>
            <span className="font-mono text-[10px] text-app-muted select-all">
              ({field.key})
            </span>
            {field.isAdvanced && (
              <span className="px-1 py-0.2 rounded-none text-[9px] font-mono bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
                ADV
              </span>
            )}
          </div>
          {field.description && (
            <p className="text-[11px] text-app-muted mt-0.5 leading-tight">
              {field.description}
            </p>
          )}
        </div>
        <div className="shrink-0 self-start sm:self-auto">
          {renderFieldDisplayOrInput(field)}
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full overflow-hidden text-xs">
      {/* Sub-header with Category, Summary, Mode Toggle and Tabs */}
      <div className="px-4 py-2 border-b border-app-border bg-app-surface flex flex-col md:flex-row md:items-center justify-between gap-2.5 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="px-1.5 py-0.5 rounded-none bg-app-subtle text-app-text font-mono font-semibold text-[10px] border border-app-border shrink-0 uppercase tracking-wider">
            {category}
          </span>
          <p className="text-[11px] text-app-muted truncate max-w-md" title={description}>
            {description}
          </p>
        </div>

        {/* View Controls: Basic/Advanced Toggle & Sub-Tabs */}
        <div className="flex items-center gap-1.5 shrink-0 self-start md:self-auto">
          {/* Basic / Advanced Disclosure Toggle */}
          <button
            type="button"
            onClick={() => setIsAdvancedMode(!isAdvancedMode)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-none text-xs font-mono border transition-colors cursor-pointer ${
              isAdvancedMode
                ? "bg-purple-500/15 text-purple-600 dark:text-purple-300 border-purple-500/30"
                : "bg-app-bg text-app-muted hover:text-app-heading border-app-border"
            }`}
            title="Toggle between essential parameters and full advanced configuration"
          >
            {isAdvancedMode ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>{isAdvancedMode ? "Advanced View" : "Basic View"}</span>
          </button>

          {/* Sub-tabs: [Hyperparameters] and [Prompt Logic] */}
          <div className="flex items-center rounded-none bg-app-bg p-0.5 border border-app-border">
            <button
              onClick={() => setActiveTab("hyperparameters")}
              className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-none text-xs font-mono transition-colors cursor-pointer ${
                activeTab === "hyperparameters"
                  ? "bg-app-surface text-app-heading font-semibold border border-app-border"
                  : "text-app-muted hover:text-app-heading border border-transparent"
              }`}
            >
              <Sliders className="w-3 h-3 text-app-muted" />
              <span>Hyperparameters</span>
              <span className="ml-0.5 text-[10px] font-mono px-1 rounded-none bg-app-subtle text-app-muted">
                {parameters.length}
              </span>
            </button>

            {prompts.length > 0 && (
              <button
                onClick={() => setActiveTab("prompts")}
                className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-none text-xs font-mono transition-colors cursor-pointer ${
                  activeTab === "prompts"
                    ? "bg-app-surface text-app-heading font-semibold border border-app-border"
                    : "text-app-muted hover:text-app-heading border border-transparent"
                }`}
              >
                <Sparkles className="w-3 h-3 text-app-muted" />
                <span>Prompt Logic</span>
                <span className="ml-0.5 text-[10px] font-mono px-1 rounded-none bg-app-subtle text-app-heading font-semibold">
                  {prompts.length}
                </span>
              </button>
            )}

            <button
              onClick={() => setActiveTab("raw")}
              className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-none text-xs font-mono transition-colors cursor-pointer ${
                activeTab === "raw"
                  ? "bg-app-surface text-app-heading font-semibold border border-app-border"
                  : "text-app-muted hover:text-app-heading border border-transparent"
              }`}
            >
              <FileCode className="w-3 h-3 text-app-muted" />
              <span>Raw JSON</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Tab Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Tab 1: Hyperparameters */}
        {activeTab === "hyperparameters" && (
          <div className="space-y-4">
            {/* Search Filter Header */}
            {parameters.length > 3 && (
              <div className="relative max-w-sm">
                <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-app-muted pointer-events-none" />
                <input
                  type="text"
                  placeholder="Filter parameters..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full h-7 bg-app-bg text-app-heading placeholder-app-muted/60 text-xs font-mono rounded-none pl-7 pr-2.5 border border-app-border focus:outline-none focus:border-app-muted transition-colors"
                />
              </div>
            )}

            {/* Group 1: Probabilistic Thresholds (0.00 - 1.00 numeric continuous sliders) */}
            {(isAdvancedMode ? probabilisticThresholds : basicThresholds).length > 0 && (
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 pb-1 text-xs font-mono font-semibold text-app-heading uppercase tracking-wider border-b border-app-border">
                  <Percent className="w-3.5 h-3.5 text-app-muted" />
                  <span>Probabilistic Thresholds (0.00 – 1.00)</span>
                  <span className="text-[10px] font-mono text-app-muted font-normal lowercase">
                    continuous parameters
                  </span>
                </div>
                <div className="border border-app-border bg-app-surface divide-y divide-app-border overflow-hidden">
                  {(isAdvancedMode ? probabilisticThresholds : basicThresholds).map((field) =>
                    renderFieldRow(field)
                  )}
                </div>
              </div>
            )}

            {/* Group 2: Execution Limits (batch size, max candidates, hops, counts) */}
            {(isAdvancedMode ? executionLimits : basicLimits).length > 0 && (
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 pb-1 text-xs font-mono font-semibold text-app-heading uppercase tracking-wider border-b border-app-border">
                  <Gauge className="w-3.5 h-3.5 text-app-muted" />
                  <span>Execution Limits</span>
                  <span className="text-[10px] font-mono text-app-muted font-normal lowercase">
                    chunk ceilings, candidate limits & hop depths
                  </span>
                </div>
                <div className="border border-app-border bg-app-surface divide-y divide-app-border overflow-hidden">
                  {(isAdvancedMode ? executionLimits : basicLimits).map((field) =>
                    renderFieldRow(field)
                  )}
                </div>
              </div>
            )}

            {/* General Parameters (if any other parameters exist) */}
            {(isAdvancedMode ? generalParameters : basicGeneral).length > 0 && (
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 pb-1 text-xs font-mono font-semibold text-app-heading uppercase tracking-wider border-b border-app-border">
                  <Sliders className="w-3.5 h-3.5 text-app-muted" />
                  <span>General Parameters</span>
                </div>
                <div className="border border-app-border bg-app-surface divide-y divide-app-border overflow-hidden">
                  {(isAdvancedMode ? generalParameters : basicGeneral).map((field) =>
                    renderFieldRow(field)
                  )}
                </div>
              </div>
            )}

            {/* Collapsible Advanced Settings Section in Basic View */}
            {!isAdvancedMode && hasAdvancedItems && (
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => setIsAdvancedGroupOpen(!isAdvancedGroupOpen)}
                  className="flex items-center justify-between w-full px-3 py-2 rounded-none border border-app-border bg-app-bg hover:bg-app-subtle text-xs text-app-heading transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-2 font-mono font-semibold">
                    {isAdvancedGroupOpen ? (
                      <ChevronDown className="w-3.5 h-3.5 text-app-muted" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-app-muted" />
                    )}
                    <span>Advanced Settings</span>
                    <span className="text-[10px] font-mono px-1 py-0.2 rounded-none bg-app-subtle text-app-muted border border-app-border">
                      {advancedThresholds.length + advancedLimits.length + advancedGeneral.length} params
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-app-muted uppercase">
                    {isAdvancedGroupOpen ? "Collapse" : "Disclose"}
                  </span>
                </button>

                {isAdvancedGroupOpen && (
                  <div className="mt-1.5 border border-app-border bg-app-surface divide-y divide-app-border overflow-hidden">
                    {[...advancedThresholds, ...advancedLimits, ...advancedGeneral].map((field) =>
                      renderFieldRow(field)
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Execution / Persistence Settings */}
            {executionSettings.length > 0 && (
              <div className="pt-1 space-y-1.5">
                <div className="flex items-center gap-1.5 pb-1 text-xs font-mono font-semibold text-app-heading uppercase tracking-wider border-b border-app-border">
                  <HardDrive className="w-3.5 h-3.5 text-app-muted" />
                  <span>Execution & Persistence Directives</span>
                </div>
                <div className="border border-app-border bg-app-surface divide-y divide-app-border overflow-hidden">
                  {executionSettings.map((execField) => renderFieldRow(execField))}
                </div>
              </div>
            )}

            {queryFilteredParams.length === 0 && (
              <div className="p-6 text-center text-app-muted font-mono bg-app-surface border border-app-border">
                No parameters match "{searchQuery}".
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Prompt Logic (CodeMirror syntax highlighting & collapsible blocks) */}
        {activeTab === "prompts" && (
          <PromptTemplateViewer prompts={prompts} />
        )}

        {/* Tab 3: Raw JSON */}
        {activeTab === "raw" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-app-muted font-mono">
                Configuration snapshot for <code className="text-app-heading font-semibold">{descriptor.phaseKey}</code>:
              </span>
              <button
                onClick={handleCopyRaw}
                className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-none bg-app-surface hover:bg-app-subtle text-app-text hover:text-app-heading border border-app-border text-[11px] font-mono transition-colors cursor-pointer"
              >
                {copiedRaw ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-500" />
                    <span className="text-emerald-500">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3 text-app-muted" />
                    <span>Copy JSON</span>
                  </>
                )}
              </button>
            </div>

            <div className="p-2.5 bg-app-bg border border-app-border overflow-x-auto max-h-[60vh]">
              <pre className="text-[11px] font-mono leading-relaxed text-app-heading select-text">
                {JSON.stringify(rawConfig, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
