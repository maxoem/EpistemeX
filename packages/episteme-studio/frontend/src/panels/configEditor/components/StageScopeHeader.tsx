import React from "react";
import {ChevronDown, RotateCcw} from "lucide-react";
import {AvailableInputDoc} from "../../../api/types";

interface StageScopeHeaderProps {
  selectedInputPath: string;
  setSelectedInputPath: (path: string) => void;
  availableInputs: AvailableInputDoc[];

  executionMode: "single" | "corpus";
  setExecutionMode: (mode: "single" | "corpus") => void;

  selectedProfile: string;
  setSelectedProfile: (prof: string) => void;
  profiles: string[];

  patchCount: number;
  clearPatch: () => void;
}

export const StageScopeHeader: React.FC<StageScopeHeaderProps> = ({
  selectedInputPath,
  setSelectedInputPath,
  availableInputs,
  executionMode,
  setExecutionMode,
  selectedProfile,
  setSelectedProfile,
  profiles,
  patchCount,
  clearPatch,
}) => {
  return (
    <div className="h-11 px-6 border-b border-app-border bg-app-surface/90 backdrop-blur-sm flex items-center justify-between gap-4 shrink-0 select-none">
      <div className="flex items-center gap-3 min-w-0">
        {/* Document Target Selector */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-app-muted font-medium">Target:</span>
          <div className="relative">
            <select
              value={selectedInputPath}
              onChange={(e) => setSelectedInputPath(e.target.value)}
              className="h-7.5 pl-2.5 pr-7 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 text-app-heading border border-app-border font-medium text-xs focus:outline-none focus:border-blue-500/80 cursor-pointer appearance-none max-w-[240px] truncate transition-colors"
              title={selectedInputPath}
            >
              {availableInputs.map((input) => (
                <option key={input.path} value={input.path}>
                  {input.name}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 absolute right-2 top-1/2 -translate-y-1/2 text-app-muted pointer-events-none" />
          </div>
        </div>

        {/* Scope Mode Switch (Single Document vs Full Corpus) */}
        <div className="p-0.5 inline-flex items-center bg-app-subtle rounded-md border border-app-border/60 gap-0.5 text-xs">
          <button
            type="button"
            onClick={() => setExecutionMode("single")}
            className={`h-6 px-2.5 rounded text-[11px] transition-all cursor-pointer font-medium ${
              executionMode === "single"
                ? "bg-app-surface text-app-heading shadow-xs font-semibold border border-app-border/80"
                : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
            }`}
          >
            Single Document
          </button>
          <button
            type="button"
            onClick={() => setExecutionMode("corpus")}
            className={`h-6 px-2.5 rounded text-[11px] transition-all cursor-pointer font-medium ${
              executionMode === "corpus"
                ? "bg-app-surface text-app-heading shadow-xs font-semibold border border-app-border/80"
                : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
            }`}
          >
            Full Corpus
          </button>
        </div>

      </div>

      {/* Right Header Actions */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Profile Selector */}
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-app-muted font-mono text-[11px]">Profile:</span>
          <select
            value={selectedProfile}
            onChange={(e) => {
              setSelectedProfile(e.target.value);
              clearPatch();
            }}
            className="h-7 px-2.5 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 text-app-heading border border-app-border text-xs font-mono focus:outline-none cursor-pointer transition-colors"
          >
            {profiles.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        {/* Reset Overrides */}
        {patchCount > 0 && (
          <button
            type="button"
            onClick={clearPatch}
            className="h-7 px-2.5 rounded border border-app-border bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-heading text-xs font-mono transition-colors cursor-pointer inline-flex items-center gap-1"
            title="Discard all staged parameter modifications"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Reset ({patchCount})</span>
          </button>
        )}
      </div>
    </div>
  );
};
