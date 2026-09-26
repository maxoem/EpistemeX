import { useEffect } from "react";

export interface EvaluationHotkeyHandlers {
  onAccept?: () => void;
  onReject?: () => void;
  onOpenAlias?: () => void;
  onUndo?: () => void;
  onNext?: () => void;
  onPrev?: () => void;
  onCommit?: () => void;
  enabled?: boolean;
}

/**
 * Global keyboard listener governing human-in-the-loop triage ergonomics.
 * Strictly bypasses when user focus is inside text fields, textareas, contenteditable elements,
 * or CodeMirror editors to prevent typing interference.
 */
export function useEvaluationHotkeys({
  onAccept,
  onReject,
  onOpenAlias,
  onUndo,
  onNext,
  onPrev,
  onCommit,
  enabled = true,
}: EvaluationHotkeyHandlers) {
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;

      // Detect if user is focused inside a typing context
      const isInput =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable ||
          Boolean(target.closest(".cm-editor")) ||
          Boolean(target.closest("[role='combobox']")) ||
          Boolean(target.closest("[data-hotkey-ignore]")));

      // Allow Cmd+Enter (or Ctrl+Enter) to commit even from inside a text input
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        if (onCommit) {
          e.preventDefault();
          onCommit();
        }
        return;
      }

      // If user is actively typing, bypass all navigation and triage single-key shortcuts
      if (isInput) {
        return;
      }

      // Undo shortcut: 'u' or Cmd+Z / Ctrl+Z
      if (
        (e.key === "u" || e.key === "U") ||
        ((e.metaKey || e.ctrlKey) && (e.key === "z" || e.key === "Z") && !e.shiftKey)
      ) {
        if (onUndo) {
          e.preventDefault();
          onUndo();
        }
        return;
      }

      // Navigation: j/ArrowDown (next), k/ArrowUp (prev)
      if (e.key === "j" || e.key === "ArrowDown") {
        if (onNext) {
          e.preventDefault();
          onNext();
        }
        return;
      }

      if (e.key === "k" || e.key === "ArrowUp") {
        if (onPrev) {
          e.preventDefault();
          onPrev();
        }
        return;
      }

      // Actions: 'a' or '1' -> True Positive
      if (e.key === "a" || e.key === "A" || e.key === "1") {
        if (onAccept) {
          e.preventDefault();
          onAccept();
        }
        return;
      }

      // Actions: 'r' or '2' -> False Positive
      if (e.key === "r" || e.key === "R" || e.key === "2") {
        if (onReject) {
          e.preventDefault();
          onReject();
        }
        return;
      }

      // Actions: 's' or '3' -> Map Schema Alias
      if (e.key === "s" || e.key === "S" || e.key === "3") {
        if (onOpenAlias) {
          e.preventDefault();
          onOpenAlias();
        }
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onAccept, onReject, onOpenAlias, onUndo, onNext, onPrev, onCommit, enabled]);
}
