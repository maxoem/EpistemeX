import React, {useEffect, useMemo, useState} from "react";
import {
    getAllRegisteredPhases,
    isPhaseMandatory,
    isPhasePostProcessor,
    PHASE_REGISTRY,
    PhaseMetadata,
} from "./phaseConfig/phaseRegistry";
import {
    ArrowRight,
    Boxes,
    Brain,
    Check,
    Cpu,
    FileText,
    Layers,
    Lock,
    Plus,
    RotateCcw,
    Search,
    SlidersHorizontal,
    Tag,
    X,
} from "lucide-react";

export interface PhaseCatalogDrawerProps {
  activePhaseKeys: string[];
  selectedPhaseKey: string;
  onSelectPhase: (phaseKey: string) => void;
  onTogglePhase: (phaseKey: string, nextActive: boolean) => void;
  onResetToDefault: () => void;
  onClose: () => void;
  onRegisterCustomPhase?: (meta: PhaseMetadata) => void;
}

const getPhaseIcon = (phase: PhaseMetadata) => {
  if (phase.key === "phase0") {
    return <Cpu className="w-3.5 h-3.5 text-app-muted group-hover:text-blue-500 shrink-0 transition-colors" />;
  }
  if (phase.key === "schema") {
    return <Tag className="w-3.5 h-3.5 text-app-muted group-hover:text-blue-500 shrink-0 transition-colors" />;
  }
  if (phase.key === "phase1") {
    return <FileText className="w-3.5 h-3.5 text-app-muted group-hover:text-blue-500 shrink-0 transition-colors" />;
  }
  if (phase.key === "phase2" || phase.key === "phase3" || phase.key === "phase3b") {
    return <Boxes className="w-3.5 h-3.5 text-app-muted group-hover:text-blue-500 shrink-0 transition-colors" />;
  }
  if (phase.key.includes("maturation") || phase.key === "phase4") {
    return <Brain className="w-3.5 h-3.5 text-app-muted group-hover:text-blue-500 shrink-0 transition-colors" />;
  }
  if (phase.isPostProcessor || phase.key === "phase7") {
    return <SlidersHorizontal className="w-3.5 h-3.5 text-app-muted group-hover:text-blue-500 shrink-0 transition-colors" />;
  }
  return <Layers className="w-3.5 h-3.5 text-app-muted group-hover:text-blue-500 shrink-0 transition-colors" />;
};

