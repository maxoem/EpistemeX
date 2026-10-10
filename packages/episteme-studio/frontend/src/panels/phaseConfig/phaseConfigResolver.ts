/**
 * Pure domain resolver for phase configuration inspection.
 * Conforms to Single Responsibility Principle (SRP) and Dependency Inversion Principle (DIP).
 * Decoupled from React, DOM, and UI state.
 */

import type {PhaseStatus} from "../../api/types.ts";
import {PHASE_REGISTRY, type PhaseMetadata} from "./phaseRegistry.ts";
import type {
    ConfigValueType,
    PhaseConfigDescriptor,
    PhaseConfigField,
    PhaseTabOption,
    PromptRole,
    PromptTemplateItem,
} from "./types.ts";

/**
 * Determine the canonical phase key from phase name or ordinal.
 */
export function resolvePhaseKey(
  phase: PhaseStatus | { phase_name?: string; phase_ordinal?: number; key?: string }
): string {
  if ("key" in phase && phase.key && PHASE_REGISTRY[phase.key]) {
    return phase.key;
  }

  const name = (phase.phase_name || "").trim().toLowerCase();
  const ordinal = phase.phase_ordinal;

  // Specific matches before generic "Phase 3" or "Phase 4"
  if (name.includes("phase 3b") || name.includes("3b") || name.includes("latent")) {
    return "phase3b";
  }
  if (name.includes("maturation") || name.includes("entity maturation") || name.includes("4_maturation")) {
    return "phase4_maturation";
  }
  if (name.includes("phase 1") || name.includes("foundation")) {
    return "phase1";
  }
  if (name.includes("phase 2") || name.includes("entity & local") || name.includes("discovery")) {
    return "phase2";
  }
  if (name.includes("phase 3") || name.includes("global relation")) {
    return "phase3";
  }
  if (name.includes("phase 4") || name.includes("argument mining") || name.includes("adu")) {
    return "phase4";
  }
  if (name.includes("phase 5") || name.includes("argument web") || name.includes("fusion")) {
    return "phase5";
  }
  if (name.includes("phase 6") || name.includes("theorynet") || name.includes("epistemic consolidation")) {
    return "phase6";
  }
  if (name.includes("execution")) {
    return "execution";
  }

  // Fallback by ordinal
  switch (ordinal) {
    case 1:
      return "phase1";
    case 2:
      return "phase2";
    case 3:
      return "phase3";
    case 4:
      return "phase3b";
    case 5:
      return "phase4_maturation";
    case 6:
      return "phase4";
    case 7:
      return "phase5";
    case 8:
      return "phase6";
    case 9:
      return "execution";
    default:
      return "phase1";
  }
}

/**
 * Extract variable interpolations (e.g. {chunk_text}) from prompt string.
 */
export function extractPromptVariables(template: string): string[] {
  if (!template) return [];
  const matches = template.match(/\{([a-zA-Z0-9_]+)\}/g);
  if (!matches) return [];
  const vars = new Set<string>();
  for (const m of matches) {
    vars.add(m.slice(1, -1));
  }
  return Array.from(vars);
}

/**
 * Format snake_case key to Human Title Case.
 */
function humanizeKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

/**
 * Classify JavaScript value into ConfigValueType.
 */
function getValueType(val: any): ConfigValueType {
  if (val === null || val === undefined) return "null";
  if (Array.isArray(val)) return "array";
  if (typeof val === "number") return "number";
  if (typeof val === "boolean") return "boolean";
  if (typeof val === "string") return "string";
  if (typeof val === "object") return "object";
  return "string";
}

/**
 * Extract prompt items from a phase configuration object.
 */
