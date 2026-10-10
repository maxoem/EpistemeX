import React, {useEffect, useRef} from "react";
import {StudioEdge} from "../api/types";
import {Copy, Filter, Search} from "lucide-react";
import {useEngineSchema} from "../store/engineSettingsStore";

interface EdgeContextMenuProps {
  edge: StudioEdge;
  x: number;
  y: number;
  onInspect: (edge: StudioEdge) => void;
  onFilterPath: (edge: StudioEdge) => void;
  onClose: () => void;
  onNotify?: (msg: string) => void;
}

export const EdgeContextMenu: React.FC<EdgeContextMenuProps> = ({
  edge,
  x,
  y,
  onInspect,
  onFilterPath,
  onClose,
  onNotify,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on Escape or click outside
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

  const { getPolarity } = useEngineSchema();

  const handleCopyIdAndPolarity = () => {
    const resolvedPolarity = getPolarity(edge.type) ?? edge.polarity ?? (edge.props as any)?.polarity ?? null;
    const polarityStr =
      resolvedPolarity === 1
        ? "support (+1)"
        : resolvedPolarity === -1
        ? "attack (-1)"
        : resolvedPolarity === 0
        ? "neutral (0)"
        : "unmapped (null)";
    const text = `Edge ID: ${edge.id}\nType: ${edge.type}\nPolarity: ${polarityStr}\nSource: ${edge.source}\nTarget: ${edge.target}`;
    navigator.clipboard.writeText(text);
    onNotify?.(`Copied Edge Details: ${edge.type} (${polarityStr})`);
    onClose();
  };

  const adjustedX = Math.min(x, window.innerWidth - 220);
  const adjustedY = Math.min(y, window.innerHeight - 180);

  return (
    <div
      ref={menuRef}
      role="menu"
      aria-label={`Context menu for edge ${edge.type}`}
      style={{ top: `${adjustedY}px`, left: `${adjustedX}px` }}
      className="fixed z-50 w-56 bg-app-surface border border-app-border py-1 text-xs text-app-text select-none animate-in fade-in duration-75"
    >
      <div className="px-3 py-1.5 border-b border-app-border-subtle text-[10px] text-app-muted truncate font-mono">
        {edge.type} ({edge.source} → {edge.target})
      </div>

      <button
        role="menuitem"
        onClick={() => {
          onInspect(edge);
          onClose();
        }}
        className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-app-subtle hover:text-app-heading transition-colors cursor-pointer text-xs"
      >
        <Search className="w-3.5 h-3.5 text-app-muted" />
        <span>Inspect Relation & Evidence</span>
      </button>

      <button
        role="menuitem"
        onClick={() => {
          onFilterPath(edge);
          onClose();
        }}
        className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-app-subtle hover:text-app-heading transition-colors cursor-pointer text-xs"
      >
        <Filter className="w-3.5 h-3.5 text-app-muted" />
        <span>Filter Path between Endpoints</span>
      </button>

      <div className="my-1 border-t border-app-border-subtle" />

      <button
        role="menuitem"
        onClick={handleCopyIdAndPolarity}
        className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-app-subtle transition-colors cursor-pointer text-app-muted hover:text-app-heading text-xs"
      >
        <Copy className="w-3.5 h-3.5" />
        <span>Copy Edge ID & Polarity</span>
      </button>
    </div>
  );
};
