import React, {useEffect, useMemo, useState} from "react";
import {
    AlertCircle,
    ArrowDown,
    ArrowUp,
    ArrowUpDown,
    Braces,
    Check,
    CheckCircle2,
    Copy,
    Download,
    FileJson,
    Filter,
    Layers,
    Network,
    Play,
    Search,
    Sliders,
    SlidersHorizontal,
    Sparkles,
    Table as TableIcon,
    Terminal,
    X,
} from "lucide-react";
import {getCoreRowModel, getSortedRowModel, LegacyColumnDef, useLegacyTable,} from "@tanstack/react-table/legacy";
import {flexRender, SortingState} from "@tanstack/react-table";
import {PromptCodeEditor} from "./phaseConfig/PromptCodeEditor";
import {PhaseConfigDescriptor, PhaseConfigField} from "./phaseConfig/types";
import {CypherResult, PhaseStatus} from "../api/types";
import {api} from "../api/client";
import {EPISTEMIC_TAXONOMY, getEpistemicLayerForPhase} from "./epistemicTheme";

export interface StageProvenancePaneProps {
  descriptor: PhaseConfigDescriptor;
  phaseRecord?: PhaseStatus;
  inspectorTab: "params" | "prompts" | "raw" | "validation";
  onTabChange: (tab: "params" | "prompts" | "raw" | "validation") => void;
  llmModel?: string;
  embModel?: string;
  rrkModel?: string;
  phaseViewMode?: "artifacts" | "config";
  onPhaseViewModeChange?: (mode: "artifacts" | "config") => void;
  lensId?: string;
  lensName?: string;
  onDrilldownToGraph?: (lensId: string) => void;
}

