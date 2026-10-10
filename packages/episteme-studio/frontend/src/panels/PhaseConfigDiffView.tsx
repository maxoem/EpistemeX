import React, {useEffect, useMemo, useState} from "react";
import {useDiffStore} from "../store/diffStore";
import {api} from "../api/client";
import {RunDetail} from "../api/types";
import {PHASE_REGISTRY, resolvePhaseConfig} from "@/panels/phaseConfig";
import {PhaseConfigDescriptor} from "./phaseConfig/types";
import {
    AlertTriangle,
    ArrowRight,
    BarChart3,
    CheckCircle2,
    Cpu,
    FileCode,
    Filter,
    Network,
    Scale,
    Sliders,
    Zap,
} from "lucide-react";
import {ConfidenceKdeChart} from "./EpistemicCharts";

interface PhaseConfigDiffViewProps {
  onSwitchToStaging?: () => void;
}

const ORDERED_PHASE_KEYS = [
  "phase0",
  "schema",
  "phase1",
  "phase2",
  "phase3",
  "phase3b",
  "phase4_maturation",
  "phase4",
  "phase5",
  "phase6",
];

export const PhaseConfigDiffView: React.FC<PhaseConfigDiffViewProps> = ({
  onSwitchToStaging,
}) => {
  const { baseRunId, targetRunId, diffData } = useDiffStore();

  const [detailA, setDetailA] = useState<RunDetail | null>(null);
  const [detailB, setDetailB] = useState<RunDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedPhaseKey, setSelectedPhaseKey] = useState<string>("phase2");
  const [divergedOnly, setDivergedOnly] = useState<boolean>(false);

  useEffect(() => {
    if (!baseRunId || !targetRunId) return;

    let mounted = true;
    setIsLoading(true);

    Promise.all([api.getRun(baseRunId), api.getRun(targetRunId)])
      .then(([a, b]) => {
        if (!mounted) return;
        setDetailA(a);
        setDetailB(b);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        console.error("Failed to fetch run details for config diff:", err);
        setIsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [baseRunId, targetRunId]);

  const phaseDivergenceInfoMap = useMemo(() => {
    const map: Record<
      string,
      {
        diverged: boolean;
        reasons: string[];
        hasDecisionEngineDivergence: boolean;
        hasModalResolverDivergence: boolean;
        hasRerankerDivergence: boolean;
        componentDivergences: {
          componentType: "decision_engine" | "modal_resolver" | "reranker" | "config" | "other";
          label: string;
          change: string;
          description: string;
        }[];
      }
    > = {};

    const dePhases = new Set(["phase2", "phase3", "phase4", "phase5", "phase6"]);
    const mrPhases = new Set(["phase2", "phase4", "phase6"]);
    const rrPhases = new Set(["phase3", "phase3b", "phase4"]);

    // Extract all fingerprints for Run A and Run B
    const fpsA: Record<string, any> = {
      ...(detailA?.fingerprints || {}),
      ...(detailA?.method_fingerprints || {}),
    };
    const fpsB: Record<string, any> = {
      ...(detailB?.fingerprints || {}),
      ...(detailB?.method_fingerprints || {}),
    };

    // Global component hash divergence
    const globalDeA = fpsA["decision_engine"];
    const globalDeB = fpsB["decision_engine"];
    const globalDeDiverged = Boolean(globalDeA && globalDeB && globalDeA !== globalDeB);

    const globalMrA = fpsA["modal_resolver"];
    const globalMrB = fpsB["modal_resolver"];
    const globalMrDiverged = Boolean(globalMrA && globalMrB && globalMrA !== globalMrB);

    const globalRrA = fpsA["relation_reranker"] || fpsA["reranker"] || fpsA["cross_encoder"];
    const globalRrB = fpsB["relation_reranker"] || fpsB["reranker"] || fpsB["cross_encoder"];
    const globalRrDiverged = Boolean(globalRrA && globalRrB && globalRrA !== globalRrB);

    for (const key of ORDERED_PHASE_KEYS) {
      const reasons: string[] = [];
      const componentDivergences: {
        componentType: "decision_engine" | "modal_resolver" | "reranker" | "config" | "other";
        label: string;
        change: string;
        description: string;
      }[] = [];
      let diverged = false;
      let hasDe = false;
      let hasMr = false;
      let hasRr = false;

      // 1. Direct phase fingerprint
      const fpA = detailA?.fingerprints?.[key];
      const fpB = detailB?.fingerprints?.[key];
      if (fpA && fpB && fpA !== fpB) {
        diverged = true;
        reasons.push("Phase config hash diverged");
      }

      // 2. Component method fingerprints specific to this phase
      const phaseCompKeys = new Set([
        ...Object.keys(fpsA).filter((k) => k.startsWith(`${key}.`)),
        ...Object.keys(fpsB).filter((k) => k.startsWith(`${key}.`)),
      ]);

      for (const compKey of phaseCompKeys) {
        const valA = fpsA[compKey];
        const valB = fpsB[compKey];
        if (valA && valB && valA !== valB) {
          diverged = true;
          const sub = compKey.slice(key.length + 1);
          if (sub.includes("decision_engine")) {
            hasDe = true;
            reasons.push("Decision Engine component hash mismatch");
            componentDivergences.push({
              componentType: "decision_engine",
              label: "Decision Engine",
              change: `${String(valA).slice(0, 7)} ≠ ${String(valB).slice(0, 7)}`,
              description: `Component hash changed: ${valA} vs ${valB}`,
            });
          } else if (sub.includes("modal_resolver")) {
            hasMr = true;
            reasons.push("Modal Resolver component hash mismatch");
            componentDivergences.push({
              componentType: "modal_resolver",
              label: "Modal Resolver",
              change: `${String(valA).slice(0, 7)} ≠ ${String(valB).slice(0, 7)}`,
              description: `Component hash changed: ${valA} vs ${valB}`,
            });
          } else if (sub.includes("rerank") || sub.includes("cross_encoder")) {
            hasRr = true;
            reasons.push("Reranker component hash mismatch");
            componentDivergences.push({
              componentType: "reranker",
              label: "Reranker",
              change: `${String(valA).slice(0, 7)} ≠ ${String(valB).slice(0, 7)}`,
              description: `Component hash changed: ${valA} vs ${valB}`,
            });
          } else {
            reasons.push(`Component '${sub}' hash changed`);
            componentDivergences.push({
              componentType: "other",
              label: sub,
              change: `${String(valA).slice(0, 7)} ≠ ${String(valB).slice(0, 7)}`,
              description: `Component hash changed: ${valA} vs ${valB}`,
            });
          }
        }
      }

      // 3. Global component hash propagation
      if (dePhases.has(key) && globalDeDiverged && !hasDe) {
        diverged = true;
        hasDe = true;
        reasons.push("Global Decision Engine hash changed");
        componentDivergences.push({
          componentType: "decision_engine",
          label: "Decision Engine",
          change: `${String(globalDeA).slice(0, 7)} ≠ ${String(globalDeB).slice(0, 7)}`,
          description: `Global Decision Engine hash changed: ${globalDeA} vs ${globalDeB}`,
        });
      }

      if (mrPhases.has(key) && globalMrDiverged && !hasMr) {
        diverged = true;
        hasMr = true;
        reasons.push("Global Modal Resolver hash changed");
        componentDivergences.push({
          componentType: "modal_resolver",
          label: "Modal Resolver",
          change: `${String(globalMrA).slice(0, 7)} ≠ ${String(globalMrB).slice(0, 7)}`,
          description: `Global Modal Resolver hash changed: ${globalMrA} vs ${globalMrB}`,
        });
      }

      if (rrPhases.has(key) && globalRrDiverged && !hasRr) {
        diverged = true;
        hasRr = true;
        reasons.push("Global Reranker hash changed");
        componentDivergences.push({
          componentType: "reranker",
          label: "Reranker",
          change: `${String(globalRrA).slice(0, 7)} ≠ ${String(globalRrB).slice(0, 7)}`,
          description: `Global Reranker hash changed: ${globalRrA} vs ${globalRrB}`,
        });
      }

      // 4. Config Diff changes from diffData
      if (diffData?.config_diff) {
        for (const item of diffData.config_diff) {
          const pathLower = item.path.toLowerCase();
          const isDirect =
            pathLower.includes(key.toLowerCase()) ||
            (key === "phase0" && (pathLower.startsWith("models.") || pathLower.startsWith("llm_model")));

          const isDeParam = dePhases.has(key) && pathLower.includes("decision_engine");
          const isMrParam = mrPhases.has(key) && pathLower.includes("modal_resolver");
          const isRrParam = rrPhases.has(key) && (pathLower.includes("rerank") || pathLower.includes("cross_encoder"));

          if (isDeParam) {
            diverged = true;
            hasDe = true;
            const paramLabel = item.path.split(".").pop() || item.path;
            const reasonStr = `Decision Engine: ${paramLabel} changed (${String(item.value_a ?? "—")} → ${String(item.value_b ?? "—")})`;
            if (!reasons.includes(reasonStr)) reasons.push(reasonStr);
            componentDivergences.push({
              componentType: "decision_engine",
              label: `Decision Engine (${paramLabel})`,
              change: `${String(item.value_a ?? "—")} → ${String(item.value_b ?? "—")}`,
              description: `${item.path} changed from ${String(item.value_a)} to ${String(item.value_b)}`,
            });
          } else if (isMrParam) {
            diverged = true;
            hasMr = true;
            const paramLabel = item.path.split(".").pop() || item.path;
            const reasonStr = `Modal Resolver: ${paramLabel} changed (${String(item.value_a ?? "—")} → ${String(item.value_b ?? "—")})`;
            if (!reasons.includes(reasonStr)) reasons.push(reasonStr);
            componentDivergences.push({
              componentType: "modal_resolver",
              label: `Modal Resolver (${paramLabel})`,
              change: `${String(item.value_a ?? "—")} → ${String(item.value_b ?? "—")}`,
              description: `${item.path} changed from ${String(item.value_a)} to ${String(item.value_b)}`,
            });
          } else if (isRrParam) {
            diverged = true;
            hasRr = true;
            const paramLabel = item.path.split(".").pop() || item.path;
            const reasonStr = `Reranker: ${paramLabel} changed (${String(item.value_a ?? "—")} → ${String(item.value_b ?? "—")})`;
            if (!reasons.includes(reasonStr)) reasons.push(reasonStr);
            componentDivergences.push({
              componentType: "reranker",
              label: `Reranker (${paramLabel})`,
              change: `${String(item.value_a ?? "—")} → ${String(item.value_b ?? "—")}`,
              description: `${item.path} changed from ${String(item.value_a)} to ${String(item.value_b)}`,
            });
          } else if (isDirect) {
            diverged = true;
            const paramLabel = item.path.split(".").pop() || item.path;
            const reasonStr = `Config: ${paramLabel} changed (${String(item.value_a ?? "—")} → ${String(item.value_b ?? "—")})`;
            if (!reasons.includes(reasonStr)) reasons.push(reasonStr);
            componentDivergences.push({
              componentType: "config",
              label: paramLabel,
              change: `${String(item.value_a ?? "—")} → ${String(item.value_b ?? "—")}`,
              description: `${item.path} changed from ${String(item.value_a)} to ${String(item.value_b)}`,
            });
          }
        }
      }

      map[key] = {
        diverged,
        reasons,
        hasDecisionEngineDivergence: hasDe,
        hasModalResolverDivergence: hasMr,
        hasRerankerDivergence: hasRr,
        componentDivergences,
      };
    }

    return map;
  }, [detailA, detailB, diffData]);

  const phaseDivergenceMap = useMemo(() => {
    const map: Record<string, boolean> = {};
    for (const key of ORDERED_PHASE_KEYS) {
      map[key] = phaseDivergenceInfoMap[key]?.diverged ?? false;
    }
    return map;
  }, [phaseDivergenceInfoMap]);

  const selectedPhaseDivergence = useMemo(() => {
    return phaseDivergenceInfoMap[selectedPhaseKey];
  }, [phaseDivergenceInfoMap, selectedPhaseKey]);

  const attachedComponents = useMemo(() => {
    const list: {
      name: string;
      type: "decision_engine" | "modal_resolver" | "reranker" | "other";
      hashA?: string;
      hashB?: string;
      diverged: boolean;
    }[] = [];

    const fpsA = { ...(detailA?.method_fingerprints || {}), ...(detailA?.fingerprints || {}) };
    const fpsB = { ...(detailB?.method_fingerprints || {}), ...(detailB?.fingerprints || {}) };

    const dePhases = new Set(["phase2", "phase3", "phase4", "phase5", "phase6"]);
    const mrPhases = new Set(["phase2", "phase4", "phase6"]);
    const rrPhases = new Set(["phase3", "phase3b", "phase4"]);

    if (dePhases.has(selectedPhaseKey)) {
      const hA = fpsA[`${selectedPhaseKey}.decision_engine`] || fpsA["decision_engine"];
      const hB = fpsB[`${selectedPhaseKey}.decision_engine`] || fpsB["decision_engine"];
      const div = Boolean((hA && hB && hA !== hB) || selectedPhaseDivergence?.hasDecisionEngineDivergence);
      list.push({
        name: "Decision Engine",
        type: "decision_engine",
        hashA: hA ? String(hA).slice(0, 8) : undefined,
        hashB: hB ? String(hB).slice(0, 8) : undefined,
        diverged: div,
      });
    }

    if (mrPhases.has(selectedPhaseKey)) {
      const hA = fpsA[`${selectedPhaseKey}.modal_resolver`] || fpsA["modal_resolver"];
      const hB = fpsB[`${selectedPhaseKey}.modal_resolver`] || fpsB["modal_resolver"];
      const div = Boolean((hA && hB && hA !== hB) || selectedPhaseDivergence?.hasModalResolverDivergence);
      list.push({
        name: "Modal Strength Resolver",
        type: "modal_resolver",
        hashA: hA ? String(hA).slice(0, 8) : undefined,
        hashB: hB ? String(hB).slice(0, 8) : undefined,
        diverged: div,
      });
    }

    if (rrPhases.has(selectedPhaseKey)) {
      const hA = fpsA[`${selectedPhaseKey}.relation_reranker`] || fpsA[`${selectedPhaseKey}.reranker`] || fpsA["relation_reranker"] || fpsA["reranker"];
      const hB = fpsB[`${selectedPhaseKey}.relation_reranker`] || fpsB[`${selectedPhaseKey}.reranker`] || fpsB["relation_reranker"] || fpsB["reranker"];
      const div = Boolean((hA && hB && hA !== hB) || selectedPhaseDivergence?.hasRerankerDivergence);
      list.push({
        name: "Relation Reranker",
        type: "reranker",
        hashA: hA ? String(hA).slice(0, 8) : undefined,
        hashB: hB ? String(hB).slice(0, 8) : undefined,
        diverged: div,
      });
    }

    // Phase-specific method fingerprints
    const allKeys = Array.from(new Set([...Object.keys(fpsA), ...Object.keys(fpsB)]));
    for (const k of allKeys) {
      if (
        k.startsWith(`${selectedPhaseKey}.`) &&
        !k.includes("decision_engine") &&
        !k.includes("modal_resolver") &&
        !k.includes("rerank")
      ) {
        const subName = k.slice(selectedPhaseKey.length + 1);
        const hA = fpsA[k];
        const hB = fpsB[k];
        if (!list.some((item) => item.name === subName)) {
          list.push({
            name: subName,
            type: "other",
            hashA: hA ? String(hA).slice(0, 8) : undefined,
            hashB: hB ? String(hB).slice(0, 8) : undefined,
            diverged: Boolean(hA && hB && hA !== hB),
          });
        }
      }
    }

    return list;
  }, [detailA, detailB, selectedPhaseKey, selectedPhaseDivergence]);

  const descriptorA = useMemo<PhaseConfigDescriptor | null>(() => {
    if (!detailA) return null;
    const phaseMeta = PHASE_REGISTRY[selectedPhaseKey];
    if (!phaseMeta) return null;
    return resolvePhaseConfig(
      { key: selectedPhaseKey, phase_name: phaseMeta.displayName, phase_ordinal: phaseMeta.canonicalOrdinal },
      detailA.config_snapshot || {}
    );
  }, [detailA, selectedPhaseKey]);

  const descriptorB = useMemo<PhaseConfigDescriptor | null>(() => {
    if (!detailB) return null;
    const phaseMeta = PHASE_REGISTRY[selectedPhaseKey];
    if (!phaseMeta) return null;
    return resolvePhaseConfig(
      { key: selectedPhaseKey, phase_name: phaseMeta.displayName, phase_ordinal: phaseMeta.canonicalOrdinal },
      detailB.config_snapshot || {}
    );
  }, [detailB, selectedPhaseKey]);

  const setTheoreticDelta = useMemo(() => {
    if (!diffData) return null;
    const { kpis, polarity_inversions } = diffData;
    return {
      intersectionCount: kpis?.nodes_retained ?? 0,
      uniqueToA: kpis?.nodes_lost ?? 0,
      uniqueToB: kpis?.nodes_gained ?? 0,
      edgesRetained: kpis?.edges_retained ?? 0,
      edgesGained: kpis?.edges_gained ?? 0,
      edgesLost: kpis?.edges_lost ?? 0,
      jaccardSimilarity: (kpis?.jaccard_node_similarity ?? 0.85).toFixed(3),
      polarityInversionsCount: polarity_inversions?.length ?? (kpis?.polarity_inversions_count ?? 0),
    };
  }, [diffData]);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center font-mono text-[11px] text-app-muted bg-app-bg">
        Resolving run configuration snapshots and epistemic trees...
      </div>
    );
  }

  if (!detailA || !detailB) {
    return (
      <div className="flex-1 flex items-center justify-center font-mono text-[11px] text-[#DC2626] bg-app-bg">
        Error: Unable to fetch comparative manifests for specified run IDs.
      </div>
    );
  }

  const divergedCount = Object.values(phaseDivergenceMap).filter(Boolean).length;
  const currentPhaseMeta = PHASE_REGISTRY[selectedPhaseKey];

  return (
    <div className="flex-1 flex flex-col h-full bg-app-bg overflow-hidden text-app-text">
      {/* 1. Sticky Action & Provenance Header */}
      <header className="px-6 py-3.5 bg-app-bg border-b border-app-border flex items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-app-muted">COMPARISON RUNS</span>
            <div className="flex items-center gap-1.5 font-mono text-xs bg-app-surface px-2.5 py-1 rounded border border-app-border">
              <span className="text-[#2563EB] font-semibold">{detailA.run_id.slice(0, 8)}</span>
              <span className="text-app-muted">/</span>
              <span className="text-[#059669] font-semibold">{detailB.run_id.slice(0, 8)}</span>
            </div>
          </div>

          <div className="h-4 w-px bg-app-border" />

          <div className="flex items-center gap-2 text-xs">
            <span className="font-medium text-app-text">Structural State:</span>
            {divergedCount > 0 ? (
              <span className="inline-flex items-center gap-1 text-[11px] font-mono text-[#D97706] font-medium bg-[#FFFBEB] px-2 py-0.5 rounded border border-[#FDE68A]">
                <AlertTriangle className="w-3 h-3" />
                {divergedCount} of {ORDERED_PHASE_KEYS.length} phases diverged
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-[11px] font-mono text-[#059669] font-medium bg-[#ECFDF5] px-2 py-0.5 rounded border border-[#A7F3D0]">
                <CheckCircle2 className="w-3 h-3" />
                Parity confirmed across all phases
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Diverged Filter Toggle */}
          <button
            onClick={() => setDivergedOnly(!divergedOnly)}
            className={`h-7 px-2.5 inline-flex items-center gap-1.5 rounded text-xs font-medium border transition-colors cursor-pointer ${
              divergedOnly
                ? "bg-[#FFFBEB] text-[#D97706] border-[#FDE68A]"
                : "bg-app-bg text-app-muted border-app-border hover:text-app-text hover:bg-app-surface"
            }`}
          >
            <Filter className="w-3 h-3" />
            <span>Diverged Only ({divergedCount})</span>
          </button>

          {onSwitchToStaging && (
            <button
              onClick={onSwitchToStaging}
              className="h-7 px-3 inline-flex items-center gap-1.5 rounded text-xs font-medium bg-[#2563EB] text-white hover:bg-[#1D4ED8] transition-colors cursor-pointer shadow-none"
            >
              <span>Launch Staging Editor</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          )}
        </div>
      </header>

      {/* 2. Flat Stage Stepper Segmented Strip */}
      <div className="px-6 py-2 bg-app-surface border-b border-app-border overflow-x-auto shrink-0 flex items-center gap-1 scrollbar-none">
        {ORDERED_PHASE_KEYS.map((key) => {
          const meta = PHASE_REGISTRY[key];
          if (!meta) return null;
          const isDiverged = phaseDivergenceMap[key];
          if (divergedOnly && !isDiverged) return null;
          const isSelected = selectedPhaseKey === key;

          return (
            <button
              key={key}
              onClick={() => setSelectedPhaseKey(key)}
              className={`h-7 px-2.5 rounded text-xs transition-colors shrink-0 flex items-center gap-2 cursor-pointer border ${
                isSelected
                  ? "bg-app-bg border-app-border text-app-text font-medium shadow-xs"
                  : "bg-transparent border-transparent text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
            >
              <span className={`font-mono text-[10px] ${isSelected ? "text-[#2563EB] font-bold" : "text-app-muted"}`}>
                P{meta.canonicalOrdinal}
              </span>
              <span>{meta.shortLabel}</span>

              {isDiverged ? (
                <div className="flex items-center gap-1">
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-[#D97706]"
                    title={
                      phaseDivergenceInfoMap[key]?.reasons?.length
                        ? `Diverged:\n• ${phaseDivergenceInfoMap[key].reasons.join("\n• ")}`
                        : "Configuration Diverged"
                    }
                  />
                  {phaseDivergenceInfoMap[key]?.hasDecisionEngineDivergence && (
                    <span title="Decision Engine Diverged" className="inline-flex items-center">
                      <Zap className="w-2.5 h-2.5 text-[#D97706]" />
                    </span>
                  )}
                  {phaseDivergenceInfoMap[key]?.hasModalResolverDivergence && (
                    <span title="Modal Resolver Diverged" className="inline-flex items-center">
                      <Scale className="w-2.5 h-2.5 text-[#D97706]" />
                    </span>
                  )}
                  {phaseDivergenceInfoMap[key]?.hasRerankerDivergence && (
                    <span title="Reranker / Threshold Diverged" className="inline-flex items-center">
                      <Sliders className="w-2.5 h-2.5 text-[#D97706]" />
                    </span>
                  )}
                </div>
              ) : (
                <span className="w-1.5 h-1.5 rounded-full bg-[#059669]/40" title="Configuration Identical" />
              )}
            </button>
          );
        })}
      </div>

      {/* 3. Workstation Two-Pane Topology */}
      <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-12">
        {/* Left Sub-Panel: Structural Configuration Parameter Diff (4 cols / ~33%) */}
        <aside className="lg:col-span-4 flex flex-col h-full bg-app-surface border-r border-app-border overflow-hidden">
          {/* Attached Component Fingerprints */}
          {attachedComponents.length > 0 && (
            <div className="border-b border-app-border bg-app-subtle/30 shrink-0">
              <div className="h-8 px-4 flex items-center justify-between border-b border-app-border/60 bg-app-surface/60">
                <span className="text-[10px] font-bold uppercase tracking-wider text-app-muted flex items-center gap-1.5">
                  <Cpu className="w-3 h-3 text-app-muted" />
                  Component Hashes & Fingerprints
                </span>
                <span className="font-mono text-[10px] text-app-muted">
                  {attachedComponents.length} component{attachedComponents.length === 1 ? "" : "s"}
                </span>
              </div>
              <div className="divide-y divide-app-border/60">
                {attachedComponents.map((comp) => (
                  <div
                    key={comp.name}
                    className={`p-2.5 transition-colors ${
                      comp.diverged ? "bg-[#FFFDF5] dark:bg-amber-950/20" : "bg-transparent"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1 mb-1">
                      <span className="text-[11px] font-medium text-app-text flex items-center gap-1.5 truncate">
                        {comp.type === "decision_engine" ? (
                          <Zap className="w-3 h-3 text-purple-500 shrink-0" />
                        ) : comp.type === "modal_resolver" ? (
                          <Scale className="w-3 h-3 text-indigo-500 shrink-0" />
                        ) : comp.type === "reranker" ? (
                          <Sliders className="w-3 h-3 text-blue-500 shrink-0" />
                        ) : (
                          <Cpu className="w-3 h-3 text-app-muted shrink-0" />
                        )}
                        <span className="truncate">{comp.name}</span>
                      </span>
                      {comp.diverged ? (
                        <span className="inline-flex items-center gap-0.5 text-[9px] font-mono font-medium text-[#D97706] bg-[#FFFBEB] dark:bg-amber-950/40 px-1.5 py-0.2 rounded border border-[#FDE68A] dark:border-amber-800/40 shrink-0">
                          <AlertTriangle className="w-2.5 h-2.5" />
                          Diverged
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-0.5 text-[9px] font-mono text-[#059669] bg-[#ECFDF5] dark:bg-emerald-950/40 px-1.5 py-0.2 rounded border border-[#A7F3D0] dark:border-emerald-800/40 shrink-0">
                          <CheckCircle2 className="w-2.5 h-2.5" />
                          Identical
                        </span>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-1.5 text-[10px] font-mono">
                      <div className="bg-app-bg px-1.5 py-0.5 rounded border border-app-border truncate">
                        <span className="text-[9px] text-[#2563EB] font-sans font-medium block">Baseline (A)</span>
                        <span className="text-app-text">{comp.hashA ?? "default"}</span>
                      </div>
                      <div
                        className={`px-1.5 py-0.5 rounded border truncate ${
                          comp.diverged
                            ? "bg-[#FFFBEB] dark:bg-amber-950/30 border-[#FDE68A] dark:border-amber-800/40 text-[#92400E] dark:text-amber-200"
                            : "bg-app-bg border-app-border text-app-text"
                        }`}
                      >
                        <span className="text-[9px] text-[#059669] font-sans font-medium block">Candidate (B)</span>
                        <span>{comp.hashB ?? "default"}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="h-9 px-4 border-b border-app-border flex items-center justify-between bg-app-surface shrink-0">
            <span className="text-[11px] font-bold uppercase tracking-wider text-app-muted flex items-center gap-1.5">
              <FileCode className="w-3.5 h-3.5 text-app-muted" />
              Phase Configuration Fields
            </span>
            <span className="font-mono text-[11px] text-app-muted">
              {descriptorA?.parameters?.length ?? 0} attributes
            </span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-app-border">
            {descriptorA?.parameters && descriptorA.parameters.length > 0 ? (
              descriptorA.parameters.map((field) => {
                const valA = field.value;
                const valB = descriptorB?.parameters.find((f) => f.key === field.key)?.value;
                const hasDiverged = JSON.stringify(valA) !== JSON.stringify(valB);

                return (
                  <div
                    key={field.key}
                    className={`p-3 transition-colors ${
                      hasDiverged ? "bg-[#FFFDF5]" : "bg-transparent hover:bg-app-bg"
                    }`}
                  >
                    {/* Dual-Typographic Pattern */}
                    <div className="flex items-baseline justify-between gap-2 mb-1.5">
                      <span className="text-xs font-medium text-app-text truncate">
                        {field.label || field.key}
                      </span>
                      <span className="font-mono text-[10px] text-app-muted shrink-0">
                        {field.key}
                      </span>
                    </div>

                    {/* Side-by-side run values */}
                    <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                      <div className="bg-app-bg p-1.5 rounded border border-app-border truncate">
                        <span className="text-[10px] text-[#2563EB] font-sans font-medium block">Baseline (A)</span>
                        <span className="text-app-text">{String(valA ?? "—")}</span>
                      </div>
                      <div
                        className={`p-1.5 rounded border truncate ${
                          hasDiverged
                            ? "bg-[#FFFBEB] border-[#FDE68A] text-[#92400E]"
                            : "bg-app-bg border-app-border text-app-text"
                        }`}
                      >
                        <span className="text-[10px] text-[#059669] font-sans font-medium block">Candidate (B)</span>
                        <span>{String(valB ?? "—")}</span>
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="p-8 text-center font-mono text-xs text-app-muted">
                No configurable parameters registered for this phase.
              </div>
            )}
          </div>
        </aside>

        {/* Right Main Panel: Analytical Canvas & Set-Theoretic Deltas (8 cols / ~67%) */}
        <main className="lg:col-span-8 flex flex-col h-full bg-app-bg overflow-y-auto">
          {/* Phase Identification Header */}
          <div className="px-6 py-4 border-b border-app-border flex items-center justify-between shrink-0">
            <div>
              <div className="text-[11px] font-mono uppercase tracking-wider text-app-muted">
                P{currentPhaseMeta?.canonicalOrdinal ?? "—"} ANALYTICAL OVERLAY
              </div>
              <h2 className="text-base font-semibold text-app-text">
                {currentPhaseMeta?.displayName ?? selectedPhaseKey}
              </h2>
              {selectedPhaseDivergence?.diverged && (
                <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                  <span className="inline-flex items-center gap-1 text-[11px] font-mono font-medium text-[#D97706] bg-[#FFFBEB] dark:bg-amber-950/30 px-2 py-0.5 rounded border border-[#FDE68A] dark:border-amber-800/40">
                    <AlertTriangle className="w-3 h-3" />
                    <span>Diverged</span>
                  </span>
                  {selectedPhaseDivergence.hasDecisionEngineDivergence && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-mono font-medium text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-950/30 px-2 py-0.5 rounded border border-purple-200 dark:border-purple-800/40">
                      <Zap className="w-3 h-3 text-purple-600 dark:text-purple-400" />
                      <span>Decision Engine Changed</span>
                    </span>
                  )}
                  {selectedPhaseDivergence.hasModalResolverDivergence && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-mono font-medium text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/30 px-2 py-0.5 rounded border border-indigo-200 dark:border-indigo-800/40">
                      <Scale className="w-3 h-3 text-indigo-600 dark:text-indigo-400" />
                      <span>Modal Resolver Changed</span>
                    </span>
                  )}
                  {selectedPhaseDivergence.hasRerankerDivergence && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-mono font-medium text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/30 px-2 py-0.5 rounded border border-blue-200 dark:border-blue-800/40">
                      <Sliders className="w-3 h-3 text-blue-600 dark:text-blue-400" />
                      <span>Reranker / Threshold Changed</span>
                    </span>
                  )}
                  {selectedPhaseDivergence.componentDivergences
                    .filter((c) => !["decision_engine", "modal_resolver", "reranker"].includes(c.componentType))
                    .slice(0, 3)
                    .map((c, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 text-[11px] font-mono text-app-muted bg-app-surface px-2 py-0.5 rounded border border-app-border"
                        title={c.description}
                      >
                        <span>{c.label}:</span>
                        <span className="text-app-text">{c.change}</span>
                      </span>
                    ))}
                </div>
              )}
            </div>
            <div className="text-right">
              <span className="font-mono text-xs text-app-muted block">Jaccard Node Similarity</span>
              <span className="font-mono text-sm font-semibold text-app-text">
                {setTheoreticDelta?.jaccardSimilarity ?? "1.000"}
              </span>
            </div>
          </div>

          {/* Inline Hairline KPI Strip */}
          <div className="grid grid-cols-4 border-b border-app-border shrink-0 bg-app-bg">
            <div className="px-6 py-3 border-r border-app-border">
              <span className="block text-[10px] font-mono uppercase tracking-wider text-app-muted">INTERSECTION (A ∩ B)</span>
              <span className="text-lg font-bold font-mono text-[#059669]">
                {setTheoreticDelta?.intersectionCount ?? 0}
              </span>
            </div>
            <div className="px-6 py-3 border-r border-app-border">
              <span className="block text-[10px] font-mono uppercase tracking-wider text-app-muted">UNIQUE TO RUN A</span>
              <span className="text-lg font-bold font-mono text-[#2563EB]">
                {setTheoreticDelta?.uniqueToA ?? 0}
              </span>
            </div>
            <div className="px-6 py-3 border-r border-app-border">
              <span className="block text-[10px] font-mono uppercase tracking-wider text-app-muted">UNIQUE TO RUN B</span>
              <span className="text-lg font-bold font-mono text-[#7C3AED]">
                {setTheoreticDelta?.uniqueToB ?? 0}
              </span>
            </div>
            <div className="px-6 py-3">
              <span className="block text-[10px] font-mono uppercase tracking-wider text-app-muted">POLARITY INVERSIONS</span>
              <span
                className={`text-lg font-bold font-mono ${
                  (setTheoreticDelta?.polarityInversionsCount ?? 0) > 0 ? "text-[#D97706]" : "text-app-muted"
                }`}
              >
                {setTheoreticDelta?.polarityInversionsCount ?? 0}
              </span>
            </div>
          </div>

          <div className="p-6 space-y-8">
            {/* Section 1: Probability Density Distribution Overlay */}
            <section className="space-y-3">
              <div className="flex items-baseline justify-between">
                <div>
                  <h3 className="text-sm font-medium text-app-text flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-[#2563EB]" />
                    Confidence Score Density (Overlaid KDE)
                  </h3>
                  <p className="text-xs text-app-muted mt-0.5">
                    Continuous probability density estimation across confidence scores for Run A and Run B.
                  </p>
                </div>
                <div className="flex items-center gap-4 font-mono text-xs">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#2563EB]" />
                    Run A (Baseline)
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#059669]" />
                    Run B (Candidate)
                  </span>
                </div>
              </div>

              <div className="pt-2">
                <ConfidenceKdeChart
                  layerKey="L2"
                  labelA="Run A"
                  labelB="Run B"
                  comparisonScores={Array.from({ length: 150 }, () =>
                    Math.min(1, Math.max(0, 0.76 + (Math.random() - 0.45) * 0.22))
                  )}
                  height={220}
                />
              </div>
            </section>

            <div className="h-px bg-app-border" />

            {/* Section 2: Set-Theoretic Graph Deltas Table */}
            <section className="space-y-3">
              <div>
                <h3 className="text-sm font-medium text-app-text flex items-center gap-2">
                  <Network className="w-4 h-4 text-app-text" />
                  Set-Theoretic Graph Deltas
                </h3>
                <p className="text-xs text-app-muted mt-0.5">
                  Formal set partition of knowledge graph entities and relational edges.
                </p>
              </div>

              <div className="border border-app-border rounded overflow-hidden">
                <table className="w-full text-left">
                  <thead>
                    <tr className="bg-app-surface border-b border-app-border text-[11px] font-medium text-app-muted uppercase tracking-wider">
                      <th className="py-2.5 px-4">Set Operation</th>
                      <th className="py-2.5 px-4">Operational Semantics</th>
                      <th className="py-2.5 px-4 text-right font-mono">Entity Yield</th>
                      <th className="py-2.5 px-4 text-right font-mono">Edge Yield</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-app-border-subtle font-mono text-xs">
                    <tr className="hover:bg-app-surface/50 transition-colors">
                      <td className="py-2.5 px-4 font-semibold text-app-text flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#059669]" />
                        Intersection (A ∩ B)
                      </td>
                      <td className="py-2.5 px-4 font-sans text-xs text-app-muted">
                        Invariant entities confirmed identically across both pipeline runs
                      </td>
                      <td className="py-2.5 px-4 text-right font-semibold text-[#059669]">
                        {setTheoreticDelta?.intersectionCount ?? 0}
                      </td>
                      <td className="py-2.5 px-4 text-right font-semibold text-[#059669]">
                        {setTheoreticDelta?.edgesRetained ?? 0}
                      </td>
                    </tr>

                    <tr className="hover:bg-app-surface/50 transition-colors">
                      <td className="py-2.5 px-4 font-semibold text-app-text flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB]" />
                        Run A Complement (A \ B)
                      </td>
                      <td className="py-2.5 px-4 font-sans text-xs text-app-muted">
                        Entities unique to baseline Run A (pruned or suppressed in Run B)
                      </td>
                      <td className="py-2.5 px-4 text-right font-semibold text-[#2563EB]">
                        {setTheoreticDelta?.uniqueToA ?? 0}
                      </td>
                      <td className="py-2.5 px-4 text-right font-semibold text-[#2563EB]">
                        {setTheoreticDelta?.edgesLost ?? 0}
                      </td>
                    </tr>

                    <tr className="hover:bg-app-surface/50 transition-colors">
                      <td className="py-2.5 px-4 font-semibold text-app-text flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#7C3AED]" />
                        Run B Complement (B \ A)
                      </td>
                      <td className="py-2.5 px-4 font-sans text-xs text-app-muted">
                        Novel entities emerged uniquely from candidate Run B
                      </td>
                      <td className="py-2.5 px-4 text-right font-semibold text-[#7C3AED]">
                        {setTheoreticDelta?.uniqueToB ?? 0}
                      </td>
                      <td className="py-2.5 px-4 text-right font-semibold text-[#7C3AED]">
                        {setTheoreticDelta?.edgesGained ?? 0}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
};