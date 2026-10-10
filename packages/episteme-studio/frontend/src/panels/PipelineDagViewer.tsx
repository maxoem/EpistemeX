import React, {useCallback, useLayoutEffect, useMemo, useRef, useState} from "react";
import {PhaseStatus} from "../api/types";
import {Activity, ArrowRight, Coins, GitBranch, Layers,} from "lucide-react";
import {getEpistemicLayerForPhase} from "./epistemicTheme";
import {resolvePhaseKey} from "./phaseConfig/phaseConfigResolver";
import {useRunsStore} from "../store/runsStore";
import {GitRailNode, ViewPerspective} from "./gitRail/types";
import {OrthogonalGitRail} from "./gitRail/OrthogonalGitRail";
import {GitRailRow} from "./gitRail/GitRailRow";
import {LayerRollupView} from "./gitRail/LayerRollupView";

export interface PipelineDagViewerProps {
  phaseRecords: PhaseStatus[];
  selectedPhaseKey: string | null;
  onSelectPhase: (phaseKey: string | null) => void;
  showOverviewOption?: boolean;
  showHeader?: boolean;
  llmModel?: string;
  candidatePhaseRecords?: PhaseStatus[];
}

// Fixed width for the 3-lane orthogonal bus rail
const RAIL_WIDTH = 36;

