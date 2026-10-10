import React, {useEffect, useRef, useState} from "react";
import {
    Activity,
    ChevronDown,
    Eye,
    EyeOff,
    Layers,
    Loader2,
    Maximize2,
    RefreshCw,
    RotateCcw,
    Sliders,
    X,
    ZoomIn,
    ZoomOut,
} from "lucide-react";
import {Overlay} from "../api/types";
import {useViewOverlayStore} from "../store/viewOverlayStore";

export type LayoutType = "d3-force" | "concentric" | "radial" | "circular" | "grid" | "antv-dagre";

export interface GraphCanvasHudProps {
  // Layout
  layoutType: LayoutType;
  onLayoutChange: (layout: LayoutType) => void;
  // Viewport
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitView: () => void;
  onFitCenter: () => void;
  onRefresh?: () => void;
  isLoading?: boolean;
  isExpanding?: boolean;
  // Layers
  showL1: boolean;
  showL2: boolean;
  showL3: boolean;
  layerCounts?: Record<number, number>;
  onToggleL1: () => void;
  onToggleL2: () => void;
  onToggleL3: () => void;
  onResetLayers?: () => void;
  onShowAllLayers?: () => void;
  // Overlays
  runId?: string | null;
  graphVersion?: string;
  activeOverlay: Overlay | null;
  onOverlayChange: (overlay: Overlay | null) => void;
  onNavigateToCypher?: () => void;
  nodeTypesInGraph?: string[];
  edgeTypesInGraph?: string[];
  // Views & Overlays Drawer
  isViewOverlayDrawerOpen?: boolean;
  onToggleViewOverlayDrawer?: () => void;
  // Metrics
  isMetricsDrawerOpen: boolean;
  activeMetricResult: any;
  activeMetricInstancesCount?: number;
  onToggleMetricsDrawer: () => void;
  onClearMetric: () => void;
}

