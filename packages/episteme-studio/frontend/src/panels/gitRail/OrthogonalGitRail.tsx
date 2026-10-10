import React from "react";
import {GitRailNode, GitRailTrackEdge} from "./types";
import {EPISTEMIC_TAXONOMY} from "../epistemicTheme";

interface OrthogonalGitRailProps {
  nodes: GitRailNode[];
  nodePositions: Record<string, number>;
  svgHeight: number;
  railWidth: number;
  activeKey: string | null;
  directParents: Set<string>;
  directChildren: Set<string>;
  livePhaseKey: string | null;
  isRunActive: boolean;
}

// Spacing configuration: 10px per lane, 8px padding
const LANE_SPACING = 10;
const LANE_OFFSET = 10;

export const getLaneX = (lane: number): number => {
  return LANE_OFFSET + lane * LANE_SPACING;
};

/**
 * Renders strict orthogonal bus tracks with 45° chamfers or 90° corners,
 * port sockets, dotted cache pathways, and epistemic commit dots.
 */
export const OrthogonalGitRail: React.FC<OrthogonalGitRailProps> = ({
  nodes,
  nodePositions,
  svgHeight,
  railWidth,
  activeKey,
  directParents,
  directChildren,
  livePhaseKey,
  isRunActive,
}) => {
  const nodeMap = React.useMemo(() => {
    const map: Record<string, GitRailNode> = {};
    nodes.forEach((n) => {
      map[n.key] = n;
    });
    return map;
  }, [nodes]);

  // Compute all edges between parents and children
  const edges: GitRailTrackEdge[] = React.useMemo(() => {
    const list: GitRailTrackEdge[] = [];
    nodes.forEach((fromNode) => {
      const fromY = nodePositions[fromNode.key];
      if (fromY === undefined) return;

      fromNode.children.forEach((toKey) => {
        const toNode = nodeMap[toKey];
        if (!toNode) return;
        const toY = nodePositions[toKey];
        if (toY === undefined) return;

        const isOutgoingActive =
          activeKey === fromNode.key && directChildren.has(toKey);
        const isIncomingActive =
          activeKey === toKey && directParents.has(fromNode.key);
        const isActive = isOutgoingActive || isIncomingActive;

        list.push({
          fromKey: fromNode.key,
          toKey,
          fromLane: fromNode.lane,
          toLane: toNode.lane,
          fromY,
          toY,
          isCached: !!(fromNode.cacheHit && toNode.cacheHit),
          isActive,
          isGhost: toNode.isGhost,
        });
      });
    });
    return list;
  }, [nodes, nodePositions, nodeMap, activeKey, directParents, directChildren]);

  return (
    <svg
      className="absolute top-0 left-0 pointer-events-none z-0"
      style={{ width: `${railWidth}px`, height: `${svgHeight}px` }}
    >
      <defs>
        {/* Subtle pattern or filters if needed */}
      </defs>

      {/* Guide lines for each lane (up to 3 lanes) */}
      {[0, 1, 2].map((lane) => {
        const x = getLaneX(lane);
        return (
          <line
            key={`guide-${lane}`}
            x1={x}
            y1={4}
            x2={x}
            y2={Math.max(svgHeight - 4, 4)}
            stroke="currentColor"
            className="text-app-muted"
            strokeWidth="1"
            strokeDasharray="2 3"
          />
        );
      })}

      {/* Edges with strict orthogonal 45° chamfers or 90° corners */}
      {edges.map((edge) => {
        const x1 = getLaneX(edge.fromLane);
        const y1 = edge.fromY;
        const x2 = getLaneX(edge.toLane);
        const y2 = edge.toY;

        let pathD = "";
        if (x1 === x2) {
          // Pure vertical track
          pathD = `M ${x1} ${y1} L ${x2} ${y2}`;
        } else {
          // Orthogonal bus track with 45° chamfers
          const dx = x2 - x1;
          const absDx = Math.abs(dx);
          // Chamfer vertical extent is min(absDx, half distance)
          const chamferDist = Math.min(absDx, Math.abs(y2 - y1) * 0.4);
          const yMid1 = y1 + 6;
          const yMid2 = yMid1 + chamferDist;

          pathD = `M ${x1} ${y1} L ${x1} ${yMid1} L ${x2} ${yMid2} L ${x2} ${y2}`;
        }

        const isIncoming =
          activeKey === edge.toKey && directParents.has(edge.fromKey);
        const isOutgoing =
          activeKey === edge.fromKey && directChildren.has(edge.toKey);
        const isMuted = activeKey !== null && !edge.isActive;

        const strokeColor = isIncoming
          ? "#2563EB"
          : isOutgoing
          ? "#9333EA"
          : isMuted
          ? "rgba(148, 163, 184, 0.2)"
          : "#94A3B8";

        return (
          <path
            key={`${edge.fromKey}->${edge.toKey}`}
            d={pathD}
            fill="none"
            stroke={strokeColor}
            strokeWidth={edge.isActive ? "1.75" : "1.25"}
            strokeDasharray={
              edge.isGhost ? "2 2" : edge.isCached ? "3 2" : undefined
            }
          />
        );
      })}

      {/* Commit Dots, Port Sockets & Station Bus Connectors */}
      {nodes.map((node) => {
        const y = nodePositions[node.key];
        if (y === undefined) return null;
        const x = getLaneX(node.lane);

        const isSelf = activeKey === node.key;
        const isParent = directParents.has(node.key);
        const isChild = directChildren.has(node.key);
        const isNodeLive =
          node.phaseRecord?.status === "running" ||
          (isRunActive &&
            ((livePhaseKey !== null && node.key === livePhaseKey) ||
              (node.isCompound &&
                !!node.compoundMembers?.some((m) => m === livePhaseKey))));

        const epistemic = EPISTEMIC_TAXONOMY[node.layerId];
        const dotHue = epistemic.color;

        // Port socket connector line from track to right rail boundary
        const socketConnectorX2 = railWidth - 3;

        return (
          <g key={`station-${node.key}`}>
            {/* Bus wire connecting the track lane to the card's port socket */}
            <line
              x1={x}
              y1={y}
              x2={socketConnectorX2}
              y2={y}
              stroke={
                isSelf || isNodeLive
                  ? "#2563EB"
                  : isParent
                  ? "#0284C7"
                  : isChild
                  ? "#9333EA"
                  : "#CBD5E1"
              }
              className="dark:stroke-zinc-700"
              strokeWidth={isSelf || isNodeLive ? "1.5" : "1"}
            />

            {/* Commit Dot on track: Solid 6px circle with 1px border to anchor computational vertex */}
            {isNodeLive ? (
              <g>
                <circle
                  cx={x}
                  cy={y}
                  r="5.5"
                  fill="none"
                  stroke={dotHue}
                  strokeWidth="1.5"
                  className="animate-ping opacity-75"
                />
                <circle
                  cx={x}
                  cy={y}
                  r="3"
                  fill={dotHue}
                  stroke="#FFFFFF"
                  className="dark:stroke-zinc-900"
                  strokeWidth="1"
                />
              </g>
            ) : node.cacheHit ? (
              <g>
                <circle
                  cx={x}
                  cy={y}
                  r="3"
                  fill={dotHue}
                  stroke="#FFFFFF"
                  className="dark:stroke-zinc-900"
                  strokeWidth="1"
                />
                <circle cx={x} cy={y} r="1" fill="#FFFFFF" />
              </g>
            ) : node.phaseRecord?.status === "completed" ? (
              // Solid epistemic dot for fresh completed run
              <circle
                cx={x}
                cy={y}
                r="3"
                fill={dotHue}
                stroke="#FFFFFF"
                className="dark:stroke-zinc-900"
                strokeWidth="1"
              />
            ) : node.phaseRecord?.status === "failed" ? (
              // Crimson failure indicator
              <circle
                cx={x}
                cy={y}
                r="3"
                fill="#E11D48"
                stroke="#FFFFFF"
                className="dark:stroke-zinc-900"
                strokeWidth="1"
              />
            ) : (
              // Solid neutral vertex for unexecuted/planned phase
              <circle
                cx={x}
                cy={y}
                r="3"
                fill="#71717A"
                stroke="#FFFFFF"
                className="dark:stroke-zinc-900"
                strokeWidth="1"
              />
            )}

            {/* Port Socket Terminal at edge of card */}
            <circle
              cx={socketConnectorX2}
              cy={y}
              r={isSelf ? "2.5" : "1.75"}
              fill={isSelf ? "#2563EB" : isParent ? "#0284C7" : isChild ? "#9333EA" : "#94A3B8"}
              stroke="#FFFFFF"
              className="dark:stroke-zinc-900"
              strokeWidth="1"
            />
          </g>
        );
      })}
    </svg>
  );
};
