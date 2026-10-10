import React from "react";
import {useDiffStore} from "../store/diffStore";
import {CheckCircle2, Cpu, Layers, MessageSquare, Settings2, Sliders, X} from "lucide-react";

export const ConfigDiffDrawer: React.FC = () => {
  const { isConfigDrawerOpen, setIsConfigDrawerOpen, diffData, baseRunId, targetRunId } =
    useDiffStore();

  if (!isConfigDrawerOpen || !diffData) return null;

  const configDiff = diffData.config_diff;

  const getCategoryIcon = (cat: string) => {
    switch (cat) {
      case "models":
        return <Cpu className="w-3.5 h-3.5 text-purple-400" />;
      case "prompts":
        return <MessageSquare className="w-3.5 h-3.5 text-blue-400" />;
      case "phase":
        return <Layers className="w-3.5 h-3.5 text-emerald-400" />;
      default:
        return <Settings2 className="w-3.5 h-3.5 text-cyan-400" />;
    }
  };

  return (
    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-40 max-w-4xl w-[94%] bg-app-surface/95 dark:bg-zinc-900/95 backdrop-blur-md border border-app-border rounded-xl shadow-2xl overflow-hidden flex flex-col text-xs max-h-[50vh] animate-in fade-in slide-in-from-bottom-2 duration-150 select-none">
      {/* Drawer Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-app-border bg-app-surface">
        <div className="flex items-center gap-2">
          <Sliders className="w-4 h-4 text-cyan-400" />
          <h3 className="font-semibold text-app-heading text-xs flex items-center gap-2">
            Configuration & Lineage Divergence
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-cyan-500/10 text-cyan-500 font-mono border border-cyan-500/20">
              {configDiff.length} parameter{configDiff.length === 1 ? "" : "s"} changed
            </span>
          </h3>
        </div>
        <button
          onClick={() => setIsConfigDrawerOpen(false)}
          className="p-1 rounded-md text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Table Content */}
      <div className="overflow-y-auto p-3 flex-1">
        {configDiff.length === 0 ? (
          <div className="py-6 text-center text-app-muted space-y-1">
            <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto opacity-80" />
            <p className="text-xs">Configurations are completely identical across both runs.</p>
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-app-border text-[10px] uppercase font-semibold text-app-muted">
                <th className="py-1.5 px-2">Parameter Path</th>
                <th className="py-1.5 px-2">Category</th>
                <th className="py-1.5 px-2 text-blue-500">Run A (Baseline)</th>
                <th className="py-1.5 px-2 text-emerald-500">Run B (Candidate)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-app-border-subtle font-mono text-[11px]">
              {configDiff.map((item, idx) => (
                <tr key={item.path || idx} className="hover:bg-app-subtle/50 transition-colors">
                  <td className="py-2 px-2 font-medium text-app-heading select-all">
                    {item.path}
                  </td>
                  <td className="py-2 px-2">
                    <span className="inline-flex items-center gap-1 font-sans text-[10px] px-1.5 py-0.2 rounded bg-app-subtle text-app-muted border border-app-border capitalize">
                      {getCategoryIcon(item.category)}
                      <span>{item.category}</span>
                    </span>
                  </td>
                  <td className="py-2 px-2 text-blue-600 dark:text-blue-400 select-all">
                    {item.value_a !== undefined && item.value_a !== null
                      ? String(item.value_a)
                      : "—"}
                  </td>
                  <td className="py-2 px-2 text-emerald-600 dark:text-emerald-400 font-semibold select-all">
                    {item.value_b !== undefined && item.value_b !== null
                      ? String(item.value_b)
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
