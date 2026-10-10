import React from "react";
import {AlertTriangle, ArrowRight, Database, X} from "lucide-react";

export interface DatabaseCollisionModalProps {
  isOpen: boolean;
  databaseName: string;
  conflictingRunIds: string[];
  onProceed: () => void;
  onCancel: () => void;
  onChangeDatabase?: () => void;
}

export const DatabaseCollisionModal: React.FC<DatabaseCollisionModalProps> = ({
  isOpen,
  databaseName,
  conflictingRunIds,
  onProceed,
  onCancel,
  onChangeDatabase,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="relative w-full max-w-md rounded-xl border border-amber-500/30 bg-slate-900 p-6 shadow-2xl text-slate-100 space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-100">
                Database Collision Warning
              </h3>
              <p className="text-xs text-slate-400">
                Target database is already in use
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="rounded p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="space-y-3 text-xs leading-relaxed text-slate-300">
          <p>
            The selected database <strong className="font-mono text-amber-400 font-semibold">{databaseName}</strong> has
            already been written to by {conflictingRunIds.length === 1 ? "a previous run" : `${conflictingRunIds.length} previous runs`}:
          </p>

          <div className="max-h-28 overflow-y-auto rounded-md border border-slate-800 bg-slate-950/60 p-2 space-y-1 font-mono text-[11px] text-slate-400">
            {conflictingRunIds.map((id) => (
              <div key={id} className="flex items-center gap-1.5 truncate">
                <Database className="w-3 h-3 text-amber-400/70 shrink-0" />
                <span className="truncate">{id}</span>
              </div>
            ))}
          </div>

          <div className="rounded-md border border-amber-500/20 bg-amber-500/5 p-2.5 text-[11px] text-amber-300/90 leading-tight">
            <strong>Caution:</strong> Launching another run against this database may overwrite existing graph entities, merge unrelated claims, or pollute epistemic evaluation metrics.
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end gap-2 pt-2 border-t border-slate-800">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
          >
            Cancel
          </button>

          {onChangeDatabase && (
            <button
              type="button"
              onClick={onChangeDatabase}
              className="rounded-lg px-3 py-1.5 text-xs font-medium bg-slate-800 text-slate-200 hover:bg-slate-700 border border-slate-700 transition-colors"
            >
              Change Database
            </button>
          )}

          <button
            type="button"
            onClick={onProceed}
            className="flex items-center justify-center gap-1 rounded-lg px-3.5 py-1.5 text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white shadow-xs transition-colors"
          >
            <span>Proceed Anyway</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