export const PipelineDagViewer: React.FC<PipelineDagViewerProps> = ({
  phaseRecords,
  selectedPhaseKey,
  onSelectPhase,
  showOverviewOption = true,
  showHeader = true,
  llmModel,
  candidatePhaseRecords,
}) => {
  const [foldedBranches, setFoldedBranches] = useState<Record<string, boolean>>({});
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  const [autoFollow, setAutoFollow] = useState<boolean>(true);
  const [viewPerspective, setViewPerspective] = useState<ViewPerspective>("topological");

  const liveProgress = useRunsStore((s) => s.liveProgress);
  const selectedRunDetail = useRunsStore((s) => s.selectedRunDetail);
  const phaseScores = useRunsStore((s) => s.phaseScores);
  const isRunActive = selectedRunDetail?.status === "running";

  const livePhaseKey = useMemo(() => {
    if (liveProgress?.phaseName) {
      return resolvePhaseKey({ phase_name: liveProgress.phaseName });
    }
    const runningRec = (selectedRunDetail?.phase_records || []).find((p) => p.status === "running");
    if (runningRec) {
      return resolvePhaseKey(runningRec);
    }
    return null;
  }, [liveProgress?.phaseName, selectedRunDetail?.phase_records]);

  // Auto-follow active phase during execution
  React.useEffect(() => {
    if (!autoFollow || !isRunActive || !livePhaseKey) return;
    if (selectedPhaseKey !== livePhaseKey) {
      onSelectPhase(livePhaseKey);
    }
  }, [autoFollow, isRunActive, livePhaseKey, selectedPhaseKey, onSelectPhase]);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const nodeRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [nodePositions, setNodePositions] = useState<Record<string, number>>({});
  const [svgHeight, setSvgHeight] = useState<number>(0);

  // Define canonical schema with strict 3-lane assignment (0: root/synthesis, 1: kg, 2: arg/diverged)
  const rawCanonicalNodes: GitRailNode[] = useMemo(() => {
    const recordMap: Record<string, PhaseStatus> = {};
    (phaseRecords || []).forEach((p) => {
      recordMap[resolvePhaseKey(p)] = p;
    });

    const candidateMap: Record<string, PhaseStatus> = {};
    (candidatePhaseRecords || []).forEach((p) => {
      candidateMap[resolvePhaseKey(p)] = p;
    });

    const canonicalSchema = [
      { key: "phase1", name: "Foundation & Ingestion", ordinal: 1, lane: 0, parents: [], children: ["phase2", "phase4"], branch: "root", branchLabel: "Ingest", layerId: "L1" as const, deltaLabel: "source doc" },
      { key: "phase2", name: "Entity & Local Extraction", ordinal: 2, lane: 1, parents: ["phase1"], children: ["phase3", "phase3b"], branch: "kg", branchLabel: "KG Local", layerId: "L2" as const, deltaLabel: "Δ +ent/rels" },
      { key: "phase3", name: "Global Relations", ordinal: 3, lane: 1, parents: ["phase2"], children: ["phase4_maturation"], branch: "kg", branchLabel: "KG Global", layerId: "L2" as const, deltaLabel: "Δ global" },
      { key: "phase3b", name: "Latent Transitivity", ordinal: 4, lane: 1, parents: ["phase2"], children: ["phase5"], branch: "kg", branchLabel: "KG Latent", layerId: "L2" as const, deltaLabel: "Δ latent" },
      { key: "phase4_maturation", name: "Entity Maturation", ordinal: 5, lane: 1, parents: ["phase3"], children: ["phase5"], branch: "kg", branchLabel: "KG Mature", layerId: "L2" as const, deltaLabel: "Δ mature" },
      { key: "phase4", name: "Argument Mining", ordinal: 6, lane: 2, parents: ["phase1"], children: ["phase5"], branch: "arg", branchLabel: "Arg Mining", layerId: "L3" as const, deltaLabel: "Δ claims" },
      { key: "phase5", name: "Argument Fusion", ordinal: 7, lane: 0, parents: ["phase3b", "phase4_maturation", "phase4"], children: ["phase6"], branch: "synthesis", branchLabel: "Fusion", layerId: "L3" as const, deltaLabel: "Δ web/arg" },
      { key: "phase6", name: "TheoryNet & Bridges", ordinal: 8, lane: 0, parents: ["phase5"], children: [], branch: "synthesis", branchLabel: "TheoryNet", layerId: "L4" as const, deltaLabel: "Δ theory" },
    ];

    const allCandidateKeys = Object.keys(candidateMap);
    const ghostKeys = allCandidateKeys.filter(
      (k) => !canonicalSchema.some((c) => c.key === k) && !recordMap[k]
    );

    const list: GitRailNode[] = canonicalSchema.map((def) => {
      const rec = recordMap[def.key];
      const candRec = candidateMap[def.key];
      const scores = phaseScores[def.key] || [];
      const meanScore = scores.length > 0 ? (scores.reduce((a, b) => a + b, 0) / scores.length) * 100 : undefined;

      return {
        key: def.key,
        phaseName: rec?.phase_name || def.name,
        ordinal: rec?.phase_ordinal || def.ordinal,
        lane: def.lane,
        phaseRecord: rec,
        candidateRecord: candRec,
        parents: def.parents,
        children: def.children,
        branchId: def.branch,
        branchLabel: def.branchLabel,
        model: llmModel,
        cacheHit: rec?.reused ?? false,
        layerId: getEpistemicLayerForPhase(def.key, def.ordinal),
        deltaLabel: def.deltaLabel,
        confidencePct: meanScore,
      };
    });

    ghostKeys.forEach((k) => {
      const candRec = candidateMap[k];
      list.push({
        key: k,
        phaseName: candRec.phase_name || k,
        ordinal: candRec.phase_ordinal || 99,
        lane: 2,
        candidateRecord: candRec,
        parents: ["phase5"],
        children: [],
        branchId: "diverged",
        branchLabel: "Diff Diverged",
        isGhost: true,
        layerId: "L2",
        deltaLabel: "Δ ghost",
      });
    });

    return list;
  }, [phaseRecords, candidatePhaseRecords, llmModel, phaseScores]);

  // Support folding the KG branch into a single super-node
  const visibleNodes: GitRailNode[] = useMemo(() => {
    const isKgFolded = foldedBranches["kg"];
    if (!isKgFolded) return rawCanonicalNodes;

    const kgMembers = rawCanonicalNodes.filter((n) => n.branchId === "kg");
    const kgKeys = new Set(kgMembers.map((m) => m.key));

    const totalDuration = kgMembers.reduce(
      (acc, m) => acc + (m.phaseRecord?.duration_seconds || 0),
      0
    );
    const terminalYield = kgMembers[kgMembers.length - 1]?.phaseRecord?.artifact_count ?? 0;
    const allCompleted = kgMembers.every((m) => m.phaseRecord?.status === "completed");
    const anyFailed = kgMembers.some((m) => m.phaseRecord?.status === "failed");
    const anyRunning = kgMembers.some((m) => m.phaseRecord?.status === "running");

    const compoundStatus: PhaseStatus["status"] = anyFailed
      ? "failed"
      : anyRunning
      ? "running"
      : allCompleted
      ? "completed"
      : "planned";

    const compoundNode: GitRailNode = {
      key: "compound_kg",
      phaseName: "KG Cluster",
      ordinal: 2,
      lane: 1,
      parents: ["phase1"],
      children: ["phase5"],
      branchId: "kg",
      branchLabel: "4 Phases",
      isCompound: true,
      compoundMembers: Array.from(kgKeys),
      totalDurationSeconds: totalDuration,
      aggregateArtifactCount: terminalYield,
      cacheHit: kgMembers.every((m) => m.cacheHit),
      layerId: "L2",
      deltaLabel: "Δ 4 phases",
      phaseRecord: {
        phase_name: "KG Cluster",
        phase_ordinal: 2,
        status: compoundStatus,
        duration_seconds: totalDuration,
        artifact_count: terminalYield,
        reused: kgMembers.every((m) => m.cacheHit),
      },
    };

    const result: GitRailNode[] = [];
    let compoundInserted = false;

    rawCanonicalNodes.forEach((node) => {
      if (kgKeys.has(node.key)) {
        if (!compoundInserted) {
          result.push(compoundNode);
          compoundInserted = true;
        }
      } else {
        const remappedParents = node.parents.map((p) => (kgKeys.has(p) ? "compound_kg" : p));
        const remappedChildren = node.children.map((c) => (kgKeys.has(c) ? "compound_kg" : c));
        result.push({
          ...node,
          parents: Array.from(new Set(remappedParents)),
          children: Array.from(new Set(remappedChildren)),
        });
      }
    });

    return result;
  }, [rawCanonicalNodes, foldedBranches]);

  const nodeMap = useMemo(() => {
    const map: Record<string, GitRailNode> = {};
    visibleNodes.forEach((n) => {
      map[n.key] = n;
    });
    return map;
  }, [visibleNodes]);

  const activeKey = hoveredKey || selectedPhaseKey;

  const resolvedActiveKey = useMemo(() => {
    if (!activeKey) return null;
    if (
      foldedBranches["kg"] &&
      ["phase2", "phase3", "phase3b", "phase4_maturation"].includes(activeKey)
    ) {
      return "compound_kg";
    }
    return activeKey;
  }, [activeKey, foldedBranches]);

  const activeNode = resolvedActiveKey ? nodeMap[resolvedActiveKey] : null;

  const directParents = useMemo(() => new Set(activeNode?.parents || []), [activeNode]);
  const directChildren = useMemo(() => new Set(activeNode?.children || []), [activeNode]);

  const measureOffsets = useCallback(() => {
    if (!containerRef.current) return;
    const positions: Record<string, number> = {};

    Object.entries(nodeRefs.current).forEach(([key, el]) => {
      if (el) {
        positions[key] = el.offsetTop + el.offsetHeight / 2;
      }
    });

    setNodePositions(positions);
    setSvgHeight(containerRef.current.scrollHeight);
  }, []);

  useLayoutEffect(() => {
    measureOffsets();
    const observer = new ResizeObserver(() => measureOffsets());
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [visibleNodes, viewPerspective, measureOffsets]);

  const toggleBranchFold = (branchId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setFoldedBranches((prev) => ({ ...prev, [branchId]: !prev[branchId] }));
  };

  const isOverviewSelected = !selectedPhaseKey;

  return (
    <div className="flex flex-col h-full bg-app-bg/50 select-none text-app-heading overflow-hidden">
      {/* Precision Instrument Header with Dual-Perspective Toggle */}
      {showHeader && (
        <div className="h-8 px-2.5 border-b border-app-border flex items-center justify-between shrink-0 bg-app-bg">
          <div className="flex items-center gap-1.5">
            <GitBranch className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
            <span className="text-[11px] font-semibold tracking-tight text-app-heading font-sans">
              Topology
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            {/* View Mode Toggle: Topological vs Layer Rollup */}
            <div className="inline-flex p-0.5 rounded bg-app-subtle border border-app-border text-[9px] font-mono">
              <button
                type="button"
                onClick={() => setViewPerspective("topological")}
                className={`px-1.5 py-0.5 rounded transition-colors cursor-pointer ${
                  viewPerspective === "topological"
                    ? "bg-app-bg text-app-heading font-semibold"
                    : "text-app-muted hover:text-app-heading"
                }`}
                title="Topological chronological execution flow"
              >
                DAG
              </button>
              <button
                type="button"
                onClick={() => setViewPerspective("layers")}
                className={`px-1.5 py-0.5 rounded transition-colors cursor-pointer ${
                  viewPerspective === "layers"
                    ? "bg-app-bg text-app-heading font-semibold"
                    : "text-app-muted hover:text-app-heading"
                }`}
                title="Epistemic Layer Rollup (L1–L4)"
              >
                L1–L4
              </button>
            </div>

            {/* Auto Follow Toggle (When Running) */}
            {isRunActive && (
              <button
                type="button"
                onClick={() => {
                  const next = !autoFollow;
                  setAutoFollow(next);
                  if (next && livePhaseKey) {
                    onSelectPhase(livePhaseKey);
                  }
                }}
                className={`text-[9px] font-mono px-1.5 py-0.5 rounded border transition-colors flex items-center gap-1 cursor-pointer ${
                  autoFollow
                    ? "bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-800"
                    : "bg-app-subtle text-app-muted border-app-border"
                }`}
                title={autoFollow ? "Auto-follow is ON" : "Auto-follow is OFF"}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${autoFollow ? "bg-blue-600 animate-ping" : "bg-app-muted"}`} />
                Live
              </button>
            )}
          </div>
        </div>
      )}

      {/* Run Level Navigation: Overview, Generations & Costs, Run Configuration */}
      {showOverviewOption && (
        <div className="flex flex-col border-b border-app-border shrink-0">
          <button
            type="button"
            onClick={() => onSelectPhase(null)}
            className={`h-7 px-2.5 flex items-center justify-between text-[11px] font-sans border-b border-app-border transition-colors cursor-pointer shrink-0 ${
              isOverviewSelected
                ? "bg-app-subtle text-app-heading font-semibold border-l-2 border-l-blue-600"
                : "bg-app-bg hover:bg-app-subtle/50 text-app-muted border-l-2 border-l-transparent"
            }`}
          >
            <div className="flex items-center gap-1.5">
              <Layers className={`w-3.5 h-3.5 ${isOverviewSelected ? "text-blue-600 dark:text-blue-400" : "text-app-muted"}`} />
              <span>Cumulative Overview</span>
            </div>
            <span className="text-[9px] font-mono text-app-muted">L1–L4</span>
          </button>

          <button
            type="button"
            onClick={() => onSelectPhase("generations")}
            className={`h-7 px-2.5 flex items-center justify-between text-[11px] font-sans border-b border-app-border transition-colors cursor-pointer shrink-0 ${
              selectedPhaseKey === "generations"
                ? "bg-app-subtle text-app-heading font-semibold border-l-2 border-l-blue-600"
                : "bg-app-bg hover:bg-app-subtle/50 text-app-muted border-l-2 border-l-transparent"
            }`}
          >
            <div className="flex items-center gap-1.5">
              <Coins className={`w-3.5 h-3.5 ${selectedPhaseKey === "generations" ? "text-blue-600 dark:text-blue-400" : "text-app-muted"}`} />
              <span>Generation & Costs</span>
            </div>
            <span className="text-[9px] font-mono text-app-muted">Tokens</span>
          </button>
        </div>
      )}

      {/* Main Body: Either Topological Git-Rail or Layer Rollup */}
      {viewPerspective === "topological" ? (
        <div
          ref={containerRef}
          className="flex-1 overflow-y-auto relative bg-app-bg"
        >
          {/* Strict Orthogonal Git Bus Rail SVG */}
          <OrthogonalGitRail
            nodes={visibleNodes}
            nodePositions={nodePositions}
            svgHeight={svgHeight}
            railWidth={RAIL_WIDTH}
            activeKey={resolvedActiveKey}
            directParents={directParents}
            directChildren={directChildren}
            livePhaseKey={livePhaseKey}
            isRunActive={isRunActive}
          />

          {/* Compact 32px Flush Tabular Rows (indented by rail width) */}
          <div
            className="flex flex-col"
            style={{ paddingLeft: `${RAIL_WIDTH}px` }}
          >
            {visibleNodes.map((node) => {
              const isSelected = selectedPhaseKey === node.key;
              const isSelf = resolvedActiveKey === node.key;
              const isParent = directParents.has(node.key);
              const isChild = directChildren.has(node.key);
              const isDimmed = activeKey !== null && !isSelf && !isParent && !isChild;

              const isNodeLive = Boolean(
                node.phaseRecord?.status === "running" ||
                (isRunActive &&
                  ((livePhaseKey !== null && node.key === livePhaseKey) ||
                    (node.isCompound &&
                      !!node.compoundMembers?.some((m) => m === livePhaseKey))))
              );

              return (
                <div
                  key={node.key}
                  onMouseEnter={() => setHoveredKey(node.key)}
                  onMouseLeave={() => setHoveredKey(null)}
                >
                  <GitRailRow
                    node={node}
                    isSelected={isSelected}
                    isParent={isParent}
                    isChild={isChild}
                    isDimmed={isDimmed}
                    isLiveRunning={isNodeLive}
                    onSelect={(key) => {
                      if (node.isCompound) {
                        toggleBranchFold("kg", {} as React.MouseEvent);
                      } else {
                        if (isRunActive && key !== livePhaseKey) {
                          setAutoFollow(false);
                        }
                        onSelectPhase(key);
                      }
                    }}
                    onToggleFold={toggleBranchFold}
                    isFolded={foldedBranches["kg"]}
                    nodeRef={(el) => {
                      nodeRefs.current[node.key] = el;
                    }}
                    liveProgress={isNodeLive ? liveProgress : null}
                  />
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        /* Layer Rollup Perspective (L1–L4) */
        <div className="flex-1 overflow-y-auto bg-app-bg">
          <LayerRollupView
            nodes={rawCanonicalNodes}
            selectedPhaseKey={selectedPhaseKey}
            onSelectPhase={onSelectPhase}
          />
        </div>
      )}

      {/* Epistemic Status / Lineage Bar */}
      <div className="h-6 px-2.5 bg-app-bg border-t border-app-border text-[9px] shrink-0 font-mono flex items-center justify-between text-app-muted">
        {activeNode ? (
          <div className="flex items-center justify-between w-full">
            <span className="truncate">
              IN: {activeNode.parents.length > 0 ? activeNode.parents.join(",") : "—"}
            </span>
            <ArrowRight className="w-2.5 h-2.5 opacity-40 mx-1 shrink-0" />
            <span className="truncate">
              OUT: {activeNode.children.length > 0 ? activeNode.children.join(",") : "—"}
            </span>
          </div>
        ) : (
          <div className="flex items-center justify-between w-full">
            <span>Precision Epistemic Rail</span>
            <Activity className="w-2.5 h-2.5 text-blue-600 dark:text-blue-400" />
          </div>
        )}
      </div>
    </div>
  );
};