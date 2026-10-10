import React, {useEffect, useRef} from "react";
import {StudioNode} from "../api/types";
import {Activity, Copy, Info, Zap} from "lucide-react";

interface NodeContextMenuProps {
  node: StudioNode;
  x: number;
  y: number;
  onExpand: (nodeId: string) => void;
  onCalculateMetrics: (node: StudioNode) => void;
  onInspect: (node: StudioNode) => void;
  onClose: () => void;
  onNotify?: (msg: string) => void;
}

export const NodeContextMenu: React.FC<NodeContextMenuProps> = ({
  node,
  x,
  y,
  onExpand,
  onCalculateMetrics,
  onInspect,
  onClose,
  onNotify,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);

  // Close when clicking outside or pressing Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("mousedown", handleClickOutside);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("mousedown", handleClickOutside);
    };
  }, [onClose]);

  const handleCopyId = () => {
    navigator.clipboard.writeText(node.id);
    onNotify?.(`Copied Node ID: ${node.id}`);
    onClose();
  };

  // Adjust positioning to avoid overflowing viewport
  const adjustedX = Math.min(x, window.innerWidth - 220);
  const adjustedY = Math.min(y, window.innerHeight - 180);

  return (
    <div
      ref={menuRef}
      role="menu"
      aria-label={`Context menu for node ${node.label || node.id}`}
      style={{ top: `${adjustedY}px`, left: `${adjustedX}px` }}
      className="fixed z-50 w-56 bg-app-surface border border-app-border py-1 text-xs text-app-text select-none animate-in fade-in duration-75"
    >
      <div className="px-3 py-1.5 border-b border-app-border-subtle text-[10px] text-app-muted truncate font-mono">
        {node.label || node.id}
      </div>

      <button
        role="menuitem"
        onClick={() => {
          onExpand(node.id);
          onClose();
        }}
        className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-app-subtle hover:text-app-heading transition-colors cursor-pointer text-xs"
      >
        <Zap className="w-3.5 h-3.5 text-app-muted" />
        <span>Expand Neighbors (+1 hop)</span>
      </button>

      <button
        role="menuitem"
        onClick={() => {
          onCalculateMetrics(node);
          onClose();
        }}
        className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-app-subtle hover:text-app-heading transition-colors cursor-pointer text-xs"
      >
        <Activity className="w-3.5 h-3.5 text-app-muted" />
        <span>Calculate Metrics for Node</span>
      </button>

      <button
        role="menuitem"
        onClick={() => {
          onInspect(node);
          onClose();
        }}
        className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-app-subtle hover:text-app-heading transition-colors cursor-pointer text-xs"
      >
        <Info className="w-3.5 h-3.5 text-app-muted" />
        <span>Inspect Details</span>
      </button>

      <div className="my-1 border-t border-app-border-subtle" />

      <button
        role="menuitem"
        onClick={handleCopyId}
        className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-app-subtle transition-colors cursor-pointer text-app-muted hover:text-app-heading text-xs"
      >
        <Copy className="w-3.5 h-3.5" />
        <span>Copy Node ID</span>
      </button>
    </div>
  );
};
