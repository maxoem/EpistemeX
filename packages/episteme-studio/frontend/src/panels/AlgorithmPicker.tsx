import React, {useMemo, useState} from "react";
import {MetricDescriptor} from "../api/types";
import {Activity, AlertTriangle, Boxes, Check, Network, Scale, Search, Share2, TrendingUp, X,} from "lucide-react";

interface AlgorithmPickerProps {
  descriptors: MetricDescriptor[];
  selectedMetricId?: string;
  onSelect: (metricId: string) => void;
  onClose?: () => void;
}

interface CategoryGroup {
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  metricIds: string[];
}

const CATEGORY_GROUPS: CategoryGroup[] = [
  {
    name: "Argumentation & Epistemic Semantics",
    icon: Scale,
    description: "Acceptability semantics, causal support/attack explanations, tenability",
    metricIds: ["gradual_strength_local", "tenability_evaluation", "b_consistency", "stable_extension"],
  },
  {
    name: "Centrality & Structural Influence",
    icon: TrendingUp,
    description: "Recursive endorsement, graph importance, degree & flow",
    metricIds: ["pagerank_global", "degree_global", "betweenness_global", "closeness_global"],
  },
  {
    name: "Communities & Clustering",
    icon: Network,
    description: "Modular partition, graph hulls, weakly connected components",
    metricIds: ["leiden_global", "component_global", "internal_correlation"],
  },
];

export const AlgorithmPicker: React.FC<AlgorithmPickerProps> = ({
  descriptors,
  selectedMetricId,
  onSelect,
  onClose,
}) => {
  const [search, setSearch] = useState("");

  const filteredDescriptors = useMemo(() => {
    if (!search.trim()) return descriptors;
    const q = search.toLowerCase();
    return descriptors.filter(
      (d) =>
        d.label.toLowerCase().includes(q) ||
        d.id.toLowerCase().includes(q) ||
        d.description.toLowerCase().includes(q) ||
        d.engine.toLowerCase().includes(q)
    );
  }, [descriptors, search]);

  // Group filtered descriptors
  const grouped = useMemo(() => {
    const matchedIds = new Set<string>();
    const groups: { category: CategoryGroup; items: MetricDescriptor[] }[] = [];

    for (const cat of CATEGORY_GROUPS) {
      const items = filteredDescriptors.filter((d) => {
        const matches = cat.metricIds.some((id) => d.id.includes(id) || id.includes(d.id));
        if (matches) matchedIds.add(d.id);
        return matches;
      });
      if (items.length > 0) {
        groups.push({ category: cat, items });
      }
    }

    // Remaining items not in fixed categories
    const remaining = filteredDescriptors.filter((d) => !matchedIds.has(d.id));
    if (remaining.length > 0) {
      groups.push({
        category: {
          name: "Other Graph Metrics",
          icon: Activity,
          description: "Topological metrics & analytical algorithms",
          metricIds: [],
        },
        items: remaining,
      });
    }

    return groups;
  }, [filteredDescriptors]);

  const getMetricIcon = (id: string) => {
    if (id.includes("gradual") || id.includes("tenability")) return <Scale className="w-3.5 h-3.5 shrink-0" />;
    if (id.includes("pagerank")) return <TrendingUp className="w-3.5 h-3.5 shrink-0" />;
    if (id.includes("degree")) return <Share2 className="w-3.5 h-3.5 shrink-0" />;
    if (id.includes("component")) return <Boxes className="w-3.5 h-3.5 shrink-0" />;
    if (id.includes("leiden")) return <Network className="w-3.5 h-3.5 shrink-0" />;
    return <Activity className="w-3.5 h-3.5 shrink-0" />;
  };

  return (
    <div className="flex flex-col bg-app-surface text-app-text rounded-lg border border-app-border shadow-xl overflow-hidden max-h-[480px] w-full text-xs">
      {/* Header & Search */}
      <div className="p-2.5 border-b border-app-border bg-app-subtle/50 flex items-center justify-between gap-2 shrink-0">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-app-muted" />
          <input
            type="text"
            placeholder="Search algorithms, engines, papers..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
            className="w-full pl-8 pr-2 py-1 text-xs bg-app-surface border border-app-border rounded-md text-app-heading placeholder:text-app-muted focus:outline-none focus:border-blue-500"
          />
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 text-app-muted hover:text-app-heading rounded hover:bg-app-subtle transition-colors cursor-pointer"
            title="Close algorithm picker"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Grouped Algorithm Items */}
      <div className="flex-1 overflow-y-auto p-2 space-y-3">
        {grouped.length === 0 ? (
          <div className="py-8 text-center text-app-muted text-xs italic">
            No algorithms match &quot;{search}&quot;.
          </div>
        ) : (
          grouped.map(({ category, items }) => (
            <div key={category.name} className="space-y-1">
              <div className="flex items-center gap-1.5 px-2 py-1 text-[11px] font-semibold text-app-muted uppercase tracking-wider">
                <category.icon className="w-3 h-3 text-app-muted shrink-0" />
                <span>{category.name}</span>
              </div>

              <div className="space-y-1">
                {items.map((desc) => {
                  const isSelected = desc.id === selectedMetricId;
                  const isAvailable = desc.available;

                  return (
                    <button
                      key={desc.id}
                      disabled={!isAvailable}
                      onClick={() => onSelect(desc.id)}
                      className={`w-full text-left px-2.5 py-2 rounded-md transition-colors flex items-start justify-between gap-2.5 cursor-pointer ${
                        isSelected
                          ? "bg-blue-500/10 border border-blue-500/30 text-app-heading"
                          : isAvailable
                          ? "hover:bg-app-subtle border border-transparent text-app-text"
                          : "opacity-50 cursor-not-allowed bg-app-subtle/30 border border-transparent"
                      }`}
                    >
                      <div className="flex items-start gap-2 min-w-0">
                        <span className="mt-0.5 text-app-muted group-hover:text-blue-500">
                          {getMetricIcon(desc.id)}
                        </span>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="font-medium text-app-heading text-xs">
                              {desc.label}
                            </span>
                            {isSelected && (
                              <Check className="w-3 h-3 text-blue-500 shrink-0" />
                            )}
                          </div>
                          <p className="text-[11px] text-app-muted line-clamp-1 mt-0.5">
                            {desc.description}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0 text-[10px] font-mono">
                        <span className="px-1.5 py-0.5 rounded bg-app-subtle text-app-muted border border-app-border uppercase">
                          {desc.scope === "single_node" ? "node" : "global"}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-app-subtle text-app-muted border border-app-border uppercase">
                          {desc.engine}
                        </span>
                        {!isAvailable && (
                          <span
                            className="text-amber-500 flex items-center gap-0.5"
                            title={desc.unavailable_reason || "Unavailable"}
                          >
                            <AlertTriangle className="w-3 h-3" />
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
