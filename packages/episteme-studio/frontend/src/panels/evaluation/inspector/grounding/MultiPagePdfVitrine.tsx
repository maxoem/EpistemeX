/**
 * @file MultiPagePdfVitrine.tsx
 * @description Continuous Virtualized Multi-Page Document Stage with High-Acuity SVG Coordinate Overlays.
 *
 * Implements two-tier continuous PDF coordinate projection, bounding quads,
 * and cubic Bézier splines across page breaks for multi-page span arguments.
 *
 * Reference: ISSUE-029 (Multimodal Document Grounding)
 */

import React, { useState, useRef, useEffect, useMemo } from "react";
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  ZoomIn,
  ZoomOut,
  Layers,
  Sparkles,
  Eye,
  EyeOff,
  Navigation,
  FileText,
} from "lucide-react";
import type {
  GroundingEvaluationDetail,
  BoundingBoxCoordinates,
  TextSpanCoordinates,
} from "../../../../api/types";
import {
  computeGlobalBoundingBox,
  computeLocalBoundingBox,
  computeBezierSplineAcrossPages,
  type PageDimension,
} from "./coordinateScaling";

export interface MultiPagePdfVitrineProps {
  activeEvidence: GroundingEvaluationDetail | null;
  selectedPage?: number;
  onPageChange?: (page: number) => void;
  documentTitle?: string;
  startPage?: number;
  totalPages?: number;
  highlightComponentId?: string;
}

const DEFAULT_PAGE_WIDTH = 760;
const DEFAULT_PAGE_HEIGHT = 1040;
const PAGE_GAP = 24;

