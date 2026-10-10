import React, {useEffect, useMemo, useRef, useState} from "react";
import {useVirtualizer} from "@tanstack/react-virtual";
import {useRunsStore} from "../store/runsStore";
import {StudioEvent} from "../api/types";
import {
    Activity,
    AlertTriangle,
    ArrowDown,
    Check,
    ChevronDown,
    ChevronRight,
    Copy,
    FileText,
    Search,
    Terminal,
} from "lucide-react";

import {ProgressConsoleElement} from "./ProgressConsoleElement";

export interface LogConsoleProps {
  resizable?: boolean;
  defaultHeight?: number;
  minHeight?: number;
  maxHeight?: number;
  storageKey?: string;
  onHeightChange?: (height: number) => void;
}

export const LogConsole: React.FC<LogConsoleProps> = ({
  resizable = false,
  defaultHeight = 224, // 14rem / h-56 equivalent
  minHeight = 120,
  maxHeight = 800,
  storageKey = "glp-studio-log-console-height",
  onHeightChange,
}) => {
  const {
    events,
    selectedRunId,
    selectedRunDetail,
    logFilterLevel,
    logFilterPhase,
    logSearch,
    autoScroll,
    setLogFilterLevel,
    setLogFilterPhase,
    setLogSearch,
    setAutoScroll,
    clearEvents,
    subtasks,
    showSubtasksInTerminal,
    setShowSubtasksInTerminal,
  } = useRunsStore();

  const [consoleMode, setConsoleMode] = useState<"telemetry" | "terminal">("telemetry");
  const [terminalSearch, setTerminalSearch] = useState<string>("");
  const [copiedPath, setCopiedPath] = useState<boolean>(false);
  const [copiedTerminal, setCopiedTerminal] = useState<boolean>(false);
  const [expandedSeq, setExpandedSeq] = useState<number | null>(null);

  // Height and drag-to-resize state
  const [height, setHeight] = useState<number>(() => {
    if (!resizable || !storageKey) return defaultHeight;
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= minHeight && parsed <= maxHeight) {
          return parsed;
        }
      }
    } catch {
      // ignore
    }
    return defaultHeight;
  });

  const [isDraggingHeight, setIsDraggingHeight] = useState<boolean>(false);
  const startYRef = useRef<number>(0);
  const startHeightRef = useRef<number>(height);
  const currentHeightRef = useRef<number>(height);

  useEffect(() => {
    currentHeightRef.current = height;
  }, [height]);

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDraggingHeight(true);
    startYRef.current = e.clientY;
    startHeightRef.current = currentHeightRef.current;
  };

  useEffect(() => {
    if (!isDraggingHeight) return;

    const handleMouseMove = (e: MouseEvent) => {
      // Dragging UP decreases clientY, which should INCREASE height
      const deltaY = startYRef.current - e.clientY;
      const dynamicMax = Math.min(maxHeight, window.innerHeight - 150);
      const effectiveMax = Math.max(minHeight, dynamicMax);
      const newHeight = Math.max(minHeight, Math.min(effectiveMax, startHeightRef.current + deltaY));
      setHeight(newHeight);
      onHeightChange?.(newHeight);
    };

    const handleMouseUp = () => {
      setIsDraggingHeight(false);
      try {
        if (storageKey) {
          localStorage.setItem(storageKey, String(currentHeightRef.current));
        }
      } catch {
        // ignore
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDraggingHeight, minHeight, maxHeight, storageKey, onHeightChange]);

  const parentRef = useRef<HTMLDivElement>(null);
  const terminalParentRef = useRef<HTMLDivElement>(null);

  // Path where logs and manifests are persisted on disk
  const logFilePath = selectedRunId ? `.pipeline_runs/${selectedRunId}/pipeline.log` : null;

  const handleCopyLogPath = () => {
    if (!logFilePath) return;
    navigator.clipboard.writeText(logFilePath);
    setCopiedPath(true);
    setTimeout(() => setCopiedPath(false), 2000);
  };

  // Split events between domain telemetry and raw terminal output
  const telemetryEvents = useMemo(() => {
    return events.filter((e) => e.kind !== "terminal.output");
  }, [events]);

  const terminalEvents: StudioEvent[] = useMemo(() => {
    return events.flatMap((e): StudioEvent[] => {
      if (e.kind === "terminal.output") {
        if (e.payload?.lines && Array.isArray(e.payload.lines)) {
          return (e.payload.lines as string[]).map((line: string) => ({
            ...e,
            message: line,
          }));
        }
        return [e];
      }
      if (showSubtasksInTerminal) {
        const isProgressStart = e.kind === "progress.started" || e.payload?._raw_type === "ProgressStarted";
        const isProgressComplete = e.kind === "progress.completed" || e.payload?._raw_type === "ProgressCompleted";

        if (isProgressStart) {
          const task = (e.payload?.task_name as string) || (e.payload?.description as string) || e.message;
          const total = e.payload?.total_items ? ` (${e.payload.total_items} items)` : "";
          const desc = e.payload?.description && e.payload.description !== task ? ` — ${e.payload.description}` : "";
          return [
            {
              ...e,
              kind: "terminal.output",
              level: "info" as const,
              message: `▶ [subtask] Started: ${task}${total}${desc}`,
              payload: { ...e.payload, stream: "subtask", subtaskType: "started" },
            },
          ];
        }
        if (isProgressComplete) {
          const task = (e.payload?.task_name as string) || e.message;
          return [
            {
              ...e,
              kind: "terminal.output",
              level: "info" as const,
              message: `✔ [subtask] Completed: ${task}`,
              payload: { ...e.payload, stream: "subtask", subtaskType: "completed" },
            },
          ];
        }
      }
      return [];
    });
  }, [events, showSubtasksInTerminal]);

  const activeSubtaskCount = useMemo(() => {
    return Object.values(subtasks || {}).filter((s) => s.status === "running").length;
  }, [subtasks]);

  // Extract distinct phases present in telemetry events for filter dropdown
  const availablePhases = useMemo(() => {
    const phases = new Set<string>();
    telemetryEvents.forEach((e) => {
      if (e.phase) phases.add(e.phase);
    });
    return Array.from(phases);
  }, [telemetryEvents]);

  // Filter domain telemetry events by level, phase, and search query
  const filteredTelemetryEvents = useMemo(() => {
    return telemetryEvents.filter((e) => {
      if (logFilterLevel !== "all" && e.level !== logFilterLevel) return false;
      if (logFilterPhase !== "all" && e.phase !== logFilterPhase) return false;
      if (logSearch) {
        const query = logSearch.toLowerCase();
        const msg = (e.message || "").toLowerCase();
        const kind = (e.kind || "").toLowerCase();
        if (!msg.includes(query) && !kind.includes(query)) return false;
      }
      return true;
    });
  }, [telemetryEvents, logFilterLevel, logFilterPhase, logSearch]);

  // Filter terminal events by text search
  const filteredTerminalEvents = useMemo(() => {
    if (!terminalSearch) return terminalEvents;
    const q = terminalSearch.toLowerCase();
    return terminalEvents.filter((e) => (e.message || "").toLowerCase().includes(q));
  }, [terminalEvents, terminalSearch]);

  const handleCopyAllTerminal = () => {
    const text = filteredTerminalEvents.map((e) => e.message).join("\n");
    navigator.clipboard.writeText(text);
    setCopiedTerminal(true);
    setTimeout(() => setCopiedTerminal(false), 2000);
  };

  // Virtualizer for domain telemetry list
  const virtualizer = useVirtualizer({
    count: filteredTelemetryEvents.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 36,
    overscan: 20,
  });

  // Virtualizer for raw terminal list
  const terminalVirtualizer = useVirtualizer({
    count: filteredTerminalEvents.length,
    getScrollElement: () => terminalParentRef.current,
    estimateSize: () => 24,
    overscan: 25,
  });

  // Autoscroll to bottom on new events
  useEffect(() => {
    if (autoScroll && filteredTelemetryEvents.length > 0 && consoleMode === "telemetry") {
      virtualizer.scrollToIndex(filteredTelemetryEvents.length - 1, { align: "end" });
    }
  }, [filteredTelemetryEvents.length, autoScroll, consoleMode, virtualizer]);

  useEffect(() => {
    if (autoScroll && filteredTerminalEvents.length > 0 && consoleMode === "terminal") {
      terminalVirtualizer.scrollToIndex(filteredTerminalEvents.length - 1, { align: "end" });
    }
  }, [filteredTerminalEvents.length, autoScroll, consoleMode, terminalVirtualizer]);

  const getLevelColor = (level: string) => {
    switch (level) {
      case "error":
        return "text-red-500 dark:text-red-400 bg-red-500/10 border-red-500/20";
      case "warning":
        return "text-amber-500 dark:text-amber-400 bg-amber-500/10 border-amber-500/20";
      case "debug":
        return "text-app-muted bg-app-subtle border-app-border";
      default:
        return "text-blue-500 dark:text-blue-400 bg-blue-500/10 border-blue-500/20";
    }
  };

  return (
    <div
      style={resizable ? { height: `${height}px` } : undefined}
      className={`flex flex-col bg-app-bg rounded-lg border border-app-border overflow-hidden relative ${
        resizable ? "flex-shrink-0" : "h-full"
      } ${isDraggingHeight ? "select-none" : ""}`}
    >
      {/* Resizing / Pull-up Drag Handle */}
      {resizable && (
        <div
          onMouseDown={handleDragStart}
          role="separator"
          aria-orientation="horizontal"
          aria-label="Drag up or down to resize console height"
          title="Drag up to expand height, down to reduce height"
          className={`h-2 -mt-1 -mb-1 z-30 cursor-row-resize flex items-center justify-center transition-colors group select-none ${
            isDraggingHeight ? "bg-blue-500/30" : "hover:bg-blue-500/20"
          }`}
        >
          <div
            className={`w-14 h-1 rounded-full bg-app-muted/40 group-hover:bg-blue-400 transition-all ${
              isDraggingHeight ? "bg-blue-500 w-20" : ""
            }`}
          />
        </div>
      )}

      {/* Top Console Mode & Path Toolbar */}
      <div className="flex flex-wrap items-center justify-between p-2 gap-2 border-b border-app-border bg-app-surface select-none text-xs">
        {/* Left: Mode segmented control */}
        <div className="flex items-center gap-2">
          <div className="inline-flex items-center bg-app-bg rounded border border-app-border p-0.5">
            <button
              type="button"
              onClick={() => setConsoleMode("telemetry")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors cursor-pointer font-medium ${
                consoleMode === "telemetry"
                  ? "bg-app-surface text-app-heading shadow-xs font-semibold"
                  : "text-app-muted hover:text-app-heading"
              }`}
            >
              <Activity className="w-3.5 h-3.5 text-blue-500" />
              <span>Domain Telemetry</span>
              <span className="ml-1 px-1.5 py-0.2 rounded-full bg-app-subtle text-[10px] text-app-muted font-mono">
                {filteredTelemetryEvents.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setConsoleMode("terminal")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors cursor-pointer font-medium ${
                consoleMode === "terminal"
                  ? "bg-app-surface text-app-heading shadow-xs font-semibold"
                  : "text-app-muted hover:text-app-heading"
              }`}
            >
              <Terminal className="w-3.5 h-3.5 text-emerald-500" />
              <span>Terminal Output</span>
              <span className="ml-1 px-1.5 py-0.2 rounded-full bg-app-subtle text-[10px] text-app-muted font-mono">
                {filteredTerminalEvents.length}
              </span>
            </button>
          </div>

          {/* Disk Log Location indicator */}
          {logFilePath && (
            <div className="hidden sm:flex items-center gap-1.5 px-2 py-1 rounded bg-app-bg border border-app-border text-[11px] font-mono text-app-muted">
              <FileText className="w-3 h-3 text-app-muted flex-shrink-0" />
              <span>
                Log: <strong className="text-app-heading">{logFilePath}</strong>
              </span>
              <button
                type="button"
                onClick={handleCopyLogPath}
                className="p-0.5 hover:text-app-heading transition-colors cursor-pointer"
                title="Copy log file path"
              >
                {copiedPath ? (
                  <Check className="w-3 h-3 text-emerald-500" />
                ) : (
                  <Copy className="w-3 h-3 text-app-muted" />
                )}
              </button>
            </div>
          )}
        </div>

        {/* Right: Actions (Auto-scroll, Copy, Clear) */}
        <div className="flex items-center space-x-2 text-xs">
          {consoleMode === "terminal" && (
            <button
              type="button"
              onClick={() => setShowSubtasksInTerminal(!showSubtasksInTerminal)}
              className={`flex items-center gap-1.5 px-2 py-1 rounded border transition-colors cursor-pointer ${
                showSubtasksInTerminal
                  ? "bg-cyan-500/15 text-cyan-500 dark:text-cyan-400 border-cyan-500/30 font-medium"
                  : "bg-app-subtle text-app-muted border-app-border"
              }`}
              title="Show pipeline subtasks in terminal emulator stream"
            >
              <Activity className="w-3 h-3 text-cyan-400" />
              <span>Subtasks</span>
              {activeSubtaskCount > 0 && (
                <span className="px-1.5 py-0.2 rounded-full bg-cyan-500/20 text-cyan-300 text-[9px] font-bold">
                  {activeSubtaskCount}
                </span>
              )}
            </button>
          )}

          {consoleMode === "terminal" && filteredTerminalEvents.length > 0 && (
            <button
              onClick={handleCopyAllTerminal}
              className="flex items-center gap-1 px-2 py-1 rounded bg-app-subtle text-app-muted hover:text-app-heading border border-app-border transition-colors cursor-pointer"
              title="Copy all terminal text"
            >
              {copiedTerminal ? (
                <>
                  <Check className="w-3 h-3 text-emerald-500" />
                  <span>Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy Terminal</span>
                </>
              )}
            </button>
          )}

          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`flex items-center gap-1 px-2 py-1 rounded border transition-colors cursor-pointer ${
              autoScroll
                ? "bg-blue-600/20 text-blue-500 dark:text-blue-400 border-blue-500/30 font-medium"
                : "bg-app-subtle text-app-muted border-app-border"
            }`}
          >
            <ArrowDown className="w-3 h-3" />
            Auto-scroll
          </button>

          <button
            onClick={clearEvents}
            className="px-2 py-1 rounded bg-app-subtle text-app-muted hover:text-app-heading border border-app-border transition-colors cursor-pointer"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Mode Filter Bar */}
      {consoleMode === "telemetry" ? (
        <div className="flex flex-wrap items-center justify-between p-2 gap-2 border-b border-app-border bg-app-surface/50 select-none text-xs">
          <div className="flex items-center space-x-2 flex-1 min-w-[240px]">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-2 w-3.5 h-3.5 text-app-muted" />
              <input
                type="text"
                placeholder="Search telemetry events..."
                value={logSearch}
                onChange={(e) => setLogSearch(e.target.value)}
                className="w-full bg-app-bg border border-app-border rounded pl-8 pr-2 py-1 text-xs text-app-text focus:outline-none focus:border-blue-500"
              />
            </div>

            {/* Level selector */}
            <select
              value={logFilterLevel}
              onChange={(e) => setLogFilterLevel(e.target.value)}
              className="bg-app-bg border border-app-border rounded px-2 py-1 text-xs text-app-text focus:outline-none"
            >
              <option value="all">All Levels</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
              <option value="debug">Debug</option>
            </select>

            {/* Phase selector */}
            {availablePhases.length > 0 && (
              <select
                value={logFilterPhase}
                onChange={(e) => setLogFilterPhase(e.target.value)}
                className="bg-app-bg border border-app-border rounded px-2 py-1 text-xs text-app-text focus:outline-none max-w-[150px] truncate"
              >
                <option value="all">All Phases</option>
                {availablePhases.map((phase) => (
                  <option key={phase} value={phase}>
                    {phase}
                  </option>
                ))}
              </select>
            )}
          </div>

          <span className="text-app-muted font-mono text-xs">
            {filteredTelemetryEvents.length} / {telemetryEvents.length} events
          </span>
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between p-2 gap-2 border-b border-app-border bg-app-surface/50 select-none text-xs">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-2.5 top-2 w-3.5 h-3.5 text-app-muted" />
            <input
              type="text"
              placeholder="Search terminal output..."
              value={terminalSearch}
              onChange={(e) => setTerminalSearch(e.target.value)}
              className="w-full bg-app-bg border border-app-border rounded pl-8 pr-2 py-1 text-xs text-app-text focus:outline-none focus:border-blue-500"
            />
          </div>

          <span className="text-app-muted font-mono text-xs">
            {filteredTerminalEvents.length} / {terminalEvents.length} lines
          </span>
        </div>
      )}

      {/* Main Console Content */}
      {consoleMode === "telemetry" ? (
        /* Domain Telemetry View (TanStack Virtual - D-06) */
        <div ref={parentRef} className="flex-1 overflow-auto font-mono text-xs p-2">
          {filteredTelemetryEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-app-muted space-y-1">
              <Activity className="w-6 h-6 opacity-30" />
              <p>No telemetry events recorded yet.</p>
              <p className="text-[11px]">Connect to a stream or launch a run to inspect events.</p>
            </div>
          ) : (
            <div
              style={{
                height: `${virtualizer.getTotalSize()}px`,
                width: "100%",
                position: "relative",
              }}
            >
              {virtualizer.getVirtualItems().map((virtualRow) => {
                const event = filteredTelemetryEvents[virtualRow.index];
                const isExpanded = expandedSeq === event.seq;

                return (
                  <div
                    key={event.seq}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                    className="flex flex-col py-0.5"
                  >
                    {/* Bounded queue gap marker banner (M5) */}
                    {event.dropped_before > 0 && (
                      <div className="flex items-center gap-1.5 px-2.5 py-1 mb-1 rounded bg-amber-500/10 text-amber-500 dark:text-amber-400 border border-amber-500/30 text-[11px]">
                        <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                        <span>
                          ⚠️ <strong>{event.dropped_before} events dropped</strong> prior to #{event.seq} due to observer queue saturation
                        </span>
                      </div>
                    )}

                    {/* Main Event Row */}
                    <div
                      onClick={() => setExpandedSeq(isExpanded ? null : event.seq)}
                      className="flex items-start gap-2 px-2 py-1 rounded hover:bg-app-surface cursor-pointer group transition-colors"
                    >
                      <span className="text-app-muted w-8 text-right flex-shrink-0">
                        #{event.seq}
                      </span>

                      <span className="text-app-muted flex-shrink-0 w-16">
                        {event.ts ? new Date(event.ts).toLocaleTimeString() : "--"}
                      </span>

                      <span
                        className={`uppercase text-[10px] px-1.5 py-0.2 rounded border font-semibold flex-shrink-0 ${getLevelColor(
                          event.level
                        )}`}
                      >
                        {event.level}
                      </span>

                      {event.phase && (
                        <span className="text-[11px] px-1.5 py-0.2 rounded bg-app-subtle text-app-text border border-app-border flex-shrink-0 max-w-[150px] truncate">
                          {event.phase}
                        </span>
                      )}

                      <span className="text-blue-500 dark:text-[#58a6ff] font-medium flex-shrink-0">
                        {event.kind}
                      </span>

                      <span className="text-app-text flex-1 truncate">{event.message}</span>

                      <span className="text-app-muted group-hover:text-app-heading flex-shrink-0">
                        {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                      </span>
                    </div>

                    {/* Expandable JSON Payload Inspector */}
                    {isExpanded && event.payload && Object.keys(event.payload).length > 0 && (
                      <div className="ml-10 my-1 p-2 bg-app-surface border border-app-border rounded text-[11px] overflow-x-auto text-app-muted">
                        <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        /* Raw Terminal Output View with Docked Progress Console */
        <div className="flex-1 flex flex-col min-h-0 bg-[#0d1117] overflow-hidden">
          {/* Docked Rich-style visual progress console element showing subtasks */}
          <div className="p-2 border-b border-zinc-800 bg-[#161b22]/50 shrink-0">
            <ProgressConsoleElement variant="terminal" showCompleted={false} />
          </div>

          <div
            ref={terminalParentRef}
            className="flex-1 overflow-auto bg-[#0d1117] text-[#c9d1d9] font-mono text-xs p-3 select-text"
          >
            {filteredTerminalEvents.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-zinc-500 space-y-2">
                <Terminal className="w-8 h-8 opacity-40 text-zinc-400" />
                <p className="font-semibold text-zinc-400">No terminal output received yet.</p>
                <p className="text-[11px] text-zinc-500 text-center max-w-sm">
                  Real python prints, logs, stderr exceptions, and pipeline subtasks stream here live during execution.
                </p>
                {logFilePath && (
                  <p className="text-[10px] text-zinc-600 font-mono">
                    Persisted file: {logFilePath}
                  </p>
                )}
              </div>
            ) : (
              <div
                style={{
                  height: `${terminalVirtualizer.getTotalSize()}px`,
                  width: "100%",
                  position: "relative",
                }}
              >
                {terminalVirtualizer.getVirtualItems().map((virtualRow) => {
                  const item = filteredTerminalEvents[virtualRow.index];
                  const isSubtask = item.payload?.stream === "subtask";
                  const isStderr =
                    !isSubtask &&
                    (item.payload?.stream === "stderr" ||
                    item.level === "error" ||
                    item.level === "warning");

                  return (
                    <div
                      key={item.seq}
                      style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        width: "100%",
                        transform: `translateY(${virtualRow.start}px)`,
                        height: `${virtualRow.size}px`,
                      }}
                      className="flex items-baseline gap-2 leading-relaxed hover:bg-white/5 px-1 rounded transition-colors"
                    >
                      <span className="text-zinc-600 select-none text-[10px] w-8 text-right shrink-0">
                        {virtualRow.index + 1}
                      </span>
                      <span className="text-zinc-500 select-none text-[10px] shrink-0">
                        {item.ts ? new Date(item.ts).toLocaleTimeString() : ""}
                      </span>
                      <span
                        className={`select-none text-[9px] px-1 py-0.2 rounded font-semibold uppercase shrink-0 ${
                          isSubtask
                            ? item.payload?.subtaskType === "completed"
                              ? "bg-emerald-950/80 text-emerald-400 border border-emerald-700/80"
                              : "bg-cyan-950/80 text-cyan-300 border border-cyan-700/80"
                            : isStderr
                            ? "bg-rose-950/80 text-rose-400 border border-rose-800/80"
                            : "bg-zinc-800 text-zinc-400 border border-zinc-700"
                        }`}
                      >
                        {isSubtask ? "subtask" : item.payload?.stream === "stderr" ? "stderr" : "stdout"}
                      </span>
                      <span
                        className={`whitespace-pre-wrap font-mono flex-1 break-all ${
                          isSubtask
                            ? item.payload?.subtaskType === "completed"
                              ? "text-emerald-300 font-semibold"
                              : "text-cyan-200 font-semibold"
                            : isStderr
                            ? "text-rose-300 font-medium"
                            : "text-[#c9d1d9]"
                        }`}
                      >
                        {item.message}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
