import type {StudioNode} from "../../api/types.ts";
import type {NodeStyleContext} from "./types.ts";

export interface ComputedNodeStyle {
  fill: string;
  stroke: string;
  size: number;
  lineDash?: [number, number];
  lineWidth: number;
  labelText: string;
  labelFill: string;
  labelFontSize: number;
  labelPlacement: "bottom";
  labelBackground: boolean;
  labelBackgroundFill: string;
  labelBackgroundRadius: number;
  cursor: string;
}

/**
 * Computes overlay-specific styles for a node (Tenability, continuous or categorical scales).
 */
export function getOverlayNodeStyle(nodeId: string, ctx: NodeStyleContext) {
  const { activeOverlay } = ctx;
  if (!activeOverlay || !activeOverlay.node_values) return null;
  const val = activeOverlay.node_values[nodeId];
  if (val === undefined || val === null) return null;

  if (activeOverlay.kind === "tenability") {
    const ts = typeof val === "number" ? val : 0;
    let fill = "#10b981"; // emerald-500: tenable
    let stroke = "#34d399";
    if (ts < 0.5) {
      fill = "#f43f5e"; // rose-500: non-tenable / empirical contradiction
      stroke = "#fda4af";
    } else if (ts < 0.8) {
      fill = "#f59e0b"; // amber-500: tension
      stroke = "#fcd34d";
    }
    const size = Math.round(22 + ts * 12);
    return {
      fill,
      stroke,
      size,
      lineWidth: ts < 0.5 ? 3 : 2,
    };
  }

  if (typeof val === "number" && activeOverlay.scale === "continuous") {
    const domain = activeOverlay.domain as [number, number] | undefined;
    const min = domain && domain[0] !== undefined ? domain[0] : 0;
    const max = domain && domain[1] !== undefined ? domain[1] : 1;
    const norm = max > min ? Math.max(0, Math.min(1, (val - min) / (max - min))) : 0.5;
    const size = Math.round(20 + norm * 20);
    return {
      size,
      stroke: "#fbbf24", // gold amber highlight
      lineWidth: 2.5,
    };
  } else if (activeOverlay.scale === "categorical" || typeof val === "string") {
    const colors = [
      "#f43f5e",
      "#8b5cf6",
      "#06b6d4",
      "#10b981",
      "#f59e0b",
      "#ec4899",
      "#3b82f6",
      "#14b8a6",
      "#84cc16",
      "#eab308",
    ];
    const hash = String(val)
      .split("")
      .reduce((acc, c) => acc + c.charCodeAt(0), 0);
    return {
      fill: colors[hash % colors.length],
      stroke: "#ffffff",
      lineWidth: 2,
    };
  }
  return null;
}

/**
 * Pure function computing G6 node styling attributes from domain node & context.
 */
