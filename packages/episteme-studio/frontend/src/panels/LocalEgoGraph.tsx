import React, {useEffect, useMemo, useRef, useState} from "react";
import {Layers, RotateCcw, ZoomIn, ZoomOut,} from "lucide-react";
import {useThemeStore} from "../store/themeStore";
import {GraphView} from "../api/types";

export interface EgoNode {
  id: string;
  label: string;
  type: string;
  degree: number;
  hop: 0 | 1 | 2;
  isSubject?: boolean;
  isObject?: boolean;
  isSinkhole?: boolean;
  isOrphan?: boolean;
  parentHop1Id?: string;
}

export interface EgoEdge {
  id: string;
  source: string;
  target: string;
  predicate: string;
  category: "Hierarchical" | "Associative" | "Causal" | "Dialectical" | "Unmapped";
  confidence: number;
  isBridge?: boolean;
  isInvalidBridge?: boolean;
  isPrimary?: boolean;
}

export function getNodeDimensions(label: string) {
  const width = Math.min(150, Math.max(80, label.length * 7 + 24));
  const height = 28;
  return { width, height, w: width, h: height };
}

export function getEdgeLineCoords(
  p1: { x: number; y: number },
  p2: { x: number; y: number },
  w1: number,
  h1: number,
  w2: number,
  h2: number
) {
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const dist = Math.hypot(dx, dy);
  if (dist < 1e-3) {
    return { x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y, midX: p1.x, midY: p1.y };
  }

  const ux = dx / dist;
  const uy = dy / dist;

  // Box 1 intersection (leaving box 1 border)
  const t1x = Math.abs(ux) > 1e-4 ? (w1 / 2 + 2) / Math.abs(ux) : Infinity;
  const t1y = Math.abs(uy) > 1e-4 ? (h1 / 2 + 2) / Math.abs(uy) : Infinity;
  const offset1 = Math.min(t1x, t1y);

  // Box 2 intersection (entering box 2 border, offset by 6px for arrowhead marker)
  const t2x = Math.abs(ux) > 1e-4 ? (w2 / 2 + 6) / Math.abs(ux) : Infinity;
  const t2y = Math.abs(uy) > 1e-4 ? (h2 / 2 + 6) / Math.abs(uy) : Infinity;
  const offset2 = Math.min(t2x, t2y);

  if (dist <= offset1 + offset2) {
    return {
      x1: p1.x,
      y1: p1.y,
      x2: p2.x,
      y2: p2.y,
      midX: (p1.x + p2.x) / 2,
      midY: (p1.y + p2.y) / 2,
    };
  }

  const x1 = p1.x + ux * offset1;
  const y1 = p1.y + uy * offset1;
  const x2 = p2.x - ux * offset2;
  const y2 = p2.y - uy * offset2;

  return {
    x1,
    y1,
    x2,
    y2,
    midX: (x1 + x2) / 2,
    midY: (y1 + y2) / 2,
  };
}

export interface LocalEgoGraphProps {
  focusSubject: string;
  focusPredicate: string;
  focusObject: string;
  confidence?: number;
  category?: string;
  isAnomaly?: boolean;
  onSelectNode?: (nodeId: string) => void;
  height?: number | string;
  className?: string;
  graphData?: GraphView | null;
}

