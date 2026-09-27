import test from "node:test";
import assert from "node:assert/strict";
import { useRunsStore } from "./runsStore.ts";
import type { StudioEvent } from "../api/types.ts";

test("subtask status remains running when current >= total until ProgressCompleted", () => {
  const store = useRunsStore.getState();
  store.clearEvents();
  useRunsStore.setState({
    selectedRunId: "test-run-1",
    selectedRunDetail: {
      run_id: "test-run-1",
      pipeline_version: "0.1.0",
      schema_version: "v1",
      status: "running",
      created_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      completed_at: null,
      phase_records: [],
      artifact_count: 0,
      config_snapshot: {},
      input_sources: [],
    } as any,
  });

  const startEvent: StudioEvent = {
    seq: 1,
    run_id: "test-run-1",
    ts: new Date().toISOString(),
    kind: "progress.started",
    level: "info",
    phase: "Phase 4: Argument Mining",
    message: "Starting subtask",
    payload: {
      _raw_type: "ProgressStarted",
      task_name: "Phase 4: Chunk ADU Extraction (12 chunks)",
      total_items: 12,
      description: "Chunk ADU Extraction",
    },
    dropped_before: 0,
  };

  useRunsStore.getState().addEvent(startEvent);
  let subtasks = useRunsStore.getState().subtasks;
  assert.equal(subtasks["Phase 4: Chunk ADU Extraction (12 chunks)"]?.status, "running");
  assert.equal(subtasks["Phase 4: Chunk ADU Extraction (12 chunks)"]?.completed, 0);

  // Advance to 12 / 12 (current >= total)
  const advanceEvent: StudioEvent = {
    seq: 2,
    run_id: "test-run-1",
    ts: new Date().toISOString(),
    kind: "progress.step",
    level: "info",
    phase: "Phase 4: Argument Mining",
    message: "Advanced subtask",
    payload: {
      _raw_type: "ProgressAdvanced",
      task_name: "Phase 4: Chunk ADU Extraction (12 chunks)",
      current: 12,
      total_items: 12,
    },
    dropped_before: 0,
  };

  useRunsStore.getState().addEvent(advanceEvent);
  subtasks = useRunsStore.getState().subtasks;
  const subtask = subtasks["Phase 4: Chunk ADU Extraction (12 chunks)"];
  assert.ok(subtask);
  assert.equal(subtask.completed, 12);
  assert.equal(subtask.total, 12);
  assert.equal(subtask.percentage, 100);
  // Must NOT auto-complete just because current >= total
  assert.equal(subtask.status, "running");

  // Complete event arrives
  const completeEvent: StudioEvent = {
    seq: 3,
    run_id: "test-run-1",
    ts: new Date().toISOString(),
    kind: "progress.completed",
    level: "info",
    phase: "Phase 4: Argument Mining",
    message: "Completed subtask",
    payload: {
      _raw_type: "ProgressCompleted",
      task_name: "Phase 4: Chunk ADU Extraction (12 chunks)",
    },
    dropped_before: 0,
  };

  useRunsStore.getState().addEvent(completeEvent);
  subtasks = useRunsStore.getState().subtasks;
  assert.equal(subtasks["Phase 4: Chunk ADU Extraction (12 chunks)"]?.status, "completed");
  assert.equal(subtasks["Phase 4: Chunk ADU Extraction (12 chunks)"]?.percentage, 100);
});

test("monotonic sequence check discards duplicate or out-of-order sequence events", () => {
  useRunsStore.getState().clearEvents();

  const ev1: StudioEvent = {
    seq: 10,
    run_id: "test-run-2",
    ts: new Date().toISOString(),
    kind: "test.event",
    level: "info",
    message: "Event 10",
    payload: {},
    dropped_before: 0,
  };

  const ev2Duplicate: StudioEvent = {
    seq: 10,
    run_id: "test-run-2",
    ts: new Date().toISOString(),
    kind: "test.event",
    level: "info",
    message: "Duplicate Event 10",
    payload: {},
    dropped_before: 0,
  };

  const ev3Older: StudioEvent = {
    seq: 8,
    run_id: "test-run-2",
    ts: new Date().toISOString(),
    kind: "test.event",
    level: "info",
    message: "Older Event 8",
    payload: {},
    dropped_before: 0,
  };

  const ev4Newer: StudioEvent = {
    seq: 11,
    run_id: "test-run-2",
    ts: new Date().toISOString(),
    kind: "test.event",
    level: "info",
    message: "Event 11",
    payload: {},
    dropped_before: 0,
  };

  useRunsStore.getState().addEvents([ev1, ev2Duplicate, ev3Older, ev4Newer]);
  const events = useRunsStore.getState().events;
  assert.equal(events.length, 2);
  assert.equal(events[0].seq, 10);
  assert.equal(events[1].seq, 11);
  assert.equal(useRunsStore.getState().lastSeq, 11);
});

test("event buffer is capped at MAX_STORE_EVENTS (5000) to prevent unbounded memory growth", () => {
  useRunsStore.getState().clearEvents();

  const batch: StudioEvent[] = [];
  for (let i = 1; i <= 5200; i++) {
    batch.push({
      seq: i,
      run_id: "test-run-3",
      ts: new Date().toISOString(),
      kind: "test.flood",
      level: "info",
      message: `Flood event ${i}`,
      payload: {},
      dropped_before: 0,
    });
  }

  useRunsStore.getState().addEvents(batch);
  const events = useRunsStore.getState().events;
  assert.equal(events.length, 5000);
  assert.equal(events[0].seq, 201);
  assert.equal(events[events.length - 1].seq, 5200);
});

test("phase matching isolates Phase 4 Maturation from Phase 4 Argument Mining", () => {
  useRunsStore.getState().clearEvents();
  useRunsStore.setState({
    selectedRunId: "test-run-4",
    selectedRunDetail: {
      run_id: "test-run-4",
      status: "running",
      phase_records: [
        {
          phase_name: "Phase 4: Entity Maturation (Batch Epistemic Synthesis)",
          phase_ordinal: 5,
          status: "running",
          artifact_count: 0,
        },
        {
          phase_name: "Phase 4: Argument Mining",
          phase_ordinal: 6,
          status: "planned",
          artifact_count: 0,
        },
      ],
    } as any,
  });

  // Emitting completion for Phase 4 Maturation
  const maturationComplete: StudioEvent = {
    seq: 1,
    run_id: "test-run-4",
    ts: new Date().toISOString(),
    kind: "phase.completed",
    level: "info",
    phase: "Phase 4: Entity Maturation (Batch Epistemic Synthesis)",
    message: "Phase completed",
    payload: {
      _raw_type: "PhaseCompleted",
      phase_name: "Phase 4: Entity Maturation (Batch Epistemic Synthesis)",
      artifact_count: 50,
    },
    dropped_before: 0,
  };

  useRunsStore.getState().addEvent(maturationComplete);
  const detail = useRunsStore.getState().selectedRunDetail;
  assert.ok(detail);
  const records = detail.phase_records;
  // Phase 4 Maturation must be completed
  assert.equal(records[0].status, "completed");
  assert.equal(records[0].artifact_count, 50);
  // Phase 4 Argument Mining must NOT be touched or completed
  assert.equal(records[1].status, "planned");
  assert.equal(records[1].artifact_count, 0);
});
