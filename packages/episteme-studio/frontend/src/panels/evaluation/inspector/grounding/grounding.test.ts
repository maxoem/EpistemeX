import test from "node:test";
import assert from "node:assert/strict";
import {
  computeGlobalBoundingBox,
  computeLocalBoundingBox,
  computeBezierSplineAcrossPages,
  computeBoundingBoxIoU,
  verifyLatexFormulaEquivalence,
  normalizeLatexFormula,
  spanToBoundingBox,
} from "./coordinateScaling.ts";
import type { BoundingBoxCoordinates, TextSpanCoordinates } from "../../../../api/types.ts";

test("coordinateScaling: Tier 1 Global Continuous Container eliminates Page 1 stacking", () => {
  const pageDims = [
    { width: 800, height: 1000 },
    { width: 800, height: 1000 },
    { width: 800, height: 1000 },
  ];
  const pageGap = 20;

  // Box on Page 1 at y = 0.25 to 0.75
  const boxPage1: BoundingBoxCoordinates = {
    page: 1,
    x0: 0.1,
    y0: 0.25,
    x1: 0.9,
    y1: 0.75,
  };
  const g1 = computeGlobalBoundingBox(boxPage1, pageDims, pageGap);
  assert.equal(g1.top_global, 250);
  assert.equal(g1.bottom_global, 750);
  assert.equal(g1.height, 500);
  assert.equal(g1.left_global, 80);
  assert.equal(g1.width, 640);

  // Box on Page 2 at y = 0.10 to 0.30
  // top_global = (1000 + 20) + (0.10 * 1000) = 1020 + 100 = 1120
  const boxPage2: BoundingBoxCoordinates = {
    page: 2,
    x0: 0.15,
    y0: 0.10,
    x1: 0.85,
    y1: 0.30,
  };
  const g2 = computeGlobalBoundingBox(boxPage2, pageDims, pageGap);
  assert.equal(g2.top_global, 1120);
  assert.equal(g2.bottom_global, 1320);
  assert.equal(g2.height, 200);

  // Box on Page 3 at y = 0.50 to 0.80
  // top_global = (1000 + 20) + (1000 + 20) + (0.50 * 1000) = 2040 + 500 = 2540
  const boxPage3: BoundingBoxCoordinates = {
    page: 3,
    x0: 0.2,
    y0: 0.50,
    x1: 0.8,
    y1: 0.80,
  };
  const g3 = computeGlobalBoundingBox(boxPage3, pageDims, pageGap);
  assert.equal(g3.top_global, 2540);
  assert.equal(g3.bottom_global, 2840);

  // Strictly increasing vertical positions across pages
  assert.ok(g1.bottom_global < g2.top_global);
  assert.ok(g2.bottom_global < g3.top_global);
});

test("coordinateScaling: Tier 2 Page-Local SVG Viewport scaling", () => {
  const pageDim = { width: 800, height: 1200 };
  const bbox: BoundingBoxCoordinates = {
    page: 14,
    x0: 0.15,
    y0: 0.30,
    x1: 0.85,
    y1: 0.55,
  };

  const local = computeLocalBoundingBox(bbox, pageDim);
  assert.equal(local.page, 14);
  assert.equal(local.x, 0.15 * 800); // 120
  assert.equal(local.y, 0.30 * 1200); // 360
  assert.equal(local.width, 0.70 * 800); // 560
  assert.equal(local.height, 0.25 * 1200); // 300
});

test("coordinateScaling: Cubic Bézier spline across page breaks for multi-page SpanArray", () => {
  const pageDims = (page: number) => ({ width: 800, height: 1000 });
  const pageGap = 30;

  const span1: TextSpanCoordinates = {
    page: 4,
    bbox: [0.12, 0.82, 0.88, 0.96],
  };

  const span2: TextSpanCoordinates = {
    page: 5,
    bbox: [0.12, 0.04, 0.65, 0.18],
    is_continuation: true,
  };

  const spline = computeBezierSplineAcrossPages(span1, span2, pageDims, pageGap);

  // Must generate an SVG cubic curve command 'M ... C ...'
  assert.ok(spline.pathData.startsWith("M "));
  assert.ok(spline.pathData.includes(" C "));

  // Source point should be at bottom of Span 1
  assert.equal(spline.sourcePoint.y, spline.controlPoints.p0.y);
  // Target point should be at top of Span 2
  assert.equal(spline.targetPoint.y, spline.controlPoints.p3.y);

  // Target point y must be strictly greater than source point y (page 5 is below page 4)
  assert.ok(spline.targetPoint.y > spline.sourcePoint.y);

  // Control point 1 must be below p0, and control point 2 must be above p3
  assert.ok(spline.controlPoints.p1.y > spline.controlPoints.p0.y);
  assert.ok(spline.controlPoints.p2.y < spline.controlPoints.p3.y);
});