export function computeNodeStyle(node: StudioNode, ctx: NodeStyleContext): ComputedNodeStyle {
  const { isDark, graphSettings, activeMetricResult, isDiffActive, diffData } = ctx;

  let fill = "#3b82f6"; // L1 Chunk (blue)
  let stroke = "#60a5fa";
  let size = 20;

  if (node.layer === 2) {
    fill = "#7c3aed"; // L2 Entity (purple)
    stroke = "#a78bfa";
    size = 24;
  } else if (node.layer === 3) {
    fill = "#059669"; // L3 TheoryNet (emerald)
    stroke = "#34d399";
    size = 26;
  }

  if (node.synthetic) {
    fill = "#0891b2";
    stroke = "#38bdf8";
  }

  // Apply customizable node size scaling
  size = Math.max(10, Math.round(size * graphSettings.nodeSizeMultiplier));

  let lineDash: [number, number] | undefined = undefined;
  let lineWidth = 1.5;

  if (!node.resolved) {
    // Dangling unresolved reference (D-16)
    stroke = "#f59e0b";
    lineDash = [4, 4];
    fill = isDark ? "#78350f" : "#d97706";
    lineWidth = 2;
  }

  const overlayStyle = getOverlayNodeStyle(node.id, ctx);
  if (overlayStyle) {
    if (overlayStyle.fill) fill = overlayStyle.fill;
    if (overlayStyle.stroke) stroke = overlayStyle.stroke;
    if (overlayStyle.size) size = overlayStyle.size;
    if (overlayStyle.lineWidth) lineWidth = overlayStyle.lineWidth;
  }

  let rawLabel = node.label || node.id;

  // Diff mode visual highlighting
  if (isDiffActive && diffData) {
    const nodeStatus = diffData.node_diff[node.id];
    if (nodeStatus === "gained") {
      stroke = "#10b981";
      lineWidth = 3;
      rawLabel = `[+] ${rawLabel}`;
    } else if (nodeStatus === "lost") {
      stroke = "#ef4444";
      lineDash = [4, 4];
      lineWidth = 1.5;
      fill = isDark ? "#450a0a" : "#fee2e2";
      rawLabel = `[-] ${rawLabel}`;
    }

    if (diffData.rho_deltas && diffData.rho_deltas[node.id] !== undefined) {
      const delta = diffData.rho_deltas[node.id];
      if (Math.abs(delta) > 0.01) {
        rawLabel = `${rawLabel} (Δρ: ${delta > 0 ? "+" : ""}${delta})`;
      }
    }
  }

  // Metric Overlay state styling (Multi-layer stackable with conflict resolution)
  const activeInstances = (ctx.metricInstances || []).filter(
    (inst) => inst.status === "completed" && inst.result && inst.styling?.enabled !== false
  );

  if (activeInstances.length > 0) {
    let sizeScaled = false;
    let colorGradientApplied = false;
    const isStack = ctx.scaleMode !== "overwrite";

    for (const inst of activeInstances) {
      const res = inst.result!;
      const detail = res.affected_nodes?.[node.id];
      const isFocusNode = node.id === inst.focusNodeId || node.id === res.focus_node_id;

      if (isFocusNode) {
        size = Math.round(size * 1.25);
        stroke = "#06b6d4";
        lineWidth = 3.5;
      }

      if (detail) {
        // Extract normalized score if available
        let score = 0.5;
        if (typeof detail.metadata?.pagerank === "number") {
          score = detail.metadata.pagerank;
        } else if (typeof detail.metadata?.degree === "number") {
          score = detail.metadata.degree;
        } else if (typeof detail.metadata?.score === "number") {
          score = detail.metadata.score;
        } else if (typeof detail.net_contribution === "number") {
          score = Math.abs(detail.net_contribution);
        }

        // Clamp to [0, 1]
        const normScore = Math.max(0, Math.min(1, score > 1 ? score / 10 : score));

        // 1. Size scaling modulated by influence strength
        if (inst.styling?.sizeScaling) {
          const strength = inst.styling.sizeStrength || "normal";
          const strengthMultiplier =
            strength === "subtle" ? 0.5 : strength === "strong" ? 1.8 : 1.0;

          if (isStack) {
            // Stack mode: Additive size scaling modulated by influence strength
            const delta = 0.35 * strengthMultiplier * normScore;
            size = Math.min(80, Math.round(size * (1 + delta)));
            sizeScaled = true;
          } else if (!sizeScaled) {
            // Overwrite mode: Only top priority applies, modulated by influence strength
            const delta = 0.6 * strengthMultiplier * normScore;
            size = Math.min(80, Math.round(size * (1 + delta)));
            sizeScaled = true;
          }
        }

        // 2. Color gradient
        if (inst.styling?.colorGradient) {
          // Viridis-like sequential color ramp
          const ramp = [
            "#38bdf8", // Sky blue (low)
            "#6366f1", // Indigo (mid-low)
            "#a855f7", // Purple (mid)
            "#ec4899", // Pink (mid-high)
            "#f59e0b", // Amber/Gold (high)
          ];
          const rampIdx = Math.min(ramp.length - 1, Math.floor(normScore * ramp.length));
          const rampColor = ramp[rampIdx];

          if (!colorGradientApplied) {
            // Primary color driver sets the solid fill
            fill = rampColor;
            colorGradientApplied = true;
          } else if (!isFocusNode) {
            // Secondary color driver sets the outer stroke / ring (halo) so it isn't silenced
            stroke = rampColor;
            lineWidth = Math.max(lineWidth, 3);
          }
        }

        // 3. Semantic causal roles (QBAF support / attack)
        const isMultiRole = detail.roles.includes("support") && detail.roles.includes("attack");
        if (isMultiRole) {
          if (!isFocusNode && !colorGradientApplied) stroke = "#a855f7";
          lineWidth = Math.max(lineWidth, 3);
          if (!rawLabel.startsWith("[")) rawLabel = `[▲/▼] ${rawLabel}`;
        } else if (detail.roles.includes("support")) {
          if (!isFocusNode && !colorGradientApplied) stroke = "#10b981";
          lineWidth = Math.max(lineWidth, 2.5);
          if (!rawLabel.startsWith("[")) rawLabel = `[▲] ${rawLabel}`;
        } else if (detail.roles.includes("attack")) {
          if (!isFocusNode && !colorGradientApplied) stroke = "#ef4444";
          lineWidth = Math.max(lineWidth, 2.5);
          if (!rawLabel.startsWith("[")) rawLabel = `[▼] ${rawLabel}`;
        } else if (detail.roles.includes("cluster") && !isFocusNode && !colorGradientApplied) {
          const comm = detail.metadata?.community ?? detail.metadata?.cluster;
          if (comm !== undefined) {
            const clusterColors = [
              "#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6",
              "#06b6d4", "#f97316", "#14b8a6", "#6366f1", "#84cc16",
            ];
            const idx = typeof comm === "number" ? comm : String(comm).charCodeAt(0);
            stroke = clusterColors[Math.abs(idx) % clusterColors.length];
            lineWidth = 2.5;
          }
        }
      }
    }
  } else if (activeMetricResult) {
    // Single active metric fallback
    if (node.id === activeMetricResult.focus_node_id) {
      size = Math.round(size * 1.25);
      stroke = "#06b6d4";
      lineWidth = 3.5;
    } else if (activeMetricResult.affected_nodes[node.id]) {
      const detail = activeMetricResult.affected_nodes[node.id];
      const isMultiRole = detail.roles.includes("support") && detail.roles.includes("attack");
      if (isMultiRole) {
        stroke = "#a855f7"; // purple
        lineWidth = 3;
        rawLabel = `[▲/▼] ${rawLabel}`;
      } else if (detail.roles.includes("support")) {
        stroke = "#10b981"; // green
        lineWidth = 2.5;
        rawLabel = `[▲] ${rawLabel}`;
      } else if (detail.roles.includes("attack")) {
        stroke = "#ef4444"; // red
        lineWidth = 2.5;
        rawLabel = `[▼] ${rawLabel}`;
      } else if (detail.roles.includes("cluster")) {
        const comm = detail.metadata?.community ?? detail.metadata?.cluster;
        if (comm !== undefined) {
          const clusterColors = [
            "#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6",
            "#06b6d4", "#f97316", "#14b8a6", "#6366f1", "#84cc16"
          ];
          const idx = typeof comm === "number" ? comm : String(comm).charCodeAt(0);
          stroke = clusterColors[Math.abs(idx) % clusterColors.length];
          lineWidth = 2.5;
        }
      }
    }
  }

  const maxLen = graphSettings.labelMaxLength;
  const displayLabel =
    rawLabel.length > maxLen
      ? rawLabel.slice(0, Math.max(3, maxLen - 2)) + "…"
      : rawLabel;

  return {
    fill,
    stroke,
    size,
    lineDash,
    lineWidth,
    labelText: displayLabel,
    labelFill: isDark ? "#e6edf3" : "#1f2328",
    labelFontSize: graphSettings.labelFontSize,
    labelPlacement: "bottom" as const,
    labelBackground: true,
    labelBackgroundFill: isDark ? "#0d1117" : "#f6f8fa",
    labelBackgroundRadius: 3,
    cursor: "pointer",
  };
}
