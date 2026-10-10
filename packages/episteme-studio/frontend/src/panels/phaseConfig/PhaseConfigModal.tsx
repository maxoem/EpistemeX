import React, {useEffect, useMemo, useState} from "react";
import {PhaseStatus} from "../../api/types";
import {getAvailablePhaseTabs, resolvePhaseConfig, resolvePhaseKey} from "./phaseConfigResolver";
import {PhaseConfigViewer} from "./PhaseConfigViewer";
import {SlidersHorizontal, Sparkles, X,} from "lucide-react";

export interface PhaseConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  activePhase: PhaseStatus | { phase_name?: string; phase_ordinal?: number; key?: string } | null;
  allPhases?: PhaseStatus[];
  configSnapshot: Record<string, any>;
  runId?: string;
}

export const PhaseConfigModal: React.FC<PhaseConfigModalProps> = ({
  isOpen,
  onClose,
  activePhase,
  allPhases = [],
  configSnapshot = {},
  runId,
}) => {
  // Current active phase key in modal
  const initialKey = useMemo(() => {
    return activePhase ? resolvePhaseKey(activePhase) : "phase1";
  }, [activePhase]);

  const [selectedPhaseKey, setSelectedPhaseKey] = useState<string>(initialKey);

  // Synchronize when activePhase changes from outside
  useEffect(() => {
    if (activePhase) {
      setSelectedPhaseKey(resolvePhaseKey(activePhase));
    }
  }, [activePhase]);

  // Handle ESC key to dismiss modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Available tabs
  const tabs = useMemo(() => {
    return getAvailablePhaseTabs(configSnapshot, allPhases);
  }, [configSnapshot, allPhases]);

  // Resolve config descriptor for current selected phase key
  const descriptor = useMemo(() => {
    // Find phase record matching selectedPhaseKey if available
    const matchingRecord = allPhases.find((p) => resolvePhaseKey(p) === selectedPhaseKey);
    const target = matchingRecord || {
      phase_name: tabs.find((t) => t.key === selectedPhaseKey)?.label || selectedPhaseKey,
      phase_ordinal: tabs.find((t) => t.key === selectedPhaseKey)?.ordinal || 1,
      key: selectedPhaseKey,
    };
    return resolvePhaseConfig(target, configSnapshot);
  }, [selectedPhaseKey, allPhases, configSnapshot, tabs]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-black/60 backdrop-blur-xs select-none animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="w-full max-w-4xl bg-app-surface border border-app-border rounded-xl shadow-2xl overflow-hidden flex flex-col h-[85vh] max-h-[820px] select-text"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-app-border bg-app-surface shrink-0">
          <div className="flex items-center space-x-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/25 flex items-center justify-center text-cyan-500 shrink-0">
              <SlidersHorizontal className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="flex items-center justify-center w-5 h-5 rounded-full bg-app-subtle text-[10px] font-mono font-bold text-app-heading border border-app-border shrink-0">
                  {descriptor.phaseOrdinal}
                </span>
                <h2 className="text-sm font-semibold text-app-heading truncate">
                  {descriptor.phaseName}
                </h2>
              </div>
              {runId && (
                <p className="text-[11px] text-app-muted font-mono truncate mt-0.5">
                  Run: <span className="text-app-heading font-medium">{runId}</span>
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <span className="text-[10px] font-mono text-app-muted px-1.5 py-0.5 rounded bg-app-subtle border border-app-border">
              ESC
            </span>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
              title="Close overlay (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Phase Navigation Bar (Pills) */}
        {tabs.length > 1 && (
          <div className="px-5 py-2 bg-app-subtle/40 border-b border-app-border flex items-center gap-1.5 overflow-x-auto shrink-0 scrollbar-none">
            {tabs.map((tab) => {
              const isSelected = tab.key === selectedPhaseKey;
              return (
                <button
                  key={tab.key}
                  onClick={() => setSelectedPhaseKey(tab.key)}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium whitespace-nowrap transition-colors cursor-pointer shrink-0 ${
                    isSelected
                      ? "bg-app-surface text-app-heading shadow-xs border border-app-border font-semibold"
                      : "text-app-muted hover:text-app-heading hover:bg-app-surface/60"
                  }`}
                  title={tab.label}
                >
                  <span className="font-mono text-[10px] text-app-muted">
                    {tab.ordinal}
                  </span>
                  <span>{tab.shortLabel}</span>
                  {tab.hasPrompts && (
                    <Sparkles className="w-2.5 h-2.5 text-purple-400 shrink-0" />
                  )}
                </button>
              );
            })}
          </div>
        )}

        {/* Phase Configuration Viewer Content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <PhaseConfigViewer descriptor={descriptor} />
        </div>
      </div>
    </div>
  );
};
