import test from "node:test";
import assert from "node:assert/strict";
import { useLeaderboardStore } from "./leaderboardStore.ts";

test("leaderboardStore: initial state and defaults", () => {
  const state = useLeaderboardStore.getState();
  assert.equal(state.sortBy, "f1");
  assert.equal(state.ascending, false);
  assert.equal(state.xAxis, "cost");
  assert.equal(state.yAxis, "f1");
  assert.equal(state.selectedRunIdA, null);
  assert.equal(state.selectedRunIdB, null);
  assert.equal(state.isDiffDrawerOpen, false);
});

test("leaderboardStore: sorting and axis changes", () => {
  const store = useLeaderboardStore.getState();

  store.setXAxis("duration");
  assert.equal(useLeaderboardStore.getState().xAxis, "duration");

  store.setYAxis("delta_star");
  assert.equal(useLeaderboardStore.getState().yAxis, "delta_star");
});

test("leaderboardStore: pairwise diff selection toggle", () => {
  const store = useLeaderboardStore.getState();
  store.clearComparison();

  // Toggle run-082 -> sets as Run A
  store.toggleRunForDiff("run-082");
  assert.equal(useLeaderboardStore.getState().selectedRunIdA, "run-082");
  assert.equal(useLeaderboardStore.getState().selectedRunIdB, null);

  // Toggle run-041 -> sets as Run B and opens drawer
  store.toggleRunForDiff("run-041");
  assert.equal(useLeaderboardStore.getState().selectedRunIdA, "run-082");
  assert.equal(useLeaderboardStore.getState().selectedRunIdB, "run-041");
  assert.equal(useLeaderboardStore.getState().isDiffDrawerOpen, true);

  // Toggle run-082 again -> deselects Run A
  store.toggleRunForDiff("run-082");
  assert.equal(useLeaderboardStore.getState().selectedRunIdA, null);
  assert.equal(useLeaderboardStore.getState().selectedRunIdB, "run-041");

  // Clear comparison
  store.clearComparison();
  assert.equal(useLeaderboardStore.getState().selectedRunIdA, null);
  assert.equal(useLeaderboardStore.getState().selectedRunIdB, null);
  assert.equal(useLeaderboardStore.getState().isDiffDrawerOpen, false);
});
