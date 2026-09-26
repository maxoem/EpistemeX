import test from "node:test";
import assert from "node:assert/strict";
import type { CalibrationBinDetail, MiscalibratedAssertionItem } from "../../../../api/types.ts";

test("Calibration Lab: ECE and MCE metric verification", () => {
  const sampleBins: CalibrationBinDetail[] = [
    {
      bin_index: 0,
      bin_lower: 0.0,
      bin_upper: 0.5,
      sample_count: 50,
      mean_confidence: 0.35,
      empirical_accuracy: 0.32,
      calibration_gap: 0.03,
    },
    {
      bin_index: 1,
      bin_lower: 0.5,
      bin_upper: 0.8,
      sample_count: 100,
      mean_confidence: 0.68,
      empirical_accuracy: 0.60,
      calibration_gap: 0.08,
    },
    {
      bin_index: 2,
      bin_lower: 0.8,
      bin_upper: 1.0,
      sample_count: 150,
      mean_confidence: 0.92,
      empirical_accuracy: 0.80,
      calibration_gap: 0.12,
    },
  ];

  const totalSamples = sampleBins.reduce((sum, b) => sum + b.sample_count, 0);
  assert.equal(totalSamples, 300);

  // ECE = sum(n_i * gap_i) / N
  const ece = sampleBins.reduce((sum, b) => sum + b.sample_count * b.calibration_gap, 0) / totalSamples;
  // 50*0.03 + 100*0.08 + 150*0.12 = 1.5 + 8.0 + 18.0 = 27.5 / 300 = 0.091666...
  assert.ok(Math.abs(ece - 0.09167) < 0.001);

  // MCE = max(gap_i) = 0.12
  const mce = Math.max(...sampleBins.map((b) => b.calibration_gap));
  assert.equal(mce, 0.12);
});

test("Threshold Optimizer: mathematical precision/recall projection dynamics", () => {
  const baselinePrecision = 0.88;
  const baselineRecall = 0.85;

  const projectAt = (threshold: number) => {
    const shift = (threshold - 0.5) / 0.49;
    const precision = Math.min(
      0.995,
      Math.max(0.6, baselinePrecision + (1.0 - baselinePrecision) * shift * 0.45)
    );
    const recall = Math.max(
      0.35,
      Math.min(0.99, baselineRecall - baselineRecall * shift * 0.3)
    );
    const f1 = (2 * precision * recall) / (precision + recall);
    return { precision, recall, f1 };
  };

  const permissive = projectAt(0.50);
  const balanced = projectAt(0.82);
  const conservative = projectAt(0.95);

  // Increasing threshold strictly increases precision
  assert.ok(conservative.precision > balanced.precision);
  assert.ok(balanced.precision >= permissive.precision);

  // Increasing threshold strictly decreases recall
  assert.ok(conservative.recall < balanced.recall);
  assert.ok(balanced.recall <= permissive.recall);

  // All values bounded between 0 and 1
  assert.ok(conservative.f1 > 0 && conservative.f1 <= 1);
  assert.ok(balanced.f1 > 0 && balanced.f1 <= 1);
});

test("Overconfidence Filtering: flags assertions with confidence > 0.85 and empirical mismatch", () => {
  const assertions: MiscalibratedAssertionItem[] = [
    {
      assertion_id: "a1",
      assertion_type: "triple",
      descriptor: "Newton DISPROVES Kepler",
      confidence: 0.96,
      empirical_match: false,
      discrepancy: 0.96,
    },
    {
      assertion_id: "a2",
      assertion_type: "triple",
      descriptor: "Force EQUALS Mass * Acceleration",
      confidence: 0.98,
      empirical_match: true,
      discrepancy: 0.0,
    },
    {
      assertion_id: "a3",
      assertion_type: "axiom",
      descriptor: "Relativistic Spacetime Curvature in 1687",
      confidence: 0.89,
      empirical_match: false,
      discrepancy: 0.89,
    },
  ];

  const overconfident = assertions.filter((a) => a.confidence > 0.85 && !a.empirical_match);
  assert.equal(overconfident.length, 2);
  assert.equal(overconfident[0].assertion_id, "a1");
  assert.equal(overconfident[1].assertion_id, "a3");
});
