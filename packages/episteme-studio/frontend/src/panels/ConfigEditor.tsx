import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { GitFork, X } from "lucide-react";
import { api } from "../api/client";
import {
  AvailableInputDoc,
  ConfigView,
  GlobalStructuralAnchor,
  InvalidationPreview,
  PromptResolveResponse,
  ResolvedPromptItem,
} from "../api/types";
import { useRunsStore } from "../store/runsStore";
import { useProjectSettingsStore } from "../store/projectSettingsStore";
import { useNavigationStore } from "../store/navigationStore";
import {
  PHASE_REGISTRY,
  PhaseMetadata,
  isPhaseMandatory,
  isPhasePostProcessor,
  registerCustomPhase,
  CORE_DAG_PHASE_KEYS,
  POST_PROCESSOR_KEYS,
  PIPELINE_DEFAULTS_KEY,
} from "./phaseConfig/phaseRegistry";
import { PhaseCatalogDrawer } from "./PhaseCatalogDrawer";
import { ResizablePanel } from "./ResizablePanel";
import { useCredentialStore } from "../store/credentialStore";
import { DatabaseCollisionModal } from "./DatabaseCollisionModal";
import {
  ConfigEditorProps,
  RunMetadataItem,
  BASELINE_PREVIEW,
  derivePhaseExecutionStatus,
  PhaseExecutionStatusMap,
  StageScopeHeader,
  PipelineComposerRail,
  PreFlightInspectorRail,
  StructuralAnchorsView,
  PipelineDefaultsView,
  EpistemicSchemaView,
  StageWorkspaceView,
} from "./configEditor/index";

export type { ConfigEditorProps };

