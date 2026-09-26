import React from "react";
import {
  CheckCircle2,
  Eye,
  Layers,
  Sliders,
  TriangleAlert,
  Users,
  XCircle,
  HelpCircle,
} from "lucide-react";
import { useEvaluationStore } from "../../../../store/evaluationStore";

export interface CanvasEvaluationHudProps {
  borderlineCount?: number;
}

export const CanvasEvaluationHud: React.FC<CanvasEvaluationHudProps> = ({
  borderlineCount = 0,
}) => {
  const {
    graphOverlay,
    alignmentFilters,
    toggleAlignmentFilter,
    ghostOpacity,
    setGhostOpacity,
    bourbakiHullEnabled,
    setBourbakiHullEnabled,
    selectedBourbakiClasses,
    toggleBourbakiClass,
    setIsAmbiguousDrawerOpen,
  } = useEvaluationStore();

  const counts = graphOverlay?.summary_counts || {};
  const tpCount = (counts.tp_nodes ?? 0) + (counts.tp_edges ?? 0);
  const fpCount = (counts.fp_nodes ?? 0) + (counts.fp_edges ?? 0);
  const fnCount = (counts.fn_nodes ?? 0) + (counts.fn_edges ?? 0);
  const conflictCount = counts.conflict_edges ?? 0;

  const BOURBAKI_CLASSES = [
    { id: "Mp", label: "Mp", title: "Potential Models (Axiomatic framework)" },
    { id: "M", label: "M", title: "Actual Models (Specific laws)" },
    { id: "Mpp", label: "Mpp", title: "Partial Potential Models (Observables)" },
    { id: "C", label: "C", title: "Constraints (Cross-model connections)" },
    { id: "I", label: "I", title: "Intended Applications (Empirical claims)" },
  ];

  return (
    <div className="w-[230px] bg-app-surface/90 dark:bg-app-surface/95 backdrop-blur-md border border-app-border rounded-lg shadow-xl p-3 text-xs select-none space-y-3.5 transition-all">
      {/* HUD Header */}
      <div className="flex items-center justify-between border-b border-app-border/60 pb-2">
        <span className="font-semibold text-app-heading flex items-center gap-1.5 text-[11px] uppercase tracking-wider">
          <Sliders className="w-3.5 h-3.5 text-blue-500" />
          <span>Canvas HUD</span>
        </span>
        <span className="text-[10px] font-mono text-app-muted">
          {(graphOverlay?.nodes?.length ?? 0)}N · {(graphOverlay?.edges?.length ?? 0)}E
        </span>
      </div>

      {/* Alignment Toggles */}
      <div className="space-y-1.5">
        <div className="text-[10px] uppercase font-semibold text-app-muted tracking-wider">
          Alignment Filter
        </div>

        {/* True Positives */}
        <label className="flex items-center justify-between px-2 py-1 rounded cursor-pointer hover:bg-app-subtle transition-colors group">
          <div className="flex items-center gap-2 min-w-0">
            <input
              type="checkbox"
              checked={alignmentFilters.tp}
              onChange={() => toggleAlignmentFilter("tp")}
              className="rounded border-app-border text-emerald-600 focus:ring-0 w-3.5 h-3.5 cursor-pointer"
            />
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
              <span className="text-xs text-app-text group-hover:text-app-heading">
                True Positives
              </span>
            </div>
          </div>
          <span className="font-mono text-[10px] tabular-nums px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            {tpCount}
          </span>
        </label>

        {/* False Positives */}
        <label className="flex items-center justify-between px-2 py-1 rounded cursor-pointer hover:bg-app-subtle transition-colors group">
          <div className="flex items-center gap-2 min-w-0">
            <input
              type="checkbox"
              checked={alignmentFilters.fp}
              onChange={() => toggleAlignmentFilter("fp")}
              className="rounded border-app-border text-rose-600 focus:ring-0 w-3.5 h-3.5 cursor-pointer"
            />
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-500 shrink-0" />
              <span className="text-xs text-app-text group-hover:text-app-heading">
                False Positives
              </span>
            </div>
          </div>
          <span className="font-mono text-[10px] tabular-nums px-1.5 py-0.2 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400">
            {fpCount}
          </span>
        </label>

        {/* Ghost False Negatives */}
        <label className="flex items-center justify-between px-2 py-1 rounded cursor-pointer hover:bg-app-subtle transition-colors group">
          <div className="flex items-center gap-2 min-w-0">
            <input
              type="checkbox"
              checked={alignmentFilters.fn}
              onChange={() => toggleAlignmentFilter("fn")}
              className="rounded border-app-border text-zinc-500 focus:ring-0 w-3.5 h-3.5 cursor-pointer"
            />
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full border border-dashed border-zinc-400 dark:border-zinc-500 bg-zinc-400/30 shrink-0" />
              <span className="text-xs text-app-text group-hover:text-app-heading">
                Ghost Omissions
              </span>
            </div>
          </div>
          <span className="font-mono text-[10px] tabular-nums px-1.5 py-0.2 rounded bg-zinc-500/10 text-zinc-600 dark:text-zinc-400">
            {fnCount}
          </span>
        </label>

        {/* Polarity Inversions */}
        <label className="flex items-center justify-between px-2 py-1 rounded cursor-pointer hover:bg-app-subtle transition-colors group">
          <div className="flex items-center gap-2 min-w-0">
            <input
              type="checkbox"
              checked={alignmentFilters.polarity}
              onChange={() => toggleAlignmentFilter("polarity")}
              className="rounded border-app-border text-amber-500 focus:ring-0 w-3.5 h-3.5 cursor-pointer"
            />
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
              <span className="text-xs text-app-text group-hover:text-app-heading">
                Polarity Conflicts
              </span>
            </div>
          </div>
          <span className="font-mono text-[10px] tabular-nums px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400">
            {conflictCount}
          </span>
        </label>
      </div>

      {/* Ghost Opacity Slider */}
      <div className="space-y-1.5 pt-2 border-t border-app-border/60">
        <div className="flex items-center justify-between text-[10px]">
          <span className="uppercase font-semibold text-app-muted tracking-wider flex items-center gap-1">
            <Eye className="w-3 h-3 text-app-muted" />
            Ghost Opacity
          </span>
          <span className="font-mono text-app-text font-medium tabular-nums">
            {Math.round(ghostOpacity * 100)}%
          </span>
        </div>
        <input
          type="range"
          min="0.10"
          max="1.0"
          step="0.05"
          value={ghostOpacity}
          onChange={(e) => setGhostOpacity(parseFloat(e.target.value))}
          className="w-full accent-blue-600 h-1 bg-app-border rounded-lg appearance-none cursor-pointer"
        />
      </div>

      {/* Bourbaki Model Class Filter & Hull Toggle */}
      <div className="space-y-2 pt-2 border-t border-app-border/60">
        <div className="flex items-center justify-between text-[10px]">
          <span className="uppercase font-semibold text-app-muted tracking-wider flex items-center gap-1">
            <Layers className="w-3 h-3 text-blue-500" />
            Bourbaki Hulls
          </span>
          <button
            onClick={() => setBourbakiHullEnabled(!bourbakiHullEnabled)}
            className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors ${
              bourbakiHullEnabled
                ? "bg-blue-600 text-white"
                : "bg-app-bg text-app-muted hover:text-app-text border border-app-border"
            }`}
          >
            {bourbakiHullEnabled ? "Active" : "Off"}
          </button>
        </div>

        {/* Bourbaki class pills */}
        <div className="flex items-center gap-1">
          {BOURBAKI_CLASSES.map((cls) => {
            const isSelected = selectedBourbakiClasses.has(cls.id);
            return (
              <button
                key={cls.id}
                onClick={() => toggleBourbakiClass(cls.id)}
                title={cls.title}
                className={`flex-1 py-0.5 text-[10px] font-mono font-medium rounded transition-colors text-center border ${
                  isSelected
                    ? "bg-blue-600/10 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400 border-blue-500/30"
                    : "bg-app-bg/50 text-app-muted hover:text-app-text border-app-border/60 opacity-60"
                }`}
              >
                {cls.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Ambiguous Halos Card */}
      <div className="pt-2 border-t border-app-border/60">
        <div className="p-2 rounded bg-violet-500/10 dark:bg-violet-500/15 border border-violet-500/30 space-y-1.5">
          <div className="flex items-center justify-between text-violet-700 dark:text-violet-300">
            <span className="flex items-center gap-1 text-[11px] font-semibold">
              <Users className="w-3.5 h-3.5" />
              Ambiguous Halos
            </span>
            <span className="font-mono text-[10px] font-bold px-1.5 py-0.2 rounded bg-violet-500/20">
              {borderlineCount}
            </span>
          </div>
          <p className="text-[10px] text-violet-700/80 dark:text-violet-300/80 leading-tight">
            Borderline alignments (&tau; &isin; [0.75, 0.88]).
          </p>
          <button
            onClick={() => setIsAmbiguousDrawerOpen(true)}
            className="w-full mt-1 px-2 py-1 rounded text-[11px] font-medium bg-violet-600 hover:bg-violet-700 text-white transition-colors shadow-2xs text-center"
          >
            Resolve Drawer
          </button>
        </div>
      </div>
    </div>
  );
};
