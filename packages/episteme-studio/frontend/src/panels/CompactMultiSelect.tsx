import React, {useEffect, useMemo, useRef, useState} from "react";
import {Check, ChevronDown, Search, X} from "lucide-react";

export interface CompactMultiSelectProps {
  label: string;
  allOptions: string[];
  selectedOptions: string[]; // empty array [] means all active
  onChange: (next: string[]) => void;
  placeholder?: string;
}

export const CompactMultiSelect: React.FC<CompactMultiSelectProps> = ({
  label,
  allOptions,
  selectedOptions,
  onChange,
  placeholder,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const isNone = selectedOptions.length === 1 && selectedOptions[0] === "__NONE__";
  const isAll = !isNone && (selectedOptions.length === 0 || selectedOptions.length === allOptions.length);

  const filteredOptions = useMemo(() => {
    if (!search.trim()) return allOptions;
    const q = search.toLowerCase();
    return allOptions.filter((opt) => opt.toLowerCase().includes(q));
  }, [allOptions, search]);

  const displayText = useMemo(() => {
    if (placeholder && isNone) return placeholder;
    if (isNone) return "None selected";
    if (isAll) return `All (${allOptions.length})`;
    if (selectedOptions.length === 1) return selectedOptions[0];
    if (selectedOptions.length === 2) return `${selectedOptions[0]}, ${selectedOptions[1]}`;
    return `${selectedOptions.length} of ${allOptions.length} active`;
  }, [isNone, isAll, selectedOptions, allOptions.length, placeholder]);

  const toggleOption = (opt: string) => {
    if (isNone) {
      onChange([opt]);
      return;
    }
    if (isAll) {
      onChange(allOptions.filter((o) => o !== opt));
      return;
    }
    if (selectedOptions.includes(opt)) {
      const next = selectedOptions.filter((o) => o !== opt);
      onChange(next.length === 0 ? ["__NONE__"] : next);
    } else {
      const next = [...selectedOptions, opt];
      if (next.length === allOptions.length) {
        onChange([]); // restore empty array which represents all in domain model
      } else {
        onChange(next);
      }
    }
  };

  const handleSelectAll = () => {
    onChange([]);
  };

  const handleClearAll = () => {
    onChange(["__NONE__"]);
  };

  return (
    <div className="space-y-1 relative" ref={containerRef}>
      <label className="text-[11px] font-medium text-app-muted block truncate">
        {label}
      </label>

      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={`w-full flex items-center justify-between px-2.5 py-1 text-xs rounded border transition-colors cursor-pointer text-left bg-app-bg ${
          isOpen
            ? "border-blue-500 ring-1 ring-blue-500/20"
            : !isAll
            ? "border-blue-500/40 text-blue-600 dark:text-blue-400 bg-blue-500/5 font-medium"
            : "border-app-border text-app-heading hover:border-app-border-hover"
        }`}
        title={`Configure ${label} filter`}
      >
        <span className="truncate pr-1">{displayText}</span>
        <ChevronDown
          className={`w-3.5 h-3.5 text-app-muted shrink-0 transition-transform ${
            isOpen ? "rotate-180 text-blue-500" : ""
          }`}
        />
      </button>

      {/* Floating Dropdown Popover */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 z-50 bg-app-surface border border-app-border rounded-md shadow-lg overflow-hidden animate-in fade-in-50 zoom-in-95 duration-100 min-w-[200px]">
          {/* Search Header */}
          <div className="p-1.5 border-b border-app-border-subtle bg-app-subtle/30 space-y-1.5">
            <div className="relative">
              <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-app-muted" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={`Search ${label.toLowerCase()}...`}
                className="w-full pl-6 pr-5 py-0.5 text-[11px] bg-app-bg border border-app-border-subtle rounded text-app-heading placeholder:text-app-muted focus:outline-none focus:border-blue-500"
                autoFocus
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 text-app-muted hover:text-app-heading p-0.5"
                >
                  <X className="w-2.5 h-2.5" />
                </button>
              )}
            </div>

            {/* Quick Actions Row */}
            <div className="flex items-center justify-between text-[10px] px-0.5">
              <span className="text-app-muted font-mono">
                {isNone ? "0" : isAll ? allOptions.length : selectedOptions.length} of {allOptions.length}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleSelectAll}
                  className="text-blue-500 hover:text-blue-400 font-medium hover:underline cursor-pointer"
                >
                  Select All
                </button>
                <span className="text-app-border">|</span>
                <button
                  type="button"
                  onClick={handleClearAll}
                  className="text-app-muted hover:text-rose-500 hover:underline cursor-pointer"
                >
                  Clear
                </button>
              </div>
            </div>
          </div>

          {/* Options List */}
          <div className="max-h-48 overflow-y-auto divide-y divide-app-border-subtle p-0.5">
            {filteredOptions.length === 0 ? (
              <div className="py-3 text-center text-[10px] text-app-muted">
                No matching {label.toLowerCase()}
              </div>
            ) : (
              filteredOptions.map((opt) => {
                const isSelected = !isNone && (isAll || selectedOptions.includes(opt));
                return (
                  <div
                    key={opt}
                    onClick={() => toggleOption(opt)}
                    className="flex items-center justify-between px-2 py-1 text-[11px] hover:bg-app-hover cursor-pointer transition-colors rounded-xs group select-none"
                  >
                    <span
                      className={`font-mono truncate ${
                        isSelected
                          ? "text-app-heading font-medium"
                          : "text-app-muted group-hover:text-app-heading"
                      }`}
                    >
                      {opt}
                    </span>
                    <div
                      className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 ml-2 ${
                        isSelected
                          ? "bg-blue-600 border-blue-600 text-white"
                          : "border-app-border bg-app-bg group-hover:border-app-border-hover"
                      }`}
                    >
                      {isSelected && <Check className="w-2.5 h-2.5 stroke-[3]" />}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
