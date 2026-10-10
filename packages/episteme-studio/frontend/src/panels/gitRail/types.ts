import {PhaseStatus} from "../../api/types";

export interface GitRailNode {
  key: string;
  phaseName: string;
  ordinal: number;
  lane: number; // 0, 1, or 2 (capped at 3 parallel tracks)
  phaseRecord?: PhaseStatus;
  candidateRecord?: PhaseStatus;
  parents: string[];
  children: string[];
  branchId: string;
  branchLabel?: string;
  model?: string;
  cacheHit?: boolean;
  isGhost?: boolean;
  isCompound?: boolean;
  compoundMembers?: string[];
  totalDurationSeconds?: number;
  aggregateArtifactCount?: number;
  layerId: "L1" | "L2" | "L3" | "L4";
  deltaLabel?: string;
  confidencePct?: number;
}

export interface GitRailTrackEdge {
  fromKey: string;
  toKey: string;
  fromLane: number;
  toLane: number;
  fromY: number;
  toY: number;
  isCached: boolean;
  isActive: boolean;
  isGhost?: boolean;
}

export type ViewPerspective = "topological" | "layers";
