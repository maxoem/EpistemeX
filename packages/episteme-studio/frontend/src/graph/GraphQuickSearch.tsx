import React, {useEffect, useState} from "react";
import {Command} from "cmdk";
import {ArrowRight, Circle, Search} from "lucide-react";
import {StudioNode} from "../api/types";

interface GraphQuickSearchProps {
  nodes: StudioNode[];
  onSelectNode: (node: StudioNode) => void;
  className?: string;
}

export const GraphQuickSearch: React.FC<GraphQuickSearchProps> = ({
  nodes,
  onSelectNode,
  className,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");

  // Keyboard shortcut listener for Cmd+K, Ctrl+K, or '/'
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        (e.key === "k" && (e.metaKey || e.ctrlKey)) ||
        (e.key === "/" &&
          !isOpen &&
          !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement))
      ) {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      } else if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  // Group nodes by layer for structured search results
  const l3Nodes = nodes.filter((n) => n.layer === 3);
  const l2Nodes = nodes.filter((n) => n.layer === 2 || !n.layer);
  const l1Nodes = nodes.filter((n) => n.layer === 1);

  return (
    <>
      {/* Toolbar Trigger Button */}
      <button
        onClick={() => setIsOpen(true)}
        className={
          className ||
          "h-8 px-2.5 inline-flex items-center justify-between gap-2 bg-app-bg text-app-muted hover:text-app-heading hover:border-app-border rounded-md border border-app-border transition-colors text-xs w-44 sm:w-48 lg:w-56 group cursor-pointer shrink-0"
        }
        title="Quick Find Node (⌘K or /)"
        aria-label="Quick Find Node"
      >
        <div className="flex items-center gap-1.5 truncate">
          <Search className="w-3.5 h-3.5 text-app-muted group-hover:text-app-heading transition-colors shrink-0" />
          <span className="truncate">Quick find node...</span>
        </div>
        <div className="flex items-center gap-1 shrink-0 font-mono text-[10px] text-app-muted">
          <kbd className="bg-app-subtle px-1.5 py-0.5 rounded border border-app-border text-[9px] leading-none">
            ⌘K
          </kbd>
        </div>
      </button>

      {/* Floating Command Palette Modal */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-50 flex items-start justify-center pt-20 px-4 select-none"
          onClick={() => setIsOpen(false)}
        >
          <div
            className="w-full max-w-xl bg-app-surface border border-app-border rounded-xl shadow-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-100"
            onClick={(e) => e.stopPropagation()}
          >
            <Command
              className="w-full flex flex-col"
              loop
            >
              {/* Search Header */}
              <div className="flex items-center px-3 border-b border-app-border bg-app-surface">
                <Search className="w-4 h-4 text-app-muted mr-2 shrink-0" />
                <Command.Input
                  value={search}
                  onValueChange={setSearch}
                  placeholder="Search by label, ID, or type... (Esc to close)"
                  className="w-full py-3 bg-transparent text-app-heading text-xs placeholder:text-app-muted focus:outline-none"
                  autoFocus
                />
                <kbd
                  onClick={() => setIsOpen(false)}
                  className="text-[10px] text-app-muted font-mono bg-app-subtle px-1.5 py-0.5 rounded border border-app-border cursor-pointer hover:text-app-heading"
                >
                  ESC
                </kbd>
              </div>

              {/* Results List */}
              <Command.List className="max-h-80 overflow-y-auto p-1.5">
                <Command.Empty className="p-6 text-center text-xs text-app-muted">
                  No matching nodes found.
                </Command.Empty>

                {/* Layer 3: TheoryNet & Claims */}
                {l3Nodes.length > 0 && (
                  <Command.Group
                    heading="TheoryNet & Arguments (L3)"
                    className="text-[10px] font-semibold text-app-muted uppercase tracking-wider px-2 py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-app-muted [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:mb-1"
                  >
                    {l3Nodes.map((node) => (
                      <Command.Item
                        key={node.id}
                        value={`${node.label || ""} ${node.id} ${node.type} L3 TheoryNet`}
                        onSelect={() => {
                          onSelectNode(node);
                          setIsOpen(false);
                        }}
                        className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-app-subtle data-[selected=true]:text-app-heading transition-colors"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Circle className="w-2.5 h-2.5 fill-emerald-400 text-emerald-400 shrink-0" />
                          <span className="font-medium truncate text-app-heading">
                            {node.label || node.id}
                          </span>
                          <span className="text-[10px] font-mono text-app-muted bg-app-bg px-1 py-0.2 rounded border border-app-border shrink-0">
                            {node.type}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 text-[11px] text-app-muted font-mono shrink-0">
                          <span className="truncate max-w-[120px]">{node.id}</span>
                          <ArrowRight className="w-3 h-3 text-app-muted" />
                        </div>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}

                {/* Layer 2: Entities & Relations */}
                {l2Nodes.length > 0 && (
                  <Command.Group
                    heading="Entities & Concepts (L2)"
                    className="text-[10px] font-semibold text-app-muted uppercase tracking-wider px-2 py-1.5 mt-1 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-app-muted [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:mb-1"
                  >
                    {l2Nodes.map((node) => (
                      <Command.Item
                        key={node.id}
                        value={`${node.label || ""} ${node.id} ${node.type} L2 Entity`}
                        onSelect={() => {
                          onSelectNode(node);
                          setIsOpen(false);
                        }}
                        className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-app-subtle data-[selected=true]:text-app-heading transition-colors"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Circle className="w-2.5 h-2.5 fill-purple-400 text-purple-400 shrink-0" />
                          <span className="font-medium truncate text-app-heading">
                            {node.label || node.id}
                          </span>
                          <span className="text-[10px] font-mono text-app-muted bg-app-bg px-1 py-0.2 rounded border border-app-border shrink-0">
                            {node.type}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 text-[11px] text-app-muted font-mono shrink-0">
                          <span className="truncate max-w-[120px]">{node.id}</span>
                          <ArrowRight className="w-3 h-3 text-app-muted" />
                        </div>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}

                {/* Layer 1: Chunks */}
                {l1Nodes.length > 0 && (
                  <Command.Group
                    heading="Evidence Chunks (L1)"
                    className="text-[10px] font-semibold text-app-muted uppercase tracking-wider px-2 py-1.5 mt-1 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-app-muted [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:mb-1"
                  >
                    {l1Nodes.map((node) => (
                      <Command.Item
                        key={node.id}
                        value={`${node.label || ""} ${node.id} ${node.type} L1 Chunk`}
                        onSelect={() => {
                          onSelectNode(node);
                          setIsOpen(false);
                        }}
                        className="flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer text-xs text-app-text hover:bg-app-subtle hover:text-app-heading data-[selected=true]:bg-app-subtle data-[selected=true]:text-app-heading transition-colors"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Circle className="w-2.5 h-2.5 fill-blue-400 text-blue-400 shrink-0" />
                          <span className="font-medium truncate text-app-heading">
                            {node.label || node.id}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 text-[11px] text-app-muted font-mono shrink-0">
                          <span className="truncate max-w-[120px]">{node.id}</span>
                          <ArrowRight className="w-3 h-3 text-app-muted" />
                        </div>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}
              </Command.List>

              {/* Palette Footer */}
              <div className="flex items-center justify-between px-3 py-2 border-t border-app-border bg-app-bg text-[10px] text-app-muted font-mono">
                <span>Navigate: ↑ ↓ · Select: ↵ · Close: Esc</span>
                <span>{nodes.length} total nodes</span>
              </div>
            </Command>
          </div>
        </div>
      )}
    </>
  );
};
