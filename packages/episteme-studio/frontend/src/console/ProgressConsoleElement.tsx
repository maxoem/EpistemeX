import React, {useEffect, useState} from "react";
import {SubtaskProgress, useRunsStore} from "../store/runsStore";
import {CheckCircle2, ChevronDown, ChevronRight,} from "lucide-react";

export interface ProgressConsoleElementProps {
  tasks?: SubtaskProgress[];
  variant?: "terminal" | "card" | "hero";
  showCompleted?: boolean;
  maxTasks?: number;
  className?: string;
  onToggleExpand?: (expanded: boolean) => void;
}

const formatTime = (seconds?: number | null): string => {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return "--:--";
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const remS = s % 60;
  if (m < 60) {
    return `${m.toString().padStart(2, "0")}:${remS.toString().padStart(2, "0")}`;
  }
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h.toString().padStart(2, "0")}:${remM.toString().padStart(2, "0")}:${remS.toString().padStart(2, "0")}`;
};

const SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

export const ProgressConsoleElement: React.FC<ProgressConsoleElementProps> = ({
  tasks: propTasks,
  variant = "terminal",
  showCompleted = false,
  maxTasks = 5,
  className = "",
}) => {
  const storeSubtasks = useRunsStore((s) => s.subtasks);
  const liveProgress = useRunsStore((s) => s.liveProgress);

  const [spinnerIndex, setSpinnerIndex] = useState(0);
  const [isExpanded, setIsExpanded] = useState(true);

  // Ticking spinner animation
  useEffect(() => {
    const timer = setInterval(() => {
      setSpinnerIndex((prev) => (prev + 1) % SPINNER_FRAMES.length);
    }, 80);
    return () => clearInterval(timer);
  }, []);

  const allTasks: SubtaskProgress[] = React.useMemo(() => {
    if (propTasks) return propTasks;
    const fromMap = Object.values(storeSubtasks || {});
    if (fromMap.length > 0) return fromMap;
    // Fallback synthesize from liveProgress if individual tasks haven't registered
    if (liveProgress?.taskName || liveProgress?.description) {
      return [
        {
          id: liveProgress.taskName || "current-task",
          taskName: liveProgress.taskName || "Active Task",
          description: liveProgress.description || "Executing pipeline phase...",
          phaseName: liveProgress.phaseName,
          phaseOrdinal: liveProgress.phaseOrdinal,
          completed: liveProgress.step || 0,
          total: liveProgress.totalSteps || null,
          percentage: liveProgress.percentage || null,
          status: "running" as const,
          startedAt: liveProgress.lastUpdated || new Date().toISOString(),
          updatedAt: liveProgress.lastUpdated || new Date().toISOString(),
          elapsedSeconds: liveProgress.elapsedSeconds || 0,
          remainingSeconds: liveProgress.remainingSeconds || null,
          rate: liveProgress.rate || null,
        },
      ];
    }
    return [];
  }, [propTasks, storeSubtasks, liveProgress]);

  const activeTasks = allTasks.filter((t) => t.status === "running");
  const completedTasks = allTasks.filter((t) => t.status === "completed");

  const displayTasks = (showCompleted ? allTasks : activeTasks.length > 0 ? activeTasks : completedTasks).slice(
    0,
    maxTasks
  );

  if (displayTasks.length === 0) {
    return null;
  }

  const isTerminal = variant === "terminal";
  const isHero = variant === "hero";

  return (
    <div
      className={`font-mono text-xs transition-all ${
        isTerminal
          ? "bg-[#161b22]/95 border border-emerald-500/30 text-[#c9d1d9] rounded-md p-2.5 shadow-lg backdrop-blur-xs"
          : isHero
          ? "bg-blue-500/10 border border-blue-500/25 rounded-lg p-3 text-app-text"
          : "bg-app-surface border border-app-border rounded-md p-2 text-app-text"
      } ${className}`}
    >
      {/* Header bar */}
      <div className="flex items-center justify-between gap-2 pb-1.5 mb-1.5 border-b border-white/10 text-[11px] select-none">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`font-bold ${isTerminal ? "text-emerald-400" : "text-blue-600 dark:text-blue-400"}`}>
            {SPINNER_FRAMES[spinnerIndex]}
          </span>
          <span className="font-semibold uppercase tracking-wider text-[10px] text-app-heading">
            {isTerminal ? "Active Subtasks" : "Pipeline Progress"}
          </span>
          <span
            className={`px-1.5 py-0.2 rounded-full text-[9px] font-bold ${
              isTerminal
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                : "bg-blue-500/20 text-blue-600 dark:text-blue-400 border border-blue-500/30"
            }`}
          >
            {activeTasks.length} running
          </span>
          {completedTasks.length > 0 && (
            <span className="text-[9px] text-app-muted">
              ({completedTasks.length} completed)
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="p-0.5 text-app-muted hover:text-app-heading transition-colors cursor-pointer flex items-center gap-1 text-[10px]"
          title={isExpanded ? "Collapse subtasks" : "Expand subtasks"}
        >
          <span>{isExpanded ? "Hide" : "Show"}</span>
          {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        </button>
      </div>

      {/* Task list matching Rich Console columns: [Spinner] [Description] [Bar] [M/N] [%] • [Elapsed] < [ETA] */}
      {isExpanded && (
        <div className="space-y-2.5">
          {displayTasks.map((task) => {
            const isCompleted = task.status === "completed";
            const total = task.total;
            const completed = task.completed;
            const pct =
              task.percentage !== null && task.percentage !== undefined
                ? task.percentage
                : total && total > 0
                ? Math.min(100, Math.round((completed / total) * 100))
                : 0;

            const hasTotal = total !== null && total !== undefined && total > 0;

            return (
              <div key={task.id} className="flex flex-col gap-1">
                {/* Top line: Spinner + Description + Counts & Times */}
                <div className="flex items-baseline justify-between gap-2 text-[11px]">
                  <div className="flex items-center gap-1.5 min-w-0 flex-1">
                    {isCompleted ? (
                      <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                    ) : (
                      <span className={`font-bold shrink-0 ${isTerminal ? "text-emerald-400" : "text-blue-600 dark:text-blue-400"}`}>
                        {SPINNER_FRAMES[spinnerIndex]}
                      </span>
                    )}

                    <span
                      className={`truncate font-semibold ${
                        isTerminal
                          ? "text-emerald-200"
                          : "text-app-heading"
                      }`}
                      title={task.description}
                    >
                      {task.description || task.taskName}
                    </span>

                    {task.phaseName && (
                      <span
                        className={`hidden sm:inline px-1.5 py-0.2 rounded text-[9px] shrink-0 ${
                          isTerminal
                            ? "bg-white/5 text-zinc-400 border border-white/10"
                            : "bg-app-subtle text-app-muted border border-app-border"
                        }`}
                      >
                        {task.phaseName}
                      </span>
                    )}
                  </div>

                  {/* Columns: M/N Complete • % • Elapsed < ETA */}
                  <div className="flex items-center gap-2 text-[10px] shrink-0 font-mono">
                    <span className={isTerminal ? "text-zinc-300 font-medium" : "text-app-text font-medium"}>
                      {completed}
                      {hasTotal ? `/${total}` : " items"}
                    </span>

                    <span
                      className={`px-1 py-0.2 rounded font-bold text-[9px] ${
                        isCompleted
                          ? "bg-emerald-500/20 text-emerald-300"
                          : isTerminal
                          ? "bg-emerald-950/60 text-emerald-300 border border-emerald-800/60"
                          : "bg-blue-500/20 text-blue-600 dark:text-blue-400"
                      }`}
                    >
                      {pct}%
                    </span>

                    <span className={isTerminal ? "text-zinc-500" : "text-app-muted"}>•</span>

                    <span className={isTerminal ? "text-zinc-400" : "text-app-muted"} title="Time elapsed">
                      {formatTime(task.elapsedSeconds)}
                    </span>

                    {task.remainingSeconds !== null && task.remainingSeconds !== undefined && !isCompleted && (
                      <>
                        <span className={isTerminal ? "text-zinc-500" : "text-app-muted"}>&lt;</span>
                        <span className={`font-medium ${isTerminal ? "text-amber-400" : "text-amber-500"}`} title="Estimated time remaining (ETA)">
                          {formatTime(task.remainingSeconds)}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Progress Bar Column: Rich BarColumn visual emulation */}
                <div
                  className={`w-full h-1.5 rounded-full overflow-hidden relative ${
                    isTerminal
                      ? "bg-zinc-800 border border-zinc-700/50"
                      : "bg-app-subtle border border-app-border"
                  }`}
                >
                  <div
                    className={`h-full rounded-full transition-all duration-300 relative overflow-hidden ${
                      isCompleted
                        ? "bg-emerald-500"
                        : isTerminal
                        ? "bg-gradient-to-r from-emerald-500 to-cyan-400"
                        : "bg-gradient-to-r from-blue-600 to-indigo-500"
                    }`}
                    style={{
                      width: hasTotal ? `${Math.max(4, pct)}%` : "100%",
                    }}
                  >
                    {!isCompleted && (
                      <div className="absolute inset-0 bg-white/25 animate-pulse" />
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
