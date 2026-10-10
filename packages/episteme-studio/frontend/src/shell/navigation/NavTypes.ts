import React from "react";

/**
 * Single navigation item leaf contract (Single Responsibility Principle & Interface Segregation).
 */
export interface NavItemDef {
  id: string;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  badge?: string | number | React.ReactNode;
  badgeVariant?: "default" | "warning" | "success" | "danger" | "info";
  description?: string;
  disabled?: boolean;
  active?: boolean;
  onClick: () => void;
}

/**
 * Collapsible / expandable navigation group contract (e.g., accordion folder).
 */
export interface NavGroupDef {
  id: string;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  badge?: string | number | React.ReactNode;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  active?: boolean;
  children: NavItemDef[];
  onTitleClick?: () => void;
}

/**
 * Discriminated union for local navigation entries.
 */
export type NavEntry =
  | { type: "item"; item: NavItemDef }
  | { type: "group"; group: NavGroupDef }
  | { type: "divider" };

/**
 * High-level section definition within a local navigation sidebar.
 */
export interface NavSectionDef {
  id: string;
  title?: string;
  entries: NavEntry[];
}