export const ConfigEditor: React.FC<ConfigEditorProps> = ({ onNavigateToRuns }) => {
  const { startNewRun, runs, forkedRunDetail, setForkedRunDetail } = useRunsStore();
  const hasRunBaseline = useMemo(
    () => runs.some((r) => r.status === "completed") || Boolean(forkedRunDetail),
    [runs, forkedRunDetail]
  );
  const {
    openProjectSettings,
    langfuseHost,
    langfusePublicKey,
    langfuseSecretKey,
    promptProvider,
    promptLabel,
    setPromptProvider,
    setPromptLabel,
  } = useProjectSettingsStore();

  // Execution target and profiles
  const [profiles, setProfiles] = useState<string[]>(["default"]);
  const [selectedProfile, setSelectedProfile] = useState<string>("default");
  const [availableInputs, setAvailableInputs] = useState<AvailableInputDoc[]>([]);
  const [selectedInputPath, setSelectedInputPath] = useState<string>("examples/text/teachers_expectancies.md");
  const [executionMode, setExecutionMode] = useState<"single" | "corpus">("single");
  const [simulationMode, setSimulationMode] = useState<boolean>(false);

  // Multi-source and bibliography references state
  const [multiSourcePaths, setMultiSourcePaths] = useState<string[]>(["examples/text/teachers_expectancies.md"]);
  const [customSourceInput, setCustomSourceInput] = useState<string>("");
  const [selectedBibPaths, setSelectedBibPaths] = useState<string[]>([]);
  const [customBibInput, setCustomBibInput] = useState<string>("");

  // Execution metadata state (arbitrary key-value strings)
  const [runMetadata, setRunMetadata] = useState<RunMetadataItem[]>([]);
  const [newMetaKey, setNewMetaKey] = useState<string>("");
  const [newMetaValue, setNewMetaValue] = useState<string>("");

  // Global structural anchor state
  const [tocStructure, setTocStructure] = useState<string>("");
  const [documentSummary, setDocumentSummary] = useState<string>("");
  const [globalThesis, setGlobalThesis] = useState<string>("");

  // Sync inputs from forked run when staged
  useEffect(() => {
    if (!forkedRunDetail) return;
    if (forkedRunDetail.input_sources && forkedRunDetail.input_sources.length > 0) {
      setSelectedInputPath(forkedRunDetail.input_sources[0]);
      setMultiSourcePaths(forkedRunDetail.input_sources);
      if (forkedRunDetail.input_sources.length > 1) {
        setExecutionMode("corpus");
      } else {
        setExecutionMode("single");
      }
    }
    if (forkedRunDetail.bib_sources && forkedRunDetail.bib_sources.length > 0) {
      setSelectedBibPaths(forkedRunDetail.bib_sources);
    }
    if (forkedRunDetail.metadata) {
      setRunMetadata(
        Object.entries(forkedRunDetail.metadata).map(([k, v]) => ({
          id: k,
          key: k,
          value: String(v),
        }))
      );
    }
    if (forkedRunDetail.structural_anchor) {
      const anc = forkedRunDetail.structural_anchor;
      setTocStructure(
        Array.isArray(anc.toc_structure)
          ? anc.toc_structure.join("\n")
          : typeof anc.toc_structure === "string"
          ? anc.toc_structure
          : ""
      );
      setDocumentSummary(anc.document_summary || "");
      setGlobalThesis(anc.global_thesis || "");
    }
  }, [forkedRunDetail]);

  // File upload state (source document)
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploadingFile, setIsUploadingFile] = useState<boolean>(false);
  const [uploadSuccessMessage, setUploadSuccessMessage] = useState<string | null>(null);

  // File upload state (bibliography references)
  const bibFileInputRef = useRef<HTMLInputElement>(null);
  const [isUploadingBib, setIsUploadingBib] = useState<boolean>(false);
  const [bibUploadSuccessMessage, setBibUploadSuccessMessage] = useState<string | null>(null);

  // Config values & staged patch overrides
  const [configView, setConfigView] = useState<ConfigView | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [patch, setPatch] = useState<Record<string, any>>({});
  const [invalidationPreview, setInvalidationPreview] = useState<InvalidationPreview | null>(BASELINE_PREVIEW);
  const [isPreviewLoading, setIsPreviewLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [isCustomThinkingActive, setIsCustomThinkingActive] = useState<boolean>(false);
  const [customThinkingInput, setCustomThinkingInput] = useState<string>("");

  // Prompt governance & resolved prompts
  const [resolvedPrompts, setResolvedPrompts] = useState<Record<string, ResolvedPromptItem>>({});
  const [promptWarning, setPromptWarning] = useState<string | null>(null);
  const [isFetchingPrompts, setIsFetchingPrompts] = useState<boolean>(false);
  const [promptFetchSuccess, setPromptFetchSuccess] = useState<boolean>(false);
  const [stagedPrompts, setStagedPrompts] = useState<Record<string, string>>({});

  // Active selected stage in Stage Workspace (defaults to "phase0" Baseline Setup)
  const [selectedPhaseKey, setSelectedPhaseKey] = useState<string>(PIPELINE_DEFAULTS_KEY);

  // Active pipeline stages in run
  const [corePhaseKeys, setCorePhaseKeys] = useState<string[]>(CORE_DAG_PHASE_KEYS);
  const [postProcessorKeys, setPostProcessorKeys] = useState<string[]>(POST_PROCESSOR_KEYS);

  // Slide-over Phase & Processor Catalog Drawer open state
  const [isPhaseDrawerOpen, setIsPhaseDrawerOpen] = useState<boolean>(false);

  // Collapsible drawers
  const [isAdvancedDrawerOpen, setIsAdvancedDrawerOpen] = useState<boolean>(false);
  const [isCliExportExpanded, setIsCliExportExpanded] = useState<boolean>(false);
  const [activePromptSubTab, setActivePromptSubTab] = useState<string>("");

  // Status & copy feedback
  const [copiedCli, setCopiedCli] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);

  // Database collision warning modal state
  const [collisionWarning, setCollisionWarning] = useState<{
    database: string;
    runIds: string[];
  } | null>(null);

  // Cross-module prompt tuning target listener (Phase 6)
  const { promptTuningTarget, setPromptTuningTarget } = useNavigationStore();
  useEffect(() => {
    if (!promptTuningTarget) return;

    if (promptTuningTarget.phaseKey) {
      setSelectedPhaseKey(promptTuningTarget.phaseKey);
    }
    if (promptTuningTarget.promptKey) {
      setActivePromptSubTab(promptTuningTarget.promptKey);
    }
    if (promptTuningTarget.sourceText) {
      setCustomSourceInput(promptTuningTarget.sourceText);
    }
    setPromptTuningTarget(null);
  }, [promptTuningTarget, setPromptTuningTarget]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploadingFile(true);
    setUploadSuccessMessage(null);
    try {
      const doc = await api.uploadInputFile(file);
      setAvailableInputs((prev) => {
        const filtered = prev.filter((d) => d.path !== doc.path);
        return [doc, ...filtered];
      });
      setSelectedInputPath(doc.path);
      setMultiSourcePaths((prev) => (prev.includes(doc.path) ? prev : [...prev, doc.path]));
      setUploadSuccessMessage(`Uploaded "${doc.name}"`);
      setTimeout(() => setUploadSuccessMessage(null), 4000);
    } catch (err) {
      console.error("Failed to upload file:", err);
      setErrorMessage("Failed to upload candidate file. Check console or server logs.");
    } finally {
      setIsUploadingFile(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleBibFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploadingBib(true);
    setBibUploadSuccessMessage(null);
    try {
      const doc = await api.uploadInputFile(file);
      setAvailableInputs((prev) => {
        const filtered = prev.filter((d) => d.path !== doc.path);
        return [doc, ...filtered];
      });
      setSelectedBibPaths((prev) => (prev.includes(doc.path) ? prev : [...prev, doc.path]));
      setBibUploadSuccessMessage(`Uploaded "${doc.name}"`);
      setTimeout(() => setBibUploadSuccessMessage(null), 4000);
    } catch (err) {
      console.error("Failed to upload bibliography file:", err);
      setErrorMessage("Failed to upload bibliography file. Check console or server logs.");
    } finally {
      setIsUploadingBib(false);
      if (bibFileInputRef.current) {
        bibFileInputRef.current.value = "";
      }
    }
  };

  // Discovered bibliography files
  const availableBibDocs = useMemo(() => {
    return availableInputs.filter(
      (doc) => doc.path.toLowerCase().endsWith(".bib") || doc.name.toLowerCase().endsWith(".bib")
    );
  }, [availableInputs]);

  // Derived effective source paths
  const effectiveSourcePaths = useMemo(() => {
    if (executionMode === "corpus") {
      return multiSourcePaths.length > 0 ? multiSourcePaths : availableInputs.map((i) => i.path);
    }
    return selectedInputPath ? [selectedInputPath] : [];
  }, [executionMode, multiSourcePaths, availableInputs, selectedInputPath]);

  // Derived effective metadata record
  const effectiveMetadata = useMemo(() => {
    const record: Record<string, string> = {};
    for (const item of runMetadata) {
      const k = item.key.trim();
      if (k) {
        record[k] = item.value;
      }
    }
    return record;
  }, [runMetadata]);

  // Derived effective structural anchor
  const effectiveAnchor = useMemo<GlobalStructuralAnchor | null>(() => {
    const hasToc = tocStructure.trim().length > 0;
    const hasSummary = documentSummary.trim().length > 0;
    const hasThesis = globalThesis.trim().length > 0;
    if (!hasToc && !hasSummary && !hasThesis) return null;

    const tocLines = tocStructure.split("\n").map((l) => l.trim()).filter(Boolean);
    const parsedToc = tocLines.length > 1 ? tocLines : tocStructure.trim();

    return {
      toc_structure: parsedToc || "",
      document_summary: hasSummary ? documentSummary.trim() : null,
      global_thesis: hasThesis ? globalThesis.trim() : null,
    };
  }, [tocStructure, documentSummary, globalThesis]);

  // Formatted prompt context preview text generated by to_prompt_context()
  const anchorPromptContextPreview = useMemo(() => {
    if (!effectiveAnchor) return "";
    const lines: string[] = [];
    if (effectiveAnchor.toc_structure) {
      if (Array.isArray(effectiveAnchor.toc_structure)) {
        const tocList = effectiveAnchor.toc_structure.filter(Boolean).map((h) => `- ${h}`).join("\n");
        if (tocList) lines.push(`Global Table of Contents / Outline:\n${tocList}`);
      } else if (String(effectiveAnchor.toc_structure).trim()) {
        lines.push(`Global Table of Contents / Outline:\n${String(effectiveAnchor.toc_structure).trim()}`);
      }
    }
    if (effectiveAnchor.document_summary) {
      lines.push(`Document Overview:\n${effectiveAnchor.document_summary}`);
    }
    if (effectiveAnchor.global_thesis) {
      lines.push(`Global Thesis / Scope:\n${effectiveAnchor.global_thesis}`);
    }
    return lines.join("\n\n").trim();
  }, [effectiveAnchor]);

  // Load profiles and inputs on mount
  useEffect(() => {
    api
      .listProfiles()
      .then((profs) => {
        if (profs && profs.length > 0) setProfiles(profs);
      })
      .catch((err) => console.error("Failed to fetch profiles:", err));

    api
      .getAvailableInputs()
      .then((inputs) => {
        if (inputs && inputs.length > 0) {
          setAvailableInputs(inputs);
          setSelectedInputPath(inputs[0].path);
        }
      })
      .catch((err) => console.error("Failed to fetch available inputs:", err));
  }, []);

  // Fetch effective base configuration
  const loadEffectiveConfig = useCallback(() => {
    setIsLoading(true);
    api
      .getEffectiveConfig(selectedProfile)
      .then((cfg) => {
        setConfigView(cfg);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load effective config:", err);
        setIsLoading(false);
      });
  }, [selectedProfile]);

  // Real-time cache invalidation preview
  const runPreview = useCallback(
    (currentPatch: Record<string, any>) => {
      const parentRunId = forkedRunDetail?.run_id || null;
      if (Object.keys(currentPatch).length === 0 && selectedProfile === "default" && !parentRunId) {
        setInvalidationPreview(BASELINE_PREVIEW);
        setErrorMessage(null);
        return;
      }

      setIsPreviewLoading(true);
      setErrorMessage(null);
      api
        .previewInvalidation({
          profile_id: selectedProfile !== "default" ? selectedProfile : undefined,
          patch: currentPatch,
          parent_run_id: parentRunId,
          source_paths: effectiveSourcePaths,
          bib_paths: selectedBibPaths,
          structural_anchor: effectiveAnchor || undefined,
        })
        .then((preview) => {
          setInvalidationPreview(preview);
          setIsPreviewLoading(false);
        })
        .catch((err) => {
          console.error("Preview failed:", err);
          setErrorMessage(err?.detail || err?.title || "Invalidation preview failed.");
          setIsPreviewLoading(false);
        });
    },
    [selectedProfile, forkedRunDetail, effectiveSourcePaths, selectedBibPaths, effectiveAnchor]
  );

  useEffect(() => {
    loadEffectiveConfig();
    runPreview(patch);
  }, [loadEffectiveConfig, selectedProfile, runPreview, patch]);

  // Fetch / resolve prompt bundles (Langfuse or Default)
  const handleResolvePrompts = useCallback(
    (provider: "default" | "langfuse", label: string) => {
      setIsFetchingPrompts(true);
      setPromptFetchSuccess(false);
      setPromptWarning(null);
      api
        .resolvePrompts({
          provider,
          label_or_version: label,
          host: langfuseHost,
          public_key: langfusePublicKey || undefined,
          secret_key: langfuseSecretKey || undefined,
        })
        .then((resp: PromptResolveResponse) => {
          setResolvedPrompts(resp.bundles || {});
          if (resp.warning) {
            setPromptWarning(resp.warning);
          } else {
            setPromptFetchSuccess(true);
            setTimeout(() => setPromptFetchSuccess(false), 3000);
          }
          setIsFetchingPrompts(false);
        })
        .catch((err) => {
          console.error("Prompt resolution failed:", err);
          setPromptWarning("Failed to connect to prompt provider.");
          setIsFetchingPrompts(false);
        });
    },
    [langfuseHost, langfusePublicKey, langfuseSecretKey]
  );

  useEffect(() => {
    handleResolvePrompts(promptProvider, promptLabel);
  }, [promptProvider]);

  // Field updates
  const updateField = (fieldPath: string, value: any) => {
    const nextPatch = { ...patch, [fieldPath]: value };
    setPatch(nextPatch);
    runPreview(nextPatch);
  };

  const clearField = (fieldPath: string) => {
    const nextPatch = { ...patch };
    delete nextPatch[fieldPath];
    setPatch(nextPatch);
    runPreview(nextPatch);
  };

  const clearPatch = () => {
    setPatch({});
    setStagedPrompts({});
    setIsCustomThinkingActive(false);
    setCustomThinkingInput("");
    setInvalidationPreview(BASELINE_PREVIEW);
    setErrorMessage(null);
  };

  const doLaunchRun = useCallback(async () => {
    setIsLaunching(true);
    setCollisionWarning(null);
    try {
      await startNewRun({
        demoMode: simulationMode,
        patch: Object.keys(patch).length > 0 ? patch : undefined,
        profileId: selectedProfile !== "default" ? selectedProfile : undefined,
        sourcePaths: effectiveSourcePaths.length > 0 ? effectiveSourcePaths : undefined,
        bibPaths: selectedBibPaths.length > 0 ? selectedBibPaths : undefined,
        metadata: Object.keys(effectiveMetadata).length > 0 ? effectiveMetadata : undefined,
        structuralAnchor: effectiveAnchor || undefined,
        parentRunId: forkedRunDetail?.run_id || undefined,
      });
      onNavigateToRuns?.();
    } catch (err) {
      console.error("Failed to launch pipeline run:", err);
      setErrorMessage("Run launch failed. Check console or server logs.");
    } finally {
      setIsLaunching(false);
    }
  }, [
    simulationMode,
    patch,
    selectedProfile,
    effectiveSourcePaths,
    selectedBibPaths,
    effectiveMetadata,
    effectiveAnchor,
    forkedRunDetail,
    startNewRun,
    onNavigateToRuns,
  ]);

  // Launch pipeline execution with database collision check
  const handleLaunchRun = useCallback(async () => {
    const lastCreds = useCredentialStore.getState().lastUsedCredentials;
    const targetDb = String(
      patch["execution.neo4j_database"] ||
      configView?.values?.["execution.neo4j_database"] ||
      lastCreds?.database ||
      "neo4j"
    ).trim();

    const conflicts = useCredentialStore.getState().findRunsForDatabase(targetDb);
    if (conflicts.length > 0) {
      setCollisionWarning({
        database: targetDb,
        runIds: conflicts,
      });
      return;
    }

    await doLaunchRun();
  }, [patch, configView?.values, doLaunchRun]);

  // Header launch event listener
  useEffect(() => {
    const handleHeaderLaunch = () => {
      handleLaunchRun();
    };
    window.addEventListener("glp-launch-run", handleHeaderLaunch);
    return () => window.removeEventListener("glp-launch-run", handleHeaderLaunch);
  }, [handleLaunchRun]);

  // Global default values
  const defaultLlm =
    patch["models.llm_model"] ||
    configView?.values?.["models.llm_model"] ||
    "openai/gpt-4o-mini";

  const defaultEmbed =
    patch["models.embedding_model"] ||
    configView?.values?.["models.embedding_model"] ||
    "sentence-transformers/all-MiniLM-L6-v2";

  const defaultReranker =
    patch["models.reranker_model"] ||
    configView?.values?.["models.reranker_model"] ||
    "Alibaba-NLP/gte-reranker-modernbert-base";

  const defaultTemp =
    patch["models.temperature"] !== undefined
      ? patch["models.temperature"]
      : configView?.values?.["models.temperature"] ?? 0.0;

  const defaultSeed =
    patch["models.seed"] !== undefined
      ? patch["models.seed"]
      : configView?.values?.["models.seed"] ?? 42;

  const defaultThinkingLevel =
    patch["models.thinking_level"] !== undefined
      ? String(patch["models.thinking_level"])
      : String(configView?.values?.["models.thinking_level"] || "off");

  // Active stage metadata
  const activePhaseMeta: PhaseMetadata | undefined = PHASE_REGISTRY[selectedPhaseKey];

  // Count modifications per stage
  const getPhaseModificationCount = (phaseKey: string): number => {
    if (phaseKey === "phase0") {
      return Object.keys(patch).filter((k) => k.startsWith("models.") || k.startsWith("execution.")).length;
    }
    if (phaseKey === "schema") {
      return Object.keys(patch).filter((k) => k.startsWith("graph_schema.")).length;
    }
    const meta = PHASE_REGISTRY[phaseKey];
    const prefix = meta?.configPrefix || phaseKey;
    return Object.keys(patch).filter(
      (k) => k.startsWith(`${prefix}.`) || k.startsWith(`${phaseKey}.`)
    ).length;
  };

  // Context-aware dynamic blast radius calculation
  const effectiveInvalidationPreview = useMemo<InvalidationPreview>(() => {
    if (invalidationPreview) {
      return invalidationPreview;
    }

    if (!hasRunBaseline) {
      return {
        invalidated_phases: [1, 2, 3, 4, 5, 6, 7, 8],
        reused_phases: [],
        changed_fingerprints: {},
        reason: "Initial execution (no prior completed run checkpoint)",
        estimated_artifact_loss: 0,
      };
    }

    return BASELINE_PREVIEW;
  }, [invalidationPreview, hasRunBaseline]);

  const phaseExecutionStatus = useMemo<PhaseExecutionStatusMap>(
    () => derivePhaseExecutionStatus(hasRunBaseline, effectiveInvalidationPreview),
    [hasRunBaseline, effectiveInvalidationPreview]
  );

  const baselineRunId = useMemo<string | null>(() => {
    if (forkedRunDetail?.run_id) return forkedRunDetail.run_id;
    const completedRun = runs.find((r) => r.status === "completed");
    return completedRun?.run_id || null;
  }, [forkedRunDetail, runs]);

  // CLI Command generation
  const cliCommand = useMemo(() => {
    const args: string[] = ["uv run python pipeline/pipeline.py"];
    if (effectiveSourcePaths.length > 0) {
      effectiveSourcePaths.forEach((p) => args.push(`--input ${p}`));
    }
    if (selectedBibPaths.length > 0) {
      selectedBibPaths.forEach((b) => args.push(`--bib ${b}`));
    }
    if (selectedProfile && selectedProfile !== "default") {
      args.push(`--profile ${selectedProfile}`);
    }
    if (executionMode === "single") {
      args.push("--demo");
    }
    if (Object.keys(patch).length > 0) {
      const overrides = Object.entries(patch)
        .map(([k, v]) => `--set ${k}=${JSON.stringify(v)}`)
        .join(" ");
      args.push(overrides);
    }
    return args.join(" \\\n  ");
  }, [effectiveSourcePaths, selectedBibPaths, selectedProfile, executionMode, patch]);

  const handleCopyCli = () => {
    navigator.clipboard.writeText(cliCommand);
    setCopiedCli(true);
    setTimeout(() => setCopiedCli(false), 2000);
  };

  // Stage toggling
  const handleTogglePhase = (phaseKey: string, nextActive: boolean) => {
    if (isPhaseMandatory(phaseKey)) return;
    const isPostProc = isPhasePostProcessor(phaseKey);
    const meta = PHASE_REGISTRY[phaseKey];
    const prefix = meta?.configPrefix || phaseKey;

    if (isPostProc) {
      if (nextActive) {
        setPostProcessorKeys((prev) => (prev.includes(phaseKey) ? prev : [...prev, phaseKey]));
        updateField(`${prefix}.enabled`, true);
      } else {
        setPostProcessorKeys((prev) => prev.filter((k) => k !== phaseKey));
        updateField(`${prefix}.enabled`, false);
        if (selectedPhaseKey === phaseKey) setSelectedPhaseKey("phase0");
      }
    } else {
      if (nextActive) {
        setCorePhaseKeys((prev) => (prev.includes(phaseKey) ? prev : [...prev, phaseKey]));
      } else {
        setCorePhaseKeys((prev) => prev.filter((k) => k !== phaseKey));
        if (selectedPhaseKey === phaseKey) setSelectedPhaseKey("phase0");
      }
    }
  };

  const handleResetStageOverrides = (phaseKey: string) => {
    const meta = PHASE_REGISTRY[phaseKey];
    const prefix = meta?.configPrefix || phaseKey;
    const nextPatch = { ...patch };
    Object.keys(nextPatch)
      .filter((k) => k.startsWith(`${prefix}.`) || k.startsWith(`${phaseKey}.`))
      .forEach((k) => delete nextPatch[k]);
    setPatch(nextPatch);
    runPreview(nextPatch);
  };

  return (
    <div className="flex h-full w-full bg-app-bg overflow-hidden text-xs text-app-text select-none">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* PLANE 1: Left Rail (Pipeline Composer)                             */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <ResizablePanel
        side="left"
        storageKey="glp-studio-panel-config-left-width"
        defaultWidth={300}
        minWidth={240}
        maxWidth={480}
        collapsible={false}
        showFooter={true}
      >
        <PipelineComposerRail
          selectedPhaseKey={selectedPhaseKey}
          setSelectedPhaseKey={setSelectedPhaseKey}
          corePhaseKeys={corePhaseKeys}
          postProcessorKeys={postProcessorKeys}
          effectiveSourcePathsCount={effectiveSourcePaths.length}
          selectedBibPathsCount={selectedBibPaths.length}
          runMetadataCount={Object.keys(effectiveMetadata).length}
          hasEffectiveAnchor={Boolean(effectiveAnchor)}
          defaultLlm={defaultLlm}
          defaultEmbed={defaultEmbed}
          phaseExecutionStatus={phaseExecutionStatus}
          reusedPhasesCount={effectiveInvalidationPreview.reused_phases.length}
          baselineRunId={baselineRunId}
          getPhaseModificationCount={getPhaseModificationCount}
          handleTogglePhase={handleTogglePhase}
          handleResetStageOverrides={handleResetStageOverrides}
          setIsPhaseDrawerOpen={setIsPhaseDrawerOpen}
        />
      </ResizablePanel>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* PLANE 2: Center Canvas (Stage Workspace)                           */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 bg-app-surface overflow-hidden">
        {/* Top Target Scope Bar */}
        <StageScopeHeader
          selectedInputPath={selectedInputPath}
          setSelectedInputPath={setSelectedInputPath}
          availableInputs={availableInputs}
          executionMode={executionMode}
          setExecutionMode={setExecutionMode}
          selectedProfile={selectedProfile}
          setSelectedProfile={setSelectedProfile}
          profiles={profiles}
          patchCount={Object.keys(patch).length}
          clearPatch={clearPatch}
        />

        {/* Forked Run Indicator Banner */}
        {forkedRunDetail && (
          <div className="mx-6 mt-3 px-4 py-2.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-xs flex items-center justify-between gap-3 text-blue-900 dark:text-blue-200">
            <div className="flex items-center gap-2 min-w-0">
              <span className="inline-flex items-center gap-1 font-semibold px-2 py-0.5 rounded bg-blue-500/20 text-blue-700 dark:text-blue-300 uppercase text-[10px] tracking-wider shrink-0">
                <GitFork className="w-3 h-3" />
                Forked
              </span>
              <div className="truncate">
                <span className="text-app-muted">Parent Run: </span>
                <span className="font-mono font-medium text-app-text">{forkedRunDetail.run_id}</span>
                <span className="text-app-muted ml-2 hidden sm:inline text-[11px]">
                  (Unchanged phases will be warm-cached and reused)
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setForkedRunDetail(null)}
              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-text border border-app-border text-[11px] font-medium transition-colors cursor-pointer shrink-0"
              title="Detach from parent run and stage as an independent run"
            >
              <X className="w-3 h-3" />
              <span>Detach Fork</span>
            </button>
          </div>
        )}

        {/* Stage Content Scroll Area */}
        <div className="flex-1 overflow-y-auto p-6 sm:p-8 lg:p-10 select-text">
          <div className="max-w-4xl w-full mx-auto">
            {isLoading ? (
                <div className="text-center py-16 text-app-muted font-mono text-xs">Loading configuration...</div>
              ) : selectedPhaseKey === "input_config" ? (
                <StructuralAnchorsView
                  effectiveSourcePaths={effectiveSourcePaths}
                  effectiveMetadata={effectiveMetadata}
                  effectiveAnchor={effectiveAnchor}
                  anchorPromptContextPreview={anchorPromptContextPreview}
                  executionMode={executionMode}
                  selectedInputPath={selectedInputPath}
                  setSelectedInputPath={setSelectedInputPath}
                  multiSourcePaths={multiSourcePaths}
                  setMultiSourcePaths={setMultiSourcePaths}
                  availableInputs={availableInputs}
                  availableBibDocs={availableBibDocs}
                  selectedBibPaths={selectedBibPaths}
                  setSelectedBibPaths={setSelectedBibPaths}
                  handleFileUpload={handleFileUpload}
                  isUploadingFile={isUploadingFile}
                  uploadSuccessMessage={uploadSuccessMessage}
                  fileInputRef={fileInputRef}
                  handleBibFileUpload={handleBibFileUpload}
                  isUploadingBib={isUploadingBib}
                  bibUploadSuccessMessage={bibUploadSuccessMessage}
                  bibFileInputRef={bibFileInputRef}
                  customSourceInput={customSourceInput}
                  setCustomSourceInput={setCustomSourceInput}
                  customBibInput={customBibInput}
                  setCustomBibInput={setCustomBibInput}
                  runMetadata={runMetadata}
                  setRunMetadata={setRunMetadata}
                  newMetaKey={newMetaKey}
                  setNewMetaKey={setNewMetaKey}
                  newMetaValue={newMetaValue}
                  setNewMetaValue={setNewMetaValue}
                  globalThesis={globalThesis}
                  setGlobalThesis={setGlobalThesis}
                  documentSummary={documentSummary}
                  setDocumentSummary={setDocumentSummary}
                  tocStructure={tocStructure}
                  setTocStructure={setTocStructure}
                />
              ) : selectedPhaseKey === "phase0" ? (
                <PipelineDefaultsView
                  patch={patch}
                  configView={configView}
                  activePhaseMeta={activePhaseMeta}
                  updateField={updateField}
                  clearField={clearField}
                  defaultLlm={defaultLlm}
                  defaultEmbed={defaultEmbed}
                  defaultReranker={defaultReranker}
                  defaultTemp={defaultTemp}
                  defaultSeed={defaultSeed}
                  defaultThinkingLevel={defaultThinkingLevel}
                  isCustomThinkingActive={isCustomThinkingActive}
                  setIsCustomThinkingActive={setIsCustomThinkingActive}
                  customThinkingInput={customThinkingInput}
                  setCustomThinkingInput={setCustomThinkingInput}
                  openProjectSettings={openProjectSettings}
                  promptProvider={promptProvider}
                  setPromptProvider={setPromptProvider}
                  promptLabel={promptLabel}
                  setPromptLabel={setPromptLabel}
                  handleResolvePrompts={handleResolvePrompts}
                  isFetchingPrompts={isFetchingPrompts}
                  promptFetchSuccess={promptFetchSuccess}
                  setPromptFetchSuccess={setPromptFetchSuccess}
                  isAdvancedDrawerOpen={isAdvancedDrawerOpen}
                  setIsAdvancedDrawerOpen={setIsAdvancedDrawerOpen}
                />
              ) : selectedPhaseKey === "schema" ? (
                <EpistemicSchemaView
                  patch={patch}
                  configValues={configView?.values}
                  updateField={updateField}
                />
              ) : activePhaseMeta ? (
                <StageWorkspaceView
                  selectedPhaseKey={selectedPhaseKey}
                  activePhaseMeta={activePhaseMeta}
                  patch={patch}
                  configView={configView}
                  updateField={updateField}
                  clearField={clearField}
                  promptProvider={promptProvider}
                  promptLabel={promptLabel}
                  resolvedPrompts={resolvedPrompts}
                  stagedPrompts={stagedPrompts}
                  setStagedPrompts={setStagedPrompts}
                  activePromptSubTab={activePromptSubTab}
                  setActivePromptSubTab={setActivePromptSubTab}
                  defaultLlm={defaultLlm}
                  defaultTemp={defaultTemp}
                  defaultThinkingLevel={defaultThinkingLevel}
                  onSelectPhase={setSelectedPhaseKey}
                  isAdvancedDrawerOpen={isAdvancedDrawerOpen}
                  setIsAdvancedDrawerOpen={setIsAdvancedDrawerOpen}
                />
              ) : null}
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* PLANE 3: Right Rail (Pre-Flight Impact Inspector)                   */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <ResizablePanel
        side="right"
        storageKey="glp-studio-panel-config-right-width"
        defaultWidth={340}
        minWidth={280}
        maxWidth={650}
        collapsible={false}
        showFooter={true}
      >
        <PreFlightInspectorRail
          hasRunBaseline={hasRunBaseline}
          phaseExecutionStatus={phaseExecutionStatus}
          effectiveInvalidationPreview={effectiveInvalidationPreview}
          isLaunching={isLaunching}
          handleLaunchRun={handleLaunchRun}
          isPreviewLoading={isPreviewLoading}
          errorMessage={errorMessage}
          corePhaseKeys={corePhaseKeys}
          selectedProfile={selectedProfile}
          effectiveSourcePaths={effectiveSourcePaths}
          selectedBibPaths={selectedBibPaths}
          effectiveMetadata={effectiveMetadata}
          effectiveAnchor={effectiveAnchor}
          executionMode={executionMode}
          simulationMode={simulationMode}
          setSimulationMode={setSimulationMode}
          isCliExportExpanded={isCliExportExpanded}
          setIsCliExportExpanded={setIsCliExportExpanded}
          cliCommand={cliCommand}
          copiedCli={copiedCli}
          handleCopyCli={handleCopyCli}
        />
      </ResizablePanel>

      {/* Slide-over Phase & Post-Processor Catalog Drawer */}
      {isPhaseDrawerOpen && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-2xs select-none transition-opacity animate-in fade-in duration-150"
          onClick={() => setIsPhaseDrawerOpen(false)}
        >
          <div
            className="w-full max-w-[560px] h-full bg-app-surface border-l border-app-border shadow-2xl flex flex-col select-text animate-in slide-in-from-right duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <PhaseCatalogDrawer
              activePhaseKeys={[...corePhaseKeys, ...postProcessorKeys]}
              selectedPhaseKey={selectedPhaseKey}
              onSelectPhase={(k) => {
                setSelectedPhaseKey(k);
                setIsPhaseDrawerOpen(false);
              }}
              onTogglePhase={handleTogglePhase}
              onResetToDefault={() => {
                setCorePhaseKeys(CORE_DAG_PHASE_KEYS);
                setPostProcessorKeys(POST_PROCESSOR_KEYS);
              }}
              onClose={() => setIsPhaseDrawerOpen(false)}
              onRegisterCustomPhase={(newMeta) => {
                registerCustomPhase(newMeta);
                setPostProcessorKeys((prev) => [...prev, newMeta.key]);
              }}
            />
          </div>
        </div>
      )}

      {/* Database Collision Warning Modal */}
      {collisionWarning && (
        <DatabaseCollisionModal
          isOpen={true}
          databaseName={collisionWarning.database}
          conflictingRunIds={collisionWarning.runIds}
          onProceed={doLaunchRun}
          onCancel={() => setCollisionWarning(null)}
          onChangeDatabase={() => {
            setCollisionWarning(null);
            setSelectedPhaseKey("execution");
          }}
        />
      )}
    </div>
  );
};
