import type { StudioEdge } from "../../api/types.ts";
import type { EdgeStyleContext } from "./types.ts";

export interface ComputedEdgeStyle {
  stroke: string;
  lineDash?: [number, number];
  lineWidth: number;
  endArrow: boolean;
  labelText: string;
  labelFill: string;
  labelFontSize: number;
  labelBackground: boolean;
  labelBackgroundFill: string;
  labelBackgroundRadius: number;
  cursor: string;
  halo: boolean;
  haloStroke: string;
  haloLineWidth: number;
}

/**
 * Pure function computing G6 edge styling attributes from domain edge & context.
 * Transparently integrates dynamic schema polarity and open-vocabulary alias resolution.
 */
export function computeEdgeStyle(edge: StudioEdge, ctx: EdgeStyleContext): ComputedEdgeStyle {
  const { isDark, graphSettings, activeOverlay, activeMetricResult, isDiffActive, diffData, getPolarity } = ctx;

  // 1. Dynamic polarity resolution: Schema/alias mapping takes priority, falls back to edge payload
  const polarity = getPolarity(edge.type) ?? edge.polarity ?? (edge.props as any)?.polarity ?? null;

  let stroke = isDark ? "#94a3b8" : "#64748b"; // neutral (0)
  let lineDash: [number, number] | undefined = undefined;

  if (polarity === 1) {
    stroke = "#10b981"; // support (+1) emerald
  } else if (polarity === -1) {
    stroke = "#ef4444"; // attack (-1) red
  } else if (polarity === 0) {
    stroke = isDark ? "#94a3b8" : "#64748b"; // neutral (0) solid
  } else {
    // null or undefined: open-vocabulary unmapped predicate (D-15)
    stroke = isDark ? "#64748b" : "#94a3b8";
    lineDash = [4, 4];
  }

  // 2. Diff mode edge styling
  if (isDiffActive && diffData) {
    const edgeStatus = diffData.edge_diff[edge.id];
    if (edgeStatus === "polarity_inverted") {
      stroke = "#f59e0b"; // amber
      lineDash = [6, 3];
    } else if (edgeStatus === "gained") {
      stroke = "#10b981"; // emerald
    } else if (edgeStatus === "lost") {
      stroke = "#ef4444"; // red
      lineDash = [4, 4];
    }
  }

  // Line width mapping prioritizing empirical accuracy / inferential force
  let lineWidth = 1.5;
  if (edge.empirical_accuracy !== null && edge.empirical_accuracy !== undefined) {
    lineWidth = Math.max(1, Math.min(4, Math.round(edge.empirical_accuracy * 3.5)));
  } else if (edge.weight !== null && edge.weight !== undefined) {
    lineWidth = Math.max(1, Math.min(3.5, Math.round(edge.weight * 3)));
  }

  if (isDiffActive && diffData) {
    const edgeStatus = diffData.edge_diff[edge.id];
    if (edgeStatus === "polarity_inverted") {
      lineWidth = 3.5;
    } else if (edgeStatus === "gained") {
      lineWidth = 2.5;
    }
  }

  // Apply customizable edge thickness multiplier
  lineWidth = Math.max(0.5, Math.round(lineWidth * graphSettings.edgeThicknessMultiplier * 2) / 2);

  // 3. Metric Overlay edge styling (Check across all active instances)
  const activeInstances = (ctx.metricInstances || []).filter(
    (inst) => inst.status === "completed" && inst.result && inst.styling?.enabled !== false
  );

  let affectedEdgeDetail = null;
  for (const inst of activeInstances) {
    const aff = inst.result?.affected_edges.find(
      (ae) =>
        ae.relationship_id === edge.id ||
        (ae.source_node_id === edge.source && ae.target_node_id === edge.target)
    );
    if (aff) {
      affectedEdgeDetail = aff;
      break;
    }
  }

  if (!affectedEdgeDetail && activeMetricResult) {
    affectedEdgeDetail = activeMetricResult.affected_edges.find(
      (ae) =>
        ae.relationship_id === edge.id ||
        (ae.source_node_id === edge.source && ae.target_node_id === edge.target)
    );
  }

  if (affectedEdgeDetail) {
    if (affectedEdgeDetail.role === "support") {
      stroke = "#10b981";
      lineDash = undefined;
      lineWidth = Math.max(2, Math.min(5, Math.round(Math.abs(affectedEdgeDetail.contribution || affectedEdgeDetail.weight || 1) * 3)));
    } else if (affectedEdgeDetail.role === "attack") {
      stroke = "#ef4444";
      lineDash = [6, 4];
      lineWidth = Math.max(2, Math.min(5, Math.round(Math.abs(affectedEdgeDetail.contribution || affectedEdgeDetail.weight || 1) * 3)));
    } else if (affectedEdgeDetail.role === "undercut") {
      stroke = "#f59e0b";
      lineDash = [4, 4];
      lineWidth = 2.5;
    }
  }

  // 4. Active Overlay edge styling (Tenability TS_edge or Conformal Uncertainty)
  if (activeOverlay?.kind === "conformal_uncertainty") {
    const isAmbiguous = (edge.conformal_set_size !== null && edge.conformal_set_size !== undefined && edge.conformal_set_size > 1);
    const isLowAcc = (edge.empirical_accuracy !== null && edge.empirical_accuracy !== undefined && edge.empirical_accuracy < 0.85);
    if (isAmbiguous) {
      stroke = "#f59e0b"; // amber for ambiguous multi-class set
      lineDash = [6, 3];
      lineWidth = Math.max(2.5, lineWidth);
    } else if (isLowAcc) {
      stroke = "#ef4444"; // red warning for low empirical accuracy
      lineDash = [4, 4];
      lineWidth = Math.max(2, lineWidth);
    } else {
      stroke = "#10b981"; // calibrated green
    }
  } else if (activeOverlay?.edge_values) {
    const val = activeOverlay.edge_values[edge.id];
    if (val !== undefined && val !== null) {
      if (activeOverlay.kind === "tenability") {
        const ts = typeof val === "number" ? val : 0;
        if (ts >= 0.8) {
          stroke = "#10b981"; // emerald
          lineWidth = Math.max(2, lineWidth);
        } else if (ts >= 0.5) {
          stroke = "#f59e0b"; // amber
          lineWidth = Math.max(2, lineWidth);
        } else {
          stroke = "#f43f5e"; // rose/red
          lineDash = [4, 4];
          lineWidth = Math.max(2.5, lineWidth);
        }
      }
    }
  }

  // 5. Decision Tier Styling (System 1 Fast-Exit dashed vs System 2 Escalation halo)
  let halo = false;
  let haloStroke = "transparent";
  let haloLineWidth = 0;

  if (edge.decision_tier === "fast_exit" || edge.decision_tier === "system1") {
    if (!lineDash) {
      lineDash = [5, 4];
    }
  } else if (edge.decision_tier === "system2") {
    halo = true;
    haloStroke = isDark ? "rgba(59, 130, 246, 0.35)" : "rgba(37, 99, 235, 0.25)";
    haloLineWidth = 3.5;
  }

  // Dual-Attribute Label Text [Acc • I]
  let labelText = "";
  if (graphSettings.showEdgeLabels) {
    labelText = edge.type;
    const hasAcc = edge.empirical_accuracy !== null && edge.empirical_accuracy !== undefined;
    const hasInf = edge.inferential_force !== null && edge.inferential_force !== undefined;
    if (hasAcc && hasInf) {
      labelText += ` [${edge.empirical_accuracy!.toFixed(2)} • ${edge.inferential_force!.toFixed(2)}]`;
    } else if (hasAcc) {
      labelText += ` [Acc: ${edge.empirical_accuracy!.toFixed(2)}]`;
    }
  }

  return {
    stroke,
    lineDash,
    lineWidth,
    endArrow: true,
    labelText,
    labelFill: isDark ? "#8b949e" : "#57606a",
    labelFontSize: 9,
    labelBackground: true,
    labelBackgroundFill: isDark ? "#161b22" : "#ffffff",
    labelBackgroundRadius: 2,
    cursor: "pointer",
    halo,
    haloStroke,
    haloLineWidth,
  };
}
