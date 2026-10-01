import React, { useState, useEffect, useRef, useCallback } from "react";
import { MoveHorizontal, PanelLeftOpen, PanelRightOpen } from "lucide-react";

export interface ResizablePanelProps {
  children: React.ReactNode;
  side?: "left" | "right";
  storageKey?: string;
  defaultWidth?: number;
  minWidth?: number;
  maxWidth?: number;
  collapsible?: boolean;
  collapseThreshold?: number;
  collapsedWidth?: number;
  showFooter?: boolean;
  className?: string;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onCollapseChange?: (collapsed: boolean) => void;
  collapsedLabel?: string;
  collapsedContent?: React.ReactNode;
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
  collapsedWidth = 48,
  showFooter = false,
  className = "",
  collapsed: externalCollapsed,
  onToggleCollapse,
  onCollapseChange,
  collapsedLabel,
  collapsedContent,
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

  const isControlled = externalCollapsed !== undefined;
  const isCollapsed = isControlled ? externalCollapsed : internalCollapsed;

  const setCollapsedState = useCallback(
    (nextCollapsed: boolean) => {
      if (!isControlled) {
        setInternalCollapsed(nextCollapsed);
      }
      if (storageKey) {
        try {
          localStorage.setItem(`${storageKey}-collapsed`, String(nextCollapsed));
        } catch {
          // ignore
        }
      }
      if (onCollapseChange) {
        onCollapseChange(nextCollapsed);
      } else if (onToggleCollapse && nextCollapsed !== isCollapsed) {
        onToggleCollapse();
      }
    },
    [isControlled, storageKey, onCollapseChange, onToggleCollapse, isCollapsed]
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
  const rafIdRef = useRef<number | null>(null);
  const wasCollapsedAtDragStartRef = useRef<boolean>(false);

  useEffect(() => {
    currentWidthRef.current = width;
    if (width >= minWidth) {
      lastExpandedWidthRef.current = width;
    }
  }, [width, minWidth]);

  // Sync cursor and prevent text selection during drag operations
  useEffect(() => {
    if (isDragging) {
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    } else {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isDragging]);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(true);
      startXRef.current = e.clientX;
      startWidthRef.current = isCollapsed ? collapsedWidth : width;
      wasCollapsedAtDragStartRef.current = isCollapsed;
    },
    [isCollapsed, collapsedWidth, width]
  );

  const toggleCollapse = useCallback(() => {
    if (!collapsible) return;
    const next = !isCollapsed;
    if (!next && width < minWidth) {
      setWidth(lastExpandedWidthRef.current || defaultWidth);
    }
    setCollapsedState(next);
  }, [collapsible, isCollapsed, width, minWidth, defaultWidth, setCollapsedState]);

  const handleDoubleClick = useCallback(() => {
    if (isCollapsed) {
      setCollapsedState(false);
      setWidth(defaultWidth);
    } else {
      setWidth(defaultWidth);
    }
  }, [isCollapsed, defaultWidth, setCollapsedState]);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - startXRef.current;
      const rawDelta = isLeft ? dx : -dx;

      // Case A: Dragging to expand from collapsed state
      if (wasCollapsedAtDragStartRef.current) {
        if (rawDelta > 15) {
          const targetWidth = minWidth + (rawDelta - 15);
          const clamped = Math.max(minWidth, Math.min(maxWidth, targetWidth));
          setWidth(clamped);
          currentWidthRef.current = clamped;
          setCollapsedState(false);
          wasCollapsedAtDragStartRef.current = false;
          startXRef.current = e.clientX;
          startWidthRef.current = clamped;
        }
        return;
      }

      // Case B: Normal resizing from expanded state
      const targetWidth = startWidthRef.current + rawDelta;

      // Collapse snap threshold
      if (collapsible && targetWidth < collapseThreshold) {
        if (!isCollapsed) {
          setCollapsedState(true);
        }
        return;
      }

      if (collapsible && isCollapsed && targetWidth >= collapseThreshold) {
        setCollapsedState(false);
      }

      // Resistance and magnetic snapping to defaultWidth (within 12px)
      let effectiveWidth = targetWidth;
      if (Math.abs(targetWidth - defaultWidth) < 12) {
        effectiveWidth = defaultWidth;
      }

      // Resistance and magnetic snapping to minWidth (within 12px)
      if (Math.abs(targetWidth - minWidth) < 12) {
        effectiveWidth = minWidth;
      }

      const dynamicMax = Math.min(maxWidth, window.innerWidth - 200);
      const effectiveMax = Math.max(minWidth, dynamicMax);
      const newWidth = Math.max(minWidth, Math.min(effectiveMax, effectiveWidth));

      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
      rafIdRef.current = requestAnimationFrame(() => {
        setWidth(newWidth);
        currentWidthRef.current = newWidth;
      });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
      try {
        if (storageKey) {
          localStorage.setItem(storageKey, String(currentWidthRef.current));
        }
      } catch {
        // ignore
      }
    };

    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, [
    isDragging,
    isLeft,
    minWidth,
    maxWidth,
    defaultWidth,
    collapsible,
    collapseThreshold,
    isCollapsed,
    setCollapsedState,
    storageKey,
  ]);

  // ─────────────────────────────────────────────────────────────────────────
  // Collapsed View (Supports customized functional icon rail or rotated label)
  // ─────────────────────────────────────────────────────────────────────────
  if (collapsible && isCollapsed) {
    return (
      <div
        style={{ width: `${collapsedWidth}px` }}
        className={`relative h-full flex-shrink-0 flex flex-col bg-app-surface z-20 ${
          isLeft ? "border-r border-app-border" : "border-l border-app-border"
        } ${className}`}
      >
        {collapsedContent ? (
          collapsedContent
        ) : (
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
              {collapsedLabel ?? (isLeft ? "Navigation" : "Inspector Panel")}
            </div>

            <button
              onClick={toggleCollapse}
              className="p-1 text-app-muted hover:text-app-heading hover:bg-app-subtle rounded transition-colors cursor-pointer"
              title="Expand"
            >
              <MoveHorizontal className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Resizing / Pull-out drag handle on the collapsed boundary */}
        <div
          onMouseDown={handleMouseDown}
          onDoubleClick={handleDoubleClick}
          role="separator"
          aria-orientation="vertical"
          aria-label="Drag to expand panel (double click to reset)"
          title="Drag to expand panel (double-click to reset)"
          className={`absolute top-0 bottom-0 w-2.5 cursor-col-resize z-30 transition-colors group ${
            isLeft ? "-right-1.5 hover:bg-blue-500/40" : "-left-1.5 hover:bg-blue-500/40"
          } ${isDragging ? "bg-blue-500" : ""}`}
        />
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Expanded View
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div
      style={{ width: `${width}px` }}
      className={`relative h-full flex-shrink-0 flex flex-col bg-app-surface overflow-hidden ${
        isLeft ? "border-r border-app-border" : "border-l border-app-border"
      } ${isDragging ? "select-none" : ""} ${className}`}
    >
      {/* Precision drag border */}
      <div
        onMouseDown={handleMouseDown}
        onDoubleClick={handleDoubleClick}
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize panel width (double-click to reset)"
        title="Drag left or right to resize (double-click to reset)"
        className={`absolute top-0 bottom-0 w-2 cursor-col-resize z-30 transition-colors group ${
          isLeft ? "-right-1 hover:bg-blue-500/50" : "-left-1 hover:bg-blue-500/50"
        } ${isDragging ? "bg-blue-500" : ""}`}
      />

      {/* Main panel content */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
};