export const GraphCanvasHud: React.FC<GraphCanvasHudProps> = ({
  layoutType,
  onLayoutChange,
  onZoomIn,
  onZoomOut,
  onFitView,
  onFitCenter,
  onRefresh,
  isLoading = false,
  isExpanding = false,
  showL1,
  showL2,
  showL3,
  layerCounts,
  onToggleL1,
  onToggleL2,
  onToggleL3,
  onResetLayers,
  onShowAllLayers,
  runId,
  graphVersion,
  activeOverlay,
  onOverlayChange,
  onNavigateToCypher,
  nodeTypesInGraph = [],
  edgeTypesInGraph = [],
  isViewOverlayDrawerOpen,
  onToggleViewOverlayDrawer,
  isMetricsDrawerOpen,
  activeMetricResult,
  activeMetricInstancesCount = 0,
  onToggleMetricsDrawer,
  onClearMetric,
}) => {

  const {
    activeMask,
    activeOverlay: storeOverlay,
    isDrawerOpen: storeDrawerOpen,
    toggleDrawer,
    clearOverlay,
  } = useViewOverlayStore();

  const [isLayersOpen, setIsLayersOpen] = useState(false);
  const layersRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (layersRef.current && !layersRef.current.contains(e.target as Node)) {
        setIsLayersOpen(false);
      }
    };
    if (isLayersOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isLayersOpen]);

  const activeLayerCount = [showL1, showL2, showL3].filter(Boolean).length;

  return (
    <aside
      aria-label="Graph Viewport and Controls HUD"
      className="absolute top-3 left-3 z-20 flex items-center bg-app-surface/90 backdrop-blur-md border border-app-border rounded-lg p-1 shadow-md text-xs select-none space-x-1.5 max-w-[calc(100%-24px)] flex-wrap gap-y-1"
    >
      {/* Layout Selector */}
      <div className="flex items-center gap-1 pl-1.5 pr-1 py-0.5 text-app-muted">
        <Sliders className="w-3.5 h-3.5 shrink-0 text-app-muted" />
        <select
          value={layoutType}
          onChange={(e) => onLayoutChange(e.target.value as LayoutType)}
          className="bg-transparent border-none text-xs text-app-heading focus:outline-none cursor-pointer pr-1"
          title="Select Graph Layout Algorithm"
          aria-label="Select Graph Layout Algorithm"
        >
          <option value="d3-force" className="bg-app-surface text-app-heading">Force-Directed</option>
          <option value="concentric" className="bg-app-surface text-app-heading">Concentric</option>
          <option value="radial" className="bg-app-surface text-app-heading">Radial</option>
          <option value="circular" className="bg-app-surface text-app-heading">Circular</option>
          <option value="grid" className="bg-app-surface text-app-heading">Grid</option>
          <option value="antv-dagre" className="bg-app-surface text-app-heading">Dagre (Hierarchical)</option>
        </select>
      </div>

      <div className="h-3.5 w-px bg-app-border shrink-0" />

      {/* Viewport Zoom / Pan & Refresh Controls */}
      <div className="flex items-center space-x-0.5 shrink-0">
        <button
          onClick={onZoomIn}
          className="p-1 text-app-muted hover:text-app-heading hover:bg-app-subtle rounded transition-colors cursor-pointer"
          title="Zoom In"
          aria-label="Zoom In"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={onZoomOut}
          className="p-1 text-app-muted hover:text-app-heading hover:bg-app-subtle rounded transition-colors cursor-pointer"
          title="Zoom Out"
          aria-label="Zoom Out"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={onFitView}
          className="p-1 text-app-muted hover:text-app-heading hover:bg-app-subtle rounded transition-colors cursor-pointer"
          title="Fit Graph to Screen"
          aria-label="Fit Graph to Screen"
        >
          <Maximize2 className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={onFitCenter}
          className="p-1 text-app-muted hover:text-app-heading hover:bg-app-subtle rounded transition-colors cursor-pointer"
          title="Recenter View"
          aria-label="Recenter View"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isLoading || isExpanding}
            className="p-1 text-app-muted hover:text-app-heading hover:bg-app-subtle rounded transition-colors cursor-pointer"
            title="Refresh Graph"
            aria-label="Refresh Graph"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin text-cyan-400" : ""}`} />
          </button>
        )}
        {isExpanding && (
          <span className="flex items-center gap-1 pl-1 text-[10px] text-app-muted font-mono">
            <Loader2 className="w-3 h-3 animate-spin text-app-muted" />
            <span>Expanding...</span>
          </span>
        )}
      </div>

      <div className="h-3.5 w-px bg-app-border shrink-0" />

      {/* Layer Visibility Dropdown */}
      <div className="relative shrink-0" ref={layersRef}>
        <button
          onClick={() => setIsLayersOpen(!isLayersOpen)}
          className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors cursor-pointer ${
            isLayersOpen
              ? "bg-app-subtle text-app-heading font-medium"
              : "text-app-muted hover:text-app-heading hover:bg-app-subtle"
          }`}
          title="Filter Graph Ontological Layers"
        >
          <Layers className="w-3.5 h-3.5 text-app-muted shrink-0" />
          <span>Layers ({activeLayerCount}/3)</span>
          <ChevronDown className={`w-3 h-3 opacity-60 transition-transform ${isLayersOpen ? "rotate-180" : ""}`} />
        </button>

        {isLayersOpen && (
          <div className="absolute top-full mt-1.5 left-0 w-56 p-2 bg-app-surface border border-app-border rounded-lg shadow-2xl z-50 text-xs select-none space-y-1">
            <div className="font-semibold text-app-heading text-[10px] uppercase tracking-wider px-1.5 py-0.5 border-b border-app-border-subtle mb-1 flex items-center justify-between">
              <span>Ontological Layers</span>
              <span className="text-app-muted font-mono">{activeLayerCount} active</span>
            </div>

            {/* L1 Chunks */}
            <button
              onClick={onToggleL1}
              className={`w-full flex items-center justify-between px-2 py-1 rounded transition-colors cursor-pointer text-left ${
                showL1 ? "bg-app-subtle text-app-heading" : "text-app-muted hover:bg-app-subtle"
              }`}
            >
              <div className="flex items-center gap-2 truncate">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500 shrink-0" />
                <span className="truncate">L1 Chunks & Evidence</span>
              </div>
              <div className="flex items-center gap-1.5 font-mono text-[10px] shrink-0 text-app-muted">
                <span>({layerCounts?.[1] || 0})</span>
                {showL1 ? <Eye className="w-3.5 h-3.5 text-app-heading" /> : <EyeOff className="w-3.5 h-3.5 opacity-40" />}
              </div>
            </button>

            {/* L2 Entities */}
            <button
              onClick={onToggleL2}
              className={`w-full flex items-center justify-between px-2 py-1 rounded transition-colors cursor-pointer text-left ${
                showL2 ? "bg-app-subtle text-app-heading" : "text-app-muted hover:bg-app-subtle"
              }`}
            >
              <div className="flex items-center gap-2 truncate">
                <span className="w-2.5 h-2.5 rounded-full bg-purple-500 shrink-0" />
                <span className="truncate">L2 Entities & Relations</span>
              </div>
              <div className="flex items-center gap-1.5 font-mono text-[10px] shrink-0 text-app-muted">
                <span>({layerCounts?.[2] || 0})</span>
                {showL2 ? <Eye className="w-3.5 h-3.5 text-app-heading" /> : <EyeOff className="w-3.5 h-3.5 opacity-40" />}
              </div>
            </button>

            {/* L3 TheoryNet */}
            <button
              onClick={onToggleL3}
              className={`w-full flex items-center justify-between px-2 py-1 rounded transition-colors cursor-pointer text-left ${
                showL3 ? "bg-app-subtle text-app-heading" : "text-app-muted hover:bg-app-subtle"
              }`}
            >
              <div className="flex items-center gap-2 truncate">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />
                <span className="truncate">L3 TheoryNet Atoms</span>
              </div>
              <div className="flex items-center gap-1.5 font-mono text-[10px] shrink-0 text-app-muted">
                <span>({layerCounts?.[3] || 0})</span>
                {showL3 ? <Eye className="w-3.5 h-3.5 text-app-heading" /> : <EyeOff className="w-3.5 h-3.5 opacity-40" />}
              </div>
            </button>

            {/* Quick Actions Footer */}
            <div className="pt-1.5 mt-1 border-t border-app-border-subtle flex items-center justify-between px-1 text-[10px]">
              <button
                onClick={() => {
                  if (onResetLayers) onResetLayers();
                }}
                className="text-app-muted hover:text-app-heading cursor-pointer"
              >
                Reset (L2+L3)
              </button>
              <button
                onClick={() => {
                  if (onShowAllLayers) onShowAllLayers();
                }}
                className="text-app-heading hover:underline font-medium cursor-pointer"
              >
                Show All
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="h-3.5 w-px bg-app-border shrink-0" />

      {/* Views, Lenses & Overlays Drawer Trigger Button */}
      <div className="flex items-center space-x-1 shrink-0">
        <button
          onClick={() => {
            if (onToggleViewOverlayDrawer) {
              onToggleViewOverlayDrawer();
            } else {
              toggleDrawer();
            }
          }}
          className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors cursor-pointer ${
            isViewOverlayDrawerOpen || storeDrawerOpen || (activeOverlay || storeOverlay) || (activeMask.lensId && activeMask.lensId !== "all")
              ? "bg-app-subtle text-app-heading font-medium border border-app-border"
              : "text-app-muted hover:text-app-heading hover:bg-app-subtle"
          }`}
          title="Open Views, Lenses & Overlays Drawer"
        >
          <Sliders className="w-3.5 h-3.5 text-app-muted shrink-0" />
          <span>
            {activeMask.lensId && activeMask.lensId !== "all"
              ? activeMask.lensId.startsWith("theory_")
                ? `Lens: ${activeMask.lensId.replace("theory_", "").replace(/[_-]/g, " ")}`
                : `Lens: ${activeMask.lensId.replace(/[_-]/g, " ")}`
              : (activeOverlay || storeOverlay)
              ? `Overlay: ${(activeOverlay || storeOverlay)?.kind}`
              : "Views & Overlays"}
          </span>
          {(activeOverlay || storeOverlay) && (
            <span className="w-1.5 h-1.5 rounded-full bg-app-muted shrink-0" />
          )}
        </button>

        {(activeOverlay || storeOverlay) && (
          <button
            onClick={() => {
              clearOverlay();
              onOverlayChange(null);
            }}
            className="p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
            title="Clear active overlay"
          >
            <X className="w-3 h-3" />
          </button>
        )}
      </div>

      <div className="h-3.5 w-px bg-app-border shrink-0" />

      {/* Graph Metrics Trigger & Active Overlay Pill */}
      <div className="flex items-center space-x-1 shrink-0">
        <button
          onClick={onToggleMetricsDrawer}
          className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors cursor-pointer ${
            isMetricsDrawerOpen || activeMetricResult || activeMetricInstancesCount > 0
              ? "bg-app-subtle text-app-heading font-medium border border-app-border"
              : "text-app-muted hover:text-app-heading hover:bg-app-subtle"
          }`}
          title="Open Graph Analysis & Stackable Algorithms"
        >
          <Activity className="w-3.5 h-3.5 text-app-muted shrink-0" />
          <span>
            {activeMetricInstancesCount > 0
              ? `Algorithms (${activeMetricInstancesCount})`
              : activeMetricResult
              ? activeMetricResult.metric_id
              : "Algorithms"}
          </span>
          {(activeMetricResult || activeMetricInstancesCount > 0) && (
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 shrink-0" />
          )}
        </button>

        {activeMetricResult && (
          <button
            onClick={onClearMetric}
            className="p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
            title="Clear active metric results"
          >
            <X className="w-3 h-3" />
          </button>
        )}
      </div>

      <div className="h-3.5 w-px bg-app-border shrink-0" />
    </aside>
  );
};
