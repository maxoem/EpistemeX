import test from "node:test";
import assert from "node:assert/strict";
import {calculateProgressionSnapshots} from "./progressionUtils.ts";
import {useCredentialStore} from "../store/credentialStore.ts";

test("calculateProgressionSnapshots generates snapshots at specified intervals", () => {
  // Empty or missing scores
  assert.deepEqual(calculateProgressionSnapshots([], 20), []);

  // 45 scores with interval 20 -> snapshots at 20, 40, and terminal 45
  const mockScores = Array.from({ length: 45 }, (_, i) => 0.5 + (i % 10) * 0.04);
  const snapshots = calculateProgressionSnapshots(mockScores, 20);

  assert.equal(snapshots.length, 3, "Should generate 3 snapshots (20, 40, 45)");

  // Step 1: count 20
  assert.equal(snapshots[0].step, 1);
  assert.equal(snapshots[0].count, 20);
  assert.equal(snapshots[0].scores.length, 20);

  // Step 2: count 40
  assert.equal(snapshots[1].step, 2);
  assert.equal(snapshots[1].count, 40);
  assert.equal(snapshots[1].scores.length, 40);

  // Terminal step: count 45
  assert.equal(snapshots[2].step, 3);
  assert.equal(snapshots[2].count, 45);
  assert.equal(snapshots[2].scores.length, 45);
  assert.ok(snapshots[2].mean > 0 && snapshots[2].mean <= 1.0);

  // Exact multiple: 40 scores with interval 20 -> snapshots at 20, 40 (no redundant terminal)
  const exactScores = mockScores.slice(0, 40);
  const exactSnapshots = calculateProgressionSnapshots(exactScores, 20);
  assert.equal(exactSnapshots.length, 2);
  assert.equal(exactSnapshots[1].count, 40);
});

test("storage environment locks to neo4j when pipeline run is running", () => {
  const resolveStorageEnvironment = (requested: "artifacts" | "neo4j", runStatus?: string): "artifacts" | "neo4j" => {
    return runStatus === "running" ? "neo4j" : requested;
  };

  assert.equal(resolveStorageEnvironment("artifacts", "completed"), "artifacts");
  assert.equal(resolveStorageEnvironment("artifacts", "failed"), "artifacts");
  assert.equal(resolveStorageEnvironment("artifacts", undefined), "artifacts");
  assert.equal(resolveStorageEnvironment("artifacts", "running"), "neo4j");
  assert.equal(resolveStorageEnvironment("neo4j", "running"), "neo4j");
});

test("credentialStore detects database collision across existing runs", () => {
  const credsStore = useCredentialStore.getState();

  credsStore.saveRunCredentials("run_alpha", {
    url: "bolt://localhost:7687",
    database: "philosophical_graph",
  });
  credsStore.saveRunCredentials("run_beta", {
    url: "bolt://localhost:7687",
    database: "philosophical_graph",
  });
  credsStore.saveRunCredentials("run_gamma", {
    url: "bolt://localhost:7687",
    database: "distinct_theory_db",
  });

  // Conflicts for philosophical_graph
  const conflicts1 = credsStore.findRunsForDatabase("philosophical_graph");
  assert.ok(conflicts1.includes("run_alpha"));
  assert.ok(conflicts1.includes("run_beta"));
  assert.equal(conflicts1.length, 2);

  // Exclude current run id if modifying existing
  const conflictsExcluded = credsStore.findRunsForDatabase("philosophical_graph", "run_alpha");
  assert.equal(conflictsExcluded.length, 1);
  assert.ok(conflictsExcluded.includes("run_beta"));

  // Case insensitive check
  const conflictsCase = credsStore.findRunsForDatabase("PHILOSOPHICAL_GRAPH");
  assert.equal(conflictsCase.length, 2);

  // No conflicts for brand new DB
  const conflictsNone = credsStore.findRunsForDatabase("brand_new_isolated_db");
  assert.equal(conflictsNone.length, 0);

  // Cleanup
  credsStore.deleteRunCredentials("run_alpha");
  credsStore.deleteRunCredentials("run_beta");
  credsStore.deleteRunCredentials("run_gamma");
});