test("coordinateScaling: AG_IoU (Alignment Grounding IoU) evaluation", () => {
  // Identical boxes
  const boxA: BoundingBoxCoordinates = { page: 1, x0: 0.1, y0: 0.2, x1: 0.5, y1: 0.6 };
  const boxIdentical: BoundingBoxCoordinates = { page: 1, x0: 0.1, y0: 0.2, x1: 0.5, y1: 0.6 };
  assert.equal(computeBoundingBoxIoU(boxA, boxIdentical), 1.0);

  // Non-overlapping boxes on same page
  const boxDisjoint: BoundingBoxCoordinates = { page: 1, x0: 0.6, y0: 0.7, x1: 0.9, y1: 0.9 };
  assert.equal(computeBoundingBoxIoU(boxA, boxDisjoint), 0.0);

  // Same coordinates but different pages
  const boxDiffPage: BoundingBoxCoordinates = { page: 2, x0: 0.1, y0: 0.2, x1: 0.5, y1: 0.6 };
  assert.equal(computeBoundingBoxIoU(boxA, boxDiffPage), 0.0);

  // Known overlap:
  // A: [0, 0] to [2, 2] => Area 4
  // B: [1, 1] to [3, 3] => Area 4
  // Intersection: [1, 1] to [2, 2] => Area 1
  // Union: 4 + 4 - 1 = 7 => IoU = 1/7
  const testA: BoundingBoxCoordinates = { page: 1, x0: 0.0, y0: 0.0, x1: 0.2, y1: 0.2 };
  const testB: BoundingBoxCoordinates = { page: 1, x0: 0.1, y0: 0.1, x1: 0.3, y1: 0.3 };
  const iou = computeBoundingBoxIoU(testA, testB);
  // (0.1 * 0.1) / (0.04 + 0.04 - 0.01) = 0.01 / 0.07 = 1/7 = 0.142857...
  assert.ok(Math.abs(iou - 1 / 7) < 0.0001);
});

test("coordinateScaling: LaTeX formula normalization and equivalence verifier", () => {
  // Exact identical formulas
  const resExact = verifyLatexFormulaEquivalence("F = m a", "F = m a");
  assert.equal(resExact.isEquivalent, true);
  assert.equal(resExact.equivalenceType, "exact");

  // Normalized spacing and wrapper commands
  const resNorm = verifyLatexFormulaEquivalence(
    "$$ F = \\frac{dp}{dt} $$",
    "F = \\frac{dp}{dt}"
  );
  assert.equal(resNorm.isEquivalent, true);
  assert.equal(resNorm.equivalenceType, "exact");

  // Structural isomorphism: Newton formulations F = dp/dt vs \vec{F} = m \vec{a}
  const resIso = verifyLatexFormulaEquivalence(
    "F = \\frac{dp}{dt}",
    "\\vec{F} = m\\vec{a}"
  );
  assert.equal(resIso.isEquivalent, true);
  assert.equal(resIso.equivalenceType, "isomorphic");

  // Gravitation formulations
  const resGrav = verifyLatexFormulaEquivalence(
    "F = G \\frac{m_1 m_2}{r^2}",
    "F = \\gamma \\frac{M m}{d^2}"
  );
  assert.equal(resGrav.isEquivalent, true);
  assert.equal(resGrav.equivalenceType, "isomorphic");

  // Clear mismatch
  const resMismatch = verifyLatexFormulaEquivalence(
    "E = mc^2",
    "\\nabla \\times B = \\mu_0 J"
  );
  assert.equal(resMismatch.isEquivalent, false);
  assert.equal(resMismatch.equivalenceType, "mismatch");
});
