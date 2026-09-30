import React, { useState, useEffect, useRef } from "react";
import { Command } from "cmdk";
import {
  GitMerge,
  Search,
  Check,
  X,
  ArrowRight,
  BookOpen,
  Sparkles,
} from "lucide-react";

export interface SchemaAliasOmnibarProps {
  isOpen: boolean;
  onClose: () => void;
  predictedPredicate: string;
  referencePredicate?: string | null;
  onSelectAlias: (aliasTarget: string) => void;
}

const CANONICAL_PREDICATES = [
  { id: "SPECIALIZES_TO", category: "Bourbaki / Poset", description: "Taxonomic sub-model specialization (Mp -> M)" },
  { id: "CO_APPLIES_WITH", category: "Bourbaki / Poset", description: "Joint constraint application" },
  { id: "HAS_GOVERNING_LAW", category: "Physical Mechanics", description: "Empirical application governed by fundamental law" },
  { id: "EXPRESSES_FORCE", category: "Physical Mechanics", description: "Kinematic or dynamical force statement" },
  { id: "DIRECTED_TOWARDS", category: "Physical Mechanics", description: "Vector directional relationship" },
  { id: "EQUALS_OPPOSITE", category: "Physical Mechanics", description: "Reciprocal action-reaction symmetry" },
  { id: "SUPPORTS", category: "Argumentation (L3)", description: "Inferential premise directly grounds claim" },
  { id: "ATTACKS", category: "Argumentation (L3)", description: "Dialectical counter-argument or rebuttal" },
  { id: "UNDERCUTS", category: "Argumentation (L3)", description: "Weakens inferential link between premise and claim" },
  { id: "ENTAILS", category: "Deductive Logic", description: "Logical entailment or semantic consequence" },
  { id: "PROVES", category: "Deductive Logic", description: "Formal derivation from established axioms" },
  { id: "EXPLAINS", category: "Scientific Epistemology", description: "Explanandum accounted for by theoretical framework" },
  { id: "has_constituent", category: "Structural Epistemics", description: "Mereological part-whole relation" },
  { id: "forms_basis_of", category: "Structural Epistemics", description: "Constitutional basis relation (Aufbau)" },
  { id: "DEFINES", category: "Ontological Taxonomy", description: "Nominal or real definition of concept" },
  { id: "DEPENDS_ON", category: "Ontological Taxonomy", description: "Existential or conceptual dependency" },
];

