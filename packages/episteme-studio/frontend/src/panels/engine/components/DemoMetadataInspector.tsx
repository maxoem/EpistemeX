import React from "react";
import {DemoAuditHistoryEntry, DemoValidationRule} from "../types";

/**
 * ============================================================================
 * DEMO DATA / MOCK SUBCOMPONENTS (SOLID: Single Responsibility & Extensibility)
 * ============================================================================
 *
 * The following subcomponents render mock validation heuristics and edit history.
 * These are hardwired demo data representations intended to be swapped with live
 * API endpoints (e.g. `api.getSchemaValidationRules(id)` and `api.getSchemaAuditLog(id)`)
 * once the respective backend services are implemented.
 */

// DEMO DATA: Hardcoded default validation rules for entity and relation criteria
const DEMO_DEFAULT_VALIDATION_RULES: Record<string, DemoValidationRule[]> = {
  default: [
    {
      id: "val-1",
      ruleName: "Minimum Extraction Confidence",
      description: "Entity instances must attain LLM confidence >= 0.85 during Phase 2 extraction.",
      severity: "error",
      enabled: true,
    },
    {
      id: "val-2",
      ruleName: "Canonical Disambiguation",
      description: "Requires resolved surface mention link or Wikidata QID anchor if named individual.",
      severity: "warning",
      enabled: true,
    },
    {
      id: "val-3",
      ruleName: "Dialectical Non-Contradiction",
      description: "Node cannot simultaneously hold opposing polarities in the same theoretical partition.",
      severity: "info",
      enabled: false,
    },
  ],
};

// DEMO DATA: Hardcoded default revision history entries
const DEMO_DEFAULT_AUDIT_HISTORY: Record<string, DemoAuditHistoryEntry[]> = {
  default: [
    {
      id: "rev-1",
      timestamp: "2026-09-17 08:30",
      author: "System (Factory Default)",
      changeSummary: "Initialized from baseline dual-graph ontology schema.",
      version: "v1.0.0",
    },
    {
      id: "rev-2",
      timestamp: "2026-09-16 14:12",
      author: "Admin",
      changeSummary: "Refined prompt guidance criteria for philosophical text corpus.",
      version: "v0.9.4",
    },
  ],
};

interface DemoValidationRulesProps {
  itemId: string;
  itemType: string;
}

/**
 * DemoValidationRules
 * 
 * NOTE: This subcomponent uses hardcoded mock validation rules.
 * Replace with live backend schema validator when the verification endpoint is available.
 */
export const DemoValidationRules: React.FC<DemoValidationRulesProps> = () => {
  const rules = DEMO_DEFAULT_VALIDATION_RULES.default;

  return (
    <div className="space-y-2 pt-3 border-t border-app-border">
      <div className="flex items-center justify-between">
        <span className="font-sans text-[12px] font-semibold text-app-text">
          Validation Rules
        </span>
        <span className="font-mono text-[10px] font-normal text-app-muted">
          {rules.length} constraints
        </span>
      </div>

      <div className="divide-y divide-app-border/60">
        {rules.map((rule) => {
          const badgeStyles =
            rule.severity === "error"
              ? "bg-[#FEE2E2] text-[#991B1B]"
              : rule.severity === "warning"
              ? "bg-[#FEF3C7] text-[#92400E]"
              : "bg-[#DBEAFE] text-[#1E40AF]";

          return (
            <div
              key={rule.id}
              className="flex items-start justify-between gap-3 py-2 border-b border-app-border last:border-b-0"
            >
              <div className="min-w-0 flex-1">
                <div className="font-sans text-[12px] font-medium text-app-text leading-snug">
                  {rule.ruleName}
                </div>
                <div className="font-sans text-[11px] text-app-muted leading-normal mt-0.5">
                  {rule.description}
                </div>
              </div>

              <span
                className={`h-[20px] px-2 py-[2px] rounded-full font-mono text-[10px] font-semibold tracking-wider uppercase shrink-0 inline-flex items-center justify-center ${badgeStyles}`}
              >
                {rule.severity}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

interface DemoEditHistoryProps {
  itemId: string;
  itemType: string;
}

/**
 * DemoEditHistory
 * 
 * NOTE: This subcomponent uses hardcoded mock audit history.
 * Replace with live schema revision API when versioning endpoint is available.
 */
export const DemoEditHistory: React.FC<DemoEditHistoryProps> = () => {
  const history = DEMO_DEFAULT_AUDIT_HISTORY.default;

  return (
    <div className="space-y-2 pt-3 border-t border-app-border">
      <div className="flex items-center justify-between">
        <span className="font-sans text-[12px] font-semibold text-app-text">
          Audit History
        </span>
        <span className="font-mono text-[10px] font-normal text-app-muted">
          {history.length} revisions
        </span>
      </div>

      {/* Quiet vertical border running down the left side */}
      <div className="border-l border-app-border pl-3 space-y-3 pt-1">
        {history.map((entry) => (
          <div key={entry.id} className="space-y-1">
            {/* Version Tag paired with timestamp */}
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px] font-medium text-app-text">
                {entry.version}
              </span>
              <span className="font-mono text-[10px] text-app-muted">
                {entry.timestamp}
              </span>
            </div>

            {/* Log Description */}
            <p className="font-sans text-[11px] text-app-muted leading-normal">
              {entry.changeSummary}
            </p>

            {/* Structured Key-Value Metadata */}
            <div className="flex items-center gap-1.5 font-sans text-[10px] text-app-muted">
              <span className="font-mono uppercase tracking-wider text-[9px] text-app-muted">
                Author:
              </span>
              <span className="font-medium text-app-text">
                {entry.author}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
