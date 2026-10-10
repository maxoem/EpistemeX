import {InvalidationPreview} from "../../api/types";

export type PhaseExecutionStatus = "exec" | "recompute" | "cached";

export type PhaseExecutionStatusMap = Record<number, PhaseExecutionStatus>;

/**
 * Ordinals of the core DAG execution phases (1-8).
 */
export const PHASE_ORDINALS: readonly number[] = [1, 2, 3, 4, 5, 6, 7, 8];

/**
 * Derive the execution status for every core phase from a single authoritative
 * invalidation preview.
 *
 * The backend invalidation preview is the single source of truth for whether a
 * phase will be recomputed or reused. This helper only adds the "fresh run"
 * short-circuit: when no reusable baseline exists at all, every phase must
 * execute from scratch regardless of what a preview would report.
 *
 * Parameters
 * ----------
 * hasRunBaseline : bool
 *     Whether a reusable cache baseline exists (a completed run or a forked
 *     parent run).
 * preview : InvalidationPreview
 *     Effective invalidation preview resolved for the current configuration.
 *
 * Returns
 * -------
 * PhaseExecutionStatusMap
 *     Mapping from phase ordinal to its derived execution status.
 */
export function derivePhaseExecutionStatus(
  hasRunBaseline: boolean,
  preview: InvalidationPreview
): PhaseExecutionStatusMap {
  const statuses: PhaseExecutionStatusMap = {};
  for (const ordinal of PHASE_ORDINALS) {
    if (!hasRunBaseline) {
      statuses[ordinal] = "exec";
    } else if (preview.invalidated_phases.includes(ordinal)) {
      statuses[ordinal] = "recompute";
    } else if (preview.reused_phases.includes(ordinal)) {
      statuses[ordinal] = "cached";
    } else {
      statuses[ordinal] = "exec";
    }
  }
  return statuses;
}

/**
 * Return a user-facing label for a phase execution status.
 *
 * Parameters
 * ----------
 * status : PhaseExecutionStatus
 *     Derived status of the phase.
 *
 * Returns
 * -------
 * string
 *     Descriptive display string ("Resuming from Store" | "Recompute" | "Exec").
 */
export function getPhaseExecutionLabel(status: PhaseExecutionStatus): string {
  switch (status) {
    case "cached":
      return "Resuming from Store";
    case "recompute":
      return "Recompute";
    case "exec":
    default:
      return "Exec";
  }
}