function extractPrompts(
  rawConfig: Record<string, any>,
  meta?: PhaseMetadata
): PromptTemplateItem[] {
  const prompts: PromptTemplateItem[] = [];
  const promptKeySet = new Set(meta?.promptKeys || []);

  // Also check all keys for prompt-like names
  for (const [key, val] of Object.entries(rawConfig)) {
    const isKnownPrompt = promptKeySet.has(key);
    const looksLikePrompt =
      key.includes("prompt") || key.includes("_template") || key.endsWith("_templates");

    if (!isKnownPrompt && !looksLikePrompt) continue;
    if (!val) continue;

    // Case 1: Prompt Bundle Object (e.g. ner_prompts, global_relation_prompts, acc_prompts)
    if (typeof val === "object" && !Array.isArray(val)) {
      const subTemplateRoles: Array<{ key: string; role: PromptRole; name: string }> = [
        { key: "direct_template", role: "direct", name: "Direct Extraction Prompt" },
        { key: "reasoning_template", role: "reasoning", name: "Chain-of-Thought Reasoning Prompt" },
        { key: "format_template", role: "format", name: "Structured Output Formatter Prompt" },
        { key: "gleaning_template", role: "gleaning", name: "Gleaning & Verification Prompt" },
      ];

      for (const sub of subTemplateRoles) {
        const text = val[sub.key];
        if (text && typeof text === "string" && text.trim().length > 0) {
          const bundleName = humanizeKey(key);
          prompts.push({
            id: `${key}.${sub.key}`,
            name: `${bundleName} — ${sub.name}`,
            role: sub.role,
            template: text,
            variables: extractPromptVariables(text),
            description: `Template for ${sub.name.toLowerCase()} in ${bundleName}.`,
          });
        }
      }

      // Check any other string fields in the bundle object
      for (const [subKey, subVal] of Object.entries(val)) {
        if (
          !subTemplateRoles.some((s) => s.key === subKey) &&
          typeof subVal === "string" &&
          subVal.trim().length > 0
        ) {
          prompts.push({
            id: `${key}.${subKey}`,
            name: `${humanizeKey(key)} — ${humanizeKey(subKey)}`,
            role: subKey.includes("reason") ? "reasoning" : "custom",
            template: subVal,
            variables: extractPromptVariables(subVal),
          });
        }
      }
    } else if (typeof val === "string" && val.trim().length > 0) {
      // Case 2: Direct string template (e.g. adu_segmentation_prompt_template, entity_linking_prompt_template)
      let role: PromptRole = "custom";
      if (key.includes("segmentation")) role = "segmentation";
      else if (key.includes("linking")) role = "linking";
      else if (key.includes("direct")) role = "direct";
      else if (key.includes("reason")) role = "reasoning";

      prompts.push({
        id: key,
        name: humanizeKey(key),
        role,
        template: val,
        variables: extractPromptVariables(val),
        description: `Direct template prompt for ${humanizeKey(key)}.`,
      });
    }
  }

  return prompts;
}

/**
 * Extract scalar and non-prompt parameters into structured fields.
 */
function extractParameters(
  rawConfig: Record<string, any>,
  meta?: PhaseMetadata
): PhaseConfigField[] {
  const fields: PhaseConfigField[] = [];
  const promptKeySet = new Set(meta?.promptKeys || []);

  for (const [key, val] of Object.entries(rawConfig)) {
    // Skip prompt bundles and templates in parameters view (they have their own section)
    if (promptKeySet.has(key)) continue;
    if (
      (key.includes("prompt") || key.includes("_template")) &&
      (typeof val === "object" || (typeof val === "string" && val.length > 80))
    ) {
      continue;
    }

    const paramMeta = meta?.parameterMeta?.[key];
    const label = paramMeta?.label || humanizeKey(key);
    const description = paramMeta?.description;
    const unit = paramMeta?.unit;
    const valueType = getValueType(val);
    const defaultValue = paramMeta?.defaultValue;
    const isAdvanced = paramMeta?.isAdvanced;
    const group = paramMeta?.group;

    fields.push({
      key,
      label,
      value: val,
      valueType,
      description,
      unit,
      defaultValue,
      isAdvanced,
      group,
    });
  }

  // Sort parameters: numbers/thresholds first, booleans next, strings, objects
  fields.sort((a, b) => {
    const typeOrder: Record<ConfigValueType, number> = {
      number: 1,
      boolean: 2,
      string: 3,
      array: 4,
      object: 5,
      null: 6,
    };
    return (typeOrder[a.valueType] || 99) - (typeOrder[b.valueType] || 99);
  });

  return fields;
}