export const SchemaAliasOmnibar: React.FC<SchemaAliasOmnibarProps> = ({
  isOpen,
  onClose,
  predictedPredicate,
  referencePredicate,
  onSelectAlias,
}) => {
  const [search, setSearch] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setSearch(referencePredicate || "");
      setTimeout(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      }, 50);
    }
  }, [isOpen, referencePredicate]);

  if (!isOpen) return null;

  const handleSelect = (alias: string) => {
    if (!alias.trim()) return;
    onSelectAlias(alias.trim());
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-100"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-app-surface border border-app-border rounded-xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
        data-hotkey-ignore="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-app-border bg-app-subtle/50">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-violet-500/10 text-violet-500">
              <GitMerge className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-semibold text-app-heading">
                Map Schema Predicate Alias
              </h3>
              <p className="text-[11px] text-app-muted">
                Align predicted vocabulary drift to canonical ontology
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Current Context Pill */}
        <div className="px-4 py-2.5 border-b border-app-border/60 bg-app-bg flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-app-muted font-sans">Predicted:</span>
            <span className="font-mono font-medium text-amber-500 truncate bg-amber-500/10 px-1.5 py-0.5 rounded">
              {predictedPredicate}
            </span>
          </div>
          <ArrowRight className="w-3.5 h-3.5 text-app-muted shrink-0" />
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-app-muted font-sans">Reference:</span>
            <span className="font-mono font-medium text-blue-500 truncate bg-blue-500/10 px-1.5 py-0.5 rounded">
              {referencePredicate || "None (Drift)"}
            </span>
          </div>
        </div>

        {/* cmdk Container */}
        <Command
          className="flex flex-col overflow-hidden text-xs"
          loop
        >
          <div className="flex items-center gap-2 px-3 py-2 border-b border-app-border">
            <Search className="w-4 h-4 text-app-muted shrink-0" />
            <Command.Input
              ref={inputRef}
              value={search}
              onValueChange={setSearch}
              placeholder="Search canonical ontology or type custom alias..."
              className="w-full bg-transparent text-xs text-app-text placeholder-app-muted outline-hidden font-mono"
            />
            {search && (
              <button
                onClick={() => setSearch("")}
                className="text-[10px] text-app-muted hover:text-app-text"
              >
                Clear
              </button>
            )}
          </div>

          <Command.List className="max-h-64 overflow-y-auto p-1.5 divide-y divide-app-border/30">
            <Command.Empty className="py-4 text-center text-xs text-app-muted">
              No matching predicate found.
              <br />
              <button
                onClick={() => handleSelect(search)}
                className="mt-2 inline-flex items-center gap-1.5 px-3 py-1 bg-violet-600 hover:bg-violet-700 text-white rounded text-xs font-mono font-medium transition-colors"
              >
                <span>Use custom alias: &quot;{search}&quot;</span>
              </button>
            </Command.Empty>

            {/* If user typed a novel alias not strictly matching, show custom option on top */}
            {search && !CANONICAL_PREDICATES.some((p) => p.id.toLowerCase() === search.toLowerCase()) && (
              <Command.Item
                value={search}
                onSelect={() => handleSelect(search)}
                className="flex items-center justify-between px-3 py-2 rounded-md hover:bg-violet-500/10 cursor-pointer text-violet-500 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span className="font-mono font-semibold">Custom Alias: &quot;{search}&quot;</span>
                </div>
                <span className="text-[10px] bg-violet-500/15 px-1.5 py-0.5 rounded font-sans">
                  Press Enter
                </span>
              </Command.Item>
            )}

            {/* Suggested Reference Match if applicable */}
            {referencePredicate && (
              <Command.Group heading="Suggested Reference Target">
                <Command.Item
                  value={referencePredicate}
                  onSelect={() => handleSelect(referencePredicate)}
                  className="flex items-center justify-between px-3 py-2 rounded-md hover:bg-blue-500/10 cursor-pointer text-app-text transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-blue-500" />
                    <span className="font-mono font-semibold text-blue-600 dark:text-blue-400">
                      {referencePredicate}
                    </span>
                    <span className="text-[10px] text-app-muted font-sans">
                      (Matches gold target)
                    </span>
                  </div>
                  <span className="text-[10px] text-app-muted font-mono">Gold Match</span>
                </Command.Item>
              </Command.Group>
            )}

            {/* Canonical Predicates Group */}
            <Command.Group heading="Canonical Predicates">
              {CANONICAL_PREDICATES.map((pred) => (
                <Command.Item
                  key={pred.id}
                  value={`${pred.id} ${pred.category} ${pred.description}`}
                  onSelect={() => handleSelect(pred.id)}
                  className="flex items-center justify-between px-3 py-2 rounded-md hover:bg-app-subtle cursor-pointer text-app-text transition-colors"
                >
                  <div className="flex flex-col min-w-0 pr-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-semibold text-app-text truncate">
                        {pred.id}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-app-subtle text-app-muted border border-app-border/40">
                        {pred.category}
                      </span>
                    </div>
                    <span className="text-[11px] text-app-muted truncate">
                      {pred.description}
                    </span>
                  </div>
                  <BookOpen className="w-3.5 h-3.5 text-app-muted shrink-0" />
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>

          {/* Footer Controls */}
          <div className="flex items-center justify-between px-4 py-2 border-t border-app-border bg-app-subtle/30 text-[11px] text-app-muted">
            <span className="font-mono">
              [↑/↓] Select · [Enter] Confirm · [Esc] Cancel
            </span>
            <button
              onClick={() => handleSelect(search || referencePredicate || predictedPredicate)}
              disabled={!search.trim() && !referencePredicate}
              className="px-3 py-1 rounded bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-medium transition-colors"
            >
              Apply Alias
            </button>
          </div>
        </Command>
      </div>
    </div>
  );
};
