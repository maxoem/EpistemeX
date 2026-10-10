import React, {useEffect, useState} from "react";
import {ThemePreference, useThemeStore} from "../store/themeStore";
import {useRunsStore} from "../store/runsStore";
import {useGraphSettingsStore} from "../store/graphSettingsStore";
import {useProjectSettingsStore} from "../store/projectSettingsStore";
import {
    BarChart3,
    Check,
    Cpu,
    Database,
    HardDrive,
    Laptop,
    Moon,
    Network,
    RotateCcw,
    SlidersHorizontal,
    Sun,
    X,
} from "lucide-react";
import {APP_CONFIG} from "@/config/app.ts";

interface StudioSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const StudioSettingsModal: React.FC<StudioSettingsModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<"general" | "graph">("general");
  const { themePreference, setThemePreference, theme } = useThemeStore();
  const { capabilities } = useRunsStore();
  const { settings, updateSettings, resetSettings } = useGraphSettingsStore();
  const {
    advancedVisualizations,
    setAdvancedVisualizations,
    confidenceProgressionInterval,
    setConfidenceProgressionInterval,
  } = useProjectSettingsStore();

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const themeOptions: {
    id: ThemePreference;
    label: string;
    description: string;
    icon: React.ReactNode;
  }[] = [
    {
      id: "dark",
      label: "Dark Mode",
      description: "Deep contrast canvas for focused research",
      icon: <Moon className="w-4 h-4 text-app-muted group-hover:text-app-heading" />,
    },
    {
      id: "light",
      label: "Light Mode",
      description: "Clean paper-like white canvas for daylight use",
      icon: <Sun className="w-4 h-4 text-app-muted group-hover:text-app-heading" />,
    },
    {
      id: "system",
      label: "System",
      description: "Synchronizes with operating system scheme",
      icon: <Laptop className="w-4 h-4 text-app-muted group-hover:text-app-heading" />,
    },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs select-none animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-app-surface border border-app-border rounded-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh] text-xs text-app-text"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-app-border bg-app-surface shrink-0">
          <div className="flex items-center space-x-2">
            <SlidersHorizontal className="w-4 h-4 text-app-heading" />
            <div>
              <h2 className="text-sm font-semibold text-app-heading leading-tight">Studio Preferences</h2>
              <span className="font-mono text-[10px] text-app-muted">Personalize workbench appearance & graph physics</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-app-muted">ESC</span>
            <button
              onClick={onClose}
              className="p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
              title="Close (Esc)"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Tabbed Navigation */}
        <div className="flex border-b border-app-border px-5 bg-app-surface text-xs gap-6 shrink-0">
          <button
            type="button"
            onClick={() => setActiveTab("general")}
            className={`py-2.5 text-xs transition-colors cursor-pointer relative flex items-center gap-1.5 ${
              activeTab === "general"
                ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
                : "text-app-muted hover:text-app-heading"
            }`}
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>General & Subsystems</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("graph")}
            className={`py-2.5 text-xs transition-colors cursor-pointer relative flex items-center gap-1.5 ${
              activeTab === "graph"
                ? "text-app-heading font-medium after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-500"
                : "text-app-muted hover:text-app-heading"
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            <span>Graph Canvas Design</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs select-text">
          {activeTab === "general" ? (
            <>
              {/* Section: Appearance / Theme */}
              <div className="space-y-2">
                <div className="pb-1 border-b border-app-border flex items-center justify-between">
                  <span className="text-xs font-semibold text-app-heading">
                    Appearance & Theme
                  </span>
                  <span className="font-mono text-[10px] text-app-muted">
                    Active: {theme}
                  </span>
                </div>

                <div className="divide-y divide-app-border-subtle">
                  {themeOptions.map((opt) => {
                    const isSelected = themePreference === opt.id;

                    return (
                      <div
                        key={opt.id}
                        onClick={() => setThemePreference(opt.id)}
                        className="py-2.5 flex items-center justify-between hover:bg-app-subtle/40 px-2 -mx-2 rounded-xs cursor-pointer group transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <div className="p-1 text-app-muted group-hover:text-app-heading">
                            {opt.icon}
                          </div>
                          <div>
                            <span className="font-medium text-app-heading text-xs block">
                              {opt.label}
                            </span>
                            <span className="text-[11px] text-app-muted block">
                              {opt.description}
                            </span>
                          </div>
                        </div>

                        {isSelected && (
                          <div className="flex items-center gap-1 text-[11px] font-mono text-blue-600 dark:text-blue-400 font-medium">
                            <Check className="w-3.5 h-3.5" />
                            <span>Active</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Section: Subsystems & Capability Status */}
              <div className="space-y-2 pt-2 border-t border-app-border-subtle">
                <div className="pb-1 border-b border-app-border">
                  <span className="text-xs font-semibold text-app-heading">
                    Connected Subsystems
                  </span>
                </div>

                <div className="divide-y divide-app-border-subtle">
                  {/* Artifacts */}
                  <div className="py-2 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <HardDrive className="w-3.5 h-3.5 text-app-muted" />
                      <div>
                        <span className="font-medium text-app-heading text-xs block">
                          Artifacts Store
                        </span>
                        <span className="text-[10px] text-app-muted font-mono block">
                          Local disk cache & parquet storage
                        </span>
                      </div>
                    </div>
                    <span
                      className={`font-mono text-[10px] font-medium ${
                        capabilities?.artifacts
                          ? "text-emerald-600 dark:text-emerald-400"
                          : "text-rose-600 dark:text-rose-400"
                      }`}
                    >
                      {capabilities?.artifacts ? "Online" : "Offline"}
                    </span>
                  </div>

                  {/* Neo4j */}
                  <div className="py-2 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <Database className="w-3.5 h-3.5 text-app-muted" />
                      <div>
                        <span className="font-medium text-app-heading text-xs block">
                          Neo4j Graph Store
                        </span>
                        <span className="text-[10px] text-app-muted font-mono block">
                          Property graph database backend
                        </span>
                      </div>
                    </div>
                    <span
                      className={`font-mono text-[10px] font-medium ${
                        capabilities?.neo4j
                          ? "text-emerald-600 dark:text-emerald-400"
                          : "text-app-muted"
                      }`}
                    >
                      {capabilities?.neo4j ? "Connected" : "Standby"}
                    </span>
                  </div>

                  {/* Execution Engine */}
                  <div className="py-2 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <Cpu className="w-3.5 h-3.5 text-app-muted" />
                      <div>
                        <span className="font-medium text-app-heading text-xs block">
                          Pipeline Engine
                        </span>
                        <span className="text-[10px] text-app-muted font-mono block">
                          8-phase runner & model router
                        </span>
                      </div>
                    </div>
                    <span
                      className={`font-mono text-[10px] font-medium ${
                        capabilities?.execution !== false
                          ? "text-emerald-600 dark:text-emerald-400"
                          : "text-app-muted"
                      }`}
                    >
                      {capabilities?.execution !== false ? "Ready" : "Standby"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Section: Advanced Visualizations & Progression Replay */}
              <div className="space-y-2">
                <div className="pb-1 border-b border-app-border flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="w-3.5 h-3.5 text-blue-500" />
                    <span className="text-xs font-semibold text-app-heading">
                      Advanced Visualizations & Progression
                    </span>
                  </div>
                  <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-500 border border-blue-500/20">
                    Analytics
                  </span>
                </div>
                <p className="text-[11px] text-app-muted leading-relaxed">
                  Enables progression replayer controls for completed stages and configures data point snapshot granularity.
                </p>

                <div className="p-3 rounded bg-app-bg border border-app-border space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <label className="text-[11px] font-medium text-app-heading block">
                        Advanced Visualizations
                      </label>
                      <span className="text-[10px] text-app-muted block">
                        Enable confidence progression replay scrubber on finished phases
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setAdvancedVisualizations(!advancedVisualizations)}
                      className={`w-9 h-5 flex items-center rounded-full p-0.5 transition-colors cursor-pointer ${
                        advancedVisualizations ? "bg-blue-600 justify-end" : "bg-app-border justify-start"
                      }`}
                      role="switch"
                      aria-checked={advancedVisualizations}
                    >
                      <span className="w-4 h-4 rounded-full bg-white shadow-xs" />
                    </button>
                  </div>

                  <div className="pt-2 border-t border-app-border-subtle flex items-center justify-between gap-3">
                    <div>
                      <label className="text-[11px] font-medium text-app-heading block">
                        Progression Snapshot Interval
                      </label>
                      <span className="text-[10px] text-app-muted block">
                        Sample snapshot every N data points (default: 20)
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <input
                        type="number"
                        min={5}
                        max={200}
                        step={5}
                        value={confidenceProgressionInterval}
                        onChange={(e) => setConfidenceProgressionInterval(Number(e.target.value))}
                        className="w-16 h-7 px-2 text-right rounded bg-app-surface text-app-heading border border-app-border text-xs font-mono focus:outline-none focus:border-blue-500"
                      />
                      <span className="text-xs text-app-muted font-mono">pts</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Section: Workbench Architecture Summary */}
              <div className="py-2 border-l border-app-border pl-3 space-y-1">
                <span className="font-medium text-app-heading text-xs block">
                  Episteme Studio — Theory Graph Workbench
                </span>
                <p className="text-app-muted text-[11px] leading-relaxed">
                  Constructs epistemic theory graphs from scientific literature using argument mining and relation learning. Preferences are persisted locally in browser storage.
                </p>
              </div>
            </>
          ) : (
            <>
              {/* Tab: Graph Canvas Design Header */}
              <div className="flex items-center justify-between pb-1 border-b border-app-border">
                <div>
                  <h3 className="text-xs font-semibold text-app-heading">
                    Graph Layout & Visuals
                  </h3>
                  <p className="text-[11px] text-app-muted">
                    Physics parameters, ontological separation, and relationship edge styling
                  </p>
                </div>
                <button
                  type="button"
                  onClick={resetSettings}
                  className="flex items-center gap-1 text-[11px] font-mono text-app-muted hover:text-app-heading transition-colors cursor-pointer"
                  title="Reset all graph visualization settings to research defaults"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Reset Defaults</span>
                </button>
              </div>

              {/* Group 1: Layout & Distances */}
              <div className="space-y-2">
                <div className="pb-1 border-b border-app-border-subtle">
                  <span className="text-xs font-semibold text-app-heading">
                    1. Force Layout & Edge Distances
                  </span>
                </div>

                <div className="divide-y divide-app-border-subtle font-mono text-[11px]">
                  {/* Link Distance */}
                  <div className="grid grid-cols-12 gap-3 py-2 items-center">
                    <div className="col-span-5 text-right font-sans">
                      <span className="font-medium text-app-heading text-xs block">Link Distance</span>
                      <span className="text-[10px] text-app-muted block">Spring base length</span>
                    </div>
                    <div className="col-span-7 space-y-1">
                      <div className="flex justify-between text-[10px]">
                        <span className="text-app-muted">40px</span>
                        <span className="font-bold text-app-heading tabular-nums">{settings.linkDistance}px</span>
                        <span className="text-app-muted">300px</span>
                      </div>
                      <input
                        type="range"
                        min={40}
                        max={300}
                        step={5}
                        value={settings.linkDistance}
                        onChange={(e) => updateSettings({ linkDistance: Number(e.target.value) })}
                        className="w-full accent-blue-500 cursor-pointer h-1 bg-app-subtle rounded-lg"
                      />
                    </div>
                  </div>

                  {/* Node Repulsion */}
                  <div className="grid grid-cols-12 gap-3 py-2 items-center">
                    <div className="col-span-5 text-right font-sans">
                      <span className="font-medium text-app-heading text-xs block">Repulsion Strength</span>
                      <span className="text-[10px] text-app-muted block">Dispersive force</span>
                    </div>
                    <div className="col-span-7 space-y-1">
                      <div className="flex justify-between text-[10px]">
                        <span className="text-app-muted">-500</span>
                        <span className="font-bold text-app-heading tabular-nums">{settings.nodeRepulsion}</span>
                        <span className="text-app-muted">-30</span>
                      </div>
                      <input
                        type="range"
                        min={-500}
                        max={-30}
                        step={10}
                        value={settings.nodeRepulsion}
                        onChange={(e) => updateSettings({ nodeRepulsion: Number(e.target.value) })}
                        className="w-full accent-blue-500 cursor-pointer h-1 bg-app-subtle rounded-lg"
                      />
                    </div>
                  </div>

                  {/* Hierarchical Rank Separation */}
                  <div className="grid grid-cols-12 gap-3 py-2 items-center">
                    <div className="col-span-5 text-right font-sans">
                      <span className="font-medium text-app-heading text-xs block">Layer Spacing</span>
                      <span className="text-[10px] text-app-muted block">Dagre rank separation</span>
                    </div>
                    <div className="col-span-7 space-y-1">
                      <div className="flex justify-between text-[10px]">
                        <span className="text-app-muted">30px</span>
                        <span className="font-bold text-app-heading tabular-nums">{settings.hierarchicalRankSep}px</span>
                        <span className="text-app-muted">250px</span>
                      </div>
                      <input
                        type="range"
                        min={30}
                        max={250}
                        step={5}
                        value={settings.hierarchicalRankSep}
                        onChange={(e) => updateSettings({ hierarchicalRankSep: Number(e.target.value) })}
                        className="w-full accent-blue-500 cursor-pointer h-1 bg-app-subtle rounded-lg"
                      />
                    </div>
                  </div>

                  {/* Live Physics Animation */}
                  <div className="grid grid-cols-12 gap-3 py-2 items-center">
                    <div className="col-span-5 text-right font-sans">
                      <span className="font-medium text-app-heading text-xs block">Live Animation</span>
                      <span className="text-[10px] text-app-muted block">Interactive tick updates</span>
                    </div>
                    <div className="col-span-7">
                      <input
                        type="checkbox"
                        checked={settings.forceLayoutAnimated}
                        onChange={(e) => updateSettings({ forceLayoutAnimated: e.target.checked })}
                        className="rounded border-app-border text-app-heading focus:ring-blue-500 cursor-pointer"
                      />
                    </div>
                  </div>

                  {/* Force Iterations */}
                  <div className="grid grid-cols-12 gap-3 py-2 items-center">
                    <div className="col-span-5 text-right font-sans">
                      <span className="font-medium text-app-heading text-xs block">Simulation Steps</span>
                      <span className="text-[10px] text-app-muted block">Ticks before settle</span>
                    </div>
                    <div className="col-span-7 space-y-1">
                      <div className="flex justify-between text-[10px]">
                        <span className="text-app-muted">30</span>
                        <span className="font-bold text-app-heading tabular-nums">{settings.forceIterations}</span>
                        <span className="text-app-muted">200</span>
                      </div>
                      <input
                        type="range"
                        min={30}
                        max={200}
                        step={5}
                        value={settings.forceIterations}
                        onChange={(e) => updateSettings({ forceIterations: Number(e.target.value) })}
                        className="w-full accent-blue-500 cursor-pointer h-1 bg-app-subtle rounded-lg"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Group 2: Node Appearance */}
              <div className="space-y-2 pt-2 border-t border-app-border-subtle">
                <div className="pb-1 border-b border-app-border-subtle">
                  <span className="text-xs font-semibold text-app-heading">
                    2. Node Appearance & Typography
                  </span>
                </div>

                <div className="divide-y divide-app-border-subtle font-mono text-[11px]">
                  {/* Node Size Multiplier */}
                  <div className="grid grid-cols-12 gap-3 py-2 items-center">
                    <div className="col-span-5 text-right font-sans">
                      <span className="font-medium text-app-heading text-xs block">Diameter Scale</span>
                      <span className="text-[10px] text-app-muted block">Uniform node scaling</span>
                    </div>
                    <div className="col-span-7 space-y-1">
                      <div className="flex justify-between text-[10px]">
                        <span className="text-app-muted">0.6x</span>
                        <span className="font-bold text-app-heading tabular-nums">{settings.nodeSizeMultiplier.toFixed(1)}x</span>
                        <span className="text-app-muted">2.0x</span>
                      </div>
                      <input
                        type="range"
                        min={0.6}
                        max={2.0}
                        step={0.1}
                        value={settings.nodeSizeMultiplier}
                        onChange={(e) => updateSettings({ nodeSizeMultiplier: Number(e.target.value) })}
                        className="w-full accent-blue-500 cursor-pointer h-1 bg-app-subtle rounded-lg"
                      />
                    </div>
                  </div>

                  {/* Label Max Length */}
                  <div className="grid grid-cols-12 gap-3 py-2 items-center">
                    <div className="col-span-5 text-right font-sans">
                      <span className="font-medium text-app-heading text-xs block">Truncation</span>
                      <span className="text-[10px] text-app-muted block">Max characters</span>
                    </div>
                    <div className="col-span-7 space-y-1">
                      <div className="flex justify-between text-[10px]">
                        <span className="text-app-muted">10</span>
                        <span className="font-bold text-app-heading tabular-nums">{settings.labelMaxLength}</span>
                        <span className="text-app-muted">60</span>
                      </div>
                      <input
                        type="range"
                        min={10}
                        max={60}
                        step={2}
                        value={settings.labelMaxLength}
                        onChange={(e) => updateSettings({ labelMaxLength: Number(e.target.value) })}
                        className="w-full accent-blue-500 cursor-pointer h-1 bg-app-subtle rounded-lg"
                      />
                    </div>
                  </div>

                  {/* Label Font Size */}
                  <div className="grid grid-cols-12 gap-3 py-2 items-center">
                    <div className="col-span-5 text-right font-sans">
                      <span className="font-medium text-app-heading text-xs block">Font Size</span>
                      <span className="text-[10px] text-app-muted block">Node text size</span>
                    </div>
                    <div className="col-span-7 space-y-1">
                      <div className="flex justify-between text-[10px]">
                        <span className="text-app-muted">8px</span>
                        <span className="font-bold text-app-heading tabular-nums">{settings.labelFontSize}px</span>
                        <span className="text-app-muted">16px</span>
                      </div>
                      <input
                        type="range"
                        min={8}
                        max={16}
                        step={1}
                        value={settings.labelFontSize}
                        onChange={(e) => updateSettings({ labelFontSize: Number(e.target.value) })}
                        className="w-full accent-blue-500 cursor-pointer h-1 bg-app-subtle rounded-lg"
                      />
                    </div>
                  </div>

                  {/* Adaptive Label Occlusion */}
                  <div className="grid grid-cols-12 gap-3 py-2 items-center">
                    <div className="col-span-5 text-right font-sans">
                      <span className="font-medium text-app-heading text-xs block">Adaptive Occlusion</span>
                      <span className="text-[10px] text-app-muted block">Hide dense overlaps</span>
                    </div>
                    <div className="col-span-7">
                      <input
                        type="checkbox"
                        checked={settings.autoAdaptLabels}
                        onChange={(e) => updateSettings({ autoAdaptLabels: e.target.checked })}
                        className="rounded border-app-border text-app-heading focus:ring-blue-500 cursor-pointer"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Group 3: Edge Appearance & Labels */}
              <div className="space-y-2 pt-2 border-t border-app-border-subtle">
                <div className="pb-1 border-b border-app-border-subtle">
                  <span className="text-xs font-semibold text-app-heading">
                    3. Relationship & Edge Styling
                  </span>
                </div>

                <div className="divide-y divide-app-border-subtle font-mono text-[11px]">
                  {/* Edge Thickness */}
                  <div className="grid grid-cols-12 gap-3 py-2 items-center">
                    <div className="col-span-5 text-right font-sans">
                      <span className="font-medium text-app-heading text-xs block">Stroke Width</span>
                      <span className="text-[10px] text-app-muted block">Line thickness scale</span>
                    </div>
                    <div className="col-span-7 space-y-1">
                      <div className="flex justify-between text-[10px]">
                        <span className="text-app-muted">0.5x</span>
                        <span className="font-bold text-app-heading tabular-nums">{settings.edgeThicknessMultiplier.toFixed(2)}x</span>
                        <span className="text-app-muted">3.0x</span>
                      </div>
                      <input
                        type="range"
                        min={0.5}
                        max={3.0}
                        step={0.25}
                        value={settings.edgeThicknessMultiplier}
                        onChange={(e) => updateSettings({ edgeThicknessMultiplier: Number(e.target.value) })}
                        className="w-full accent-blue-500 cursor-pointer h-1 bg-app-subtle rounded-lg"
                      />
                    </div>
                  </div>

                  {/* Show Edge Labels */}
                  <div className="grid grid-cols-12 gap-3 py-2 items-center">
                    <div className="col-span-5 text-right font-sans">
                      <span className="font-medium text-app-heading text-xs block">Predicate Labels</span>
                      <span className="text-[10px] text-app-muted block">Display edge types</span>
                    </div>
                    <div className="col-span-7">
                      <input
                        type="checkbox"
                        checked={settings.showEdgeLabels}
                        onChange={(e) => updateSettings({ showEdgeLabels: e.target.checked })}
                        className="rounded border-app-border text-app-heading focus:ring-blue-500 cursor-pointer"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-2.5 border-t border-app-border bg-app-surface flex items-center justify-between text-[11px] text-app-muted shrink-0">
          <span className="font-mono text-[10px]">{APP_CONFIG.version} · Theory Graph Workbench</span>
          <button
            onClick={onClose}
            className="px-3 py-1 rounded bg-app-heading text-app-surface font-medium hover:opacity-90 transition-opacity cursor-pointer text-xs"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
