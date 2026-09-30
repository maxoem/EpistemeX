import React, { useState, useEffect, useRef, useCallback } from "react";
import { MoveHorizontal, PanelLeftOpen, PanelRightOpen } from "lucide-react";

interface ResizablePanelProps {
  children: React.ReactNode;
  side?: "left" | "right";
  storageKey?: string;
  defaultWidth?: number;
  minWidth?: number;
  maxWidth?: number;
  collapsible?: boolean;
  collapseThreshold?: number;
  showFooter?: boolean;
  className?: string;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const ResizablePanel: React.FC<ResizablePanelProps> = ({
  children,
  side = "right",
  storageKey = "glp-studio-docked-panel-width",
  defaultWidth = 384,
  minWidth = 240,
  maxWidth = 900,
  collapsible = false,
  collapseThreshold = 140,
  showFooter = false,
  className = "",
  collapsed: externalCollapsed,
  onToggleCollapse,
}) => {
  const isLeft = side === "left";

  const [internalCollapsed, setInternalCollapsed] = useState<boolean>(() => {
    if (!collapsible || !storageKey) return false;
    try {
      const savedCollapsed = localStorage.getItem(`${storageKey}-collapsed`);
      if (savedCollapsed !== null) {
        return savedCollapsed === "true";
      }
    } catch {
      // ignore
    }
    return false;
  });

  const isCollapsed = externalCollapsed !== undefined ? externalCollapsed : internalCollapsed;
  const setIsCollapsed = useCallback(
    (valOrFn: boolean | ((prev: boolean) => boolean)) => {
      setInternalCollapsed((prev) => {
        const next = typeof valOrFn === "function" ? valOrFn(prev) : valOrFn;
        if (storageKey) {
          try {
            localStorage.setItem(`${storageKey}-collapsed`, String(next));
          } catch {
            // ignore
          }
        }
        return next;
      });
      if (onToggleCollapse) {
        onToggleCollapse();
      }
    },
    [storageKey, onToggleCollapse]
  );

  const [width, setWidth] = useState<number>(() => {
    if (!storageKey) return defaultWidth;
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= minWidth && parsed <= maxWidth) {
          return parsed;
        }
      }
    } catch {
      // ignore
    }
    return defaultWidth;
  });

  const [isDragging, setIsDragging] = useState(false);
  const startXRef = useRef<number>(0);
  const startWidthRef = useRef<number>(width);
  const currentWidthRef = useRef<number>(width);
  const lastExpandedWidthRef = useRef<number>(width >= minWidth ? width : defaultWidth);

  useEffect(() => {
    currentWidthRef.current = width;
    if (width >= minWidth) {
      lastExpandedWidthRef.current = width;
    }
  }, [width, minWidth, defaultWidth]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    startXRef.current = e.clientX;
    startWidthRef.current = currentWidthRef.current;
  }, []);

  const toggleCollapse = useCallback(() => {
    if (!collapsible) return;
    if (onToggleCollapse) {
      onToggleCollapse();
      return;
    }
    setIsCollapsed((prev) => {
      const next = !prev;
      if (!next && width < minWidth) {
        setWidth(lastExpandedWidthRef.current || defaultWidth);
      }
      return next;
    });
  }, [collapsible, onToggleCollapse, setIsCollapsed, width, minWidth, defaultWidth]);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - startXRef.current;
      // For left panel: dragging handle to the right (dx > 0) increases width.
      // For right panel: dragging handle to the left (dx < 0) increases width.
      const rawDelta = isLeft ? dx : -dx;
      const targetWidth = startWidthRef.current + rawDelta;

      if (collapsible && targetWidth < collapseThreshold) {
        setIsCollapsed(true);
        return;
      }

      if (collapsible && targetWidth >= collapseThreshold) {
        setIsCollapsed(false);
      }

      const dynamicMax = Math.min(maxWidth, window.innerWidth - 300);
      const effectiveMax = Math.max(minWidth, dynamicMax);
      const newWidth = Math.max(minWidth, Math.min(effectiveMax, targetWidth));
      setWidth(newWidth);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      try {
        if (storageKey) {
          localStorage.setItem(storageKey, String(currentWidthRef.current));
          if (collapsible) {
            localStorage.setItem(`${storageKey}-collapsed`, String(currentWidthRef.current < collapseThreshold));
          }
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
  }, [isDragging, isLeft, minWidth, maxWidth, collapsible, collapseThreshold, storageKey]);

  // Collapsed rail view (minimalist icon bar with expand trigger)
  if (collapsible && isCollapsed) {
    return (
      <div
        className={`relative h-full flex-shrink-0 flex flex-col bg-app-surface border-app-border z-20 ${
          isLeft ? "border-r w-10" : "border-l w-10"
        } ${className}`}
      >
        <div className="p-2 flex flex-col items-center justify-between h-full">
          <button
            onClick={toggleCollapse}
            className="p-1 rounded hover:bg-app-subtle text-app-muted hover:text-app-heading transition-colors cursor-pointer"
            title={isLeft ? "Expand sidebar (click or drag)" : "Expand panel (click or drag)"}
            aria-label="Expand sidebar"
          >
            {isLeft ? <PanelLeftOpen className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
          </button>

          {/* Vertical rotated text label */}
          <div
            onClick={toggleCollapse}
            className="flex-1 flex items-center justify-center cursor-pointer select-none py-4 text-[10px] font-mono uppercase tracking-widest text-app-muted hover:text-app-heading transition-colors"
            style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
          >
            {isLeft ? "Pipeline Runs" : "Inspector Panel"}
          </div>

          <button
            onClick={toggleCollapse}
            className="p-1 text-app-muted hover:text-app-heading hover:bg-app-subtle rounded transition-colors cursor-pointer"
            title="Expand"
          >
            <MoveHorizontal className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Resizing / Pull out handle on the collapsed border */}
        <div
          onMouseDown={handleMouseDown}
          role="separator"
          aria-orientation="vertical"
          aria-label="Drag to expand panel"
          title="Drag to expand panel"
          className={`absolute top-0 bottom-0 w-2 cursor-col-resize z-30 transition-colors group ${
            isLeft ? "-right-1 hover:bg-blue-500/40" : "-left-1 hover:bg-blue-500/40"
          } ${isDragging ? "bg-blue-500" : ""}`}
        />
      </div>
    );
  }

  return (
    <div
      style={{ width: `${width}px` }}
      className={`relative h-full flex-shrink-0 flex flex-col bg-app-surface overflow-hidden ${
        isLeft ? "border-r border-app-border" : "border-l border-app-border"
      } ${isDragging ? "select-none" : ""} ${className}`}
    >
      {/* Clean full-height drag border */}
      <div
        onMouseDown={handleMouseDown}
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize panel width"
        title="Drag left or right to resize panel width"
        className={`absolute top-0 bottom-0 w-1.5 cursor-col-resize z-30 transition-colors group ${
          isLeft ? "-right-0.5 hover:bg-blue-500/50" : "-left-0.5 hover:bg-blue-500/50"
        } ${isDragging ? "bg-blue-500" : ""}`}
      />

      {/* Main panel content */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
};
