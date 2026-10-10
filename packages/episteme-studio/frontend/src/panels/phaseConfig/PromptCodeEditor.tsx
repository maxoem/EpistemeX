import React, {useEffect, useRef} from "react";
import {EditorState, Extension} from "@codemirror/state";
import {
    Decoration,
    EditorView,
    highlightActiveLine,
    highlightActiveLineGutter,
    lineNumbers,
    MatchDecorator,
    ViewPlugin
} from "@codemirror/view";
import {useThemeStore} from "../../store/themeStore";

interface PromptCodeEditorProps {
  value: string;
  onChange?: (val: string) => void;
  readOnly?: boolean;
  minHeight?: string;
  maxHeight?: string;
  placeholder?: string;
}

// Matches variables enclosed in single or multiple curly braces, e.g. {chunk_text}
const placeholderMatcher = new MatchDecorator({
  regexp: /\{+[a-zA-Z0-9_]+\}+/g,
  decoration: () => Decoration.mark({ class: "cm-template-variable" }),
});

const placeholderPlugin = ViewPlugin.fromClass(
  class {
    decorations: any;
    constructor(view: EditorView) {
      this.decorations = placeholderMatcher.createDeco(view);
    }
    update(update: any) {
      this.decorations = placeholderMatcher.updateDeco(update, this.decorations);
    }
  },
  {
    decorations: (v) => v.decorations,
  }
);

export const PromptCodeEditor: React.FC<PromptCodeEditorProps> = ({
  value,
  onChange,
  readOnly = false,
  minHeight = "80px",
  maxHeight = "320px",
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<EditorView | null>(null);
  const { theme } = useThemeStore();

  useEffect(() => {
    if (!containerRef.current) return;

    const isDark = theme === "dark";

    const baseTheme = EditorView.theme({
      "&": {
        fontSize: "11px",
        fontFamily: "var(--font-mono)",
        backgroundColor: "transparent",
        color: isDark ? "#e6edf3" : "#111827",
      },
      ".cm-content": {
        padding: "6px 8px",
        caretColor: isDark ? "#58a6ff" : "#0969da",
        lineHeight: "1.5",
      },
      ".cm-line": {
        padding: "0 2px",
      },
      "&.cm-focused": {
        outline: "none",
      },
      ".cm-scroller": {
        minHeight,
        maxHeight,
        overflowY: "auto",
        fontFamily: "inherit",
      },
      ".cm-gutters": {
        backgroundColor: isDark ? "#161b22" : "#f6f8fa",
        color: isDark ? "#6e7681" : "#8c959f",
        borderRight: `1px solid ${isDark ? "#30363d" : "#d0d7de"}`,
        fontSize: "10px",
        userSelect: "none",
      },
      ".cm-activeLineGutter": {
        backgroundColor: isDark ? "#21262d" : "#e1e4e8",
        color: isDark ? "#f0f6fc" : "#1f2328",
      },
      ".cm-activeLine": {
        backgroundColor: isDark ? "rgba(110, 118, 129, 0.08)" : "rgba(208, 215, 222, 0.2)",
      },
    });

    const extensions: Extension[] = [
      lineNumbers(),
      highlightActiveLineGutter(),
      highlightActiveLine(),
      placeholderPlugin,
      baseTheme,
      EditorView.lineWrapping,
    ];

    if (readOnly) {
      extensions.push(EditorState.readOnly.of(true));
      extensions.push(EditorView.editable.of(false));
    }

    if (onChange) {
      extensions.push(
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            onChange(update.state.doc.toString());
          }
        })
      );
    }

    const state = EditorState.create({
      doc: value || "",
      extensions,
    });

    const view = new EditorView({
      state,
      parent: containerRef.current,
    });

    viewRef.current = view;

    return () => {
      view.destroy();
      viewRef.current = null;
    };
  }, [theme, readOnly]);

  // Synchronize document if value changes externally
  useEffect(() => {
    const view = viewRef.current;
    if (view && value !== undefined) {
      const currentDoc = view.state.doc.toString();
      if (currentDoc !== value) {
        view.dispatch({
          changes: { from: 0, to: currentDoc.length, insert: value },
        });
      }
    }
  }, [value]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-none border border-app-border bg-app-bg overflow-hidden focus-within:border-app-muted transition-colors"
    />
  );
};
