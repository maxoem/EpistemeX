import React from "react";
import { ArrowUpRight, Cpu, Network, RotateCw, Sliders, Sparkles, Wrench } from "lucide-react";
import { useNavigationStore } from "../../../store/navigationStore.ts";
import { useEngineSettingsStore } from "../../../store/engineSettingsStore.ts";
import { useEvaluationStore } from "../../../store/evaluationStore.ts";
import {
  EpistemicHookType,
  openPredicateInEngine,
  openArgRelationInEngine,
  openPhasePromptInExecution,
  isolateCycleInCanvas,
} from "./actionableHooks.ts";

export type { EpistemicHookType };
export {
  openPredicateInEngine,
  openArgRelationInEngine,
  openPhasePromptInExecution,
  isolateCycleInCanvas,
};

export interface ActionableHookPillProps {
  type: EpistemicHookType;
  label?: string;
  predicate?: string;
  relationId?: string;
  sourceNode?: string;
  targetNode?: string;
  assertionId?: string;
  sourceText?: string;
  phaseKey?: string;
  promptKey?: string;
  cycleNodes?: string[];
  className?: string;
  onClick?: () => void;
}

export const ActionableHookPill: React.FC<ActionableHookPillProps> = ({
  type,
  label,
  predicate,
  relationId,
  sourceNode,
  targetNode,
  assertionId,
  sourceText,
  phaseKey,
  promptKey,
  cycleNodes,
  className = "",
  onClick,
}) => {
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onClick) {
      onClick();
      return;
    }

    switch (type) {
      case "schema_drift":
        if (predicate) {
          openPredicateInEngine(predicate);
        } else {
          useEngineSettingsStore.getState().setActiveCategory("unmapped");
          useNavigationStore.getState().setActiveTab("engine");
        }
        break;

      case "argument_polarity":
        openArgRelationInEngine(relationId || "SUPPORTS");
        break;

      case "overconfidence":
        openPhasePromptInExecution({
          phaseKey: phaseKey || "phase2",
          promptKey: promptKey || "entity_extraction",
          sourceText,
          assertionId,
        });
        break;

      case "dag_cycle":
        if (cycleNodes && cycleNodes.length > 0) {
          isolateCycleInCanvas(cycleNodes);
        } else {
          useEvaluationStore.getState().setActiveSubTab("canvas");
        }
        break;
    }
  };

  const getConfig = () => {
    switch (type) {
      case "schema_drift":
        return {
          icon: Cpu,
          defaultLabel: predicate ? `Map "${predicate}" in Engine` : "Open Engine Schema",
          bg: "bg-purple-500/10 hover:bg-purple-500/20 text-purple-600 dark:text-purple-400 border-purple-500/30",
          title: "Jump to Engine Settings to map predicate or configure ontology aliases",
        };
      case "argument_polarity":
        return {
          icon: Sliders,
          defaultLabel: label || "Configure Polarity Criteria in Engine",
          bg: "bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 dark:text-amber-400 border-amber-500/30",
          title: "Open Engine Settings ontology to audit argument relation polarity rules",
        };
      case "overconfidence":
        return {
          icon: Wrench,
          defaultLabel: label || "Tune Extraction Prompt in Execution",
          bg: "bg-blue-600 hover:bg-blue-700 text-white border-transparent",
          title: "Pre-load source passage into Execution Workbench prompt playground",
        };
      case "dag_cycle":
        return {
          icon: RotateCw,
          defaultLabel: label || "Isolate Cycle on Canvas",
          bg: "bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 border-rose-500/30",
          title: "Navigate to Topological Canvas and isolate circular entailment back-edges",
        };
    }
  };

  const config = getConfig();
  const Icon = config.icon;
  const displayLabel = label || config.defaultLabel;

  return (
    <button
      type="button"
      onClick={handleClick}
      title={config.title}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border transition-colors cursor-pointer ${config.bg} ${className}`}
    >
      <Icon className="w-3.5 h-3.5 shrink-0" />
      <span>{displayLabel}</span>
      <ArrowUpRight className="w-3 h-3 opacity-70 shrink-0" />
    </button>
  );
};