export const PhaseCatalogDrawer: React.FC<PhaseCatalogDrawerProps> = ({
  activePhaseKeys,
  selectedPhaseKey,
  onSelectPhase,
  onTogglePhase,
  onResetToDefault,
  onClose,
  onRegisterCustomPhase,
}) => {
  const [activeTab, setActiveTab] = useState<"all" | "core" | "post_processors" | "active">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreatingCustom, setIsCreatingCustom] = useState(false);

  // Custom phase creation fields
  const [customKey, setCustomKey] = useState("");
  const [customName, setCustomName] = useState("");
  const [customShortLabel, setCustomShortLabel] = useState("");
  const [customCategory, setCustomCategory] = useState("Analysis & Post-Processing");
  const [customDescription, setCustomDescription] = useState("");
  const [customError, setCustomError] = useState<string | null>(null);

  const allPhases = useMemo(() => getAllRegisteredPhases(), []);

  const corePhases = useMemo(
    () => allPhases.filter((p) => !p.isPostProcessor),
    [allPhases]
  );

  const postProcessorPhases = useMemo(
    () => allPhases.filter((p) => Boolean(p.isPostProcessor)),
    [allPhases]
  );

  const activePhases = useMemo(
    () => allPhases.filter((p) => activePhaseKeys.includes(p.key)),
    [allPhases, activePhaseKeys]
  );

  // Selected tab list
  const tabPhases = useMemo(() => {
    switch (activeTab) {
      case "core":
        return corePhases;
      case "post_processors":
        return postProcessorPhases;
      case "active":
        return activePhases;
      case "all":
      default:
        return allPhases;
    }
  }, [activeTab, corePhases, postProcessorPhases, activePhases, allPhases]);

  // Search filter
  const filteredPhases = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return tabPhases;
    return tabPhases.filter(
      (p) =>
        p.displayName.toLowerCase().includes(q) ||
        p.key.toLowerCase().includes(q) ||
        p.shortLabel.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q)
    );
  }, [tabPhases, searchQuery]);

  const handleCreateCustomProcessor = (e: React.FormEvent) => {
    e.preventDefault();
    setCustomError(null);

    const formattedKey = customKey.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_");
    if (!formattedKey) {
      setCustomError("Identifier key is required.");
      return;
    }

    if (PHASE_REGISTRY[formattedKey]) {
      setCustomError(`Phase key '${formattedKey}' already exists.`);
      return;
    }

    if (!customName.trim()) {
      setCustomError("Display name is required.");
      return;
    }

    const newPhaseMeta: PhaseMetadata = {
      key: formattedKey,
      canonicalOrdinal: 10 + Object.keys(PHASE_REGISTRY).length,
      displayName: customName.trim(),
      shortLabel: customShortLabel.trim() || customName.trim().slice(0, 10),
      category: customCategory.trim() || "Analysis & Post-Processing",
      isPostProcessor: true,
      isMandatory: false,
      configPrefix: formattedKey,
      description: customDescription.trim() || "Custom analytical post-processor extension.",
      parameterMeta: {
        enabled: {
          label: "Enable Post-Processor",
          description: "Whether this analytical post-processor execution is enabled",
        },
      },
      promptKeys: [],
    };

    if (onRegisterCustomPhase) {
      onRegisterCustomPhase(newPhaseMeta);
    }

    // Automatically enable and select new phase
    onTogglePhase(formattedKey, true);
    onSelectPhase(formattedKey);

    // Reset form
    setCustomKey("");
    setCustomName("");
    setCustomShortLabel("");
    setCustomDescription("");
    setIsCreatingCustom(false);
  };

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="w-full h-full flex flex-col bg-app-surface text-xs text-app-text overflow-hidden select-none">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Header                                                              */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="px-5 py-3.5 border-b border-app-border bg-app-surface flex items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2.5">
          <Layers className="w-4 h-4 text-app-heading shrink-0" />
          <div>
            <h2 className="text-sm font-semibold text-app-heading leading-tight">
              Pipeline Stages & Post-Processors
            </h2>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="font-mono text-[10px] text-app-muted">
                {activePhaseKeys.length} of {allPhases.length} active
              </span>
              <span className="text-app-muted/50 text-[10px]">·</span>
              <span className="text-[10px] text-app-muted">Esc or click left to dismiss</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={onResetToDefault}
            className="flex items-center gap-1 text-[11px] font-mono text-app-muted hover:text-app-heading px-2 py-1 rounded border border-app-border hover:bg-app-subtle transition-colors cursor-pointer"
            title="Reset active stages to default baseline"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Reset</span>
          </button>
          <button
            onClick={onClose}
            className="p-1.5 text-app-muted hover:text-app-heading hover:bg-app-subtle rounded transition-colors cursor-pointer"
            title="Close Drawer (Esc or click left)"
            aria-label="Close Drawer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Minimalist Tabs: All / Core / Post-Processors / Active              */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="flex border-b border-app-border bg-app-surface px-5 text-xs gap-5 shrink-0 overflow-x-auto scrollbar-none">
        <button
          onClick={() => setActiveTab("all")}
          className={`py-2 text-xs transition-colors cursor-pointer relative shrink-0 ${
            activeTab === "all"
              ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
              : "text-app-muted hover:text-app-heading"
          }`}
        >
          All <span className="font-mono text-[10px] text-app-muted">({allPhases.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("core")}
          className={`py-2 text-xs transition-colors cursor-pointer relative shrink-0 ${
            activeTab === "core"
              ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
              : "text-app-muted hover:text-app-heading"
          }`}
        >
          Core Pipeline <span className="font-mono text-[10px] text-app-muted">({corePhases.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("post_processors")}
          className={`py-2 text-xs transition-colors cursor-pointer relative shrink-0 ${
            activeTab === "post_processors"
              ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
              : "text-app-muted hover:text-app-heading"
          }`}
        >
          Post-Processors <span className="font-mono text-[10px] text-app-muted">({postProcessorPhases.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("active")}
          className={`py-2 text-xs transition-colors cursor-pointer relative shrink-0 ${
            activeTab === "active"
              ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
              : "text-app-muted hover:text-app-heading"
          }`}
        >
          Active <span className="font-mono text-[10px] text-emerald-500 font-semibold">({activePhases.length})</span>
        </button>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Search Bar                                                          */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="px-4 py-2 border-b border-app-border-subtle bg-app-surface shrink-0">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-app-muted" />
          <input
            type="text"
            placeholder="Filter phases, categories, algorithms..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-7 pr-7 py-1 text-xs bg-transparent border-b border-app-border text-app-heading placeholder:text-app-muted focus:outline-none focus:border-app-muted font-mono"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-1 top-1/2 -translate-y-1/2 p-1 text-app-muted hover:text-app-heading cursor-pointer"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Catalog List                                                        */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2 select-text">
        {filteredPhases.length === 0 ? (
          <div className="py-8 text-center text-xs text-app-muted italic">
            {searchQuery ? `No phases match "${searchQuery}".` : "No phases in this category."}
          </div>
        ) : (
          <div className="divide-y divide-app-border-subtle">
            {filteredPhases.map((phase) => {
              const isMandatory = isPhaseMandatory(phase.key);
              const isPostProcessor = isPhasePostProcessor(phase.key);
              const isActive = activePhaseKeys.includes(phase.key);
              const isSelected = selectedPhaseKey === phase.key;
              const paramCount = Object.keys(phase.parameterMeta || {}).length;
              const promptCount = (phase.promptKeys || []).length;

              return (
                <div
                  key={phase.key}
                  className={`py-3 px-2 -mx-2 rounded-md transition-colors ${
                    isSelected
                      ? "bg-app-subtle/80 border-l-2 border-blue-500 pl-2.5"
                      : "hover:bg-app-subtle/40"
                  }`}
                >
                  {/* Top Row: Icon + Title + Status & Toggle */}
                  <div className="flex items-start justify-between gap-2">
                    <div
                      onClick={() => onSelectPhase(phase.key)}
                      className="flex items-start gap-2 min-w-0 cursor-pointer group flex-1"
                    >
                      <div className="mt-0.5">{getPhaseIcon(phase)}</div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span
                            className={`font-semibold text-xs leading-snug group-hover:text-blue-500 transition-colors ${
                              isSelected ? "text-app-heading" : "text-app-heading"
                            }`}
                          >
                            {phase.displayName}
                          </span>
                        </div>

                        {/* Badges Subtitle */}
                        <div className="flex items-center gap-1.5 mt-0.5 flex-wrap text-[10px] font-mono">
                          <span className="text-app-muted">{phase.key}</span>
                          <span className="text-app-muted">·</span>
                          <span
                            className="px-1 py-0.2 rounded border bg-app-subtle text-app-muted border-app-border font-mono text-[10px]"
                          >
                            {isPostProcessor ? "Post-Processor" : phase.category}
                          </span>

                          {isMandatory ? (
                            <span className="inline-flex items-center gap-0.5 px-1 py-0.2 rounded text-[9px] bg-app-subtle text-app-muted border border-app-border font-medium">
                              <Lock className="w-2.5 h-2.5" />
                              <span>Required</span>
                            </span>
                          ) : isActive ? (
                            <span className="inline-flex items-center gap-0.5 px-1 py-0.2 rounded text-[9px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 font-medium">
                              <Check className="w-2.5 h-2.5" />
                              <span>Active</span>
                            </span>
                          ) : (
                            <span className="px-1 py-0.2 rounded text-[9px] bg-app-subtle text-app-muted border border-app-border">
                              Inactive
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Enable / Disable Toggle Switch */}
                    <div className="shrink-0 flex items-center pt-0.5">
                      {isMandatory ? (
                        <span
                          className="text-[10px] font-mono text-app-muted bg-app-subtle px-1.5 py-0.5 rounded border border-app-border cursor-not-allowed select-none"
                          title="Mandatory foundational phase required for pipeline execution"
                        >
                          Fixed
                        </span>
                      ) : (
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={isActive}
                            onChange={(e) => onTogglePhase(phase.key, e.target.checked)}
                            className="sr-only peer"
                          />
                          <div className="w-7 h-4 bg-app-subtle border border-app-border peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-blue-600"></div>
                        </label>
                      )}
                    </div>
                  </div>

                  {/* Description */}
                  <p className="text-[11px] text-app-muted leading-relaxed mt-1.5 line-clamp-2 select-text">
                    {phase.description}
                  </p>

                  {/* Bottom Footer: Stats + Focus Inspector Trigger */}
                  <div className="flex items-center justify-between mt-2 pt-1 border-t border-app-border-subtle text-[10px] font-mono text-app-muted">
                    <div className="flex items-center gap-2">
                      {paramCount > 0 && <span>{paramCount} params</span>}
                      {promptCount > 0 && (
                        <span className="text-app-muted font-medium">
                          {promptCount} {promptCount === 1 ? "prompt" : "prompts"}
                        </span>
                      )}
                    </div>

                    <button
                      onClick={() => onSelectPhase(phase.key)}
                      className={`flex items-center gap-1 hover:text-app-heading transition-colors cursor-pointer ${
                        isSelected ? "text-blue-500 font-medium" : "text-app-muted"
                      }`}
                      title={`Inspect ${phase.displayName} parameters in workbench`}
                    >
                      <span>{isSelected ? "Inspecting" : "Configure"}</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* Register Custom Post-Processor Form                               */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="pt-3 border-t border-app-border">
          {!isCreatingCustom ? (
            <button
              onClick={() => setIsCreatingCustom(true)}
              className="w-full py-2 px-3 rounded-md border border-dashed border-app-border hover:border-blue-500/60 bg-app-bg hover:bg-app-subtle text-app-muted hover:text-blue-500 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Register Custom Post-Processor</span>
            </button>
          ) : (
            <form
              onSubmit={handleCreateCustomProcessor}
              className="p-3 rounded-md border border-app-border bg-app-bg space-y-2.5"
            >
              <div className="flex items-center justify-between pb-1 border-b border-app-border">
                <span className="font-semibold text-xs text-app-heading flex items-center gap-1.5">
                  <SlidersHorizontal className="w-3.5 h-3.5 text-app-muted" />
                  <span>New Post-Processor</span>
                </span>
                <button
                  type="button"
                  onClick={() => setIsCreatingCustom(false)}
                  className="p-0.5 text-app-muted hover:text-app-heading cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {customError && (
                <div className="p-1.5 rounded bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-[10px]">
                  {customError}
                </div>
              )}

              <div className="space-y-1">
                <label className="block text-[10px] font-mono text-app-muted">
                  Identifier Key (snake_case)
                </label>
                <input
                  type="text"
                  value={customKey}
                  onChange={(e) => setCustomKey(e.target.value)}
                  placeholder="e.g. epistemic_coherence"
                  className="w-full h-7 bg-app-surface text-app-heading border border-app-border rounded px-2 font-mono text-xs focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-[10px] font-mono text-app-muted">
                  Display Name
                </label>
                <input
                  type="text"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  placeholder="e.g. Epistemic Coherence Analyzer"
                  className="w-full h-7 bg-app-surface text-app-heading border border-app-border rounded px-2 text-xs focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="block text-[10px] font-mono text-app-muted">
                    Short Label
                  </label>
                  <input
                    type="text"
                    value={customShortLabel}
                    onChange={(e) => setCustomShortLabel(e.target.value)}
                    placeholder="Coherence"
                    className="w-full h-7 bg-app-surface text-app-heading border border-app-border rounded px-2 text-xs focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div className="space-y-1">
                  <label className="block text-[10px] font-mono text-app-muted">
                    Category
                  </label>
                  <input
                    type="text"
                    value={customCategory}
                    onChange={(e) => setCustomCategory(e.target.value)}
                    placeholder="Analysis & Post-Processing"
                    className="w-full h-7 bg-app-surface text-app-heading border border-app-border rounded px-2 text-xs focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-[10px] font-mono text-app-muted">
                  Description
                </label>
                <textarea
                  rows={2}
                  value={customDescription}
                  onChange={(e) => setCustomDescription(e.target.value)}
                  placeholder="Describe analytical purpose and theory backing..."
                  className="w-full bg-app-surface text-app-heading border border-app-border rounded p-1.5 text-xs focus:outline-none focus:border-blue-500 resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setIsCreatingCustom(false)}
                  className="h-7 px-2.5 rounded border border-app-border bg-app-surface hover:bg-app-subtle text-app-muted hover:text-app-heading text-xs cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="h-7 px-3 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium cursor-pointer"
                >
                  Register Processor
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
