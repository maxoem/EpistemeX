import React, {useState} from "react";
import {GitRailNode} from "./types";
import {EPISTEMIC_TAXONOMY, EpistemicLayerTheme} from "../epistemicTheme";
import {ChevronDown, ChevronRight} from "lucide-react";
import {getShortStageLabel} from "../stageModel";

interface LayerRollupViewProps {
  nodes: GitRailNode[];
  selectedPhaseKey: string | null;
  onSelectPhase: (key: string | null) => void;
}

const formatDuration = (seconds?: number | null): string => {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
};

const LAYER_ORDER: ("L1" | "L2" | "L3" | "L4")[] = ["L1", "L2", "L3", "L4"];

export const LayerRollupView: React.FC<LayerRollupViewProps> = ({
  nodes,
  selectedPhaseKey,
  onSelectPhase,
}) => {
  const [collapsedLayers, setCollapsedLayers] = useState<Record<string, boolean>>({});

  const toggleLayer = (layerId: string) => {
    setCollapsedLayers((prev) => ({ ...prev, [layerId]: !prev[layerId] }));
  };

  const layersGrouped = React.useMemo(() => {
    const groups: Record<"L1" | "L2" | "L3" | "L4", GitRailNode[]> = {
      L1: [],
      L2: [],
      L3: [],
      L4: [],
    };

    nodes.forEach((node) => {
      groups[node.layerId].push(node);
    });

    return groups;
  }, [nodes]);

  return (
    <div className="flex flex-col divide-y divide-app-border overflow-y-auto">
      {LAYER_ORDER.map((layerId) => {
        const layerMeta: EpistemicLayerTheme = EPISTEMIC_TAXONOMY[layerId];
        const layerNodes = layersGrouped[layerId] || [];
        const isCollapsed = !!collapsedLayers[layerId];

        const totalYield = layerNodes.reduce(
          (acc, n) =>
            acc + (n.phaseRecord?.artifact_count ?? n.aggregateArtifactCount ?? 0),
          0
        );
        const totalDuration = layerNodes.reduce(
          (acc, n) =>
            acc + (n.phaseRecord?.duration_seconds ?? n.totalDurationSeconds ?? 0),
          0
        );

        return (
          <div key={layerId} className="flex flex-col">
            {/* Layer Section Header */}
            <div
              onClick={() => toggleLayer(layerId)}
              className="h-8 px-2.5 bg-app-subtle/70 flex items-center justify-between cursor-pointer hover:bg-app-subtle transition-colors select-none"
            >
              <div className="flex items-center gap-2">
                <span className="text-app-muted">
                  {isCollapsed ? (
                    <ChevronRight className="w-3 h-3" />
                  ) : (
                    <ChevronDown className="w-3 h-3" />
                  )}
                </span>
                <span
                  className="font-mono text-[10px] font-bold px-1.5 py-0.2 rounded"
                  style={{
                    color: layerMeta.color,
                    backgroundColor: layerMeta.lightBg,
                  }}
                >
                  {layerId}
                </span>
                <span className="text-[11px] font-semibold text-app-heading tracking-tight">
                  {layerMeta.name}
                </span>
                <span className="text-[10px] font-mono text-app-muted">
                  ({layerNodes.length} phases)
                </span>
              </div>

              <div className="flex items-center gap-2 font-mono text-[10px] tabular-nums text-app-muted">
                <span>n={totalYield.toLocaleString()}</span>
                <span className="w-10 text-right">{formatDuration(totalDuration)}</span>
              </div>
            </div>

            {/* Member Phase Rows */}
            {!isCollapsed && (
              <div className="flex flex-col divide-y divide-app-border">
                {layerNodes.map((node) => {
                  const isSelected = selectedPhaseKey === node.key;
                  const duration =
                    node.phaseRecord?.duration_seconds ||
                    node.totalDurationSeconds ||
                    0;
                  const yieldCount =
                    node.phaseRecord?.artifact_count ??
                    node.aggregateArtifactCount ??
                    0;

                  return (
                    <div
                      key={node.key}
                      onClick={() => onSelectPhase(node.key)}
                      className={`h-7 px-4 pl-8 flex items-center justify-between cursor-pointer transition-colors text-xs ${
                        isSelected
                          ? "bg-app-subtle text-app-heading font-semibold border-l-2 border-l-blue-600"
                          : "hover:bg-app-subtle/30 text-app-muted border-l-2 border-l-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0 flex-1 pr-2 truncate">
                        <span
                          className="w-1.5 h-1.5 rounded-full shrink-0"
                          style={{ backgroundColor: layerMeta.color }}
                        />
                        <span className="truncate min-w-0 text-[11px]" title={node.phaseName}>
                          {getShortStageLabel(node.phaseName, node.ordinal)}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 font-mono text-[10px] tabular-nums text-app-muted">
                        <span>n={yieldCount.toLocaleString()}</span>
                        <span className="w-10 text-right">{formatDuration(duration)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
