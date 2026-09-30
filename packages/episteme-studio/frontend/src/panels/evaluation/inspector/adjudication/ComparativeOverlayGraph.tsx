import React, { useState } from "react";
import {
  RotateCcw,
  CheckCircle2,
  Info,
} from "lucide-react";
import { formatPredicate } from "../../../StageArtifactsView";

export interface ComparativeOverlayGraphProps {
  predictedEdge: {
    source?: string;
    predicate?: string;
    target?: string;
  } | null;
  referenceEdge?: {
    source?: string;
    predicate?: string;
    target?: string;
  } | null;
  decision?: "true_positive" | "false_positive" | "schema_alias" | null;
  similarityScore?: number;
  confidence?: number;
  className?: string;
  height?: number | string;
}

/**
 * Dual-State Comparative Overlay Graph
 * Superimposes predicted propositional graph over reference gold standard.
 * Features legible node labels, hover tooltips, and non-destructive spatial overlay.
 */
export const ComparativeOverlayGraph: React.FC<ComparativeOverlayGraphProps> = ({
  predictedEdge,
  referenceEdge,
  decision,
  similarityScore = 0.85,
  confidence = 0.9,
  className = "",
  height = 250,
}) => {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [hoveredEntity, setHoveredEntity] = useState<{ label: string; role: string; raw: string } | null>(null);

  if (!predictedEdge) {
    return (
      <div
        className={`flex flex-col items-center justify-center p-6 text-center text-xs text-app-muted bg-app-bg/50 border border-app-border rounded-lg ${className}`}
        style={{ height }}
      >
        <Info className="w-6 h-6 opacity-30 mb-1.5" />
        <span>No active candidate proposition to visualize</span>
      </div>
    );
  }

  const clean = (val?: string) => String(val || "").replace(/^str:|^pred:|^gold:/, "");

  const rawPredSource = String(predictedEdge.source || "");
  const rawPredTarget = String(predictedEdge.target || "");
  const predSource = clean(predictedEdge.source) || "Subject";
  const predPred = formatPredicate(predictedEdge.predicate || "relates_to");
  const predTarget = clean(predictedEdge.target) || "Object";

  const hasGold = Boolean(referenceEdge && (referenceEdge.source || referenceEdge.predicate || referenceEdge.target));
  const rawRefSource = String(referenceEdge?.source || "");
  const rawRefTarget = String(referenceEdge?.target || "");
  const refSource = hasGold ? clean(referenceEdge?.source) || predSource : null;
  const refPred = hasGold ? formatPredicate(referenceEdge?.predicate || "") : null;
  const refTarget = hasGold ? clean(referenceEdge?.target) || predTarget : null;

  const isExactPredicateMatch = refPred && refPred.toLowerCase() === predPred.toLowerCase();
  const isExactEntityMatch = refSource === predSource && refTarget === predTarget;
  const isCompleteMatch = isExactPredicateMatch && isExactEntityMatch;

  // Determine Edge Visual States
  let predEdgeColor = "#3b82f6"; // default blue
  if (decision === "true_positive") {
    predEdgeColor = "#10b981"; // green
  } else if (decision === "false_positive") {
    predEdgeColor = "#ef4444"; // red
  } else if (decision === "schema_alias") {
    predEdgeColor = "#8b5cf6"; // violet
  }

  // Generous geometry for 560x250 viewBox
  const subX = 110;
  const subY = 125;
  const objX = 450;
  const objY = 125;

  const nodeWidth = 160;
  const nodeHeight = 56;

  // Curvature offsets for dual edges
  const predCurve = isCompleteMatch ? 0 : -36;
  const goldCurve = isCompleteMatch ? 0 : 36;

  // Helper to split long entity strings into 2 lines cleanly
  const splitTextIntoLines = (text: string, maxCharsPerLine = 18): [string, string] => {
    if (text.length <= maxCharsPerLine) return [text, ""];
    // Try to split on space or underscore
    const words = text.split(/[\s_]+/);
    let line1 = "";
    let line2 = "";
    for (const w of words) {
      if ((line1 + " " + w).trim().length <= maxCharsPerLine) {
        line1 = (line1 + " " + w).trim();
      } else {
        line2 = (line2 + " " + w).trim();
      }
    }
    if (!line2 && text.length > maxCharsPerLine) {
      return [text.slice(0, maxCharsPerLine), text.slice(maxCharsPerLine, maxCharsPerLine * 2)];
    }
    return [line1 || text.slice(0, maxCharsPerLine), line2 || text.slice(maxCharsPerLine)];
  };

  const [subLine1, subLine2] = splitTextIntoLines(predSource);
  const [objLine1, objLine2] = splitTextIntoLines(predTarget);

  return (
    <div className={`relative flex flex-col bg-app-bg border border-app-border rounded-lg overflow-hidden select-none ${className}`}>
      {/* Top Status & Overlay Legend Strip */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-app-surface border-b border-app-border text-[10px]">
        <div className="flex items-center gap-2 font-mono">
          <span className="text-app-heading font-semibold">Dual-State Overlay</span>
          <span className="text-app-muted">|</span>
          <span className="flex items-center gap-1 text-app-muted">
            <span className="w-2.5 h-1 rounded-full" style={{ backgroundColor: predEdgeColor }} />
            <span>Predicted</span>
          </span>
          {hasGold && !isCompleteMatch && (
            <span className="flex items-center gap-1 text-app-muted">
              <span className="w-3 h-0.5 border-t-2 border-dashed border-emerald-500" />
              <span>Gold Target</span>
            </span>
          )}
          {isCompleteMatch && (
            <span className="flex items-center gap-1 text-emerald-500 font-semibold">
              <CheckCircle2 className="w-3 h-3" />
              <span>Aligned</span>
            </span>
          )}
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(1.6, z + 0.15))}
            className="px-1.5 py-0.5 rounded hover:bg-app-subtle text-app-muted hover:text-app-text font-mono text-xs transition-colors cursor-pointer"
            title="Zoom In"
          >
            +
          </button>
          <span className="font-mono text-[9px] text-app-muted tabular-nums">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.6, z - 0.15))}
            className="px-1.5 py-0.5 rounded hover:bg-app-subtle text-app-muted hover:text-app-text font-mono text-xs transition-colors cursor-pointer"
            title="Zoom Out"
          >
            -
          </button>
          <button
            type="button"
            onClick={() => {
              setZoom(1);
              setPan({ x: 0, y: 0 });
            }}
            className="p-1 rounded hover:bg-app-subtle text-app-muted hover:text-app-text transition-colors cursor-pointer"
            title="Reset View"
          >
            <RotateCcw className="w-2.5 h-2.5" />
          </button>
        </div>
      </div>

      {/* SVG Canvas Area */}
      <div className="flex-1 relative overflow-hidden" style={{ height }}>
        <svg
          viewBox="0 0 560 250"
          className="w-full h-full cursor-grab active:cursor-grabbing"
          style={{
            transform: `scale(${zoom}) translate(${pan.x}px, ${pan.y}px)`,
            transformOrigin: "center center",
            transition: "transform 0.15s ease-out",
          }}
        >
          <defs>
            {/* Arrow Marker for Predicted Edge */}
            <marker
              id="pred-arrow-legible"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill={predEdgeColor} />
            </marker>

            {/* Arrow Marker for Gold Standard Edge */}
            <marker
              id="gold-arrow-legible"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#10b981" />
            </marker>
          </defs>

          {/* Background Grid Pattern */}
          <pattern id="grid-dots" width="24" height="24" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1" fill="currentColor" className="text-app-border/70" />
          </pattern>
          <rect width="100%" height="100%" fill="url(#grid-dots)" />

          {/* 1. EDGE: Predicted Proposition */}
          {(() => {
            const startX = subX + nodeWidth / 2;
            const endX = objX - nodeWidth / 2;
            const midX = (startX + endX) / 2;
            const midY = (subY + objY) / 2 + predCurve;
            const pathD = `M ${startX} ${subY} Q ${midX} ${midY} ${endX} ${subY}`;
            const boxWidth = Math.max(140, predPred.length * 7.5 + 24);

            return (
              <g className="group/pred-edge">
                <path
                  d={pathD}
                  fill="none"
                  stroke={predEdgeColor}
                  strokeWidth={decision === "false_positive" ? 3 : 2.5}
                  markerEnd="url(#pred-arrow-legible)"
                  className="transition-all"
                />

                {/* Predicate label box */}
                <g transform={`translate(${midX}, ${midY + (predCurve < 0 ? -6 : 6)})`}>
                  <rect
                    x={-boxWidth / 2}
                    y="-13"
                    width={boxWidth}
                    height="24"
                    rx="5"
                    fill="currentColor"
                    className="text-app-surface"
                    stroke={predEdgeColor}
                    strokeWidth="1.5"
                  />
                  <text
                    x="0"
                    y="3"
                    textAnchor="middle"
                    className="fill-current text-app-heading font-mono text-[10px] font-bold select-none pointer-events-none"
                  >
                    {predPred}
                  </text>
                </g>

                {/* Confidence indicator pill above */}
                <g transform={`translate(${midX}, ${midY - 22})`}>
                  <rect
                    x="-26"
                    y="-8"
                    width="52"
                    height="15"
                    rx="3"
                    fill="currentColor"
                    className="text-app-bg"
                    stroke={predEdgeColor}
                    strokeWidth="0.8"
                  />
                  <text
                    x="0"
                    y="3"
                    textAnchor="middle"
                    className="fill-current text-[8.5px] font-mono font-semibold text-app-text"
                  >
                    {(confidence * 100).toFixed(0)}% conf
                  </text>
                </g>
              </g>
            );
          })()}

          {/* 2. EDGE: Reference Gold Standard (Superimposed if different) */}
          {hasGold && !isCompleteMatch && refPred && (() => {
            const startX = subX + nodeWidth / 2;
            const endX = objX - nodeWidth / 2;
            const midX = (startX + endX) / 2;
            const midY = (subY + objY) / 2 + goldCurve;
            const pathD = `M ${startX} ${subY} Q ${midX} ${midY} ${endX} ${subY}`;
            const boxWidth = Math.max(140, refPred.length * 7.5 + 28);

            return (
              <g className="group/gold-edge">
                {/* Dashed Gold Reference Edge Line */}
                <path
                  d={pathD}
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="2.5"
                  strokeDasharray="6,4"
                  markerEnd="url(#gold-arrow-legible)"
                  className="transition-all"
                />

                {/* Gold Reference Label Box */}
                <g transform={`translate(${midX}, ${midY + (goldCurve > 0 ? 10 : -10)})`}>
                  <rect
                    x={-boxWidth / 2}
                    y="-13"
                    width={boxWidth}
                    height="24"
                    rx="5"
                    fill="currentColor"
                    className="text-app-surface"
                    stroke="#10b981"
                    strokeWidth="1.5"
                    strokeDasharray="4,2"
                  />
                  <text
                    x="0"
                    y="3"
                    textAnchor="middle"
                    className="fill-emerald-600 dark:fill-emerald-400 font-mono text-[10px] font-bold select-none pointer-events-none"
                  >
                    ★ {refPred}
                  </text>
                </g>

                {/* Soft Similarity score pill below */}
                <g transform={`translate(${midX}, ${midY + 28})`}>
                  <rect
                    x="-32"
                    y="-8"
                    width="64"
                    height="15"
                    rx="3"
                    fill="currentColor"
                    className="text-app-bg"
                    stroke="#10b981"
                    strokeWidth="0.8"
                  />
                  <text
                    x="0"
                    y="3"
                    textAnchor="middle"
                    className="fill-amber-500 font-mono text-[8.5px] font-bold"
                  >
                    τ: {similarityScore.toFixed(3)}
                  </text>
                </g>
              </g>
            );
          })()}

          {/* Missing in Gold Callout (when reference edge is completely absent) */}
          {!hasGold && (
            <g transform={`translate(${(subX + objX) / 2}, ${subY + 54})`}>
              <rect
                x="-105"
                y="-11"
                width="210"
                height="22"
                rx="4"
                fill="currentColor"
                className="text-rose-500/10"
                stroke="#ef4444"
                strokeWidth="1"
                strokeDasharray="4,3"
              />
              <text
                x="0"
                y="4"
                textAnchor="middle"
                className="fill-rose-500 font-sans text-[9.5px] font-semibold"
              >
                Missing expected edge in gold standard
              </text>
            </g>
          )}

          {/* 3. NODE: Subject Entity Pill (Full Multi-Line Text) */}
          <g
            transform={`translate(${subX}, ${subY})`}
            className="cursor-pointer"
            onMouseEnter={() =>
              setHoveredEntity({ label: predSource, role: "Subject Concept", raw: rawPredSource })
            }
            onMouseLeave={() => setHoveredEntity(null)}
          >
            <title>{`Subject: ${predSource} (${rawPredSource})`}</title>
            <rect
              x={-nodeWidth / 2}
              y={-nodeHeight / 2}
              width={nodeWidth}
              height={nodeHeight}
              rx="8"
              fill="currentColor"
              className="text-app-surface transition-colors"
              stroke={decision === "false_positive" ? "#ef4444" : "#3b82f6"}
              strokeWidth="2"
            />
            {/* Subject Role Header Bar inside Node */}
            <path
              d={`M ${-nodeWidth / 2} ${-nodeHeight / 2 + 16} L ${nodeWidth / 2} ${-nodeHeight / 2 + 16}`}
              stroke="currentColor"
              className="text-app-border/80"
              strokeWidth="0.8"
            />
            <text
              x={-nodeWidth / 2 + 8}
              y={-nodeHeight / 2 + 11}
              className="fill-current text-blue-500 font-mono text-[8.5px] font-bold uppercase tracking-wider select-none"
            >
              SUBJECT CONCEPT
            </text>
            {/* Entity Name (Up to 2 Clean Lines) */}
            <text
              x="0"
              y={subLine2 ? 0 : 7}
              textAnchor="middle"
              className="fill-current text-app-heading font-sans font-bold text-[11px] select-none"
            >
              {subLine1}
            </text>
            {subLine2 && (
              <text
                x="0"
                y="15"
                textAnchor="middle"
                className="fill-current text-app-heading font-sans font-bold text-[11px] select-none"
              >
                {subLine2}
              </text>
            )}
          </g>

          {/* 4. NODE: Target Entity Pill (Full Multi-Line Text) */}
          <g
            transform={`translate(${objX}, ${objY})`}
            className="cursor-pointer"
            onMouseEnter={() =>
              setHoveredEntity({ label: predTarget, role: "Target Object", raw: rawPredTarget })
            }
            onMouseLeave={() => setHoveredEntity(null)}
          >
            <title>{`Object: ${predTarget} (${rawPredTarget})`}</title>
            <rect
              x={-nodeWidth / 2}
              y={-nodeHeight / 2}
              width={nodeWidth}
              height={nodeHeight}
              rx="8"
              fill="currentColor"
              className="text-app-surface transition-colors"
              stroke={decision === "false_positive" ? "#ef4444" : "#3b82f6"}
              strokeWidth="2"
            />
            {/* Target Role Header Bar inside Node */}
            <path
              d={`M ${-nodeWidth / 2} ${-nodeHeight / 2 + 16} L ${nodeWidth / 2} ${-nodeHeight / 2 + 16}`}
              stroke="currentColor"
              className="text-app-border/80"
              strokeWidth="0.8"
            />
            <text
              x={-nodeWidth / 2 + 8}
              y={-nodeHeight / 2 + 11}
              className="fill-current text-emerald-500 font-mono text-[8.5px] font-bold uppercase tracking-wider select-none"
            >
              TARGET OBJECT
            </text>
            {/* Entity Name (Up to 2 Clean Lines) */}
            <text
              x="0"
              y={objLine2 ? 0 : 7}
              textAnchor="middle"
              className="fill-current text-app-heading font-sans font-bold text-[11px] select-none"
            >
              {objLine1}
            </text>
            {objLine2 && (
              <text
                x="0"
                y="15"
                textAnchor="middle"
                className="fill-current text-app-heading font-sans font-bold text-[11px] select-none"
              >
                {objLine2}
              </text>
            )}
          </g>
        </svg>
      </div>

      {/* Dynamic Hover Inspector or Default Proposition Footnote */}
      <div className="px-3 py-1.5 bg-app-surface/80 border-t border-app-border flex items-center justify-between text-[10px] font-mono text-app-muted">
        {hoveredEntity ? (
          <div className="flex items-center gap-2 truncate">
            <span className="font-bold text-blue-500">{hoveredEntity.role}:</span>
            <span className="font-semibold text-app-heading">{hoveredEntity.label}</span>
            <span className="text-app-muted text-[9px] truncate">({hoveredEntity.raw})</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 truncate">
            <span className="font-semibold text-app-text truncate">{predSource}</span>
            <span className="text-app-muted">──►</span>
            <span className="font-semibold text-app-text truncate">{predTarget}</span>
          </div>
        )}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-app-muted">Soft τ:</span>
          <span className="font-bold text-amber-500 tabular-nums">
            {similarityScore.toFixed(3)}
          </span>
        </div>
      </div>
    </div>
  );
};
