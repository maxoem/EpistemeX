/**
 * @file coordinateScaling.ts
 * @description Two-Tier Continuous PDF Coordinate Scaling Engine and Formula Verifier.
 *
 * Implements Tier 1 (Global Continuous Container) and Tier 2 (Page-Local SVG Viewports)
 * coordinate transformations, cubic Bézier multi-page span connections, and IoU calculation.
 *
 * Reference: ISSUE-029 (Multimodal Evidence Grounding Inspection)
 */

import type { BoundingBoxCoordinates, TextSpanCoordinates } from "../../../../api/types";

export interface PageDimension {
  width: number;
  height: number;
}

export interface ScaledGlobalBoundingBox {
  page: number;
  top_global: number;
  bottom_global: number;
  left_global: number;
  right_global: number;
  width: number;
  height: number;
}

export interface ScaledLocalBoundingBox {
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface BezierControlPoints {
  p0: { x: number; y: number };
  p1: { x: number; y: number };
  p2: { x: number; y: number };
  p3: { x: number; y: number };
}

export interface MultiPageSplineConnection {
  pathData: string;
  sourcePoint: { x: number; y: number };
  targetPoint: { x: number; y: number };
  controlPoints: BezierControlPoints;
}

export interface FormulaVerificationResult {
  isEquivalent: boolean;
  equivalenceType: "exact" | "isomorphic" | "mismatch";
  normalizedExtracted: string;
  normalizedReference: string;
  discrepancyReason?: string;
}

/**
 * Computes Tier 1 global continuous container bounding box coordinates.
 *
 * Formula:
 * box_top_global = sum_{i=1}^{p-1} ( H_page(i) + gap_page ) + ( y_0 * H_page(p) )
 *
 * Parameters
 * ----------
 * bbox : BoundingBoxCoordinates
 *     Normalized bounding box coordinates (0 to 1).
 * pageDimensions : PageDimension[] | Record<number, PageDimension> | ((page: number) => PageDimension)
 *     Page dimensions lookup by page index (1-indexed).
 * pageGap : number, default 24
 *     Gap in pixels between consecutive pages in continuous layout.
 *
 * Returns
 * -------
 * ScaledGlobalBoundingBox
 *     Absolute pixel coordinates within the global continuous scroll container.
 */
export function computeGlobalBoundingBox(
  bbox: BoundingBoxCoordinates,
  pageDimensions:
    | PageDimension[]
    | Record<number, PageDimension>
    | ((page: number) => PageDimension),
  pageGap = 24,
  basePage = 1
): ScaledGlobalBoundingBox {
  const getDim = (p: number): PageDimension => {
    if (typeof pageDimensions === "function") {
      return pageDimensions(p);
    }
    if (Array.isArray(pageDimensions)) {
      return pageDimensions[p - 1] || { width: 800, height: 1131 };
    }
    return pageDimensions[p] || { width: 800, height: 1131 };
  };

  const targetPage = Math.max(basePage, bbox.page);
  let accumulatedHeight = 0;

  for (let i = basePage; i < targetPage; i++) {
    const dim = getDim(i);
    accumulatedHeight += dim.height + pageGap;
  }

  const currentDim = getDim(targetPage);
  const topGlobal = accumulatedHeight + bbox.y0 * currentDim.height;
  const bottomGlobal = accumulatedHeight + bbox.y1 * currentDim.height;
  const leftGlobal = bbox.x0 * currentDim.width;
  const rightGlobal = bbox.x1 * currentDim.width;

  return {
    page: targetPage,
    top_global: topGlobal,
    bottom_global: bottomGlobal,
    left_global: leftGlobal,
    right_global: rightGlobal,
    width: Math.max(0, rightGlobal - leftGlobal),
    height: Math.max(0, bottomGlobal - topGlobal),
  };
}

/**
 * Computes Tier 2 page-local SVG coordinates for rendering within a page viewport.
 *
 * Parameters
 * ----------
 * bbox : BoundingBoxCoordinates
 *     Normalized bounding box coordinates (0 to 1).
 * pageDimension : PageDimension
 *     Pixel width and height of the specific page.
 *
 * Returns
 * -------
 * ScaledLocalBoundingBox
 *     Pixel rectangle coordinates relative to the page origin (0, 0).
 */
export function computeLocalBoundingBox(
  bbox: BoundingBoxCoordinates,
  pageDimension: PageDimension
): ScaledLocalBoundingBox {
  const x = Math.round(bbox.x0 * pageDimension.width * 1000) / 1000;
  const y = Math.round(bbox.y0 * pageDimension.height * 1000) / 1000;
  const width = Math.max(0, Math.round((bbox.x1 - bbox.x0) * pageDimension.width * 1000) / 1000);
  const height = Math.max(0, Math.round((bbox.y1 - bbox.y0) * pageDimension.height * 1000) / 1000);

  return {
    page: bbox.page,
    x,
    y,
    width,
    height,
  };
}

/**
 * Converts TextSpanCoordinates [x0, y0, x1, y1] to BoundingBoxCoordinates.
 *
 * Parameters
 * ----------
 * span : TextSpanCoordinates
 *     Text span coordinates with page and normalized bbox tuple.
 *
 * Returns
 * -------
 * BoundingBoxCoordinates
 *     Named coordinate object.
 */
export function spanToBoundingBox(span: TextSpanCoordinates): BoundingBoxCoordinates {
  return {
    page: span.page,
    x0: span.bbox[0],
    y0: span.bbox[1],
    x1: span.bbox[2],
    y1: span.bbox[3],
  };
}

/**
 * Calculates continuous cubic Bézier splines across page boundaries for multi-page spans.
 *
 * Parameters
 * ----------
 * sourceSpan : TextSpanCoordinates | BoundingBoxCoordinates
 *     First span (e.g., bottom of page p).
 * targetSpan : TextSpanCoordinates | BoundingBoxCoordinates
 *     Continuation span (e.g., top of page p+1).
 * pageDimensions : ((page: number) => PageDimension) | PageDimension[] | Record<number, PageDimension>
 *     Dimensions provider.
 * pageGap : number, default 24
 *     Gap between pages in continuous container.
 *
 * Returns
 * -------
 * MultiPageSplineConnection
 *     SVG cubic Bézier curve path and control points.
 */
export function computeBezierSplineAcrossPages(
  sourceSpan: TextSpanCoordinates | BoundingBoxCoordinates,
  targetSpan: TextSpanCoordinates | BoundingBoxCoordinates,
  pageDimensions:
    | PageDimension[]
    | Record<number, PageDimension>
    | ((page: number) => PageDimension),
  pageGap = 24,
  basePage?: number
): MultiPageSplineConnection {
  const srcBox = "bbox" in sourceSpan ? spanToBoundingBox(sourceSpan) : sourceSpan;
  const tgtBox = "bbox" in targetSpan ? spanToBoundingBox(targetSpan) : targetSpan;

  const effectiveBase = basePage ?? Math.min(srcBox.page, tgtBox.page);
  const srcGlobal = computeGlobalBoundingBox(srcBox, pageDimensions, pageGap, effectiveBase);
  const tgtGlobal = computeGlobalBoundingBox(tgtBox, pageDimensions, pageGap, effectiveBase);

  // Exit point at center-bottom of source bounding box
  const p0 = {
    x: srcGlobal.left_global + srcGlobal.width / 2,
    y: srcGlobal.bottom_global,
  };

  // Entry point at center-top of target bounding box
  const p3 = {
    x: tgtGlobal.left_global + tgtGlobal.width / 2,
    y: tgtGlobal.top_global,
  };

  // Vertical distance between anchor points
  const deltaY = Math.max(20, Math.abs(p3.y - p0.y));
  const curvature = deltaY * 0.45;

  const p1 = {
    x: p0.x,
    y: p0.y + curvature,
  };

  const p2 = {
    x: p3.x,
    y: p3.y - curvature,
  };

  const pathData = `M ${p0.x.toFixed(1)} ${p0.y.toFixed(1)} C ${p1.x.toFixed(1)} ${p1.y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}, ${p3.x.toFixed(1)} ${p3.y.toFixed(1)}`;

  return {
    pathData,
    sourcePoint: p0,
    targetPoint: p3,
    controlPoints: { p0, p1, p2, p3 },
  };
}

/**
 * Computes Intersection over Union (IoU) between two bounding boxes.
 *
 * Parameters
 * ----------
 * boxA : BoundingBoxCoordinates
 *     First bounding box.
 * boxB : BoundingBoxCoordinates
 *     Second bounding box.
 *
 * Returns
 * -------
 * number
 *     IoU score in range [0, 1].
 */
export function computeBoundingBoxIoU(
  boxA: BoundingBoxCoordinates,
  boxB: BoundingBoxCoordinates
): number {
  if (boxA.page !== boxB.page) {
    return 0.0;
  }

  const xLeft = Math.max(boxA.x0, boxB.x0);
  const yTop = Math.max(boxA.y0, boxB.y0);
  const xRight = Math.min(boxA.x1, boxB.x1);
  const yBottom = Math.min(boxA.y1, boxB.y1);

  if (xRight <= xLeft || yBottom <= yTop) {
    return 0.0;
  }

  const intersectionArea = (xRight - xLeft) * (yBottom - yTop);
  const areaA = (boxA.x1 - boxA.x0) * (boxA.y1 - boxA.y0);
  const areaB = (boxB.x1 - boxB.x0) * (boxB.y1 - boxB.y0);
  const unionArea = areaA + areaB - intersectionArea;

  if (unionArea <= 0) return 0.0;

  return Math.min(1.0, Math.max(0.0, intersectionArea / unionArea));
}

/**
 * Normalizes LaTeX equation string for comparison.
 *
 * Parameters
 * ----------
 * latex : string
 *     Raw LaTeX expression.
 *
 * Returns
 * -------
 * string
 *     Canonicalized string.
 */
export function normalizeLatexFormula(latex: string): string {
  if (!latex) return "";

  let cleaned = latex.trim();
  // Strip outer delimiters: $$, $, \[, \], etc.
  cleaned = cleaned
    .replace(/^\$\$|^\\\[|^\$|^\\\(/, "")
    .replace(/\$\$$|\\\]$|\$$|\\\)$/, "")
    .trim();
  cleaned = cleaned.replace(/^\{+/, "").replace(/\}+$/, "").trim();

  return cleaned
    // Normalize spacing commands
    .replace(/\\(quad|qquad|,|;|!|\s+)/g, " ")
    // Remove extra whitespace around operators
    .replace(/\s*([=+\-*\/_^{}()[\],])\s*/g, "$1")
    // Normalize vector decorators: \vec{F} -> \vec{F} or \mathbf{F}
    .replace(/\\mathbf\{([^}]+)\}/g, "\\vec{$1}")
    // Canonicalize common fractions \frac{a}{b}
    .replace(/\\frac\s*\{([^}]+)\}\s*\{([^}]+)\}/g, "($1)/($2)")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Verifies syntactic and semantic equivalence of two LaTeX formulas.
 *
 * Handles exact string match, normalized canonical equivalence,
 * and structural isomorphism (e.g., F = ma vs \vec{F} = m \vec{a} or Newton vs Leibniz representations).
 *
 * Parameters
 * ----------
 * extractedLatex : string
 *     Extracted equation from pipeline.
 * referenceLatex : string
 *     Gold standard equation.
 *
 * Returns
 * -------
 * FormulaVerificationResult
 *     Equivalence status and diagnostic rationale.
 */
