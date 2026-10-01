import React, { useState, useEffect, useMemo } from "react";
import {
  AlertCircle,
  Copy,
  Download,
  ExternalLink,
  Eye,
  FileCode,
  Filter,
  RefreshCw,
  Search,
  Table as TableIcon,
} from "lucide-react";
import { api } from "../../../api/client";
import type {
  BenchmarkDescriptor,
  BenchmarkPreviewRecord,
  BenchmarkPreviewResponse,
} from "../../../api/types";

interface BenchmarkDataViewerProps {
  benchmark: BenchmarkDescriptor;
}

export const BenchmarkDataViewer: React.FC<BenchmarkDataViewerProps> = ({
  benchmark,
}) => {
  const [previewData, setPreviewData] = useState<BenchmarkPreviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filterText, setFilterText] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [selectedRecord, setSelectedRecord] = useState<BenchmarkPreviewRecord | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const loadPreview = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getBenchmarkPreview(benchmark.id, 100);
      setPreviewData(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load benchmark preview data.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadPreview();
  }, [benchmark.id]);

  const filteredRecords = useMemo(() => {
    if (!previewData) return [];
    return previewData.records.filter((rec) => {
      if (typeFilter !== "all" && rec.type.toLowerCase() !== typeFilter.toLowerCase()) {
        return false;
      }
      if (!filterText.trim()) return true;
      const q = filterText.toLowerCase();
      return (
        rec.record_id.toLowerCase().includes(q) ||
        rec.class_or_category.toLowerCase().includes(q) ||
        rec.label_or_text.toLowerCase().includes(q) ||
        (rec.source_doc && rec.source_doc.toLowerCase().includes(q))
      );
    });
  }, [previewData, filterText, typeFilter]);

  const handleCopyId = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const handleExportJson = () => {
    if (!previewData) return;
    const blob = new Blob([JSON.stringify(previewData.records, null, 2)], {
      type: "application/json;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${benchmark.id}_preview_records.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const uniqueTypes = useMemo(() => {
    if (!previewData) return [];
    return Array.from(new Set(previewData.records.map((r) => r.type)));
  }, [previewData]);

  return (
    <div className="flex-1 flex flex-col h-full w-full bg-app-bg text-app-text font-sans overflow-hidden">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Data Viewer Header Strip (Hugging Face Style)                      */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="h-10 px-4 border-b border-app-border bg-app-surface/60 shrink-0 flex items-center justify-between gap-3 text-xs select-none">
        <div className="flex items-center gap-2">
          <TableIcon className="w-3.5 h-3.5 text-app-muted" />
          <span className="font-display font-medium text-sm text-app-heading">Dataset Records Viewer</span>
          {previewData && (
            <span className="px-2 py-0.5 rounded text-[11px] font-sans tabular-nums bg-app-subtle border border-app-border text-app-muted">
              Showing {filteredRecords.length} of {previewData.total_records} records ({previewData.format.toUpperCase()})
            </span>
          )}
        </div>

        {/* Search, Type Filter & Actions */}
        <div className="flex items-center gap-2">
          {/* Quick Filter */}
          <div className="relative">
            <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-app-muted" />
            <input
              type="text"
              placeholder="Search records in dataset..."
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              className="pl-7 pr-2 py-0.8 text-xs rounded bg-app-bg border border-app-border text-app-text placeholder:text-app-muted/60 focus:outline-hidden focus:border-blue-500 w-48"
            />
          </div>

          {/* Type Filter */}
          {uniqueTypes.length > 1 && (
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-2 py-0.8 text-xs rounded bg-app-bg border border-app-border text-app-text cursor-pointer focus:outline-hidden"
            >
              <option value="all">All Types</option>
              {uniqueTypes.map((t) => (
                <option key={t} value={t}>
                  {t.toUpperCase()}
                </option>
              ))}
            </select>
          )}

          <button
            onClick={loadPreview}
            disabled={isLoading}
            className="p-1 rounded hover:bg-app-subtle text-app-muted hover:text-app-text transition-colors cursor-pointer"
            title="Reload dataset preview"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>

          <button
            onClick={handleExportJson}
            disabled={!previewData || previewData.records.length === 0}
            className="flex items-center gap-1 px-2 py-0.8 rounded text-[11px] font-medium bg-app-surface text-app-text border border-app-border hover:bg-app-subtle transition-colors cursor-pointer"
          >
            <Download className="w-3 h-3 text-app-muted" />
            <span>Export JSON</span>
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Main Table Content / Loading / Error                                */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-48 space-y-2 text-app-muted">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
            <p className="text-xs">Parsing benchmark records for tabular inspection...</p>
          </div>
        ) : error ? (
          <div className="p-6 text-center text-rose-500 space-y-2">
            <AlertCircle className="w-6 h-6 mx-auto" />
            <p className="text-xs font-semibold">{error}</p>
            <button
              onClick={loadPreview}
              className="px-3 py-1 rounded text-xs bg-rose-500/10 border border-rose-500/30 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 transition-colors"
            >
              Retry
            </button>
          </div>
        ) : filteredRecords.length === 0 ? (
          <div className="p-8 text-center text-app-muted">
            <p className="text-xs">No records found matching current criteria.</p>
          </div>
        ) : (
          <table className="w-full text-left border-collapse select-none">
            <thead className="sticky top-0 z-10 bg-app-surface border-b border-app-border text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
              <tr className="h-8">
                <th className="px-4 py-0 w-48">Identifier</th>
                <th className="px-3 py-0 w-24">Type</th>
                <th className="px-3 py-0 w-36">Class / Predicate</th>
                <th className="px-3 py-0">Content / Label</th>
                <th className="px-3 py-0 w-52">Provenance Document</th>
                <th className="px-3 py-0 w-24 text-right">Anchor</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-app-border/60 text-xs">
              {filteredRecords.map((rec, idx) => (
                <tr
                  key={`${rec.record_id}-${idx}`}
                  onClick={() => setSelectedRecord(rec)}
                  className={`h-9 hover:bg-app-subtle/50 transition-colors cursor-pointer ${
                    selectedRecord?.record_id === rec.record_id ? "bg-app-subtle" : ""
                  }`}
                >
                  {/* ID */}
                  <td className="px-4 py-1">
                    <div className="flex items-center gap-1.5 font-mono text-[11px] text-app-text">
                      <span className="truncate max-w-[170px]" title={rec.record_id}>
                        {rec.record_id}
                      </span>
                      <button
                        onClick={(e) => handleCopyId(e, rec.record_id)}
                        className="opacity-0 group-hover:opacity-100 hover:text-blue-500 transition-opacity"
                        title="Copy ID"
                      >
                        <Copy className="w-2.5 h-2.5" />
                      </button>
                      {copiedId === rec.record_id && (
                        <span className="text-[10px] text-emerald-500">✓</span>
                      )}
                    </div>
                  </td>

                  {/* Type */}
                  <td className="px-3 py-1 font-sans">
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-sans uppercase font-medium bg-app-subtle border border-app-border text-app-muted">
                      {rec.type}
                    </span>
                  </td>

                  {/* Class / Predicate */}
                  <td className="px-3 py-1 font-mono text-[11px] font-medium text-app-heading">
                    <span className="truncate block max-w-[140px]" title={rec.class_or_category}>
                      {rec.class_or_category}
                    </span>
                  </td>

                  {/* Label / Content */}
                  <td className="px-3 py-1">
                    <p className="text-xs text-app-text line-clamp-1" title={rec.label_or_text}>
                      {rec.label_or_text}
                    </p>
                  </td>

                  {/* Document */}
                  <td className="px-3 py-1 text-app-muted font-mono text-[11px]">
                    <span className="truncate block max-w-[190px]" title={rec.source_doc || "None"}>
                      {rec.source_doc || "—"}
                    </span>
                  </td>

                  {/* Anchor / Page */}
                  <td className="px-3 py-1 text-right text-app-muted font-mono text-[11px] tabular-nums">
                    {rec.page !== null && rec.page !== undefined ? (
                      <span>p. {rec.page}</span>
                    ) : rec.bbox ? (
                      <span>bbox</span>
                    ) : (
                      <span>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Bottom Drawer: Selected Record Inspector                           */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {selectedRecord && (
        <div className="h-36 border-t border-app-border bg-app-surface p-3 flex flex-col justify-between shrink-0 select-text font-mono text-xs">
          <div className="flex items-center justify-between pb-1.5 border-b border-app-border/60">
            <div className="flex items-center gap-2">
              <span className="text-[11px] uppercase font-semibold text-app-muted">Record Detail:</span>
              <span className="font-bold text-app-heading">{selectedRecord.record_id}</span>
              <span className="px-1.5 py-0.2 rounded text-[10px] bg-app-subtle border border-app-border text-app-muted">
                {selectedRecord.type} · {selectedRecord.class_or_category}
              </span>
            </div>
            <button
              onClick={() => setSelectedRecord(null)}
              className="text-app-muted hover:text-app-text text-xs cursor-pointer font-sans"
            >
              ✕ Close
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4 py-2 overflow-y-auto text-[11px]">
            <div>
              <span className="text-app-muted">Label / Representation:</span>
              <p className="text-app-text font-sans font-medium mt-0.5">{selectedRecord.label_or_text}</p>
            </div>
            <div>
              <span className="text-app-muted">Provenance & Grounding:</span>
              <p className="text-app-text mt-0.5">
                {selectedRecord.source_doc || "None"}{" "}
                {selectedRecord.page ? `· Page ${selectedRecord.page}` : ""}
              </p>
              {selectedRecord.bbox && (
                <p className="text-[10px] text-app-muted">
                  BBox: [{selectedRecord.bbox.join(", ")}]
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
