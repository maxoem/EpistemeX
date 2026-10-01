import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { NavGroupDef } from "./NavTypes";
import { NavItem } from "./NavItem";

interface NavGroupProps {
  group: NavGroupDef;
  depth?: number;
}

export const NavGroup: React.FC<NavGroupProps> = ({ group, depth = 0 }) => {
  const hasActiveChild = group.children.some((child) => child.active);
  const [isExpanded, setIsExpanded] = useState<boolean>(
    group.defaultExpanded ?? (hasActiveChild || true)
  );

  // If a child becomes active, auto-expand
  useEffect(() => {
    if (hasActiveChild) {
      setIsExpanded(true);
    }
  }, [hasActiveChild]);

  const Icon = group.icon;
  const paddingLeftClass = depth === 0 ? "pl-3" : "pl-6";

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (group.collapsible !== false) {
      setIsExpanded((prev) => !prev);
    }
    if (group.onTitleClick) {
      group.onTitleClick();
    }
  };

  return (
    <div className="flex flex-col space-y-0.5">
      <button
        type="button"
        onClick={handleToggle}
        className={`w-full group flex items-center justify-between pr-3 py-1.5 text-xs font-sans rounded-md transition-colors cursor-pointer select-none text-left border border-transparent ${paddingLeftClass} ${
          group.active && !hasActiveChild
            ? "bg-blue-600/10 text-blue-600 dark:text-blue-400 font-medium"
            : "text-app-heading hover:bg-app-subtle font-medium"
        }`}
      >
        <div className="flex items-center gap-2 truncate">
          {Icon && (
            <Icon
              className={`w-3.5 h-3.5 shrink-0 transition-colors ${
                group.active || hasActiveChild
                  ? "text-blue-600 dark:text-blue-400"
                  : "text-app-muted group-hover:text-app-heading"
              }`}
            />
          )}
          <span className="truncate">{group.label}</span>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {group.badge !== undefined && group.badge !== null && (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono tabular-nums font-medium bg-app-surface text-app-muted border border-app-border">
              {group.badge}
            </span>
          )}
          {group.collapsible !== false && (
            <span className="text-app-muted group-hover:text-app-heading transition-colors">
              {isExpanded ? (
                <ChevronDown className="w-3.5 h-3.5" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5" />
              )}
            </span>
          )}
        </div>
      </button>

      {/* Children elements */}
      {isExpanded && (
        <div className="flex flex-col space-y-0.5 mt-0.5">
          {group.children.map((child) => (
            <NavItem key={child.id} item={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
};
