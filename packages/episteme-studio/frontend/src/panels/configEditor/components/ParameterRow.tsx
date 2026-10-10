import React from "react";
import {FieldProvenance} from "../../../api/types";
import {ParameterFieldMeta} from "../../phaseConfig/phaseRegistry";

interface ParameterRowProps {
  paramKey: string;
  meta: ParameterFieldMeta;
  prefix: string;
  patch: Record<string, any>;
  configValues?: Record<string, any>;
  provenanceMap?: Record<string, string>;
  onUpdateField: (fieldPath: string, value: any) => void;
  onClearField: (fieldPath: string) => void;
}

export const ParameterRow: React.FC<ParameterRowProps> = ({
  paramKey,
  meta,
  prefix,
  patch,
  configValues,
  provenanceMap,
  onUpdateField,
  onClearField,
}) => {
  const fullPath = paramKey.includes(".") ? paramKey : `${prefix}.${paramKey}`;
  const isOverridden = patch[fullPath] !== undefined;
  const currentValue = isOverridden
    ? patch[fullPath]
    : configValues?.[fullPath] ?? meta.defaultValue ?? "";
  const provenance: FieldProvenance = isOverridden
    ? "override"
    : (provenanceMap?.[fullPath] as FieldProvenance) || "default";

  const isBooleanField = typeof currentValue === "boolean";
  const isZeroToOne =
    paramKey.includes("threshold") ||
    paramKey.includes("temperature") ||
    paramKey.includes("confidence") ||
    paramKey.includes("weight") ||
    (typeof currentValue === "number" && currentValue >= 0 && currentValue <= 1);
  const isNumeric = typeof currentValue === "number" || isZeroToOne;

  return (
    <div
      key={fullPath}
      className="py-3 px-1 border-b border-app-border-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-app-subtle/30 transition-colors"
    >
      <div className="flex-1 min-w-0 pr-2">
        <div className="flex items-center gap-2">
          <span className="font-medium text-xs text-app-heading">{meta.label}</span>
          <span
            className={`px-1.5 py-0.2 rounded text-[9px] font-mono border uppercase tracking-wider ${
              provenance === "override"
                ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30"
                : provenance === "profile"
                ? "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/30"
                : "bg-app-subtle text-app-muted border-app-border"
            }`}
            title={`Source: ${fullPath}`}
          >
            {provenance}
          </span>
          {meta.isAdvanced && (
            <span className="px-1 py-0.2 rounded text-[9px] font-mono bg-app-subtle text-app-muted border border-app-border">
              Advanced
            </span>
          )}
        </div>
        {meta.description && (
          <p className="text-[11px] text-app-muted mt-0.5 leading-snug">{meta.description}</p>
        )}
      </div>

      <div className="shrink-0 self-start sm:self-auto flex items-center gap-2">
        {isBooleanField ? (
          <label className="inline-flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={Boolean(currentValue)}
              onChange={(e) => onUpdateField(fullPath, e.target.checked)}
              className="w-3.5 h-3.5 rounded border border-app-border text-blue-600 focus:ring-0 cursor-pointer"
            />
            <span className="font-mono text-xs text-app-heading">
              {currentValue ? "true" : "false"}
            </span>
          </label>
        ) : isZeroToOne ? (
          <div className="flex items-center gap-2 w-56">
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={Number(currentValue) || 0}
              onChange={(e) => onUpdateField(fullPath, parseFloat(e.target.value))}
              className="flex-1 accent-blue-600 cursor-pointer h-1.5 bg-app-subtle rounded-lg"
            />
            <input
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={Number(currentValue).toFixed(2)}
              onChange={(e) => onUpdateField(fullPath, parseFloat(e.target.value) || 0)}
              className="w-16 h-7 px-1.5 text-right font-mono text-xs rounded bg-app-bg text-app-heading border border-app-border focus:outline-none focus:border-blue-500"
            />
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <input
              type={isNumeric ? "number" : "text"}
              value={currentValue}
              onChange={(e) => {
                const val = isNumeric ? parseFloat(e.target.value) || 0 : e.target.value;
                onUpdateField(fullPath, val);
              }}
              className="h-7 w-48 px-2 font-mono text-xs rounded bg-app-bg text-app-heading border border-app-border focus:outline-none focus:border-blue-500"
            />
            {meta.unit && <span className="text-[10px] text-app-muted font-mono">[{meta.unit}]</span>}
          </div>
        )}

        {isOverridden && (
          <button
            type="button"
            onClick={() => onClearField(fullPath)}
            className="text-[10px] font-mono text-app-muted hover:text-app-heading underline cursor-pointer uppercase ml-1"
            title="Reset to default value"
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
};