export const LocalEgoGraph: React.FC<LocalEgoGraphProps> = ({
  focusSubject,
  focusPredicate,
  focusObject,
  confidence = 0.85,
  category = "Associative",
  isAnomaly = false,
  onSelectNode,
  height = "100%",
  className = "",
  graphData,
}) => {
  const { theme } = useThemeStore();
  const isDark = theme !== "light";

  const [hopDepth, setHopDepth] = useState<1 | 2>(1);
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [dimensions, setDimensions] = useState<{ width: number; height: number }>({
    width: 600,
    height: 400,
  });

  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const updateSize = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        setDimensions({ width: rect.width, height: rect.height });
      }
    };
    updateSize();
    const observer = new ResizeObserver(() => updateSize());
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Generate real or deterministic 1-hop and 2-hop local graph around the active triple
  const { nodes, edges } = useMemo(() => {
    if (graphData && graphData.nodes && graphData.nodes.length > 0) {
      const subLower = (focusSubject || "").toLowerCase();
      const objLower = (focusObject || "").toLowerCase();

      const matchedSubjectNode = graphData.nodes.find(
        (n) => n.id.toLowerCase() === subLower || n.label.toLowerCase() === subLower
      );
      const matchedObjectNode = graphData.nodes.find(
        (n) => n.id.toLowerCase() === objLower || n.label.toLowerCase() === objLower
      );

      const sId = matchedSubjectNode?.id || focusSubject;
      const oId = matchedObjectNode?.id || focusObject;

      const nList: EgoNode[] = [
        {
          id: sId,
          label: matchedSubjectNode?.label || focusSubject,
          type: matchedSubjectNode?.type || "Concept",
          degree: matchedSubjectNode?.degree || 1,
          hop: 0,
          isSubject: true,
          isSinkhole: (matchedSubjectNode?.degree || 0) > 10,
        },
        {
          id: oId,
          label: matchedObjectNode?.label || focusObject,
          type: matchedObjectNode?.type || "Entity",
          degree: matchedObjectNode?.degree || 1,
          hop: 0,
          isObject: true,
        },
      ];

      const eList: EgoEdge[] = [
        {
          id: `primary-${sId}-${oId}`,
          source: sId,
          target: oId,
          predicate: focusPredicate,
          category: (category as any) || "Associative",
          confidence: confidence,
          isPrimary: true,
          isInvalidBridge: isAnomaly && confidence < 0.6,
        },
      ];

      const visitedNodeIds = new Set<string>([sId, oId]);
      const hop1NodeIds = new Set<string>();

      // 1-Hop Discovery
      for (const edge of graphData.edges || []) {
        if (
          (edge.source === sId && edge.target === oId) ||
          (edge.source === oId && edge.target === sId)
        ) {
          continue;
        }

        let neighborId: string | null = null;
        if (edge.source === sId) {
          neighborId = edge.target;
        } else if (edge.target === sId) {
          neighborId = edge.source;
        } else if (edge.source === oId) {
          neighborId = edge.target;
        } else if (edge.target === oId) {
          neighborId = edge.source;
        }

        if (neighborId && !visitedNodeIds.has(neighborId)) {
          if (hop1NodeIds.size < 10) {
            visitedNodeIds.add(neighborId);
            hop1NodeIds.add(neighborId);
            const neighborNode = graphData.nodes.find((n) => n.id === neighborId);
            nList.push({
              id: neighborId,
              label: neighborNode?.label || neighborId,
              type: neighborNode?.type || "Entity",
              degree: neighborNode?.degree || 1,
              hop: 1,
            });
            eList.push({
              id: edge.id,
              source: edge.source,
              target: edge.target,
              predicate: edge.type,
              category: (category as any) || "Associative",
              confidence: edge.confidence ?? 0.85,
              isBridge: (neighborNode?.degree || 0) > 5,
            });
          }
        }
      }

      // 2-Hop Discovery
      if (hopDepth === 2 && hop1NodeIds.size > 0) {
        let hop2Count = 0;
        for (const edge of graphData.edges || []) {
          if (hop2Count >= 10) break;
          const isFromHop1 = hop1NodeIds.has(edge.source);
          const isToHop1 = hop1NodeIds.has(edge.target);

          if (isFromHop1 && !visitedNodeIds.has(edge.target)) {
            visitedNodeIds.add(edge.target);
            const neighborNode = graphData.nodes.find((n) => n.id === edge.target);
            nList.push({
              id: edge.target,
              label: neighborNode?.label || edge.target,
              type: neighborNode?.type || "Entity",
              degree: neighborNode?.degree || 1,
              hop: 2,
              parentHop1Id: edge.source,
            });
            eList.push({
              id: edge.id,
              source: edge.source,
              target: edge.target,
              predicate: edge.type,
              category: (category as any) || "Associative",
              confidence: edge.confidence ?? 0.85,
            });
            hop2Count++;
          } else if (isToHop1 && !visitedNodeIds.has(edge.source)) {
            visitedNodeIds.add(edge.source);
            const neighborNode = graphData.nodes.find((n) => n.id === edge.source);
            nList.push({
              id: edge.source,
              label: neighborNode?.label || edge.source,
              type: neighborNode?.type || "Entity",
              degree: neighborNode?.degree || 1,
              hop: 2,
              parentHop1Id: edge.target,
            });
            eList.push({
              id: edge.id,
              source: edge.source,
              target: edge.target,
              predicate: edge.type,
              category: (category as any) || "Associative",
              confidence: edge.confidence ?? 0.85,
            });
            hop2Count++;
          }
        }
      }

      // Include all remaining intra-ego edges between discovered nodes
      const existingEdgeIds = new Set(eList.map((e) => e.id));
      for (const edge of graphData.edges || []) {
        if (
          !existingEdgeIds.has(edge.id) &&
          visitedNodeIds.has(edge.source) &&
          visitedNodeIds.has(edge.target)
        ) {
          existingEdgeIds.add(edge.id);
          eList.push({
            id: edge.id,
            source: edge.source,
            target: edge.target,
            predicate: edge.type,
            category: (category as any) || "Associative",
            confidence: edge.confidence ?? 0.85,
          });
        }
      }

      return { nodes: nList, edges: eList };
    }

    const sId = focusSubject.toLowerCase().replace(/\s+/g, "_");
    const oId = focusObject.toLowerCase().replace(/\s+/g, "_");

    const nList: EgoNode[] = [
      {
        id: sId,
        label: focusSubject,
        type: "Concept",
        degree: isAnomaly ? 14 : 5,
        hop: 0,
        isSubject: true,
        isSinkhole: isAnomaly && focusSubject.toLowerCase().includes("theory"),
      },
      {
        id: oId,
        label: focusObject,
        type: "Entity",
        degree: 3,
        hop: 0,
        isObject: true,
      },
    ];

    const eList: EgoEdge[] = [
      {
        id: `${sId}-${oId}`,
        source: sId,
        target: oId,
        predicate: focusPredicate,
        category: (category as any) || "Associative",
        confidence: confidence,
        isPrimary: true,
        isInvalidBridge: isAnomaly && confidence < 0.6,
      },
    ];

    // Synthesize realistic 1-hop neighbors
    const sNeighbors = [
      { name: "Epistemic Structure", pred: "part_of", cat: "Hierarchical", conf: 0.92, deg: 6 },
      { name: "Empirical Justification", pred: "supports", cat: "Dialectical", conf: 0.88, deg: 4 },
      { name: "Logical Positivism", pred: "historical_precursor", cat: "Associative", conf: 0.79, deg: 8 },
    ];

    sNeighbors.forEach((n, idx) => {
      const nid = `s_n_${idx}_${n.name.toLowerCase().replace(/\s+/g, "_")}`;
      nList.push({
        id: nid,
        label: n.name,
        type: "TheoryAtom",
        degree: n.deg,
        hop: 1,
      });
      eList.push({
        id: `e_${sId}_${nid}`,
        source: sId,
        target: nid,
        predicate: n.pred,
        category: n.cat as any,
        confidence: n.conf,
        isBridge: idx === 2,
        isInvalidBridge: isAnomaly && idx === 2,
      });
    });

    const oNeighbors = [
      { name: "Falsification Criterion", pred: "constrains", cat: "Causal", conf: 0.84, deg: 3 },
      { name: "Observation Report", pred: "derived_from", cat: "Hierarchical", conf: 0.91, deg: 2 },
    ];

    oNeighbors.forEach((n, idx) => {
      const nid = `o_n_${idx}_${n.name.toLowerCase().replace(/\s+/g, "_")}`;
      nList.push({
        id: nid,
        label: n.name,
        type: "Claim",
        degree: n.deg,
        hop: 1,
      });
      eList.push({
        id: `e_${oId}_${nid}`,
        source: oId,
        target: nid,
        predicate: n.pred,
        category: n.cat as any,
        confidence: n.conf,
      });
    });

    // If 2-hop enabled, add secondary extension
    if (hopDepth === 2) {
      const hop2Nodes = [
        { parentId: "s_n_0_epistemic_structure", name: "Coherence Metric", pred: "evaluates", conf: 0.86, deg: 3 },
        { parentId: "s_n_1_empirical_justification", name: "Bayesian Prior", pred: "formalizes", conf: 0.74, deg: 2 },
        { parentId: "o_n_0_falsification_criterion", name: "Popperian Demarcation", pred: "exemplifies", conf: 0.95, deg: 5 },
      ];

      hop2Nodes.forEach((n, idx) => {
        const nid = `h2_${idx}_${n.name.toLowerCase().replace(/\s+/g, "_")}`;
        nList.push({
          id: nid,
          label: n.name,
          type: "Axiom",
          degree: n.deg,
          hop: 2,
          parentHop1Id: n.parentId,
        });
        eList.push({
          id: `e_${n.parentId}_${nid}`,
          source: n.parentId,
          target: nid,
          predicate: n.pred,
          category: "Hierarchical",
          confidence: n.conf,
        });
      });
    }

    return { nodes: nList, edges: eList };
  }, [focusSubject, focusPredicate, focusObject, confidence, category, isAnomaly, hopDepth, graphData]);

  // Compute node 2D positions in a hierarchical radial layout around center
  const positions = useMemo(() => {
    const posMap: Record<string, { x: number; y: number }> = {};
    const width = Math.max(640, dimensions.width);
    const height = Math.max(420, dimensions.height);
    const centerX = width / 2;
    const centerY = height / 2;

    const sNode = nodes.find((n) => n.isSubject) || nodes[0];
    const oNode = nodes.find((n) => n.isObject) || nodes[1];

    if (!sNode || !oNode) {
      nodes.forEach((n, idx) => {
        posMap[n.id] = { x: centerX + (idx - nodes.length / 2) * 140, y: centerY };
      });
      return posMap;
    }

    const sId = sNode.id;
    const oId = oNode.id;

    // Center nodes (Subject on left, Object on right)
    // Generous spacing (340-480px) ensures no overlap with predicate badges
    const coreOffset = Math.max(175, Math.min(240, width * 0.22));
    posMap[sId] = { x: centerX - coreOffset, y: centerY };
    posMap[oId] = { x: centerX + coreOffset, y: centerY };

    // Group 1-hop nodes based on edge connections
    const hop1Nodes = nodes.filter((n) => n.hop === 1);
    const s1Hops: EgoNode[] = [];
    const o1Hops: EgoNode[] = [];
    const mutualHops: EgoNode[] = [];

    hop1Nodes.forEach((n) => {
      const connectsToSubject = edges.some(
        (e) => (e.source === n.id && e.target === sId) || (e.target === n.id && e.source === sId)
      );
      const connectsToObject = edges.some(
        (e) => (e.source === n.id && e.target === oId) || (e.target === n.id && e.source === oId)
      );

      if (connectsToSubject && connectsToObject) {
        mutualHops.push(n);
      } else if (connectsToObject) {
        o1Hops.push(n);
      } else {
        s1Hops.push(n);
      }
    });

    const r1 = Math.max(150, Math.min(190, width * 0.18));

    // Position Subject 1-hop nodes (fanning out to the left)
    s1Hops.forEach((n, idx) => {
      const count = s1Hops.length;
      let angle = Math.PI;
      if (count > 1) {
        angle = 0.62 * Math.PI + (idx * 0.76 * Math.PI) / (count - 1);
      }
      const r = count >= 4 && idx % 2 === 1 ? r1 * 1.22 : r1;
      posMap[n.id] = {
        x: centerX - coreOffset + Math.cos(angle) * r,
        y: centerY + Math.sin(angle) * r,
      };
    });

    // Position Object 1-hop nodes (fanning out to the right)
    o1Hops.forEach((n, idx) => {
      const count = o1Hops.length;
      let angle = 0;
      if (count > 1) {
        angle = -0.38 * Math.PI + (idx * 0.76 * Math.PI) / (count - 1);
      }
      const r = count >= 4 && idx % 2 === 1 ? r1 * 1.22 : r1;
      posMap[n.id] = {
        x: centerX + coreOffset + Math.cos(angle) * r,
        y: centerY + Math.sin(angle) * r,
      };
    });

    // Position mutual 1-hop nodes (placed above and below center line)
    mutualHops.forEach((n, idx) => {
      const sign = idx % 2 === 0 ? -1 : 1;
      const layer = Math.floor(idx / 2);
      const yOffset = (135 + layer * 45) * sign;
      const xOffset = layer === 0 ? 0 : layer % 2 === 1 ? -60 : 60;
      posMap[n.id] = {
        x: centerX + xOffset,
        y: centerY + yOffset,
      };
    });

    // Position 2-hop nodes fanning out outward from their parent 1-hop nodes
    const hop2Nodes = nodes.filter((n) => n.hop === 2);
    const hop2ByParent: Record<string, EgoNode[]> = {};

    hop2Nodes.forEach((n) => {
      let parentId = n.parentHop1Id;
      if (!parentId || !posMap[parentId]) {
        const edge = edges.find((e) => {
          const other = e.source === n.id ? e.target : e.target === n.id ? e.source : null;
          return other && posMap[other] && hop1Nodes.some((h) => h.id === other);
        });
        if (edge) {
          parentId = edge.source === n.id ? edge.target : edge.source;
        }
      }
      const key = parentId && posMap[parentId] ? parentId : "__orphan__";
      if (!hop2ByParent[key]) hop2ByParent[key] = [];
      hop2ByParent[key].push(n);
    });

    const r2 = 135;

    Object.entries(hop2ByParent).forEach(([parentId, children]) => {
      if (parentId === "__orphan__") {
        children.forEach((n, idx) => {
          const angle = (idx * 2 * Math.PI) / Math.max(1, children.length);
          posMap[n.id] = {
            x: centerX + Math.cos(angle) * (r1 + r2),
            y: centerY + Math.sin(angle) * (r1 + r2),
          };
        });
        return;
      }

      const pPos = posMap[parentId];
      const isLeft = pPos.x < centerX;
      const coreX = isLeft ? centerX - coreOffset : centerX + coreOffset;
      const coreY = centerY;
      const baseAngle = Math.atan2(pPos.y - coreY, pPos.x - coreX);

      children.forEach((child, idx) => {
        const count = children.length;
        const spread = count > 1 ? (idx - (count - 1) / 2) * 0.44 : 0;
        const childAngle = baseAngle + spread;
        posMap[child.id] = {
          x: pPos.x + Math.cos(childAngle) * r2,
          y: pPos.y + Math.sin(childAngle) * r2,
        };
      });
    });

    // Collision relaxation pass: guarantee zero overlapping bounding boxes
    const nodeDims = new Map<string, { w: number; h: number }>();
    nodes.forEach((n) => {
      nodeDims.set(n.id, getNodeDimensions(n.label));
    });

    for (let iter = 0; iter < 18; iter++) {
      for (let i = 0; i < nodes.length; i++) {
        const nA = nodes[i];
        const pA = posMap[nA.id];
        if (!pA) continue;
        const dimA = nodeDims.get(nA.id)!;

        for (let j = i + 1; j < nodes.length; j++) {
          const nB = nodes[j];
          const pB = posMap[nB.id];
          if (!pB) continue;
          const dimB = nodeDims.get(nB.id)!;

          const dx = pB.x - pA.x;
          const dy = pB.y - pA.y;
          const minDx = (dimA.w + dimB.w) / 2 + 18;
          const minDy = (dimA.h + dimB.h) / 2 + 12;

          if (Math.abs(dx) < minDx && Math.abs(dy) < minDy) {
            const overlapX = minDx - Math.abs(dx);
            const overlapY = minDy - Math.abs(dy);

            const isCoreA = nA.id === sId || nA.id === oId;
            const isCoreB = nB.id === sId || nB.id === oId;

            if (overlapX < overlapY * 1.5) {
              const signX = dx >= 0 ? 1 : -1;
              const shift = overlapX * 0.5;
              if (!isCoreA && !isCoreB) {
                pA.x -= signX * shift;
                pB.x += signX * shift;
              } else if (!isCoreB) {
                pB.x += signX * overlapX;
              } else if (!isCoreA) {
                pA.x -= signX * overlapX;
              }
            } else {
              const signY = dy >= 0 ? 1 : -1;
              const shift = overlapY * 0.5;
              if (!isCoreA && !isCoreB) {
                pA.y -= signY * shift;
                pB.y += signY * shift;
              } else if (!isCoreB) {
                pB.y += signY * overlapY;
              } else if (!isCoreA) {
                pA.y -= signY * overlapY;
              }
            }
          }
        }
      }
    }

    return posMap;
  }, [nodes, edges, dimensions.width, dimensions.height]);

  // Pan and drag handling
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.stopPropagation();
    const factor = e.deltaY < 0 ? 1.08 : 0.92;
    setZoom((z) => Math.min(2.5, Math.max(0.4, Number((z * factor).toFixed(2)))));
  };

  const resetView = () => {
    setZoom(hopDepth === 2 ? 0.85 : 1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <div
      className={`relative w-full h-full overflow-hidden bg-app-bg select-none ${className}`}
      style={height !== undefined ? (typeof height === "number" ? { height: `${height}px` } : { height }) : { height: "100%" }}
      ref={containerRef}
    >
      {/* Utility Bar Header */}
      <div className="absolute top-2 left-2 right-2 z-10 flex items-center justify-between pointer-events-none">
        <div className="flex items-center gap-1.5 bg-app-surface/90 backdrop-blur-xs border border-app-border px-2 py-1 rounded-[4px] pointer-events-auto shadow-2xs">
          <Layers className="w-3.5 h-3.5 text-blue-500 shrink-0" />
          <span className="text-[11px] font-semibold text-app-heading font-display">
            Local Ego-Graph
          </span>
          <span className="text-app-muted text-[10px]">·</span>
          <div className="inline-flex rounded-[3px] bg-app-subtle p-0.5 border border-app-border text-[10px] font-mono">
            <button
              type="button"
              onClick={() => {
                setHopDepth(1);
                if (zoom < 0.9) setZoom(1);
              }}
              className={`px-1.5 py-0.2 rounded-[2px] transition-colors cursor-pointer ${
                hopDepth === 1
                  ? "bg-app-surface text-blue-600 dark:text-blue-400 font-semibold shadow-2xs"
                  : "text-app-muted hover:text-app-text"
              }`}
            >
              1-Hop
            </button>
            <button
              type="button"
              onClick={() => {
                setHopDepth(2);
                if (zoom >= 1) setZoom(0.85);
              }}
              className={`px-1.5 py-0.2 rounded-[2px] transition-colors cursor-pointer ${
                hopDepth === 2
                  ? "bg-app-surface text-blue-600 dark:text-blue-400 font-semibold shadow-2xs"
                  : "text-app-muted hover:text-app-text"
              }`}
            >
              2-Hop
            </button>
          </div>
        </div>

        {/* Zoom and Fit Controls */}
        <div className="flex items-center gap-1 bg-app-surface/90 backdrop-blur-xs border border-app-border p-1 rounded-[4px] pointer-events-auto shadow-2xs">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(2.5, z + 0.15))}
            className="p-1 rounded hover:bg-app-subtle text-app-muted hover:text-app-heading transition-colors cursor-pointer"
            title="Zoom In"
          >
            <ZoomIn className="w-3 h-3" />
          </button>
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.5, z - 0.15))}
            className="p-1 rounded hover:bg-app-subtle text-app-muted hover:text-app-heading transition-colors cursor-pointer"
            title="Zoom Out"
          >
            <ZoomOut className="w-3 h-3" />
          </button>
          <button
            type="button"
            onClick={resetView}
            className="p-1 rounded hover:bg-app-subtle text-app-muted hover:text-app-heading transition-colors cursor-pointer"
            title="Reset Zoom & Center"
          >
            <RotateCcw className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* SVG Topological Sub-graph Canvas */}
      <svg
        className="w-full h-full cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <defs>
          <marker
            id="arrowhead"
            markerWidth="8"
            markerHeight="6"
            refX="7"
            refY="3"
            orient="auto"
          >
            <polygon
              points="0 0, 8 3, 0 6"
              fill={isDark ? "#71717A" : "#94A3B8"}
            />
          </marker>
          <marker
            id="arrowhead-primary"
            markerWidth="9"
            markerHeight="7"
            refX="8"
            refY="3.5"
            orient="auto"
          >
            <polygon
              points="0 0, 9 3.5, 0 7"
              fill={isAnomaly ? "#E11D48" : "#2563EB"}
            />
          </marker>
          <marker
            id="arrowhead-bridge"
            markerWidth="8"
            markerHeight="6"
            refX="7"
            refY="3"
            orient="auto"
          >
            <polygon
              points="0 0, 8 3, 0 6"
              fill="#F59E0B"
            />
          </marker>
        </defs>

        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Edges */}
          {edges.map((edge) => {
            const p1 = positions[edge.source];
            const p2 = positions[edge.target];
            if (!p1 || !p2) return null;

            const n1 = nodes.find((n) => n.id === edge.source);
            const n2 = nodes.find((n) => n.id === edge.target);
            const dim1 = getNodeDimensions(n1?.label || edge.source);
            const dim2 = getNodeDimensions(n2?.label || edge.target);

            const { x1, y1, x2, y2, midX, midY } = getEdgeLineCoords(
              p1,
              p2,
              dim1.width,
              dim1.height,
              dim2.width,
              dim2.height
            );

            const isHovered = hoveredEdgeId === edge.id;

            const strokeColor = edge.isPrimary
              ? edge.isInvalidBridge
                ? "#E11D48"
                : isDark
                ? "#3B82F6"
                : "#2563EB"
              : edge.isInvalidBridge
              ? "#F59E0B"
              : isDark
              ? "#52525B"
              : "#94A3B8";

            const badgeWidth = Math.min(100, Math.max(54, edge.predicate.length * 6 + 16));

            return (
              <g
                key={edge.id}
                onMouseEnter={() => setHoveredEdgeId(edge.id)}
                onMouseLeave={() => setHoveredEdgeId(null)}
                className="transition-opacity duration-150"
              >
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={strokeColor}
                  strokeWidth={edge.isPrimary ? 2.2 : isHovered ? 2 : 1.5}
                  strokeDasharray={edge.isInvalidBridge ? "4,3" : undefined}
                  markerEnd={
                    edge.isPrimary
                      ? "url(#arrowhead-primary)"
                      : edge.isInvalidBridge
                      ? "url(#arrowhead-bridge)"
                      : "url(#arrowhead)"
                  }
                />

                {/* Predicate label badge on edge center */}
                <g transform={`translate(${midX}, ${midY})`}>
                  <rect
                    x={-badgeWidth / 2}
                    y="-8"
                    width={badgeWidth}
                    height="16"
                    rx="3"
                    fill={isDark ? "#18181B" : "#F8FAFC"}
                    stroke={
                      edge.isInvalidBridge
                        ? "#F59E0B"
                        : isDark
                        ? "rgba(255,255,255,0.1)"
                        : "rgba(0,0,0,0.1)"
                    }
                    strokeWidth="1"
                  />
                  <text
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="font-mono text-[9px] fill-current text-app-muted"
                  >
                    {edge.predicate.length > 14
                      ? edge.predicate.slice(0, 13) + "…"
                      : edge.predicate}
                  </text>
                </g>

                {/* Invalid bridge edge warning badge */}
                {edge.isInvalidBridge && (
                  <g transform={`translate(${midX + 22}, ${midY - 14})`}>
                    <rect
                      x="-6"
                      y="-6"
                      width="12"
                      height="12"
                      rx="6"
                      fill="#F59E0B"
                    />
                    <text
                      textAnchor="middle"
                      dominantBaseline="middle"
                      className="font-sans text-[8px] font-bold fill-white"
                    >
                      !
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const pos = positions[node.id];
            if (!pos) return null;

            const isHovered = hoveredNodeId === node.id;
            const isCenter = node.hop === 0;

            const nodeBg = isCenter
              ? node.isSubject
                ? isDark
                  ? "#1e3a8a"
                  : "#dbeafe"
                : isDark
                ? "#064e3b"
                : "#d1fae5"
              : isDark
              ? "#18181B"
              : "#FFFFFF";

            const borderColor = isCenter
              ? node.isSubject
                ? "#2563EB"
                : "#059669"
              : node.isSinkhole
              ? "#E11D48"
              : isDark
              ? "rgba(255,255,255,0.12)"
              : "rgba(0,0,0,0.12)";

            const textColor = isCenter
              ? node.isSubject
                ? "text-blue-600 dark:text-blue-300 font-bold"
                : "text-emerald-600 dark:text-emerald-300 font-bold"
              : "text-app-heading";

            const { width, height: heightBox } = getNodeDimensions(node.label);

            return (
              <g
                key={node.id}
                transform={`translate(${pos.x - width / 2}, ${pos.y - heightBox / 2})`}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
                onClick={() => onSelectNode?.(node.label)}
                className="cursor-pointer group"
              >
                {/* Node Box */}
                <rect
                  width={width}
                  height={heightBox}
                  rx="4"
                  fill={nodeBg}
                  stroke={isHovered ? "#2563EB" : borderColor}
                  strokeWidth={isCenter || isHovered ? 1.8 : 1}
                  className="transition-all"
                />

                {/* Left accent bar for focus nodes */}
                {isCenter && (
                  <rect
                    x="0"
                    y="0"
                    width="3"
                    height={heightBox}
                    rx="1"
                    fill={node.isSubject ? "#2563EB" : "#059669"}
                  />
                )}

                {/* Node Label Text */}
                <text
                  x="10"
                  y={heightBox / 2}
                  dominantBaseline="middle"
                  className={`font-sans text-[11px] select-none fill-current ${textColor}`}
                >
                  {node.label.length > 17 ? node.label.slice(0, 16) + "…" : node.label}
                </text>

                {/* Degree pill */}
                <g transform={`translate(${width - 16}, ${heightBox / 2})`}>
                  <circle
                    r="6.5"
                    fill={isDark ? "#27272A" : "#F1F5F9"}
                    stroke={isDark ? "rgba(255,255,255,0.08)" : "#E2E8F0"}
                    strokeWidth="1"
                  />
                  <text
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="font-mono tabular-nums text-[8px] fill-current text-app-muted font-medium"
                  >
                    {node.degree}
                  </text>
                </g>

                {/* Sinkhole warning indicator */}
                {node.isSinkhole && (
                  <g transform={`translate(${width - 32}, -4)`}>
                    <rect x="0" y="0" width="30" height="12" rx="2" fill="#E11D48" />
                    <text
                      x="15"
                      y="6"
                      textAnchor="middle"
                      dominantBaseline="middle"
                      className="font-mono text-[7px] font-bold fill-white uppercase"
                    >
                      sinkhole
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* Bottom Status / Legend Overlay */}
      <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between text-[10px] font-mono text-app-muted pointer-events-none">
        <div className="flex items-center gap-3 bg-app-surface/90 backdrop-blur-xs border border-app-border px-2 py-0.5 rounded-[4px] pointer-events-auto">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-[2px] bg-blue-500/30 border border-blue-500 shrink-0" />
            Subject
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-[2px] bg-emerald-500/30 border border-emerald-500 shrink-0" />
            Object
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-0.5 bg-app-muted shrink-0" />
            1-Hop Relation
          </span>
          {isAnomaly && (
            <span className="flex items-center gap-1 text-amber-500 font-semibold">
              <span className="w-2.5 h-0.5 border-b border-dashed border-amber-500 shrink-0" />
              Suspect Bridge Edge
            </span>
          )}
        </div>

        <div className="bg-app-surface/90 backdrop-blur-xs border border-app-border px-2 py-0.5 rounded-[4px] pointer-events-auto">
          Click neighbor node to pivot focus
        </div>
      </div>
    </div>
  );
};
