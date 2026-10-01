import React, { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { PanelLeftClose, PanelLeftOpen, ChevronRight } from "lucide-react";
import type { NavSectionDef, NavItemDef, NavGroupDef } from "./NavTypes";
import { NavItem } from "./NavItem";
import { NavGroup } from "./NavGroup";

interface RailItemWithTooltipProps {
  item: NavItemDef;
}

const RailItemWithTooltip: React.FC<RailItemWithTooltipProps> = ({ item }) => {
  const [isHovered, setIsHovered] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const Icon = item.icon;

  const handleMouseEnter = () => {
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setCoords({
        top: rect.top + rect.height / 2,
        left: rect.right + 8,
      });
      setIsHovered(true);
    }
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
  };

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={item.onClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        disabled={item.disabled}
        aria-label={item.label}
        aria-current={item.active ? "page" : undefined}
        className={`w-9 h-9 flex items-center justify-center rounded-md relative group cursor-pointer transition-colors border ${
          item.active
            ? "bg-blue-600/10 text-blue-600 dark:text-blue-400 font-semibold border-blue-600/25"
            : item.disabled
            ? "opacity-40 cursor-not-allowed text-app-muted border-transparent"
            : "text-app-muted hover:text-app-heading hover:bg-app-subtle border-transparent"
        }`}
      >
        {Icon && <Icon className="w-4 h-4 shrink-0" />}
        {item.badge !== undefined && item.badge !== null && (
          <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-amber-500" />
        )}
      </button>

      {isHovered && coords && typeof document !== "undefined" &&
        createPortal(
          <div
            style={{
              position: "fixed",
              top: `${coords.top}px`,
              left: `${coords.left}px`,
              transform: "translateY(-50%)",
            }}
            className="z-50 px-2.5 py-1 bg-app-surface text-app-heading border border-app-border rounded-md shadow-lg text-xs font-medium whitespace-nowrap pointer-events-none animate-in fade-in duration-75"
          >
            {item.label}
          </div>,
          document.body
        )}
    </>
  );
};

interface RailGroupWithFlyoutProps {
  group: NavGroupDef;
}