const formatParamLabel = (label: string, key: string): string => {
  if (label && !label.includes(".") && !label.includes("_")) {
    return label;
  }
  const cleanKey = key.replace(/^(dense|relation|phase|models|extraction|clustering|pipeline)\./, "");
  return cleanKey
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

const isZeroToOneField = (field: PhaseConfigField): boolean => {
  if (field.valueType !== "number" && typeof field.value !== "number") return false;
  const num = Number(field.value);
  if (isNaN(num)) return false;
  const k = field.key.toLowerCase();
  const isThreshold =
    k.includes("threshold") ||
    k.includes("confidence") ||
    k.includes("ratio") ||
    k.includes("weight") ||
    k.includes("temp") ||
    k.includes("cutoff") ||
    k.includes("score") ||
    k.includes("alpha") ||
    k.includes("beta");
  return isThreshold && num >= 0 && num <= 1;
};

type ParamCategory = "all" | "models" | "thresholds" | "embeddings" | "general";

interface ValidationResultState {
  success: boolean;
  columns?: string[];
  rowCount?: number;
  rows?: Record<string, any>[];
  executionTimeMs?: number;
  error?: string;
}

export const StageProvenancePane: React.FC<StageProvenancePaneProps> = ({
  descriptor,
  phaseRecord,
  inspectorTab,
  onTabChange,
  llmModel = "openai/gpt-4o-mini",
  embModel = "sentence-transformers/all-MiniLM-L6-v2",
  rrkModel = "Alibaba-NLP/gte-reranker-modernbert-base",
  phaseViewMode = "config",
  onPhaseViewModeChange,
  lensId,
  lensName,
  onDrilldownToGraph,
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<ParamCategory>("all");
  const [activePromptIndex, setActivePromptIndex] = useState(0);
  const [sorting, setSorting] = useState<SortingState>([]);

  // Validation Query State
  const defaultCypherQuery = useMemo(() => {
    const isEntity = descriptor.phaseName?.toLowerCase().includes("entity");
    const isArgument = descriptor.phaseName?.toLowerCase().includes("argument");
    const label = isEntity ? "Entity" : isArgument ? "ArgumentComponent" : "Chunk";
    return `MATCH (n:${label})
RETURN count(n) AS yield_count,
       round(avg(coalesce(n.confidence, 0.85)), 3) AS avg_confidence,
       round(min(coalesce(n.confidence, 0.85)), 3) AS min_confidence,
       round(max(coalesce(n.confidence, 0.85)), 3) AS max_confidence`;
  }, [descriptor.phaseName]);

  const [validationCypher, setValidationCypher] = useState<string>(defaultCypherQuery);
  const [validationResult, setValidationResult] = useState<ValidationResultState | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [validationViewMode, setValidationViewMode] = useState<"table" | "json">("table");

  // Raw tab search
  const [rawSearchQuery, setRawSearchQuery] = useState("");

  useEffect(() => {
    setValidationCypher(defaultCypherQuery);
    setValidationResult(null);
    setActivePromptIndex(0);
    setSearchQuery("");
    setActiveCategory("all");
  }, [descriptor.phaseName, descriptor.phaseKey, defaultCypherQuery]);

  const handleCopyText = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1800);
  };

  // Epistemic layer theme
  const layerKey = getEpistemicLayerForPhase(descriptor.phaseKey || "", descriptor.phaseOrdinal);
  const epistemic = EPISTEMIC_TAXONOMY[layerKey];

  // Preset validation queries tailored to the active stage
  const presetQueries = useMemo(() => {
    const isEntity = descriptor.phaseName?.toLowerCase().includes("entity");
    const isArgument = descriptor.phaseName?.toLowerCase().includes("argument") || descriptor.phaseKey?.includes("phase4");
    const isChunk = descriptor.phaseName?.toLowerCase().includes("chunk") || descriptor.phaseKey?.includes("phase1");
    const isTheory = descriptor.phaseName?.toLowerCase().includes("theory") || descriptor.phaseKey?.includes("phase7");

    const primaryLabel = isEntity
      ? "Entity"
      : isArgument
      ? "ArgumentComponent"
      : isChunk
      ? "Chunk"
      : isTheory
      ? "TheoryNode"
      : "Node";

    return [
      {
        id: "yield_confidence",
        label: "Yield & Confidence",
        cypher: `MATCH (n:${primaryLabel})
RETURN count(n) AS yield_count,
       round(avg(coalesce(n.confidence, 0.85)), 3) AS avg_confidence,
       round(min(coalesce(n.confidence, 0.85)), 3) AS min_confidence,
       round(max(coalesce(n.confidence, 0.85)), 3) AS max_confidence`,
      },
      {
        id: "connectivity",
        label: "Structural Degree",
        cypher: `MATCH (n:${primaryLabel})
OPTIONAL MATCH (n)-[r]-()
WITH n, count(r) AS degree
RETURN count(n) AS total_nodes,
       count(CASE WHEN degree = 0 THEN 1 END) AS isolated_nodes,
       round(avg(degree), 2) AS avg_degree,
       max(degree) AS max_degree`,
      },
      {
        id: "integrity",
        label: "Integrity Check",
        cypher: `MATCH (n:${primaryLabel})
WHERE n.text IS NULL AND n.name IS NULL
RETURN count(n) AS null_attribute_nodes`,
      },
      {
        id: "label_distribution",
        label: "Type Distribution",
        cypher: `MATCH (n:${primaryLabel})
RETURN coalesce(n.type, labels(n)[0]) AS node_type,
       count(n) AS count,
       round(avg(coalesce(n.confidence, 0.85)), 3) AS avg_conf
ORDER BY count DESC
LIMIT 10`,
      },
    ];
  }, [descriptor.phaseName, descriptor.phaseKey]);

  // Categorize parameters
  const categorizedData = useMemo(() => {
    // Combine explicit models with phase parameters into a unified list
    const combined = [...descriptor.parameters];

    const hasLlmParam = descriptor.parameters.some((p) => p.key.toLowerCase().includes("llm_model") || p.key.toLowerCase().includes("model_name"));
    if (!hasLlmParam && llmModel) {
      combined.unshift({
        key: "models.llm_model",
        label: "LLM Backbone",
        value: llmModel,
        valueType: "string",
        description: "Primary reasoning and generation language model backbone for this stage.",
      });
    }

    const hasEmbParam = descriptor.parameters.some((p) => p.key.toLowerCase().includes("embed") && p.key.toLowerCase().includes("model"));
    if (!hasEmbParam && embModel) {
      combined.unshift({
        key: "models.embedding_model",
        label: "Vector Embedding Model",
        value: embModel,
        valueType: "string",
        description: "Dense semantic representation model for text chunking and similarity retrieval.",
      });
    }

    const hasRrkParam = descriptor.parameters.some((p) => p.key.toLowerCase().includes("rerank"));
    if (!hasRrkParam && rrkModel) {
      combined.unshift({
        key: "models.reranker_model",
        label: "Cross-Encoder Reranker",
        value: rrkModel,
        valueType: "string",
        description: "Cross-encoder scoring model for neural context reranking and passage ordering.",
      });
    }

    const categories: Record<"models" | "thresholds" | "embeddings" | "general", PhaseConfigField[]> = {
      models: [],
      thresholds: [],
      embeddings: [],
      general: [],
    };

    combined.forEach((param) => {
      const k = param.key.toLowerCase();
      if (k.includes("model") || k.includes("temp") || k.includes("top_p") || k.includes("tokens")) {
        categories.models.push(param);
      } else if (
        k.includes("threshold") ||
        k.includes("min") ||
        k.includes("max") ||
        k.includes("cutoff") ||
        k.includes("alpha") ||
        k.includes("beta")
      ) {
        categories.thresholds.push(param);
      } else if (k.includes("embed") || k.includes("dim") || k.includes("chunk") || k.includes("stride") || k.includes("window")) {
        categories.embeddings.push(param);
      } else {
        categories.general.push(param);
      }
    });

    return { combined, categories };
  }, [descriptor.parameters, llmModel, embModel, rrkModel]);

  const allParameters = categorizedData.combined;
  const categorizedParameters = categorizedData.categories;

  // Filtered parameters based on category & search query
  const filteredParameters = useMemo(() => {
    let list: PhaseConfigField[] = [];
    if (activeCategory === "all") {
      list = allParameters;
    } else {
      list = categorizedParameters[activeCategory] || [];
    }

    if (!searchQuery.trim()) {
      return list;
    }

    const q = searchQuery.toLowerCase().trim();
    return list.filter(
      (p) =>
        p.key.toLowerCase().includes(q) ||
        p.label.toLowerCase().includes(q) ||
        (p.description && p.description.toLowerCase().includes(q)) ||
        String(p.value).toLowerCase().includes(q)
    );
  }, [allParameters, categorizedParameters, activeCategory, searchQuery]);

  // TanStack Table Column Definitions (Rebalanced 3-Column Layout: 45% / 20% / 35%)
  const columns = useMemo<LegacyColumnDef<PhaseConfigField>[]>(() => {
    return [
      {
        id: "parameter",
        accessorFn: (row) => `${row.label} ${row.key}`,
        header: ({ column }) => {
          const isSorted = column.getIsSorted();
          return (
            <button
              type="button"
              onClick={column.getToggleSortingHandler()}
              className="flex items-center gap-1.5 font-semibold text-app-muted hover:text-app-heading transition-colors cursor-pointer select-none"
            >
              <span>Parameter & Semantics</span>
              {isSorted === "asc" ? (
                <ArrowUp className="w-3 h-3 text-blue-400" />
              ) : isSorted === "desc" ? (
                <ArrowDown className="w-3 h-3 text-blue-400" />
              ) : (
                <ArrowUpDown className="w-2.5 h-2.5 opacity-40 hover:opacity-100" />
              )}
            </button>
          );
        },
        cell: ({ row }) => {
          const param = row.original;
          return (
            <div className="py-0.5 pr-3 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-app-heading text-[11px] truncate">
                  {formatParamLabel(param.label, param.key)}
                </span>
                {param.badge && (
                  <span className="px-1.5 py-0.2 rounded-[3px] font-mono text-[9px] bg-app-subtle text-app-muted border border-app-border">
                    {param.badge}
                  </span>
                )}
              </div>
              <div
                className="font-mono text-[10px] text-app-muted truncate mt-0.5"
                title={param.key}
              >
                {param.key}
              </div>
              {param.description && (
                <p className="text-[10px] text-app-muted/80 dark:text-app-muted/80 mt-0.5 line-clamp-1 leading-snug font-sans">
                  {param.description}
                </p>
              )}
            </div>
          );
        },
      },
      {
        id: "domain",
        accessorFn: (row) => row.valueType || typeof row.value,
        header: ({ column }) => {
          const isSorted = column.getIsSorted();
          return (
            <button
              type="button"
              onClick={column.getToggleSortingHandler()}
              className="flex items-center gap-1.5 font-semibold text-app-muted hover:text-app-heading transition-colors cursor-pointer select-none"
            >
              <span>Type / Constraint</span>
              {isSorted === "asc" ? (
                <ArrowUp className="w-3 h-3 text-blue-400" />
              ) : isSorted === "desc" ? (
                <ArrowDown className="w-3 h-3 text-blue-400" />
              ) : (
                <ArrowUpDown className="w-2.5 h-2.5 opacity-40 hover:opacity-100" />
              )}
            </button>
          );
        },
        cell: ({ row }) => {
          const param = row.original;
          const isZeroToOne = isZeroToOneField(param);
          const isBool = typeof param.value === "boolean";
          const isNum = typeof param.value === "number";
          const numVal = Number(param.value);

          return (
            <div className="flex items-center gap-1.5 flex-wrap">
              {isZeroToOne ? (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded-[3px] font-mono text-[9px] bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 font-medium">
                  float [0..1]
                </span>
              ) : isBool ? (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded-[3px] font-mono text-[9px] bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20 font-medium">
                  boolean
                </span>
              ) : isNum ? (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded-[3px] font-mono text-[9px] bg-app-subtle text-app-muted border border-app-border font-medium">
                  {Number.isInteger(numVal) ? "integer" : "float"}
                </span>
              ) : (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded-[3px] font-mono text-[9px] bg-app-subtle text-app-muted border border-app-border font-medium">
                  {param.valueType || typeof param.value}
                </span>
              )}

              {param.defaultValue !== undefined && param.defaultValue !== null && (
                <span
                  className="font-mono text-[9px] text-app-muted/70 dark:text-app-muted/70 truncate"
                  title={`Default fallback: ${param.defaultValue}`}
                >
                  def: {String(param.defaultValue)}
                </span>
              )}
            </div>
          );
        },
      },
      {
        id: "value",
        accessorFn: (row) => row.value,
        header: ({ column }) => {
          const isSorted = column.getIsSorted();
          return (
            <button
              type="button"
              onClick={column.getToggleSortingHandler()}
              className="flex items-center gap-1.5 font-semibold text-app-muted hover:text-app-heading transition-colors cursor-pointer select-none"
            >
              <span>Configured Value</span>
              {isSorted === "asc" ? (
                <ArrowUp className="w-3 h-3 text-blue-400" />
              ) : isSorted === "desc" ? (
                <ArrowDown className="w-3 h-3 text-blue-400" />
              ) : (
                <ArrowUpDown className="w-2.5 h-2.5 opacity-40 hover:opacity-100" />
              )}
            </button>
          );
        },
        cell: ({ row }) => {
          const param = row.original;
          const isZeroToOne = isZeroToOneField(param);
          const numVal = Number(param.value);
          const isBool = typeof param.value === "boolean";
          const isNum = typeof param.value === "number";

          return (
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0 flex items-center gap-2">
                {isZeroToOne ? (
                  <div className="flex items-center gap-2">
                    <div
                      className="w-14 h-1.5 bg-app-subtle rounded-full overflow-hidden border border-app-border shrink-0"
                      title={`Normalized threshold: ${(numVal * 100).toFixed(1)}%`}
                    >
                      <div
                        className="h-full bg-blue-600 dark:bg-blue-400 rounded-full"
                        style={{ width: `${Math.min(100, Math.max(0, numVal * 100))}%` }}
                      />
                    </div>
                    <span className="font-mono text-app-heading font-medium text-[11px] tabular-nums">
                      {numVal.toFixed(3)}
                    </span>
                  </div>
                ) : isBool ? (
                  param.value ? (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[3px] font-mono text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25">
                      <CheckCircle2 className="w-2.5 h-2.5" /> true
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[3px] font-mono text-[10px] font-medium bg-app-subtle text-app-muted border border-app-border">
                      <X className="w-2.5 h-2.5" /> false
                    </span>
                  )
                ) : isNum ? (
                  <span className="font-mono text-app-heading font-medium text-[11px] tabular-nums">
                    {numVal.toLocaleString()}
                    {param.unit && (
                      <span className="text-app-muted text-[10px] ml-1 font-sans">
                        {param.unit}
                      </span>
                    )}
                  </span>
                ) : (
                  <span
                    className="font-mono text-app-heading text-[11px] break-all font-medium"
                    title={String(param.value)}
                  >
                    {param.value !== undefined && param.value !== null
                      ? String(param.value)
                      : "—"}
                  </span>
                )}
              </div>

              {/* Seamless Inline Quick-Copy Action */}
              <button
                type="button"
                onClick={() => handleCopyText(String(param.value), param.key)}
                className="opacity-0 group-hover:opacity-100 p-1 rounded-[3px] hover:bg-app-subtle text-app-muted hover:text-app-text transition-opacity cursor-pointer shrink-0"
                title={`Copy "${param.key}" value`}
              >
                {copiedKey === param.key ? (
                  <Check className="w-3 h-3 text-emerald-500" />
                ) : (
                  <Copy className="w-3 h-3" />
                )}
              </button>
            </div>
          );
        },
      },
    ];
  }, [copiedKey]);

  // TanStack Table Instance
  const table = useLegacyTable<PhaseConfigField>({
    data: filteredParameters,
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  // Copy parameters as CLI command-line arguments
  const handleCopyCliFlags = () => {
    const flags = filteredParameters
      .map((p) => {
        const val = typeof p.value === "string" && p.value.includes(" ") ? `"${p.value}"` : p.value;
        return `--${p.key}=${val}`;
      })
      .join(" ");
    handleCopyText(flags, "cli_flags");
  };

  // Copy parameters as JSON
  const handleCopyParamsJson = () => {
    const obj = filteredParameters.reduce((acc, p) => {
      acc[p.key] = p.value;
      return acc;
    }, {} as Record<string, any>);
    handleCopyText(JSON.stringify(obj, null, 2), "params_json");
  };

  // Execute Cypher query
  const handleExecuteValidationCypher = async () => {
    if (!validationCypher.trim()) return;
    setIsValidating(true);
    setValidationResult(null);
    try {
      const res: CypherResult = await api.executeCypher(validationCypher, {}, 50);
      setValidationResult({
        success: true,
        columns: res.columns,
        rowCount: res.row_count,
        rows: res.rows,
        executionTimeMs: res.execution_time_ms,
      });
    } catch (err: any) {
      setValidationResult({
        success: false,
        error: err?.detail || err?.title || err?.message || "Cypher execution error",
      });
    } finally {
      setIsValidating(false);
    }
  };

  // Export validation results as CSV
  const handleExportCsv = () => {
    if (!validationResult?.rows || validationResult.rows.length === 0) return;
    const cols = validationResult.columns || Object.keys(validationResult.rows[0]);
    const header = cols.join(",");
    const rows = validationResult.rows.map((row) =>
      cols
        .map((col) => {
          const v = row[col];
          if (v === null || v === undefined) return "";
          const s = String(v);
          return s.includes(",") || s.includes('"') || s.includes("\n") ? `"${s.replace(/"/g, '""')}"` : s;
        })
        .join(",")
    );
    const csvContent = [header, ...rows].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${descriptor.phaseKey || "stage"}_validation_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Download raw config as JSON
  const handleDownloadRawConfig = () => {
    const jsonStr = JSON.stringify(descriptor.rawConfig, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${descriptor.phaseKey || "stage"}_provenance_spec.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Filtered raw config
  const filteredRawConfig = useMemo(() => {
    if (!rawSearchQuery.trim()) return descriptor.rawConfig;
    const q = rawSearchQuery.toLowerCase();
    const result: Record<string, any> = {};
    Object.entries(descriptor.rawConfig).forEach(([k, v]) => {
      if (k.toLowerCase().includes(q) || JSON.stringify(v).toLowerCase().includes(q)) {
        result[k] = v;
      }
    });
    return result;
  }, [descriptor.rawConfig, rawSearchQuery]);

  const activePrompt = descriptor.prompts[activePromptIndex] || descriptor.prompts[0];

  return (
    <div className="flex flex-col h-full bg-app-surface text-app-text select-text overflow-hidden">
      {/* 1. Scientific Stage Identity & Provenance Header (Flat, Non-Boxed) */}
      <div className="px-4 py-2.5 border-b border-app-border shrink-0 bg-app-bg">
        <div className="flex flex-wrap items-center justify-between gap-2">
          {/* Stage Tier & Name */}
          <div className="flex items-center gap-2 min-w-0">
            <h2 className="text-xs font-semibold text-app-heading truncate tracking-tight font-display">
              P{descriptor.phaseOrdinal}
            </h2>
          </div>

          {/* Actions & Controls */}
          <div className="flex items-center gap-2 shrink-0 text-xs">
            {onPhaseViewModeChange && (
              <div className="inline-flex p-0.5 rounded-[4px] bg-app-subtle border border-app-border text-[11px] font-sans">
                <button
                  type="button"
                  onClick={() => onPhaseViewModeChange("artifacts")}
                  className={`px-2 py-0.5 rounded-[3px] transition-colors cursor-pointer flex items-center gap-1.5 ${
                    phaseViewMode === "artifacts"
                      ? "bg-app-bg text-blue-600 dark:text-blue-400 font-medium shadow-2xs border border-app-border"
                      : "text-app-muted hover:text-app-text"
                  }`}
                >
                  <Layers className="w-3 h-3" />
                  <span>Artifacts</span>
                </button>
                <button
                  type="button"
                  onClick={() => onPhaseViewModeChange("config")}
                  className={`px-2 py-0.5 rounded-[3px] transition-colors cursor-pointer flex items-center gap-1.5 ${
                    phaseViewMode === "config"
                      ? "bg-app-bg text-blue-600 dark:text-blue-400 font-medium shadow-2xs border border-app-border"
                      : "text-app-muted hover:text-app-text"
                  }`}
                >
                  <Sliders className="w-3 h-3" />
                  <span>Run Config</span>
                </button>
              </div>
            )}

            {lensId && onDrilldownToGraph && (
              <button
                type="button"
                onClick={() => onDrilldownToGraph(lensId)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[4px] border border-app-border bg-transparent hover:bg-app-subtle text-app-text font-medium text-[11px] transition-colors cursor-pointer"
                title={`Visualize ${descriptor.phaseName} items in the Graph Explorer canvas`}
              >
                <Network className="w-3.5 h-3.5 text-app-muted" />
                <span>Explore {lensName || "in Graph"} ↗</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 2. Scientific Workbench Tab Bar */}
      <div className="px-4 border-b border-app-border flex items-center justify-between shrink-0 bg-app-surface text-xs">
        <div className="flex items-center gap-2 -mb-px">
          <button
            type="button"
            onClick={() => onTabChange("params")}
            className={`px-3 py-2 text-[11px] font-medium border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
              inspectorTab === "params"
                ? "border-b-blue-600 dark:border-b-blue-400 text-blue-600 dark:text-blue-400 font-semibold"
                : "border-b-transparent text-app-muted hover:text-app-text"
            }`}
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>Parameters & Models</span>
            <span className="font-mono text-[10px] px-1.5 py-0.2 rounded-[3px] bg-app-subtle text-app-muted">
              {allParameters.length}
            </span>
          </button>

          {descriptor.prompts.length > 0 && (
            <button
              type="button"
              onClick={() => onTabChange("prompts")}
              className={`px-3 py-2 text-[11px] font-medium border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
                inspectorTab === "prompts"
                  ? "border-b-blue-600 dark:border-b-blue-400 text-blue-600 dark:text-blue-400 font-semibold"
                  : "border-b-transparent text-app-muted hover:text-app-text"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-blue-500 dark:text-blue-400" />
              <span>Prompt Templates</span>
              <span className="font-mono text-[10px] px-1.5 py-0.2 rounded-[3px] bg-app-subtle text-app-muted">
                {descriptor.prompts.length}
              </span>
            </button>
          )}

          <button
            type="button"
            onClick={() => onTabChange("validation")}
            className={`px-3 py-2 text-[11px] font-medium border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
              inspectorTab === "validation"
                ? "border-b-blue-600 dark:border-b-blue-400 text-blue-600 dark:text-blue-400 font-semibold"
                : "border-b-transparent text-app-muted hover:text-app-text"
            }`}
          >
            <Terminal className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            <span>Cypher Invariant Validation</span>
            {validationResult?.success && (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            )}
          </button>

          <button
            type="button"
            onClick={() => onTabChange("raw")}
            className={`px-3 py-2 text-[11px] font-medium border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
              inspectorTab === "raw"
                ? "border-b-blue-600 dark:border-b-blue-400 text-blue-600 dark:text-blue-400 font-semibold"
                : "border-b-transparent text-app-muted hover:text-app-text"
            }`}
          >
            <Braces className="w-3.5 h-3.5 text-app-muted" />
            <span>Raw Spec</span>
          </button>
        </div>
      </div>

      {/* 4. Tab Body Content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {/* TAB A: PARAMETERS & HYPERPARAMETERS WORKBENCH */}
        {inspectorTab === "params" && (
          <div className="flex flex-col h-full bg-app-bg">
            {/* Filter, Search & Export Toolbar */}
            <div className="px-4 py-2.5 border-b border-app-border flex flex-wrap items-center justify-between gap-2 shrink-0 bg-app-bg">
              {/* Category Pills */}
              <div className="flex items-center gap-1.5 flex-wrap">
                <button
                  type="button"
                  onClick={() => setActiveCategory("all")}
                  className={`px-2.5 py-1 rounded-[4px] text-[11px] font-medium transition-colors cursor-pointer ${
                    activeCategory === "all"
                      ? "bg-app-bg text-blue-600 dark:text-blue-400 font-semibold shadow-2xs border border-app-border dark:border-transparent"
                      : "bg-app-subtle text-app-muted border border-app-border hover:text-app-text"
                  }`}
                >
                  All ({allParameters.length})
                </button>
                {categorizedParameters.models.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setActiveCategory("models")}
                    className={`px-2.5 py-1 rounded-[4px] text-[11px] font-medium transition-colors cursor-pointer ${
                      activeCategory === "models"
                        ? "bg-app-bg text-blue-600 dark:text-blue-400 font-semibold shadow-2xs border border-app-border dark:border-transparent"
                        : "bg-app-subtle text-app-muted border border-app-border hover:text-app-text"
                    }`}
                  >
                    Directives ({categorizedParameters.models.length})
                  </button>
                )}
                {categorizedParameters.thresholds.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setActiveCategory("thresholds")}
                    className={`px-2.5 py-1 rounded-[4px] text-[11px] font-medium transition-colors cursor-pointer ${
                      activeCategory === "thresholds"
                        ? "bg-app-bg text-blue-600 dark:text-blue-400 font-semibold shadow-2xs border border-app-border dark:border-transparent"
                        : "bg-app-subtle text-app-muted border border-app-border hover:text-app-text"
                    }`}
                  >
                    Thresholds ({categorizedParameters.thresholds.length})
                  </button>
                )}
                {categorizedParameters.embeddings.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setActiveCategory("embeddings")}
                    className={`px-2.5 py-1 rounded-[4px] text-[11px] font-medium transition-colors cursor-pointer ${
                      activeCategory === "embeddings"
                        ? "bg-app-bg text-blue-600 dark:text-blue-400 font-semibold shadow-2xs border border-app-border dark:border-transparent"
                        : "bg-app-subtle text-app-muted border border-app-border hover:text-app-text"
                    }`}
                  >
                    Vectors ({categorizedParameters.embeddings.length})
                  </button>
                )}
                {categorizedParameters.general.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setActiveCategory("general")}
                    className={`px-2.5 py-1 rounded-[4px] text-[11px] font-medium transition-colors cursor-pointer ${
                      activeCategory === "general"
                        ? "bg-app-bg text-blue-600 dark:text-blue-400 font-semibold shadow-2xs border border-app-border dark:border-transparent"
                        : "bg-app-subtle text-app-muted border border-app-border hover:text-app-text"
                    }`}
                  >
                    General ({categorizedParameters.general.length})
                  </button>
                )}
              </div>

              {/* Search & Batch Export Actions */}
              <div className="flex items-center gap-2">
                <div className="relative min-w-[200px]">
                  <Search className="w-3.5 h-3.5 text-app-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search hyperparameters..."
                    className="w-full pl-8 pr-6 py-1 rounded-[4px] bg-app-surface border border-app-border text-[11px] text-app-text placeholder-app-muted focus:outline-hidden focus:border-blue-500 font-sans"
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery("")}
                      className="absolute right-1.5 top-1/2 -translate-y-1/2 text-app-muted hover:text-app-text p-0.5 cursor-pointer"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  )}
                </div>

                <button
                  type="button"
                  onClick={handleCopyCliFlags}
                  className="px-2.5 py-1 rounded-[4px] bg-app-surface hover:bg-app-subtle border border-app-border text-app-muted hover:text-app-text text-[10px] font-mono flex items-center gap-1 transition-colors cursor-pointer"
                  title="Copy all active parameters as CLI flags (e.g. --key=value)"
                >
                  {copiedKey === "cli_flags" ? (
                    <Check className="w-3 h-3 text-emerald-500" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                  <span>CLI</span>
                </button>

                <button
                  type="button"
                  onClick={handleCopyParamsJson}
                  className="px-2.5 py-1 rounded-[4px] bg-app-surface hover:bg-app-subtle border border-app-border text-app-muted hover:text-app-text text-[10px] font-mono flex items-center gap-1 transition-colors cursor-pointer"
                  title="Copy active parameters as JSON"
                >
                  {copiedKey === "params_json" ? (
                    <Check className="w-3 h-3 text-emerald-500" />
                  ) : (
                    <FileJson className="w-3 h-3" />
                  )}
                  <span>JSON</span>
                </button>
              </div>
            </div>

            {/* Scientific Parameters Data Grid (TanStack Table Layout, Full-Bleed) */}
            <div className="flex-1 overflow-x-auto">
              {table.getRowModel().rows.length === 0 ? (
                <div className="p-8 text-center text-app-muted text-xs">
                  <SlidersHorizontal className="w-7 h-7 mx-auto mb-2 opacity-30" />
                  <p className="font-medium text-app-heading font-sans">No matching parameters found</p>
                  <p className="text-[11px] mt-0.5 text-app-muted font-sans">
                    {searchQuery
                      ? `Try clearing your search query "${searchQuery}"`
                      : "No hyperparameters are registered under this category."}
                  </p>
                </div>
              ) : (
                <table className="w-full text-left text-xs border-collapse table-fixed">
                  <thead className="h-10 bg-app-surface border-b border-app-border text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted sticky top-0 z-10">
                    {table.getHeaderGroups().map((headerGroup) => (
                      <tr key={headerGroup.id}>
                        {headerGroup.headers.map((header) => {
                          const colId = header.column.id;
                          const widthClass =
                            colId === "parameter"
                              ? "w-[40%]"
                              : colId === "domain"
                              ? "w-[20%]"
                              : "w-[40%]";
                          return (
                            <th
                              key={header.id}
                              className={`py-2 px-4 ${widthClass}`}
                            >
                              {header.isPlaceholder
                                ? null
                                : flexRender(
                                    header.column.columnDef.header,
                                    header.getContext()
                                  )}
                            </th>
                          );
                        })}
                      </tr>
                    ))}
                  </thead>
                  <tbody className="divide-y divide-app-border font-mono text-[11px]">
                    {table.getRowModel().rows.map((row) => (
                      <tr
                        key={row.id}
                        className="group transition-colors h-10 border-l-2 border-l-transparent hover:border-l-[#2563EB] hover:bg-app-surface dark:hover:bg-app-subtle/30 bg-transparent"
                      >
                        {row.getVisibleCells().map((cell) => {
                          const colId = cell.column.id;
                          const alignClass =
                            colId === "parameter"
                              ? "font-sans"
                              : colId === "domain"
                              ? "align-middle"
                              : "align-middle";
                          return (
                            <td
                              key={cell.id}
                              className={`py-2.5 px-4 ${alignClass}`}
                            >
                              {flexRender(
                                cell.column.columnDef.cell,
                                cell.getContext()
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* TAB B: PROMPT ENGINEERING & TEMPLATES WORKBENCH */}
        {inspectorTab === "prompts" && descriptor.prompts.length > 0 && (
          <div className="flex flex-col h-full divide-y divide-app-border">
            {/* Multi-Prompt Selector Ribbon (if > 1 prompt) */}
            {descriptor.prompts.length > 1 && (
              <div className="px-4 py-2 bg-app-surface flex items-center gap-1.5 overflow-x-auto shrink-0 border-b border-app-border">
                {descriptor.prompts.map((p, idx) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setActivePromptIndex(idx)}
                    className={`px-2.5 py-1 rounded-[4px] text-xs font-medium transition-colors cursor-pointer shrink-0 flex items-center gap-1.5 ${
                      activePromptIndex === idx
                        ? "bg-app-bg text-blue-600 dark:text-blue-400 font-medium shadow-2xs border border-app-border"
                        : "bg-app-subtle text-app-muted border border-app-border hover:text-app-text"
                    }`}
                  >
                    <Sparkles className="w-3 h-3 text-blue-500 dark:text-blue-400" />
                    <span>{p.name}</span>
                    <span className="font-mono text-[10px] text-app-muted">
                      ~{Math.ceil(p.template.length / 4)}t
                    </span>
                  </button>
                ))}
              </div>
            )}

            {/* Prompt Metadata Bar */}
            <div className="px-4 py-3 bg-app-bg flex flex-wrap items-center justify-between gap-2 shrink-0">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-app-heading text-xs font-display">
                    {activePrompt.name}
                  </h3>
                  <span className="font-mono uppercase text-[9px] px-1.5 py-0.5 rounded-[3px] bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                    {activePrompt.role}
                  </span>
                </div>
                <div className="text-[11px] text-app-muted flex items-center gap-3 font-sans">
                  <span>~{Math.ceil(activePrompt.template.length / 4).toLocaleString()} tokens (est.)</span>
                  <span>•</span>
                  <span>{activePrompt.template.length.toLocaleString()} characters</span>
                  <span>•</span>
                  <span>{activePrompt.variables.length} template variable{activePrompt.variables.length === 1 ? "" : "s"}</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleCopyText(activePrompt.template, activePrompt.id)}
                  className="px-2.5 py-1 rounded-[4px] bg-app-surface hover:bg-app-subtle border border-app-border text-app-muted hover:text-app-text text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  {copiedKey === activePrompt.id ? (
                    <Check className="w-3.5 h-3.5 text-emerald-500" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                  <span>Copy Template</span>
                </button>
              </div>
            </div>

            {/* Variables Inspector Pill Bar */}
            {activePrompt.variables.length > 0 && (
              <div className="px-4 py-2 bg-app-surface flex items-center gap-2 flex-wrap shrink-0 border-b border-app-border">
                <span className="text-[10px] font-mono text-app-muted uppercase">Variables:</span>
                {activePrompt.variables.map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => handleCopyText(`{${v}}`, `var_${v}`)}
                    className="font-mono text-[10px] px-1.5 py-0.5 rounded-[3px] bg-app-bg border border-app-border text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors cursor-pointer"
                    title={`Click to copy {${v}}`}
                  >
                    {copiedKey === `var_${v}` ? `Copied!` : `{${v}}`}
                  </button>
                ))}
              </div>
            )}

            {/* Prompt CodeMirror Editor Canvas */}
            <div className="flex-1 p-4 min-h-[220px] bg-app-bg">
              <PromptCodeEditor
                value={activePrompt.template}
                readOnly={true}
                minHeight="220px"
                maxHeight="480px"
              />
            </div>
          </div>
        )}

        {/* TAB C: EMPIRICAL CYPHER INVARIANT VALIDATION */}
        {inspectorTab === "validation" && (
          <div className="p-4 space-y-4 bg-app-bg">
            {/* Header & Presets */}
            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-xs font-semibold text-app-heading flex items-center gap-1.5 font-display">
                    <Terminal className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                    Stage Invariant Assertion Query
                  </h3>
                  <p className="text-[11px] text-app-muted mt-0.5 font-sans">
                    Executes directly against the Neo4j Graph to mathematically verify topological invariants and confidence distributions.
                  </p>
                </div>

                <div className="text-[10px] text-app-muted font-mono">
                  Press <kbd className="px-1 py-0.2 rounded-[3px] bg-app-subtle border border-app-border">Cmd</kbd>+<kbd className="px-1 py-0.2 rounded-[3px] bg-app-subtle border border-app-border">Enter</kbd> to run
                </div>
              </div>

              {/* Preset Queries Pill Strip */}
              <div className="flex items-center gap-1.5 flex-wrap pt-1">
                <span className="text-[10px] font-mono text-app-muted uppercase flex items-center gap-1">
                  <Filter className="w-2.5 h-2.5" /> Presets:
                </span>
                {presetQueries.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => {
                      setValidationCypher(preset.cypher);
                      setValidationResult(null);
                    }}
                    className={`text-[10px] font-medium px-2 py-0.5 rounded-[4px] border transition-colors cursor-pointer ${
                      validationCypher.trim() === preset.cypher.trim()
                        ? "bg-app-bg text-blue-600 dark:text-blue-400 border border-app-border dark:border-transparent shadow-2xs font-semibold"
                        : "bg-app-subtle text-app-muted border border-app-border hover:text-app-text"
                    }`}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Cypher Query Editor Canvas */}
            <div className="space-y-2">
              <textarea
                value={validationCypher}
                onChange={(e) => setValidationCypher(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                    e.preventDefault();
                    handleExecuteValidationCypher();
                  }
                }}
                className="w-full h-28 p-2.5 bg-app-surface border border-app-border rounded-[4px] font-mono text-[11px] text-app-text focus:outline-hidden focus:border-blue-500 transition-colors resize-y leading-relaxed"
                placeholder="MATCH (n:Entity) RETURN count(n)..."
                spellCheck={false}
              />

              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={handleExecuteValidationCypher}
                  disabled={isValidating || !validationCypher.trim()}
                  className="px-4 py-1.5 rounded-[4px] bg-[#2563EB] hover:bg-blue-700 disabled:opacity-50 text-white font-medium text-xs flex items-center gap-2 transition-colors cursor-pointer shadow-xs"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>{isValidating ? "Evaluating Graph..." : "Execute Validation Assertion"}</span>
                </button>

                {validationResult?.rows && validationResult.rows.length > 0 && (
                  <div className="inline-flex p-0.5 rounded-[4px] bg-app-subtle border border-app-border text-[11px] font-sans items-center">
                    <button
                      type="button"
                      onClick={() => setValidationViewMode("table")}
                      className={`px-2 py-0.5 rounded-[3px] transition-colors cursor-pointer flex items-center gap-1 ${
                        validationViewMode === "table"
                          ? "bg-app-bg text-blue-600 dark:text-blue-400 font-medium shadow-2xs border border-app-border"
                          : "text-app-muted hover:text-app-text"
                      }`}
                    >
                      <TableIcon className="w-3 h-3" /> Table
                    </button>
                    <button
                      type="button"
                      onClick={() => setValidationViewMode("json")}
                      className={`px-2 py-0.5 rounded-[3px] transition-colors cursor-pointer flex items-center gap-1 ${
                        validationViewMode === "json"
                          ? "bg-app-bg text-blue-600 dark:text-blue-400 font-medium shadow-2xs border border-app-border"
                          : "text-app-muted hover:text-app-text"
                      }`}
                    >
                      <FileJson className="w-3 h-3" /> JSON
                    </button>
                    <button
                      type="button"
                      onClick={handleExportCsv}
                      className="px-2 py-0.5 rounded-[3px] text-app-muted hover:text-app-text flex items-center gap-1 cursor-pointer transition-colors"
                      title="Export query results as CSV"
                    >
                      <Download className="w-3 h-3" /> CSV
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Validation Results Workbench */}
            {validationResult && (
              <div className="pt-2 space-y-2">
                {/* Result Status Banner */}
                <div
                  className={`p-2.5 rounded-[4px] border text-xs flex items-center justify-between ${
                    validationResult.success
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
                      : "bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {validationResult.success ? (
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                    ) : (
                      <AlertCircle className="w-4 h-4 shrink-0" />
                    )}
                    <span className="font-semibold">
                      {validationResult.success
                        ? "Stage Assertion Succeeded"
                        : "Cypher Execution Error"}
                    </span>
                  </div>
                  {validationResult.executionTimeMs !== undefined && (
                    <span className="font-mono text-[10px] text-app-muted">
                      {validationResult.rowCount ?? 0} record{validationResult.rowCount === 1 ? "" : "s"} •{" "}
                      {validationResult.executionTimeMs}ms
                    </span>
                  )}
                </div>

                {validationResult.error && (
                  <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-[4px] font-mono text-[11px] text-red-600 dark:text-red-400">
                    {validationResult.error}
                  </div>
                )}

                {/* Tabular Result Presentation */}
                {validationResult.rows && validationResult.rows.length > 0 && (
                  validationViewMode === "table" ? (
                    <div className="border border-app-border rounded-[4px] overflow-x-auto max-h-72">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead className="h-10 bg-app-surface text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted sticky top-0 border-b border-app-border">
                          <tr>
                            <th className="py-2 px-3 w-8">#</th>
                            {(validationResult.columns || Object.keys(validationResult.rows[0])).map((col) => (
                              <th key={col} className="py-2 px-3">
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-app-border font-mono text-[11px]">
                          {validationResult.rows.map((row, idx) => (
                            <tr key={idx} className="h-9 hover:bg-app-surface dark:hover:bg-app-surface/50 transition-colors">
                              <td className="py-1.5 px-3 text-app-muted text-[10px]">{idx + 1}</td>
                              {(validationResult.columns || Object.keys(row)).map((col) => {
                                const val = row[col];
                                const isNum = typeof val === "number";
                                return (
                                  <td
                                    key={col}
                                    className={`py-1.5 px-3 ${
                                      isNum ? "text-right tabular-nums text-blue-600 dark:text-blue-400 font-medium" : "text-app-heading"
                                    }`}
                                  >
                                    {val === null || val === undefined ? (
                                      <span className="text-app-muted italic font-sans text-[10px]">null</span>
                                    ) : isNum ? (
                                      Number.isInteger(val) ? val.toLocaleString() : val.toFixed(4)
                                    ) : typeof val === "object" ? (
                                      JSON.stringify(val)
                                    ) : (
                                      String(val)
                                    )}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="p-3 bg-app-surface border border-app-border rounded-[4px] font-mono text-[10px] overflow-auto max-h-72">
                      <pre className="text-app-text whitespace-pre-wrap">
                        {JSON.stringify(validationResult.rows, null, 2)}
                      </pre>
                    </div>
                  )
                )}

                {validationResult.success && (!validationResult.rows || validationResult.rows.length === 0) && (
                  <p className="text-xs text-app-muted italic p-2 font-sans">
                    Query returned 0 rows. Graph invariant verified.
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB D: RAW SPECIFICATION & REPRODUCIBILITY WORKBENCH */}
        {inspectorTab === "raw" && (
          <div className="flex flex-col h-full bg-app-bg">
            <div className="px-4 py-2 border-b border-app-border bg-app-surface flex items-center justify-between gap-2 shrink-0">
              <div className="relative min-w-[200px]">
                <Search className="w-3.5 h-3.5 text-app-muted absolute left-2 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={rawSearchQuery}
                  onChange={(e) => setRawSearchQuery(e.target.value)}
                  placeholder="Filter JSON properties..."
                  className="w-full pl-7 pr-6 py-1 rounded-[4px] bg-app-bg border border-app-border text-[11px] text-app-text placeholder-app-muted focus:outline-hidden focus:border-blue-500 font-sans"
                />
                {rawSearchQuery && (
                  <button
                    type="button"
                    onClick={() => setRawSearchQuery("")}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 text-app-muted hover:text-app-text p-0.5 cursor-pointer"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleCopyText(JSON.stringify(descriptor.rawConfig, null, 2), "raw_json")}
                  className="px-2.5 py-1 rounded-[4px] bg-app-surface hover:bg-app-subtle border border-app-border text-app-muted hover:text-app-text text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  {copiedKey === "raw_json" ? (
                    <Check className="w-3.5 h-3.5 text-emerald-500" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                  <span>Copy JSON</span>
                </button>
                <button
                  type="button"
                  onClick={handleDownloadRawConfig}
                  className="px-2.5 py-1 rounded-[4px] bg-app-surface hover:bg-app-subtle border border-app-border text-app-muted hover:text-app-text text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
                  title="Download complete stage configuration as JSON"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download</span>
                </button>
              </div>
            </div>

            <div className="flex-1 p-4 overflow-auto font-mono text-[11px] leading-relaxed bg-app-bg select-text">
              <pre className="text-app-text whitespace-pre-wrap">
                {JSON.stringify(filteredRawConfig, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