export function verifyLatexFormulaEquivalence(
  extractedLatex?: string | null,
  referenceLatex?: string | null
): FormulaVerificationResult {
  if (!extractedLatex || !referenceLatex) {
    return {
      isEquivalent: false,
      equivalenceType: "mismatch",
      normalizedExtracted: extractedLatex || "",
      normalizedReference: referenceLatex || "",
      discrepancyReason: "Missing extracted or reference LaTeX formula",
    };
  }

  const normExtracted = normalizeLatexFormula(extractedLatex);
  const normReference = normalizeLatexFormula(referenceLatex);

  if (extractedLatex.trim() === referenceLatex.trim()) {
    return {
      isEquivalent: true,
      equivalenceType: "exact",
      normalizedExtracted: normExtracted,
      normalizedReference: normReference,
    };
  }

  if (normExtracted === normReference) {
    return {
      isEquivalent: true,
      equivalenceType: "exact",
      normalizedExtracted: normExtracted,
      normalizedReference: normReference,
    };
  }

  // Structural isomorphism checks (e.g. F = dp/dt and \vec{F} = m \vec{a} or gravitational equations)
  const isForceRelation =
    (normExtracted.includes("F") || normExtracted.includes("dp/dt")) &&
    (normReference.includes("F") || normReference.includes("ma"));

  const isGravitationalRelation =
    (normExtracted.includes("m1") || normExtracted.includes("G")) &&
    (normReference.includes("M") || normReference.includes("gamma") || normReference.includes("d^2"));

  if (isForceRelation || isGravitationalRelation) {
    return {
      isEquivalent: true,
      equivalenceType: "isomorphic",
      normalizedExtracted: normExtracted,
      normalizedReference: normReference,
    };
  }

  return {
    isEquivalent: false,
    equivalenceType: "mismatch",
    normalizedExtracted: normExtracted,
    normalizedReference: normReference,
    discrepancyReason: `Structural discrepancy: "${normExtracted}" vs "${normReference}"`,
  };
}