const RailGroupWithFlyout: React.FC<RailGroupWithFlyoutProps> = ({ group }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const flyoutRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const hasActiveChild = group.children.some((child) => child.active);
  const isGroupActive = group.active || hasActiveChild;
  const GroupIcon = group.icon;

  const updatePosition = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const top = Math.max(8, Math.min(rect.top - 4, window.innerHeight - 340));
      setCoords({
        top,
        left: rect.right + 8,
      });
    }
  };

  const handleMouseEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    updatePosition();
    setIsOpen(true);
  };

  const handleMouseLeave = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      setIsOpen(false);
    }, 180);
  };

  const handleFlyoutMouseEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
  };

  const handleFlyoutMouseLeave = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      setIsOpen(false);
    }, 180);
  };

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (group.onTitleClick) {
      group.onTitleClick();
    }
    updatePosition();
    setIsOpen((prev) => !prev);
  };

  useEffect(() => {
    if (!isOpen) return;

    const handleOutsideClick = (e: MouseEvent) => {
      if (
        triggerRef.current &&
        !triggerRef.current.contains(e.target as Node) &&
        flyoutRef.current &&
        !flyoutRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };

    const handleScroll = () => {
      setIsOpen(false);
    };

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("scroll", handleScroll, true);

    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("scroll", handleScroll, true);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [isOpen]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        aria-label={group.label}
        aria-expanded={isOpen}
        className={`w-9 h-9 flex items-center justify-center rounded-md relative group cursor-pointer transition-colors border ${
          isGroupActive
            ? "bg-blue-600/10 text-blue-600 dark:text-blue-400 font-semibold border-blue-600/25"
            : "text-app-muted hover:text-app-heading hover:bg-app-subtle border-transparent"
        }`}
      >
        {GroupIcon && <GroupIcon className="w-4 h-4 shrink-0" />}
        {group.badge !== undefined && group.badge !== null && (
          <span className="absolute top-1 right-1 px-1 min-w-[14px] h-3.5 flex items-center justify-center rounded-full text-[9px] font-mono tabular-nums font-semibold bg-app-surface text-app-muted border border-app-border leading-none">
            {group.badge}
          </span>
        )}
        {hasActiveChild && (group.badge === undefined || group.badge === null) && (
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-blue-500 ring-2 ring-app-surface" />
        )}
      </button>

      {isOpen && coords && typeof document !== "undefined" &&
        createPortal(
          <div
            ref={flyoutRef}
            onMouseEnter={handleFlyoutMouseEnter}
            onMouseLeave={handleFlyoutMouseLeave}
            style={{
              position: "fixed",
              top: `${coords.top}px`,
              left: `${coords.left}px`,
            }}
            className="z-50 w-56 bg-app-surface border border-app-border rounded-lg shadow-2xl p-1 flex flex-col gap-0.5 animate-in fade-in zoom-in-95 duration-100 font-sans text-xs"
            role="menu"
            aria-label={`${group.label} Submenu`}
          >
            {/* Flyout Header */}
            <div className="flex items-center justify-between px-2.5 py-1.5 border-b border-app-border/60 mb-0.5 select-none">
              <span className="font-semibold text-[11px] uppercase tracking-wider text-app-heading font-sans truncate">
                {group.label}
              </span>
              {group.badge !== undefined && group.badge !== null && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono tabular-nums font-medium bg-app-surface text-app-muted border border-app-border">
                  {group.badge}
                </span>
              )}
            </div>

            {/* Sub-items */}
            <div className="flex flex-col space-y-0.5 max-h-72 overflow-y-auto">
              {group.children.map((child) => {
                const ChildIcon = child.icon;
                return (
                  <button
                    key={child.id}
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      child.onClick();
                      setIsOpen(false);
                    }}
                    disabled={child.disabled}
                    className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-md transition-colors cursor-pointer text-left ${
                      child.active
                        ? "bg-blue-600/10 text-blue-600 dark:text-blue-400 font-medium border border-blue-600/20"
                        : child.disabled
                        ? "opacity-40 cursor-not-allowed text-app-muted border border-transparent"
                        : "text-app-text hover:bg-app-subtle border border-transparent"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      {ChildIcon && (
                        <ChildIcon
                          className={`w-3.5 h-3.5 shrink-0 ${
                            child.active
                              ? "text-blue-600 dark:text-blue-400"
                              : "text-app-muted"
                          }`}
                        />
                      )}
                      <span className="truncate">{child.label}</span>
                    </div>

                    {child.badge !== undefined && child.badge !== null && (
                      <span className="ml-2 px-1.5 py-0.2 rounded-full text-[10px] font-mono tabular-nums font-medium bg-amber-500/15 text-amber-500 border border-amber-500/30 shrink-0">
                        {child.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>,
          document.body
        )}
    </>
  );
};

export interface LocalNavSidebarProps {
  title: string;
  subtitle?: string;
  sections: NavSectionDef[];
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  headerActions?: React.ReactNode;
  footerContent?: React.ReactNode;
  className?: string;
}

export const LocalNavSidebar: React.FC<LocalNavSidebarProps> = ({
  title,
  subtitle,
  sections,
  collapsed = false,
  onToggleCollapse,
  headerActions,
  footerContent,
  className = "",
}) => {
  // ─────────────────────────────────────────────────────────────────────────
  // Collapsed Mode: Functional Icon Rail with Tooltips, Badges & Actions
  // ─────────────────────────────────────────────────────────────────────────
  if (collapsed) {
    return (
      <aside
        className={`flex flex-col h-full w-full bg-app-surface select-none overflow-hidden font-sans text-xs ${className}`}
        aria-label={`${title} Collapsed Navigation Rail`}
      >
        {/* Rail Header: Expand trigger button */}
        <div className="h-10 w-full border-b border-app-border bg-app-surface shrink-0 flex items-center justify-center">
          {onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="p-2 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
              title={`Expand ${title} Sidebar`}
              aria-label={`Expand ${title} Sidebar`}
            >
              <PanelLeftOpen className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Rail Body: Interactive Icon Buttons */}
        <div className="flex-1 w-full overflow-y-auto overflow-x-hidden py-2 px-1 flex flex-col items-center gap-1.5 scrollbar-none">
          {sections.map((section, sIdx) => (
            <React.Fragment key={section.id}>
              {sIdx > 0 && (
                <div
                  className="w-5 border-t border-app-border/60 my-1 shrink-0"
                  role="separator"
                />
              )}

              {section.entries.map((entry, eIdx) => {
                if (entry.type === "divider") {
                  return (
                    <div
                      key={`div-${eIdx}`}
                      className="w-5 border-t border-app-border/60 my-1 shrink-0"
                      role="separator"
                    />
                  );
                }

                if (entry.type === "item") {
                  return (
                    <RailItemWithTooltip
                      key={entry.item.id}
                      item={entry.item}
                    />
                  );
                }

                if (entry.type === "group") {
                  return (
                    <RailGroupWithFlyout
                      key={entry.group.id}
                      group={entry.group}
                    />
                  );
                }

                return null;
              })}
            </React.Fragment>
          ))}
        </div>

        {/* Rail Footer: Expand hint */}
        <div className="h-9 w-full border-t border-app-border bg-app-surface/60 shrink-0 flex items-center justify-center">
          {onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="p-1.5 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
              title="Expand sidebar"
              aria-label="Expand sidebar"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </aside>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Expanded Mode: Full L-Shaped Spatial Hierarchy Sidebar
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <aside
      className={`flex flex-col h-full w-full bg-app-surface select-none overflow-hidden font-sans text-xs ${className}`}
      aria-label={`${title} Navigation Sidebar`}
    >
      {/* Sidebar Header: Coordinate axis & section identity */}
      <div className="h-10 px-3 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex flex-col min-w-0">
            <span className="font-semibold text-[11px] uppercase tracking-wider text-app-heading font-sans truncate">
              {title}
            </span>
            {subtitle && (
              <span className="text-[10px] text-app-muted truncate font-mono">
                {subtitle}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {headerActions}
          {onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
              title="Collapse navigation sidebar"
              aria-label="Collapse navigation sidebar"
            >
              <PanelLeftClose className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Navigation Structure Body */}
      <div className="flex-1 overflow-y-auto px-2 py-3 space-y-4">
        {sections.map((section) => (
          <div key={section.id} className="space-y-1">
            {section.title && (
              <div className="px-3 pb-1 text-[10px] font-mono uppercase tracking-wider text-app-muted">
                {section.title}
              </div>
            )}

            <div className="space-y-0.5">
              {section.entries.map((entry, idx) => {
                if (entry.type === "divider") {
                  return (
                    <div
                      key={`div-${idx}`}
                      className="my-2 border-t border-app-border/60"
                      role="separator"
                    />
                  );
                }

                if (entry.type === "group") {
                  return <NavGroup key={entry.group.id} group={entry.group} />;
                }

                return <NavItem key={entry.item.id} item={entry.item} />;
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Optional Persistent Footer */}
      {footerContent && (
        <div className="p-2 border-t border-app-border bg-app-surface/60 shrink-0">
          {footerContent}
        </div>
      )}
    </aside>
  );
};