/**
 * Correlate execution settings from execution block for the given phase.
 */
function extractExecutionSettings(
  phaseKey: string,
  configSnapshot: Record<string, any>,
  meta?: PhaseMetadata
): PhaseConfigField[] {
  const executionConfig = configSnapshot.execution;
  if (!executionConfig || typeof executionConfig !== "object") return [];

  const fields: PhaseConfigField[] = [];
  const phaseExecKey = meta?.executionKey;

  if (phaseExecKey && phaseExecKey in executionConfig) {
    fields.push({
      key: phaseExecKey,
      label: humanizeKey(phaseExecKey),
      value: executionConfig[phaseExecKey],
      valueType: getValueType(executionConfig[phaseExecKey]),
      description: "Controls whether artifacts produced in this phase are written to disk",
    });
  }

  // Add general execution flags
  const generalFlags = ["allow_phase_reuse", "allow_artifact_hydration", "project_artifacts_to_graph"];
  for (const flag of generalFlags) {
    if (flag in executionConfig && flag !== phaseExecKey) {
      fields.push({
        key: flag,
        label: humanizeKey(flag),
        value: executionConfig[flag],
        valueType: getValueType(executionConfig[flag]),
        description: PHASE_REGISTRY.execution?.parameterMeta?.[flag]?.description,
      });
    }
  }

  return fields;
}

/**
 * Main resolution function: transforms a phase and run's config_snapshot into
 * a rich, structured PhaseConfigDescriptor.
 */
export function resolvePhaseConfig(
  phase: PhaseStatus | { phase_name: string; phase_ordinal: number; key?: string },
  configSnapshot: Record<string, any> = {}
): PhaseConfigDescriptor {
  const phaseKey = resolvePhaseKey(phase);
  const meta = PHASE_REGISTRY[phaseKey];

  const rawConfig =
    configSnapshot && typeof configSnapshot === "object"
      ? configSnapshot[phaseKey] || {}
      : {};

  const phaseOrdinal = meta?.canonicalOrdinal ?? phase.phase_ordinal ?? 1;
  const phaseName = meta?.displayName || phase.phase_name || `Phase ${phaseOrdinal}`;
  const description = meta?.description || "Pipeline processing phase.";
  const category = meta?.category || "Pipeline";

  const parameters = extractParameters(rawConfig, meta);
  const prompts = extractPrompts(rawConfig, meta);
  const executionSettings = extractExecutionSettings(phaseKey, configSnapshot, meta);

  return {
    phaseKey,
    phaseOrdinal,
    phaseName,
    description,
    category,
    parameters,
    prompts,
    executionSettings,
    rawConfig,
  };
}

/**
 * Generate tab navigation options for all phases present in the configuration or run.
 */
export function getAvailablePhaseTabs(
  configSnapshot: Record<string, any> = {},
  phaseRecords?: PhaseStatus[]
): PhaseTabOption[] {
  const tabs: PhaseTabOption[] = [];

  // Order defined by PHASE_REGISTRY canonical order
  const registeredKeys = Object.keys(PHASE_REGISTRY);

  for (const key of registeredKeys) {
    const meta = PHASE_REGISTRY[key];
    const rawSlice = configSnapshot[key];

    // Check if phase is represented in records or snapshot
    const isInRecords = phaseRecords?.some((pr) => resolvePhaseKey(pr) === key);
    const hasConfig = rawSlice !== undefined && rawSlice !== null;

    if (isInRecords || hasConfig) {
      const hasPrompts = meta.promptKeys.length > 0;
      tabs.push({
        key,
        ordinal: meta.canonicalOrdinal,
        label: meta.displayName,
        shortLabel: meta.shortLabel,
        hasPrompts,
      });
    }
  }

  // Ensure tabs are ordered by ordinal
  tabs.sort((a, b) => a.ordinal - b.ordinal);
  return tabs;
}
