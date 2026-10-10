import React, {useState} from "react";
import {PromptRole, PromptTemplateItem} from "./types";
import {Check, ChevronDown, ChevronUp, Code2, Copy, Sparkles, Tag} from "lucide-react";
import {PromptCodeEditor} from "./PromptCodeEditor";

interface PromptTemplateViewerProps {
  prompts: PromptTemplateItem[];
}

const getRoleBadge = (role: PromptRole) => {
  switch (role) {
    case "direct":
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded-none bg-app-subtle text-app-text border border-app-border uppercase tracking-wide">
          <Sparkles className="w-2.5 h-2.5 text-app-muted" /> Direct
        </span>
      );
    case "reasoning":
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded-none bg-app-subtle text-app-text border border-app-border uppercase tracking-wide">
          <Code2 className="w-2.5 h-2.5 text-app-muted" /> Reasoning
        </span>
      );
    case "format":
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded-none bg-app-subtle text-app-text border border-app-border uppercase tracking-wide">
          <Check className="w-2.5 h-2.5 text-app-muted" /> Format
        </span>
      );
    case "gleaning":
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded-none bg-app-subtle text-app-text border border-app-border uppercase tracking-wide">
          Gleaning
        </span>
      );
    case "segmentation":
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded-none bg-app-subtle text-app-text border border-app-border uppercase tracking-wide">
          Segmentation
        </span>
      );
    case "linking":
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded-none bg-app-subtle text-app-text border border-app-border uppercase tracking-wide">
          Linking
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded-none bg-app-subtle text-app-muted border border-app-border uppercase tracking-wide">
          Custom
        </span>
      );
  }
};

/**
 * Highlights curly-braced variables (e.g. {chunk_text}) in prompt text.
 */
const renderHighlightedTemplate = (text: string) => {
  const parts = text.split(/(\{+[a-zA-Z0-9_]+\}+)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (/^\{+[a-zA-Z0-9_]+\}+$/.test(part)) {
          return (
            <span
              key={i}
              className="bg-cyan-500/15 text-cyan-600 dark:text-cyan-300 font-semibold px-1 py-0.2 rounded border border-cyan-500/30 select-all"
            >
              {part}
            </span>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
};

export const PromptTemplateViewer: React.FC<PromptTemplateViewerProps> = ({ prompts }) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [collapsedMap, setCollapsedMap] = useState<Record<string, boolean>>({});

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  const toggleCollapse = (id: string) => {
    setCollapsedMap((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  if (prompts.length === 0) {
    return (
      <div className="p-4 rounded-none bg-app-subtle border border-app-border text-center text-app-muted font-mono text-xs">
        No LLM prompt templates configured for this phase.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {prompts.map((p) => {
        const isCollapsed = !!collapsedMap[p.id];
        const isCopied = copiedId === p.id;

        return (
          <div
            key={p.id}
            className="rounded-none border border-app-border bg-app-surface overflow-hidden"
          >
            {/* Header bar of prompt card */}
            <div className="flex items-center justify-between px-3 py-1.5 bg-app-subtle/70 border-b border-app-border">
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-mono font-semibold text-xs text-app-heading truncate">
                  {p.name}
                </span>
                {getRoleBadge(p.role)}
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => handleCopy(p.id, p.template)}
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-none bg-app-surface hover:bg-app-subtle text-app-text hover:text-app-heading border border-app-border text-[11px] font-mono transition-colors cursor-pointer"
                  title="Copy full prompt template text to clipboard"
                >
                  {isCopied ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-500" />
                      <span className="text-emerald-500">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3 text-app-muted" />
                      <span>Copy</span>
                    </>
                  )}
                </button>

                <button
                  onClick={() => toggleCollapse(p.id)}
                  className="p-1 rounded-none text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
                  title={isCollapsed ? "Expand prompt" : "Collapse prompt"}
                >
                  {isCollapsed ? (
                    <ChevronDown className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronUp className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>
            </div>

            {/* Prompt Variables Pills */}
            {p.variables.length > 0 && !isCollapsed && (
              <div className="px-3 py-1 bg-app-surface border-b border-app-border flex items-center gap-1.5 flex-wrap text-[10px]">
                <span className="text-app-muted font-mono flex items-center gap-1 uppercase tracking-wider text-[9px]">
                  <Tag className="w-2.5 h-2.5" />
                  Vars:
                </span>
                {p.variables.map((v) => (
                  <span
                    key={v}
                    className="font-mono px-1 py-0.2 rounded-none bg-app-subtle text-app-text border border-app-border"
                  >
                    {`{${v}}`}
                  </span>
                ))}
              </div>
            )}

            {/* Prompt Template Body - CodeMirror with Syntax Highlighting */}
            {!isCollapsed && (
              <div className="p-2 bg-app-bg">
                <PromptCodeEditor
                  value={p.template}
                  readOnly={true}
                  minHeight="90px"
                  maxHeight="320px"
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
