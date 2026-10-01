import React from "react";
import { PanelLeftOpen, ChevronRight } from "lucide-react";

export interface BreadcrumbItem {
  label: string;
  onClick?: () => void;
  active?: boolean;
}

export interface WorkspaceContextBarProps {
  breadcrumbs: BreadcrumbItem[];
  isSidebarCollapsed?: boolean;
  onExpandSidebar?: () => void;
  showExpandButton?: boolean;
  contextSelector?: React.ReactNode;
  metrics?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export const WorkspaceContextBar: React.FC<WorkspaceContextBarProps> = ({
  breadcrumbs,
  isSidebarCollapsed,
  onExpandSidebar,
  showExpandButton = true,
  contextSelector,
  metrics,
  actions,
  className = "",
}) => {
  return (
    <div
      className={`h-10 px-3 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs select-none overflow-x-auto gap-3 ${className}`}
      aria-label="Workspace Context & Controls"
    >
      {/* Left: Sidebar trigger + Spatial Breadcrumbs */}
      <div className="flex items-center gap-2 shrink-0 min-w-0">
        {showExpandButton && isSidebarCollapsed && onExpandSidebar && (
          <button
            type="button"
            onClick={onExpandSidebar}
            className="p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
            title="Expand local navigation sidebar"
            aria-label="Expand local navigation sidebar"
          >
            <PanelLeftOpen className="w-3.5 h-3.5" />
          </button>
        )}

        <nav aria-label="Breadcrumbs" className="flex items-center gap-1.5 text-xs">
          {breadcrumbs.map((crumb, idx) => {
            const isLast = idx === breadcrumbs.length - 1;
            return (
              <React.Fragment key={idx}>
                {idx > 0 && (
                  <ChevronRight className="w-3 h-3 text-app-muted/60 shrink-0" />
                )}
                {crumb.onClick && !isLast ? (
                  <button
                    type="button"
                    onClick={crumb.onClick}
                    className="text-app-muted hover:text-app-heading transition-colors cursor-pointer truncate max-w-[140px]"
                  >
                    {crumb.label}
                  </button>
                ) : (
                  <span
                    className={`truncate max-w-[180px] ${
                      isLast
                        ? "font-medium text-app-heading"
                        : "text-app-muted"
                    }`}
                  >
                    {crumb.label}
                  </span>
                )}
              </React.Fragment>
            );
          })}
        </nav>
      </div>

      {/* Right: State / Context Selectors, Live Metrics & Actions */}
      <div className="flex items-center gap-3 shrink-0">
        {contextSelector && (
          <div className="flex items-center">{contextSelector}</div>
        )}

        {metrics && (
          <div className="hidden lg:flex items-center">{metrics}</div>
        )}

        {actions && (
          <div className="flex items-center gap-1.5">{actions}</div>
        )}
      </div>
    </div>
  );
};