export const MultiPagePdfVitrine: React.FC<MultiPagePdfVitrineProps> = ({
  activeEvidence,
  selectedPage = 14,
  onPageChange,
  documentTitle = "principia_1687_edition.pdf",
  startPage = 1,
  totalPages = 24,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Viewport states
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);
  const [viewMode, setViewMode] = useState<"continuous" | "single">("continuous");
  const [showPredictedBBox, setShowPredictedBBox] = useState<boolean>(true);
  const [showReferenceBBox, setShowReferenceBBox] = useState<boolean>(true);
  const [showSplines, setShowSplines] = useState<boolean>(true);
  const [currentPage, setCurrentPage] = useState<number>(selectedPage);

  // Sync internal page with props and auto-scroll in continuous mode
  useEffect(() => {
    if (selectedPage) {
      setCurrentPage(selectedPage);
      if (viewMode === "continuous") {
        const timer = setTimeout(() => {
          scrollToPage(selectedPage);
        }, 50);
        return () => clearTimeout(timer);
      }
    }
  }, [selectedPage, viewMode]);

  // Page dimensions scaled by current zoom
  const pageDim = useMemo<PageDimension>(() => {
    return {
      width: Math.round(DEFAULT_PAGE_WIDTH * zoomLevel),
      height: Math.round(DEFAULT_PAGE_HEIGHT * zoomLevel),
    };
  }, [zoomLevel]);

  // Generate multi-page list around the target page
  const pageNumbers = useMemo(() => {
    if (viewMode === "single") {
      return [currentPage];
    }
    const pages: number[] = [];
    const minP = Math.min(startPage, currentPage);
    const maxP = Math.max(totalPages, currentPage);
    for (let p = minP; p <= maxP; p++) {
      pages.push(p);
    }
    return pages;
  }, [viewMode, currentPage, startPage, totalPages]);

  // Scroll smoothly to a target page
  const scrollToPage = (pageNum: number) => {
    const pageEl = pageRefs.current.get(pageNum);
    if (pageEl) {
      pageEl.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  // Center on active bounding box
  const handleCenterOnBBox = () => {
    if (!activeEvidence?.predicted_anchor?.bbox || !containerRef.current) return;
    const bbox = activeEvidence.predicted_anchor.bbox;
    const pageEl = pageRefs.current.get(bbox.page);

    if (pageEl) {
      const pageTop = pageEl.offsetTop;
      const localBoxTop = bbox.y0 * pageDim.height;
      containerRef.current.scrollTo({
        top: Math.max(0, pageTop + localBoxTop - 80),
        behavior: "smooth",
      });
    } else {
      const globalCoords = computeGlobalBoundingBox(bbox, () => pageDim, PAGE_GAP, startPage);
      containerRef.current.scrollTo({
        top: Math.max(0, globalCoords.top_global - 80),
        behavior: "smooth",
      });
    }
  };

  // Active page tracking while scrolling in continuous mode
  useEffect(() => {
    if (viewMode !== "continuous") return;
    const container = containerRef.current;
    if (!container) return;

    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    const handleScroll = () => {
      const containerTop = container.scrollTop;
      let visiblePage = currentPage;
      let minDistance = Infinity;

      pageRefs.current.forEach((el, pageNum) => {
        const pageTop = el.offsetTop;
        const dist = Math.abs(pageTop - containerTop - 40);
        if (dist < minDistance) {
          minDistance = dist;
          visiblePage = pageNum;
        }
      });

      if (visiblePage !== currentPage) {
        setCurrentPage(visiblePage);
        onPageChange?.(visiblePage);
      }
    };

    const onScroll = () => {
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(handleScroll, 80);
    };

    container.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", onScroll);
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [viewMode, currentPage, onPageChange]);

  // Compute active multi-page spans and splines
  const multiPageSpans = useMemo<{
    span1: TextSpanCoordinates;
    span2: TextSpanCoordinates;
  } | null>(() => {
    const pred = activeEvidence?.predicted_anchor;
    if (pred?.spans && pred.spans.length >= 2) {
      return {
        span1: pred.spans[0],
        span2: pred.spans[1],
      };
    }

    // Synthesize continuation span if anchor is on page 14 (or current target) for visual verification
    if (pred?.bbox && pred.bbox.y1 > 0.5) {
      return {
        span1: {
          page: pred.bbox.page,
          bbox: [pred.bbox.x0, pred.bbox.y0, pred.bbox.x1, pred.bbox.y1],
        },
        span2: {
          page: pred.bbox.page + 1,
          bbox: [pred.bbox.x0, 0.04, pred.bbox.x1 * 0.8, 0.22],
          is_continuation: true,
        },
      };
    }

    return null;
  }, [activeEvidence]);

  // Compute Bézier connection if multi-page spans are visible
  const splineConnection = useMemo(() => {
    if (!multiPageSpans || !showSplines) return null;
    const { span1, span2 } = multiPageSpans;

    // Verify both pages are in continuous view
    if (viewMode !== "continuous") return null;

    try {
      return computeBezierSplineAcrossPages(
        span1,
        span2,
        () => pageDim,
        PAGE_GAP,
        startPage
      );
    } catch {
      return null;
    }
  }, [multiPageSpans, showSplines, viewMode, pageDim, startPage]);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-app-bg select-none relative">
      {/* Vitrine Toolbar (44px Fixed) */}
      <div className="h-11 px-4 border-b border-app-border bg-app-surface/95 flex items-center justify-between shrink-0 z-20">
        {/* Left: Document Metadata & Page Stepper */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-app-text font-medium">
            <FileText className="w-4 h-4 text-blue-500" />
            <span className="font-mono truncate max-w-[220px]" title={documentTitle}>
              {documentTitle}
            </span>
          </div>

          <div className="h-4 w-px bg-app-border" />

          {/* Page Indicator & Navigation */}
          <div className="flex items-center gap-1 text-xs">
            <button
              onClick={() => {
                const next = Math.max(startPage, currentPage - 1);
                setCurrentPage(next);
                onPageChange?.(next);
                if (viewMode === "continuous") {
                  scrollToPage(next);
                }
              }}
              disabled={currentPage <= startPage}
              className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle disabled:opacity-40 disabled:hover:bg-transparent"
              title="Previous Page"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>

            <span className="font-mono text-xs tabular-nums text-app-text px-1">
              Page <span className="font-semibold text-blue-600 dark:text-blue-400">{currentPage}</span> of {totalPages}
            </span>

            <button
              onClick={() => {
                const next = Math.min(totalPages, currentPage + 1);
                setCurrentPage(next);
                onPageChange?.(next);
                if (viewMode === "continuous") {
                  scrollToPage(next);
                }
              }}
              disabled={currentPage >= totalPages}
              className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle disabled:opacity-40 disabled:hover:bg-transparent"
              title="Next Page"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Center: Quick Action to center on active BBox */}
        {activeEvidence?.predicted_anchor?.bbox && (
          <button
            onClick={handleCenterOnBBox}
            className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-500/20 border border-blue-500/30 transition-colors"
          >
            <Navigation className="w-3 h-3 text-blue-500" />
            <span>Center Active BBox</span>
          </button>
        )}

        {/* Right: Layer Toggles & Zoom Controls */}
        <div className="flex items-center gap-3 text-xs">
          {/* Layer Visibility Toggles */}
          <div className="flex items-center gap-1 bg-app-bg p-0.5 rounded border border-app-border/60">
            <button
              onClick={() => setShowPredictedBBox(!showPredictedBBox)}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors cursor-pointer ${
                showPredictedBBox
                  ? "bg-blue-600 text-white font-semibold"
                  : "text-app-muted hover:text-app-text"
              }`}
              title="Toggle Predicted Bounding Box"
            >
              Predicted
            </button>
            <button
              onClick={() => setShowReferenceBBox(!showReferenceBBox)}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors cursor-pointer ${
                showReferenceBBox
                  ? "bg-emerald-600 text-white font-semibold"
                  : "text-app-muted hover:text-app-text"
              }`}
              title="Toggle Gold Reference Bounding Box"
            >
              Gold Ref
            </button>
            <button
              onClick={() => setShowSplines(!showSplines)}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors cursor-pointer ${
                showSplines
                  ? "bg-amber-600 text-white font-semibold"
                  : "text-app-muted hover:text-app-text"
              }`}
              title="Toggle Multi-Page Spline Connectors"
            >
              Splines
            </button>
          </div>

          <div className="h-4 w-px bg-app-border" />

          {/* View Mode Toggle */}
          <div className="flex items-center gap-1 bg-app-bg p-0.5 rounded border border-app-border/60 text-[10px]">
            <button
              onClick={() => {
                setViewMode("continuous");
                setTimeout(() => scrollToPage(currentPage), 50);
              }}
              className={`px-2 py-0.5 rounded font-medium transition-colors cursor-pointer ${
                viewMode === "continuous"
                  ? "bg-app-surface text-app-heading font-semibold border border-app-border/80"
                  : "text-app-muted hover:text-app-text"
              }`}
            >
              Continuous
            </button>
            <button
              onClick={() => setViewMode("single")}
              className={`px-2 py-0.5 rounded font-medium transition-colors cursor-pointer ${
                viewMode === "single"
                  ? "bg-app-surface text-app-heading font-semibold border border-app-border/80"
                  : "text-app-muted hover:text-app-text"
              }`}
            >
              Single
            </button>
          </div>

          <div className="h-4 w-px bg-app-border" />

          {/* Zoom Controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setZoomLevel((z) => Math.max(0.6, Math.round((z - 0.15) * 100) / 100))}
              disabled={zoomLevel <= 0.6}
              className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle disabled:opacity-40"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>

            <span className="font-mono text-xs tabular-nums text-app-text min-w-[38px] text-center">
              {Math.round(zoomLevel * 100)}%
            </span>

            <button
              onClick={() => setZoomLevel((z) => Math.min(1.6, Math.round((z + 0.15) * 100) / 100))}
              disabled={zoomLevel >= 1.6}
              className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle disabled:opacity-40"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={() => setZoomLevel(1.0)}
              className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle ml-0.5"
              title="Reset Zoom (100%)"
            >
              <Maximize2 className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Continuous Document Container */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto p-8 flex justify-center relative bg-app-bg"
        style={{ scrollBehavior: "smooth" }}
      >
        {/* Continuous Page Column with exact page width and relative positioning */}
        <div
          className="relative flex flex-col items-center"
          style={{
            width: `${pageDim.width}px`,
            gap: `${PAGE_GAP}px`,
          }}
        >
          {/* Global Spline Overlay Layer (Continuous Bézier curves connecting page cards) */}
          {splineConnection && (
            <svg
              className="absolute top-0 left-0 pointer-events-none z-20"
              style={{
                width: `${pageDim.width}px`,
                height: `${pageNumbers.length * pageDim.height + Math.max(0, pageNumbers.length - 1) * PAGE_GAP}px`,
              }}
            >
              <defs>
                <linearGradient id="splineGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.8" />
                  <stop offset="50%" stopColor="#F59E0B" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="#10B981" stopOpacity="0.8" />
                </linearGradient>
                <filter id="splineGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* Glowing cubic Bézier curve */}
              <path
                d={splineConnection.pathData}
                fill="none"
                stroke="url(#splineGradient)"
                strokeWidth={3}
                strokeDasharray="6 4"
                filter="url(#splineGlow)"
                className="animate-pulse"
              />

              {/* Anchor exit and entry markers */}
              <circle
                cx={splineConnection.sourcePoint.x}
                cy={splineConnection.sourcePoint.y}
                r={4}
                fill="#3B82F6"
                stroke="#ffffff"
                strokeWidth={1.5}
              />
              <circle
                cx={splineConnection.targetPoint.x}
                cy={splineConnection.targetPoint.y}
                r={4}
                fill="#10B981"
                stroke="#ffffff"
                strokeWidth={1.5}
              />
            </svg>
          )}

          {/* Page Cards Rendering */}
          {pageNumbers.map((pageNum) => {
            const isTargetPage =
              activeEvidence?.predicted_anchor?.bbox?.page === pageNum ||
              activeEvidence?.reference_anchor?.bbox?.page === pageNum;
            const isContinuationPage =
              multiPageSpans?.span2?.page === pageNum;

            // Local page boxes
            const predLocal =
              showPredictedBBox &&
              activeEvidence?.predicted_anchor?.bbox?.page === pageNum
                ? computeLocalBoundingBox(activeEvidence.predicted_anchor.bbox, pageDim)
                : null;

            const refLocal =
              showReferenceBBox &&
              activeEvidence?.reference_anchor?.bbox?.page === pageNum
                ? computeLocalBoundingBox(activeEvidence.reference_anchor.bbox, pageDim)
                : null;

            // Continuation span on next page
            const continuationLocal =
              showSplines &&
              multiPageSpans &&
              multiPageSpans.span2.page === pageNum
                ? computeLocalBoundingBox(
                    {
                      page: pageNum,
                      x0: multiPageSpans.span2.bbox[0],
                      y0: multiPageSpans.span2.bbox[1],
                      x1: multiPageSpans.span2.bbox[2],
                      y1: multiPageSpans.span2.bbox[3],
                    },
                    pageDim
                  )
                : null;

            const docUpper = documentTitle.replace(/\.(pdf|md)$/i, "").toUpperCase().replace(/_/g, " ");

            return (
              <div
                key={pageNum}
                ref={(el) => {
                  if (el) pageRefs.current.set(pageNum, el);
                  else pageRefs.current.delete(pageNum);
                }}
                className={`relative bg-white dark:bg-[#151518] border rounded transition-colors duration-200 shadow-sm ${
                  isTargetPage
                    ? "border-blue-500 ring-1 ring-blue-500/20"
                    : "border-app-border/80"
                }`}
                style={{
                  width: `${pageDim.width}px`,
                  height: `${pageDim.height}px`,
                  minWidth: `${pageDim.width}px`,
                  minHeight: `${pageDim.height}px`,
                }}
              >
                {/* Page Physical Header */}
                <div className="absolute top-0 left-0 right-0 h-9 px-6 flex items-center justify-between border-b border-app-border/40 text-[10px] text-app-muted select-none">
                  <span className="font-serif italic tracking-wide truncate max-w-[420px]">
                    {docUpper}
                  </span>
                  <span className="font-mono tabular-nums font-medium shrink-0">Page {pageNum}</span>
                </div>

                {/* Simulated Academic Typesetting Layout */}
                <div
                  className="w-full h-full pt-12 pb-10 px-10 flex flex-col justify-between text-app-text select-text"
                  style={{ fontSize: `${Math.round(11 * zoomLevel)}px` }}
                >
                  {/* Academic Content Texture */}
                  <div className="space-y-4 text-justify font-serif leading-relaxed text-zinc-800 dark:text-zinc-200">
                    {isTargetPage ? (
                      <>
                        <div className="text-center font-bold tracking-wider uppercase text-sm mb-4 text-app-heading">
                          {activeEvidence?.label || `Construct Grounding · Page ${pageNum}`}
                        </div>

                        <p className="indent-4">
                          In evaluating the theoretical framework and foundational propositions grounded within this primary source document, the formal assertion under consideration specifies explicit empirical or mathematical constraints:
                        </p>

                        <div className="p-3 my-2 rounded bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800 font-sans">
                          <div className="font-semibold text-xs text-blue-600 dark:text-blue-400 mb-1">
                            {activeEvidence?.component_type?.toUpperCase() || "CONSTRUCT"} PROPOSITION
                          </div>
                          <p className="font-serif italic leading-relaxed text-[11px] text-app-text">
                            "{activeEvidence?.predicted_anchor?.verbatim_text ||
                              activeEvidence?.reference_anchor?.verbatim_text ||
                              "Mutationem motus proportionalem esse vi motrici impressae, & fieri secundum lineam rectam qua vis illa imprimitur."}"
                          </p>
                          {activeEvidence?.predicted_anchor?.formula_latex && (
                            <div className="mt-2 text-center font-mono text-sm py-1 bg-white dark:bg-black/40 rounded border border-zinc-200 dark:border-zinc-800 text-blue-600 dark:text-blue-400 select-all overflow-x-auto">
                              {activeEvidence.predicted_anchor.formula_latex}
                            </div>
                          )}
                        </div>

                        <p className="indent-4">
                          The empirical and mathematical consistency of this formulation is corroborated by direct derivation from the underlying model postulates, fulfilling the structuralist requirement of empirical tenability across the designated domain of intended applications.
                        </p>
                      </>
                    ) : isContinuationPage ? (
                      <>
                        <div className="text-center font-bold tracking-wider uppercase text-sm mb-4 text-app-heading">
                          {docUpper} (CONTINUATIO)
                        </div>

                        <div className="p-2 mb-3 rounded bg-amber-500/5 border border-amber-500/20 text-[10px] font-mono text-amber-600 dark:text-amber-400">
                          [Multi-Page Argument Continuation from Page {activeEvidence?.predicted_anchor?.bbox?.page || pageNum - 1}]
                        </div>

                        <p className="indent-4">
                          ...quod quidem ex secunda lege sponte fluit: nam quantitas motus oritur ex velocitate & materia conjunctim; & vis motrix impressa ex motu genito & tempore simul sumptis.
                        </p>

                        <p className="indent-4">
                          Actioni contrariam semper & aequalem esse reactionem: sive corporum duorum actiones in se mutuo semper esse aequales & in partes contrarias dirigi. Quicquid premit vel trahit alterum, tantundem ab eo premitur vel trahitur.
                        </p>
                      </>
                    ) : (
                      <>
                        <div className="font-semibold text-xs tracking-wider text-zinc-600 dark:text-zinc-400 mb-2">
                          SECTIO {pageNum} · PROPOSITIO {pageNum * 2 - 1}
                        </div>
                        <p className="indent-4">
                          Quantitas materiae est mensura ejusdem orta ex illius densitate & magnitudine conjunctim. Aer densitate duplicata, in spatio etiam duplicato, fit quadruplus; in triplicato sextuplus. Idem intellige de nive & pulveribus per compressionem vel liquefactionem condensatis.
                        </p>
                        <p className="indent-4">
                          Hanc quantitatem per corporis cujusque pondus innotescere comperi per experimenta pendulorum accuratissime instituta, ut posthac dicetur.
                        </p>
                        <p className="indent-4">
                          Quantitas motus est mensura ejusdem orta ex velocitate et quantitate materiae conjunctim. Motus totius est summa motuum in partibus singulis; ideoque in corpore duplo majore, & aequali cum velocitate, duplus est, & cum velocitate dupla quadruplus.
                        </p>
                      </>
                    )}
                  </div>

                  {/* Academic Page Footer */}
                  <div className="pt-4 border-t border-app-border/40 flex items-center justify-between text-[10px] text-app-muted font-mono">
                    <span className="truncate max-w-[320px]">{docUpper}</span>
                    <span>[§ {pageNum * 4}]</span>
                  </div>
                </div>

                {/* Tier 2: Page-Local SVG Viewport Layer */}
                <svg
                  className="absolute inset-0 w-full h-full pointer-events-none z-10"
                  style={{ width: `${pageDim.width}px`, height: `${pageDim.height}px` }}
                >
                  {/* Predicted Bounding Quad */}
                  {predLocal && (
                    <g>
                      <rect
                        x={predLocal.x}
                        y={predLocal.y}
                        width={predLocal.width}
                        height={predLocal.height}
                        fill="rgba(59, 130, 246, 0.08)"
                        stroke="#3B82F6"
                        strokeWidth={2}
                        rx={3}
                        className="transition-all duration-150"
                      />
                      {/* Top-Right Label Badge */}
                      <foreignObject
                        x={predLocal.x}
                        y={Math.max(0, predLocal.y - 20)}
                        width={Math.max(160, predLocal.width)}
                        height={20}
                      >
                        <div className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-t text-[9px] font-mono font-semibold bg-blue-600 text-white">
                          <Sparkles className="w-2.5 h-2.5" />
                          <span>PREDICTED ANCHOR</span>
                          {activeEvidence && (
                            <span className="opacity-80 ml-0.5">
                              (IoU: {activeEvidence.iou_score.toFixed(3)})
                            </span>
                          )}
                        </div>
                      </foreignObject>
                    </g>
                  )}

                  {/* Gold Reference Bounding Quad */}
                  {refLocal && (
                    <g>
                      <rect
                        x={refLocal.x}
                        y={refLocal.y}
                        width={refLocal.width}
                        height={refLocal.height}
                        fill="rgba(16, 185, 129, 0.06)"
                        stroke="#10B981"
                        strokeWidth={2}
                        strokeDasharray="5 3"
                        rx={3}
                      />
                      {/* Bottom-Right Label Badge */}
                      <foreignObject
                        x={refLocal.x}
                        y={refLocal.y + refLocal.height + 2}
                        width={Math.max(140, refLocal.width)}
                        height={20}
                      >
                        <div className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-b text-[9px] font-mono font-semibold bg-emerald-600 text-white">
                          <BookOpen className="w-2.5 h-2.5" />
                          <span>GOLD REFERENCE</span>
                        </div>
                      </foreignObject>
                    </g>
                  )}

                  {/* Continuation Span Quad */}
                  {continuationLocal && (
                    <g>
                      <rect
                        x={continuationLocal.x}
                        y={continuationLocal.y}
                        width={continuationLocal.width}
                        height={continuationLocal.height}
                        fill="rgba(245, 158, 11, 0.08)"
                        stroke="#F59E0B"
                        strokeWidth={2}
                        strokeDasharray="4 2"
                        rx={3}
                      />
                      <foreignObject
                        x={continuationLocal.x}
                        y={Math.max(0, continuationLocal.y - 18)}
                        width={160}
                        height={18}
                      >
                        <div className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px] font-mono font-semibold bg-amber-600 text-white">
                          <span>CONTINUATION SPAN</span>
                        </div>
                      </foreignObject>
                    </g>
                  )}
                </svg>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
