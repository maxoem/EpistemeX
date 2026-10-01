import React from "react";
import type { NavItemDef } from "./NavTypes";

interface NavItemProps {
  item: NavItemDef;
  depth?: number;
}

const BADGE_VARIANTS: Record<string, string> = {
  default: "bg-app-surface text-app-muted border border-app-border",
  warning: "bg-amber-500/15 text-amber-500 border border-amber-500/30",
  success: "bg-emerald-500/15 text-emerald-500 border border-emerald-500/30",
  danger: "bg-rose-500/15 text-rose-500 border border-rose-500/30",
  info: "bg-blue-500/15 text-blue-500 border border-blue-500/30",
};

export const NavItem: React.FC<NavItemProps> = ({ item, depth = 0 }) => {
  const Icon = item.icon;
  const badgeClass =
    BADGE_VARIANTS[item.badgeVariant || "default"] || BADGE_VARIANTS.default;

  const paddingLeftClass =
    depth === 1 ? "pl-7" : depth === 2 ? "pl-9" : "pl-3";

  return (
    <button
      type="button"
      onClick={item.onClick}
      disabled={item.disabled}
      title={item.description || item.label}
      aria-current={item.active ? "page" : undefined}
      className={`w-full group flex items-center justify-between pr-3 py-1.5 text-xs font-sans rounded-md transition-colors cursor-pointer select-none text-left border border-transparent ${paddingLeftClass} ${
        item.active
          ? "bg-blue-600/10 text-blue-600 dark:text-blue-400 font-medium border-blue-600/20"
          : item.disabled
          ? "opacity-40 cursor-not-allowed text-app-muted"
          : "text-app-muted hover:text-app-heading hover:bg-app-subtle font-normal"
      }`}
    >
      <div className="flex items-center gap-2 truncate">
        {Icon && (
          <Icon
            className={`w-3.5 h-3.5 shrink-0 transition-colors ${
              item.active
                ? "text-blue-600 dark:text-blue-400"
                : "text-app-muted group-hover:text-app-heading"
            }`}
          />
        )}
        <span className="truncate">{item.label}</span>
      </div>

      {item.badge !== undefined && item.badge !== null && (
        <span
          className={`ml-2 px-1.5 py-0.2 rounded-full text-[10px] font-mono tabular-nums font-medium shrink-0 ${badgeClass}`}
        >
          {item.badge}
        </span>
      )}
    </button>
  );
};
