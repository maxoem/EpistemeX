import React, {useState} from "react";
import {Overlay, OverlayKind} from "../api/types";
import {api} from "../api/client";
import {useRunsStore} from "../store/runsStore";
import {AlertTriangle, CheckCircle, Layers, RefreshCw, XCircle} from "lucide-react";

interface OverlaySwitcherProps {
  runId?: string | null;
  graphVersion?: string;
  source?: "artifacts" | "neo4j";
  activeOverlay: Overlay | null;
  onOverlayChange: (overlay: Overlay | null) => void;
  onNavigateToCypher?: () => void;
  compact?: boolean;
}

interface OverlayOption {
  kind: OverlayKind;
  label: string;
  description: string;
  reserved?: boolean;
}

const OVERLAY_OPTIONS: OverlayOption[] = [
  {
    kind: "gradual_strength",
    label: "Gradual Strength (ρ)",
    description: "Acceptability via QBAF aggregation (theorynet_concept.md §4)",
  },
  {
    kind: "modal_strength",
    label: "Modal Strength M(φ)",
    description: "Author propositional modal certainty M(φ) via structural syntax & System 1 calibration (ADR 0020)",
  },
  {
    kind: "internal_correlation",
    label: "Internal Correlation",
    description: "Epistemic community cohesion score via epistemetrics",
  },
  {
    kind: "degree",
    label: "Degree Centrality",
    description: "Total connectivity across in/out argument edges",
  },
  {
    kind: "pagerank",
    label: "PageRank Centrality",
    description: "Recursive incoming epistemic endorsement & structural centrality",
  },
  {
    kind: "component",
    label: "Connected Components",
    description: "Weakly connected subgraphs and clusters",
  },
  {
    kind: "leiden",
    label: "Leiden Communities (Hulls)",
    description: "Modular community clusters visualized via AntV G6 Hulls",
  },
  {
    kind: "conformal_uncertainty",
    label: "Decision Calibration & Uncertainty",
    description: "Visualizes conformal prediction set ambiguity |C(x)| > 1 and empirical accuracy",
  },
  {
    kind: "b_consistency",
    label: "B-Consistency",
    description: "Maximal empirical consistency (Reserved — 501 Not Implemented)",
    reserved: true,
  },
  {
    kind: "stable_extension",
    label: "Stable Extensions",
    description: "Dung acceptability semantics (Reserved — 501 Not Implemented)",
    reserved: true,
  },
];

export const OverlaySwitcher: React.FC<OverlaySwitcherProps> = ({
  runId,
  graphVersion,
  source = "artifacts",
  activeOverlay,
  onOverlayChange,
  onNavigateToCypher,
  compact = false,
}) => {
  const { capabilities } = useRunsStore();
  const [selectedKind, setSelectedKind] = useState<OverlayKind | "none">(
    activeOverlay?.kind || "none"
  );
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSelect = async (kindStr: string) => {
    setErrorMessage(null);

    if (kindStr === "none") {
      setSelectedKind("none");
      onOverlayChange(null);
      return;
    }

    const kind = kindStr as OverlayKind;
    setSelectedKind(kind);

    const option = OVERLAY_OPTIONS.find((o) => o.kind === kind);
    if (option?.reserved) {
      setErrorMessage(`${option.label} is reserved and not implemented yet (HTTP 501).`);
      return;
    }

    if (source === "neo4j" && !capabilities?.neo4j) {
      if (onNavigateToCypher) {
        onNavigateToCypher();
      } else {
        setErrorMessage("Neo4j is disconnected. Please connect in Cypher Console first.");
      }
      return;
    }

    setIsLoading(true);
    try {
      const overlay = await api.computeOverlay({
        run_id: source === "artifacts" ? runId : undefined,
        source,
        graph_version: graphVersion,
        kind,
        params: {},
      });
      onOverlayChange(overlay);
    } catch (err: any) {
      console.error("Failed to compute overlay:", err);
      setErrorMessage(err?.detail || err?.title || "Failed to compute overlay.");
      onOverlayChange(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex items-center space-x-1.5 text-xs">
      <div className="flex items-center gap-1 text-app-muted pl-1">
        <Layers className="w-3.5 h-3.5 text-app-muted shrink-0" />
        {!compact && <span className="font-medium text-app-text">Overlay:</span>}
      </div>

      <select
        value={selectedKind}
        onChange={(e) => handleSelect(e.target.value)}
        disabled={isLoading}
        className={
          compact
            ? "bg-transparent border-none text-xs text-app-heading focus:outline-none cursor-pointer pr-1"
            : "bg-app-bg text-app-heading border border-app-border rounded px-2.5 py-1 text-xs focus:outline-none focus:border-cyan-500 transition-colors cursor-pointer"
        }
        title="Select Graph Analytical Overlay"
        aria-label="Select Graph Analytical Overlay"
      >
        <option value="none" className="bg-app-surface text-app-heading">
          {compact ? "Overlay: None" : "None (Standard View)"}
        </option>
        {OVERLAY_OPTIONS.map((opt) => (
          <option
            key={opt.kind}
            value={opt.kind}
            disabled={opt.reserved}
            className={opt.reserved ? "text-app-muted bg-app-surface" : "text-app-heading bg-app-surface"}
          >
            {opt.label} {opt.reserved ? "(501)" : ""}
          </option>
        ))}
      </select>

      {isLoading && (
        <span title="Computing overlay...">
          <RefreshCw className="w-3.5 h-3.5 text-gray-500 animate-spin" />
        </span>
      )}

      {activeOverlay && !isLoading && (
        <div className="flex items-center space-x-2">
          <span
            className="flex items-center gap-1 px-2 py-0.5 rounded bg-cyan-500/10 text-gray-500 dark:text-cyan-300 border border-cyan-500/30 text-[11px]"
            title={`Computed at ${activeOverlay.computed_at}`}
          >
            <CheckCircle className="w-3 h-3 text-gray-500 " />
            <span>{activeOverlay.scale} scale</span>
          </span>

          {activeOverlay.incomplete_inputs > 0 && (
            <span
              className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-300 border border-amber-500/30 text-[11px]"
              title={`${activeOverlay.incomplete_inputs} nodes or edges skipped due to missing tau (plausibility) or phi (weight).`}
            >
              <AlertTriangle className="w-3 h-3 text-amber-500 dark:text-amber-400" />
              <span>{activeOverlay.incomplete_inputs} inputs skipped (null τ/φ)</span>
            </span>
          )}

          <button
            onClick={() => handleSelect("none")}
            className="text-app-muted hover:text-app-heading cursor-pointer"
            title="Clear overlay"
          >
            <XCircle className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {errorMessage && (
        <span className="text-red-500 dark:text-red-400 text-[11px] flex items-center gap-1.5 bg-red-500/10 px-2 py-0.5 rounded border border-red-500/30">
          <AlertTriangle className="w-3 h-3 shrink-0" />
          <span>{errorMessage}</span>
          {source === "neo4j" && onNavigateToCypher && !capabilities?.neo4j && (
            <button
              onClick={onNavigateToCypher}
              className="underline text-gray-500  hover:text-cyan-300 font-medium ml-1 cursor-pointer"
            >
              Connect in Cypher Console
            </button>
          )}
        </span>
      )}
    </div>
  );
};
