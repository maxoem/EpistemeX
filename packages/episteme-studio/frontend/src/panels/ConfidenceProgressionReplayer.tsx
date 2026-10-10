import React, {useEffect, useState} from "react";
import {Activity, Pause, Play, RotateCcw, SkipBack, SkipForward, X} from "lucide-react";
import {ProgressionSnapshot} from "../store/runsStore";

export interface ConfidenceProgressionReplayerProps {
  snapshots: ProgressionSnapshot[];
  activeIndex: number;
  onChangeIndex: (index: number) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
  onResetLive?: () => void;
  totalPoints: number;
  onClose?: () => void;
}

const PLAYBACK_SPEEDS = [0.5, 1, 2, 4] as const;
const BASE_FRAME_DELAY_MS = 800;

const formatFrameTime = (timestamp?: string): string => {
  if (!timestamp) return "—";
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString();
};

export const ConfidenceProgressionReplayer: React.FC<ConfidenceProgressionReplayerProps> = ({
  snapshots,
  activeIndex,
  onChangeIndex,
  isPlaying,
  onTogglePlay,
  onResetLive,
  totalPoints,
  onClose,
}) => {
  const [speed, setSpeed] = useState<number>(1);

  // Auto-advance when playing, honoring the selected playback speed
  useEffect(() => {
    if (!isPlaying) return;
    if (snapshots.length <= 1) return;

    const delay = Math.max(120, Math.round(BASE_FRAME_DELAY_MS / speed));
    const timer = setInterval(() => {
      onChangeIndex(activeIndex >= snapshots.length - 1 ? 0 : activeIndex + 1);
    }, delay);

    return () => clearInterval(timer);
  }, [isPlaying, activeIndex, snapshots.length, onChangeIndex, speed]);

  if (!snapshots || snapshots.length === 0) {
    return null;
  }

  const currentSnapshot = snapshots[activeIndex] || snapshots[snapshots.length - 1];
  const isAtEnd = activeIndex === snapshots.length - 1;
  const meanPct = Number.isFinite(currentSnapshot.mean) ? `${(currentSnapshot.mean * 100).toFixed(1)}%` : "—";
  const pointCount = currentSnapshot.count ?? 0;

  return (
    <div className="rounded-lg border border-app-border bg-app-surface p-3 my-2">
      {/* Header: Title, readouts, close */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ backgroundColor: "#3b82f6" }}
          />
          <span className="text-xs font-semibold uppercase tracking-wider text-app-heading flex items-center gap-1">
            <Activity className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
            Progression Replay
          </span>
          <span className="rounded bg-app-bg px-2 py-0.5 text-[11px] font-mono text-app-heading border border-app-border">
            Step {activeIndex + 1}/{snapshots.length}
          </span>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <span className="text-app-muted">
            Points:{" "}
            <strong className="text-app-heading font-mono">
              {pointCount}
            </strong>{" "}
            / {totalPoints}
          </span>
          <span className="text-app-muted">
            Mean Score:{" "}
            <strong className="text-emerald-600 dark:text-emerald-400 font-mono">
              {meanPct}
            </strong>
          </span>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
              title="Close replay"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Scrubber slider */}
      <div className="flex items-center gap-3">
        <input
          type="range"
          min={0}
          max={snapshots.length - 1}
          value={activeIndex}
          onChange={(e) => onChangeIndex(parseInt(e.target.value, 10))}
          className="precision-slider w-full"
          title={`Scrub to step ${activeIndex + 1}`}
        />
      </div>

      {/* Controls: Transport, speed toggle, live reset */}
      <div className="flex items-center justify-between flex-wrap gap-2 mt-2 pt-1 border-t border-app-border/80">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={onTogglePlay}
            className="flex items-center gap-1 rounded px-2.5 py-1 text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white border border-blue-600 transition-colors cursor-pointer"
            title={isPlaying ? "Pause Replay" : "Play Progression"}
          >
            {isPlaying ? (
              <>
                <Pause className="w-3 h-3 fill-current" />
                <span>Pause</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3 fill-current" />
                <span>Play</span>
              </>
            )}
          </button>

          <button
            type="button"
            disabled={activeIndex === 0}
            onClick={() => onChangeIndex(Math.max(0, activeIndex - 1))}
            className="rounded p-1 text-app-muted hover:text-app-heading hover:bg-app-subtle disabled:opacity-40 disabled:pointer-events-none transition-colors cursor-pointer"
            title="Previous Snapshot"
          >
            <SkipBack className="w-3.5 h-3.5" />
          </button>

          <button
            type="button"
            disabled={activeIndex === snapshots.length - 1}
            onClick={() => onChangeIndex(Math.min(snapshots.length - 1, activeIndex + 1))}
            className="rounded p-1 text-app-muted hover:text-app-heading hover:bg-app-subtle disabled:opacity-40 disabled:pointer-events-none transition-colors cursor-pointer"
            title="Next Snapshot"
          >
            <SkipForward className="w-3.5 h-3.5" />
          </button>

          <span className="ml-1 text-[10px] font-mono text-app-muted">Speed</span>
          <div className="flex items-center gap-0.5">
            {PLAYBACK_SPEEDS.map((sp) => (
              <button
                key={sp}
                type="button"
                onClick={() => setSpeed(sp)}
                className={`px-1.5 py-0.5 rounded text-[10px] font-mono border transition-colors cursor-pointer ${
                  speed === sp
                    ? "bg-blue-600 text-white border-blue-600 font-semibold"
                    : "bg-app-bg text-app-muted border-app-border hover:text-app-heading"
                }`}
                title={`Playback speed ${sp}x`}
              >
                {sp}x
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!isAtEnd && onResetLive && (
            <button
              type="button"
              onClick={onResetLive}
              className="flex items-center gap-1 text-[11px] text-blue-600 dark:text-blue-400 hover:text-blue-500 hover:underline"
            >
              <RotateCcw className="w-3 h-3" />
              Latest (Live)
            </button>
          )}
          <span className="text-[10px] text-app-muted font-mono">
            {formatFrameTime(currentSnapshot.timestamp)}
          </span>
        </div>
      </div>
    </div>
  );
};
